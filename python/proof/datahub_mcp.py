"""Fixed-plan DataHub MCP reads and bounded stable-observation protocol."""

from __future__ import annotations

import asyncio
import json
import os
import shutil
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import yaml
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from domain.hashing import content_hash

from .constants import (
    ALLOWED_REGIONS_PROPERTY_URN,
    CONNECTION_INSTANCE_ID,
    PROFILE_DATASET_URN,
    QUERY_PLAN_VERSION,
    ROOT_DATASET_URN,
    TRAVERSAL_POLICY_VERSION,
)
from .models import DependencyRow, EnvironmentObservation, ProofContractError

DATAHUB_MCP_VERSION = "0.6.0"
DEFAULT_GMS_URL = "http://localhost:8080"


def resolve_token() -> str:
    token = os.getenv("DATAHUB_GMS_TOKEN")
    if token and token.strip():
        return token
    profile = Path.home() / ".datahubenv"
    if profile.is_file():
        payload = yaml.safe_load(profile.read_text(encoding="utf-8"))
        if isinstance(payload, dict) and isinstance(payload.get("gms"), dict):
            configured = payload["gms"].get("token")
            if isinstance(configured, str) and configured.strip():
                return configured
    raise ProofContractError(
        "DataHub token is missing; run `.\\scripts\\proof.cmd up` to create the local PAT"
    )


def server_parameters(token: str | None = None) -> StdioServerParameters:
    executable = shutil.which("uvx")
    if executable is None:
        raise ProofContractError("uvx is required to launch the pinned DataHub MCP server")
    environment = os.environ.copy()
    environment.update(
        {
            "DATAHUB_GMS_URL": os.getenv("DATAHUB_GMS_URL", DEFAULT_GMS_URL),
            "DATAHUB_GMS_TOKEN": token or resolve_token(),
            "TOOLS_IS_MUTATION_ENABLED": "true",
            "PYTHONUTF8": "1",
            "LOGURU_LEVEL": "WARNING",
        }
    )
    return StdioServerParameters(
        command=executable,
        args=[
            "--python",
            "3.11",
            "--from",
            f"mcp-server-datahub=={DATAHUB_MCP_VERSION}",
            "mcp-server-datahub",
            "--transport",
            "stdio",
        ],
        env=environment,
    )


@asynccontextmanager
async def open_session(token: str | None = None) -> AsyncIterator[ClientSession]:
    async with stdio_client(server_parameters(token)) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            yield session


def tool_payload(result: Any) -> Any:
    if result.isError:
        text = next(
            (
                block.text
                for block in result.content
                if isinstance(getattr(block, "text", None), str)
            ),
            "DataHub MCP tool failed",
        )
        raise ProofContractError(text)
    for block in result.content:
        text = getattr(block, "text", None)
        if isinstance(text, str):
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                continue
    if result.structuredContent is not None:
        return result.structuredContent
    raise ProofContractError("DataHub MCP tool returned no JSON payload")


def _field_names(entity: dict[str, Any]) -> tuple[str, ...]:
    schema = entity.get("schemaMetadata")
    fields = schema.get("fields") if isinstance(schema, dict) else None
    if not isinstance(fields, list):
        return ()
    return tuple(
        sorted(
            field["fieldPath"]
            for field in fields
            if isinstance(field, dict) and isinstance(field.get("fieldPath"), str)
        )
    )


def _field_has_tag(entity: dict[str, Any], column_path: str, tag_name: str) -> bool:
    schema = entity.get("schemaMetadata")
    fields = schema.get("fields") if isinstance(schema, dict) else None
    if not isinstance(fields, list):
        return False
    for field in fields:
        if not isinstance(field, dict) or field.get("fieldPath") != column_path:
            continue
        tags = field.get("tags")
        edited_tags = field.get("editedTags")
        return (isinstance(tags, list) and tag_name in tags) or (
            isinstance(edited_tags, list) and tag_name in edited_tags
        )
    return False


def _email_has_pii(entity: dict[str, Any]) -> bool:
    return _field_has_tag(entity, "email", "PII")


def _allowed_regions(entity: dict[str, Any]) -> tuple[str, ...]:
    structured = entity.get("structuredProperties")
    properties = structured.get("properties") if isinstance(structured, dict) else None
    if not isinstance(properties, list):
        return ()
    values: list[str] = []
    for assignment in properties:
        if not isinstance(assignment, dict):
            continue
        prop = assignment.get("structuredProperty")
        if not isinstance(prop, dict) or prop.get("urn") != ALLOWED_REGIONS_PROPERTY_URN:
            continue
        raw_values = assignment.get("values")
        if isinstance(raw_values, list):
            values.extend(
                value["stringValue"]
                for value in raw_values
                if isinstance(value, dict) and isinstance(value.get("stringValue"), str)
            )
    return tuple(sorted(set(values)))


def _owner_urns(entity: dict[str, Any]) -> tuple[str, ...]:
    ownership = entity.get("ownership")
    owners = ownership.get("owners") if isinstance(ownership, dict) else None
    if not isinstance(owners, list):
        return ()
    return tuple(
        sorted(
            owner["owner"]["urn"]
            for owner in owners
            if isinstance(owner, dict)
            and isinstance(owner.get("owner"), dict)
            and isinstance(owner["owner"].get("urn"), str)
        )
    )


def _upstream_urns(lineage: dict[str, Any]) -> tuple[str, ...]:
    upstreams = lineage.get("upstreams")
    results = upstreams.get("searchResults") if isinstance(upstreams, dict) else None
    if not isinstance(results, list):
        return ()
    return tuple(
        sorted(
            result["entity"]["urn"]
            for result in results
            if isinstance(result, dict)
            and isinstance(result.get("entity"), dict)
            and isinstance(result["entity"].get("urn"), str)
        )
    )


def _normalize_observation(
    entities_payload: Any, lineage_payload: Any, *, attempts: int
) -> EnvironmentObservation:
    if not isinstance(entities_payload, list):
        raise ProofContractError("get_entities returned an unexpected payload")
    entities = {
        entity.get("urn"): entity
        for entity in entities_payload
        if isinstance(entity, dict) and isinstance(entity.get("urn"), str)
    }
    root = entities.get(ROOT_DATASET_URN)
    profile = entities.get(PROFILE_DATASET_URN)
    if not isinstance(root, dict) or not isinstance(profile, dict):
        raise ProofContractError("fixed DataHub root/profile entities are missing")
    if not isinstance(lineage_payload, dict):
        raise ProofContractError("get_lineage returned an unexpected payload")

    root_fields = _field_names(root)
    profile_fields = _field_names(profile)
    upstream_urns = _upstream_urns(lineage_payload)
    owner_urns = _owner_urns(root)
    allowed_regions = _allowed_regions(profile)
    pii_present = _email_has_pii(profile)
    dependency_values: tuple[tuple[str, str, str, Any], ...] = (
        (ROOT_DATASET_URN, "schemaMetadata", "fields", root_fields),
        (PROFILE_DATASET_URN, "schemaMetadata", "fields", profile_fields),
        (ROOT_DATASET_URN, "upstreamLineage", "datasets", upstream_urns),
        (ROOT_DATASET_URN, "ownership", "owners", owner_urns),
        (
            PROFILE_DATASET_URN,
            "structuredProperties",
            ALLOWED_REGIONS_PROPERTY_URN,
            allowed_regions,
        ),
        (PROFILE_DATASET_URN, "schemaMetadata", "fields.email.tags.PII", pii_present),
    )
    dependencies = tuple(
        sorted(
            DependencyRow(
                urn=urn,
                aspect=aspect,
                field_path=field_path,
                observed_hash=content_hash(value),
            )
            for urn, aspect, field_path, value in dependency_values
        )
    )
    semantic_payload = {
        "rootUrn": ROOT_DATASET_URN,
        "profileUrn": PROFILE_DATASET_URN,
        "rootFields": list(root_fields),
        "profileFields": list(profile_fields),
        "upstreamUrns": list(upstream_urns),
        "ownerUrns": list(owner_urns),
        "allowedRegions": list(allowed_regions),
        "piiPresent": pii_present,
        "dependencies": [row.to_dict() for row in dependencies],
    }
    semantic_hash = content_hash(semantic_payload)
    fingerprint = content_hash(
        {
            "connectionInstanceId": CONNECTION_INSTANCE_ID,
            "rootUrns": [ROOT_DATASET_URN],
            "traversalPolicyVersion": TRAVERSAL_POLICY_VERSION,
            "compilerQueryPlanVersion": QUERY_PLAN_VERSION,
            "dependencies": [row.to_dict() for row in dependencies],
        }
    )
    return EnvironmentObservation(
        root_urn=ROOT_DATASET_URN,
        profile_urn=PROFILE_DATASET_URN,
        root_fields=root_fields,
        profile_fields=profile_fields,
        upstream_urns=upstream_urns,
        owner_urns=owner_urns,
        allowed_regions=allowed_regions,
        pii_present=pii_present,
        dependencies=dependencies,
        environment_fingerprint=fingerprint,
        semantic_hash=semantic_hash,
        read_attempts=attempts,
    )


async def read_once(session: ClientSession, *, attempts: int = 1) -> EnvironmentObservation:
    entities = await session.call_tool(
        "get_entities", {"urns": [ROOT_DATASET_URN, PROFILE_DATASET_URN]}
    )
    lineage = await session.call_tool(
        "get_lineage",
        {"urn": ROOT_DATASET_URN, "upstream": True, "max_hops": 2, "max_results": 20},
    )
    return _normalize_observation(tool_payload(entities), tool_payload(lineage), attempts=attempts)


async def read_stable(session: ClientSession, *, max_attempts: int = 3) -> EnvironmentObservation:
    for attempt in range(1, max_attempts + 1):
        first = await read_once(session, attempts=attempt)
        second = await read_once(session, attempts=attempt)
        if first.semantic_hash == second.semantic_hash:
            return second
        await asyncio.sleep(0.2 * attempt)
    raise ProofContractError("CONTEXT_UNSTABLE: decisive DataHub rereads did not match")


async def create_receipt_anchor(session: ClientSession, *, title: str) -> str:
    result = await session.call_tool(
        "save_document",
        {
            "document_type": "Decision",
            "title": title,
            "content": "SIRA proof receipt anchor reserved; no success claim yet.",
            "topics": ["sira-proof", "proof-receipt"],
            "related_assets": [ROOT_DATASET_URN],
        },
    )
    payload = tool_payload(result)
    urn = payload.get("urn") if isinstance(payload, dict) else None
    if not isinstance(urn, str) or not urn.startswith("urn:li:document:"):
        raise ProofContractError("DataHub did not return a proof receipt anchor URN")
    return urn


async def publish_receipt_projection(
    session: ClientSession,
    *,
    anchor_urn: str,
    title: str,
    core_hash: str,
    projection: dict[str, Any],
) -> None:
    content = json.dumps(
        {"coreHash": core_hash, "historicalProof": projection},
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    result = await session.call_tool(
        "save_document",
        {
            "urn": anchor_urn,
            "document_type": "Decision",
            "title": title,
            "content": content,
            "topics": ["sira-proof", "proof-receipt", core_hash],
            "related_assets": [ROOT_DATASET_URN, PROFILE_DATASET_URN],
        },
    )
    tool_payload(result)


async def reread_receipt_projection(
    anchor_urn: str, *, core_hash: str, timeout_seconds: float = 20.0
) -> Any:
    deadline = asyncio.get_running_loop().time() + timeout_seconds
    while True:
        async with open_session() as session:
            result = await session.call_tool(
                "grep_documents",
                {
                    "urns": [anchor_urn],
                    "pattern": core_hash,
                    "context_chars": 2000,
                    "max_matches_per_doc": 2,
                },
            )
            payload = tool_payload(result)
            if core_hash in json.dumps(payload, sort_keys=True):
                return payload
        if asyncio.get_running_loop().time() >= deadline:
            raise ProofContractError("DATAHUB_RECEIPT_REREAD_MISMATCH")
        await asyncio.sleep(1.0)


async def set_field_tag(
    session: ClientSession,
    *,
    entity_urn: str,
    column_path: str,
    tag_urn: str,
    present: bool,
) -> None:
    tool = "add_tags" if present else "remove_tags"
    result = await session.call_tool(
        tool,
        {
            "tag_urns": [tag_urn],
            "entity_urns": [entity_urn],
            "column_paths": [column_path],
        },
    )
    tool_payload(result)


async def wait_for_pii(session: ClientSession, *, present: bool) -> EnvironmentObservation:
    deadline = asyncio.get_running_loop().time() + 20
    while True:
        observation = await read_stable(session)
        if observation.pii_present is present:
            return observation
        if asyncio.get_running_loop().time() >= deadline:
            raise ProofContractError(f"timed out waiting for PII present={present}")
        await asyncio.sleep(0.5)


async def wait_for_field_tag(
    session: ClientSession,
    *,
    entity_urn: str,
    column_path: str,
    tag_name: str,
    present: bool,
) -> None:
    deadline = asyncio.get_running_loop().time() + 20
    while True:
        result = await session.call_tool("get_entities", {"urns": [entity_urn]})
        payload = tool_payload(result)
        entity = payload[0] if isinstance(payload, list) and payload else None
        if isinstance(entity, dict) and _field_has_tag(entity, column_path, tag_name) is present:
            return
        if asyncio.get_running_loop().time() >= deadline:
            raise ProofContractError(
                f"timed out waiting for {tag_name} on {column_path} present={present}"
            )
        await asyncio.sleep(0.5)
