"""Probe the pinned self-hosted DataHub MCP contract without printing credentials."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import shutil
import sys
from pathlib import Path
from typing import Any

import yaml
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

DATAHUB_CORE_VERSION = "1.7.0"
DATAHUB_MCP_VERSION = "0.6.0"
DEFAULT_GMS_URL = "http://localhost:8080"
RAW_DATASET_URN = "urn:li:dataset:(urn:li:dataPlatform:postgres,sira_k0.raw.customer_profiles,PROD)"
CURATED_DATASET_URN = (
    "urn:li:dataset:(urn:li:dataPlatform:postgres,sira_k0.curated.customer_profiles,PROD)"
)
SERVING_DATASET_URN = (
    "urn:li:dataset:(urn:li:dataPlatform:postgres,sira_k0.serving.agent_customer_profiles,PROD)"
)
PII_TAG_URN = "urn:li:tag:PII"
REGION_PROPERTY_URN = "urn:li:structuredProperty:io.sira.proof.allowedRegion"
REQUIRED_TOOLS = {
    "add_structured_properties",
    "add_tags",
    "get_entities",
    "get_lineage",
    "remove_structured_properties",
    "remove_tags",
    "save_document",
}


def _stage(message: str) -> None:
    print(f"[k0] {message}", file=sys.stderr, flush=True)  # noqa: T201


def _token_from_datahub_env(path: Path) -> str | None:
    if not path.is_file():
        return None
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        return None
    gms = payload.get("gms")
    if not isinstance(gms, dict):
        return None
    token = gms.get("token")
    return token if isinstance(token, str) and token.strip() else None


def resolve_token() -> str:
    token = os.getenv("DATAHUB_GMS_TOKEN")
    if token and token.strip():
        return token
    token = _token_from_datahub_env(Path.home() / ".datahubenv")
    if token:
        return token
    raise RuntimeError("DATAHUB_GMS_TOKEN is missing. Run the local DataHub initialization first.")


def _server_parameters(token: str) -> StdioServerParameters:
    uvx = shutil.which("uvx")
    if uvx is None:
        raise RuntimeError("uvx is required to launch the pinned DataHub MCP server")
    server_env = os.environ.copy()
    server_env.update(
        {
            "DATAHUB_GMS_URL": os.getenv("DATAHUB_GMS_URL", DEFAULT_GMS_URL),
            "DATAHUB_GMS_TOKEN": token,
            "TOOLS_IS_MUTATION_ENABLED": "true",
            "PYTHONUTF8": "1",
        }
    )
    return StdioServerParameters(
        command=uvx,
        args=[
            "--python",
            "3.11",
            "--from",
            f"mcp-server-datahub=={DATAHUB_MCP_VERSION}",
            "mcp-server-datahub",
            "--transport",
            "stdio",
        ],
        env=server_env,
    )


def _serialize_tool_result(result: Any) -> dict[str, Any]:
    return {
        "isError": bool(result.isError),
        "content": [block.model_dump(mode="json") for block in result.content],
        "structuredContent": result.structuredContent,
    }


def _tool_payload(result: Any) -> Any:
    if result.isError:
        raise RuntimeError(json.dumps(_serialize_tool_result(result), sort_keys=True))
    for block in result.content:
        text = getattr(block, "text", None)
        if isinstance(text, str):
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                continue
    if result.structuredContent is not None:
        return result.structuredContent
    raise RuntimeError("DataHub MCP tool returned no JSON payload")


def _first_entity(result: Any) -> dict[str, Any]:
    payload = _tool_payload(result)
    if not isinstance(payload, list) or not payload or not isinstance(payload[0], dict):
        raise RuntimeError("DataHub MCP get_entities returned an unexpected payload")
    return payload[0]


def _email_has_pii(entity: dict[str, Any]) -> bool:
    schema = entity.get("schemaMetadata")
    if not isinstance(schema, dict):
        return False
    fields = schema.get("fields")
    if not isinstance(fields, list):
        return False
    for field in fields:
        if isinstance(field, dict) and field.get("fieldPath") == "email":
            tags = field.get("tags")
            edited_tags = field.get("editedTags")
            return (isinstance(tags, list) and "PII" in tags) or (
                isinstance(edited_tags, list) and "PII" in edited_tags
            )
    return False


def _exception_details(exc: BaseException) -> list[dict[str, str]]:
    if isinstance(exc, BaseExceptionGroup):
        details: list[dict[str, str]] = []
        for nested in exc.exceptions:
            details.extend(_exception_details(nested))
        return details
    return [{"type": type(exc).__name__, "message": str(exc)}]


async def _wait_for_entity(
    session: ClientSession,
    predicate: Any,
    description: str,
    *,
    timeout_seconds: float = 20.0,
) -> tuple[Any, dict[str, Any]]:
    deadline = asyncio.get_running_loop().time() + timeout_seconds
    while True:
        result = await session.call_tool("get_entities", {"urns": [SERVING_DATASET_URN]})
        entity = _first_entity(result)
        if predicate(entity):
            return result, entity
        if asyncio.get_running_loop().time() >= deadline:
            raise RuntimeError(f"Timed out waiting for DataHub reread: {description}")
        await asyncio.sleep(0.5)


async def _reread_anchor(parameters: StdioServerParameters, anchor_urn: str) -> dict[str, Any]:
    _stage("rereading the decision anchor through a fresh MCP session")
    deadline = asyncio.get_running_loop().time() + 20.0
    while True:
        async with stdio_client(parameters) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                tools_result = await session.list_tools()
                if "grep_documents" in {tool.name for tool in tools_result.tools}:
                    result = await session.call_tool(
                        "grep_documents",
                        {
                            "urns": [anchor_urn],
                            "pattern": "K0 anchor revision 2",
                            "context_chars": 80,
                            "max_matches_per_doc": 2,
                        },
                    )
                    payload = _tool_payload(result)
                    if "K0 anchor revision 2" in json.dumps(payload, sort_keys=True):
                        return _serialize_tool_result(result)
        if asyncio.get_running_loop().time() >= deadline:
            raise RuntimeError("Timed out waiting for MCP anchor revision 2 reread")
        await asyncio.sleep(1.0)


async def _verify_invalid_token_rejected() -> dict[str, Any]:
    _stage("proving invalid credentials are rejected")
    parameters = _server_parameters("sira-k0-deliberately-invalid-token")
    try:
        async with stdio_client(parameters) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                result = await session.call_tool("get_entities", {"urns": [SERVING_DATASET_URN]})
                if result.isError:
                    return {"rejected": True, "mode": "tool-error"}
                try:
                    entity = _first_entity(result)
                except RuntimeError:
                    return {"rejected": True, "mode": "no-entity"}
                if not entity.get("schemaMetadata"):
                    return {"rejected": True, "mode": "redacted-entity"}
                raise RuntimeError("DataHub MCP accepted the deliberately invalid credential")
    except Exception as exc:
        rendered = json.dumps(_exception_details(exc)).lower()
        if any(marker in rendered for marker in ("401", "403", "unauthorized", "token")):
            return {"rejected": True, "mode": "transport-error"}
        raise


async def probe_contract() -> dict[str, Any]:
    invalid_credential = await _verify_invalid_token_rejected()
    _stage("launching the pinned DataHub MCP server")
    parameters = _server_parameters(resolve_token())
    async with stdio_client(parameters) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            initialize_result = await session.initialize()
            tools_result = await session.list_tools()
            tool_names = {tool.name for tool in tools_result.tools}
            missing_tools = sorted(REQUIRED_TOOLS - tool_names)
            if missing_tools:
                raise RuntimeError(f"DataHub MCP is missing required tools: {missing_tools}")

            _stage("reading the serving asset and two-hop lineage")

            initial_entity_result = await session.call_tool(
                "get_entities", {"urns": [SERVING_DATASET_URN]}
            )
            initial_entity = _first_entity(initial_entity_result)
            if not _email_has_pii(initial_entity):
                initial_pii_result = await session.call_tool(
                    "add_tags",
                    {
                        "tag_urns": [PII_TAG_URN],
                        "entity_urns": [SERVING_DATASET_URN],
                        "column_paths": ["email"],
                    },
                )
                _tool_payload(initial_pii_result)
                initial_entity_result, initial_entity = await _wait_for_entity(
                    session, _email_has_pii, "initial PII tag present"
                )
            lineage_result = await session.call_tool(
                "get_lineage",
                {
                    "urn": SERVING_DATASET_URN,
                    "upstream": True,
                    "max_hops": 2,
                    "max_results": 10,
                },
            )
            lineage_payload = _tool_payload(lineage_result)
            lineage_json = json.dumps(lineage_payload, sort_keys=True)
            if RAW_DATASET_URN not in lineage_json or CURATED_DATASET_URN not in lineage_json:
                raise RuntimeError("Two-hop MCP lineage did not include both fixed upstream URNs")

            anchor_create_result = await session.call_tool(
                "save_document",
                {
                    "document_type": "Decision",
                    "title": "SIRA K0 proof anchor",
                    "content": "K0 anchor revision 1",
                    "topics": ["sira-k0", "proof-receipt"],
                    "related_assets": [SERVING_DATASET_URN],
                },
            )
            anchor_create_payload = _tool_payload(anchor_create_result)
            anchor_urn = (
                anchor_create_payload.get("urn")
                if isinstance(anchor_create_payload, dict)
                else None
            )
            if not isinstance(anchor_urn, str) or not anchor_urn.startswith("urn:li:document:"):
                raise RuntimeError("MCP save_document did not return a document URN")
            anchor_update_result = await session.call_tool(
                "save_document",
                {
                    "urn": anchor_urn,
                    "document_type": "Decision",
                    "title": "SIRA K0 proof anchor",
                    "content": "K0 anchor revision 2",
                    "topics": ["sira-k0", "proof-receipt"],
                    "related_assets": [SERVING_DATASET_URN],
                },
            )
            anchor_update_payload = _tool_payload(anchor_update_result)

            _stage("proving structured-property and field-tag mutation cycles")

            region_added = False
            pii_removed = False
            try:
                region_add_result = await session.call_tool(
                    "add_structured_properties",
                    {
                        "entity_urns": [SERVING_DATASET_URN],
                        "property_values": {REGION_PROPERTY_URN: ["IN"]},
                    },
                )
                _tool_payload(region_add_result)
                region_added = True
                _region_entity_result, _region_entity = await _wait_for_entity(
                    session,
                    lambda entity: (
                        REGION_PROPERTY_URN in json.dumps(entity, sort_keys=True)
                        and '"IN"' in json.dumps(entity, sort_keys=True)
                    ),
                    "allowed region IN present",
                )

                pii_remove_result = await session.call_tool(
                    "remove_tags",
                    {
                        "tag_urns": [PII_TAG_URN],
                        "entity_urns": [SERVING_DATASET_URN],
                        "column_paths": ["email"],
                    },
                )
                _tool_payload(pii_remove_result)
                pii_removed = True
                _pii_absent_result, _pii_absent_entity = await _wait_for_entity(
                    session,
                    lambda entity: not _email_has_pii(entity),
                    "PII tag absent",
                )
            finally:
                if pii_removed:
                    pii_restore_result = await session.call_tool(
                        "add_tags",
                        {
                            "tag_urns": [PII_TAG_URN],
                            "entity_urns": [SERVING_DATASET_URN],
                            "column_paths": ["email"],
                        },
                    )
                    _tool_payload(pii_restore_result)
                if region_added:
                    region_remove_result = await session.call_tool(
                        "remove_structured_properties",
                        {
                            "property_urns": [REGION_PROPERTY_URN],
                            "entity_urns": [SERVING_DATASET_URN],
                        },
                    )
                    _tool_payload(region_remove_result)

            _restored_entity_result, _restored_entity = await _wait_for_entity(
                session,
                lambda entity: (
                    _email_has_pii(entity)
                    and REGION_PROPERTY_URN not in json.dumps(entity, sort_keys=True)
                ),
                "PII tag restored and temporary region absent",
            )
            _stage("mutation recovery confirmed")
    anchor_reread_result = await _reread_anchor(parameters, anchor_urn)
    _stage("contract complete")
    tools = [
        {
            "name": tool.name,
            "description": tool.description,
            "inputSchema": tool.inputSchema,
            "annotations": tool.annotations.model_dump(mode="json")
            if tool.annotations is not None
            else None,
        }
        for tool in tools_result.tools
    ]
    return {
        "status": "PASS",
        "datahubCoreVersion": DATAHUB_CORE_VERSION,
        "datahubMcpVersion": DATAHUB_MCP_VERSION,
        "protocolVersion": initialize_result.protocolVersion,
        "server": initialize_result.serverInfo.model_dump(mode="json"),
        "authentication": {"invalidCredential": invalid_credential},
        "toolCount": len(tools),
        "tools": tools,
        "reads": {
            "servingEntity": _serialize_tool_result(initial_entity_result),
            "twoHopUpstreamLineage": _serialize_tool_result(lineage_result),
        },
        "mutations": {
            "piiBefore": True,
            "piiDuring": False,
            "piiRestored": True,
            "regionObserved": "IN",
            "regionRestoredToAbsent": True,
        },
        "anchor": {
            "urn": anchor_urn,
            "create": anchor_create_payload,
            "update": anchor_update_payload,
            "reread": anchor_reread_result,
            "expectedRevision": 2,
        },
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional path for the redacted JSON contract artifact.",
    )
    parser.add_argument("--quiet", action="store_true", help="Do not print the JSON artifact.")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    try:
        result = asyncio.run(probe_contract())
    except Exception as exc:
        result = {
            "status": "NO-GO",
            "datahubCoreVersion": DATAHUB_CORE_VERSION,
            "datahubMcpVersion": DATAHUB_MCP_VERSION,
            "errorType": type(exc).__name__,
            "error": str(exc),
            "causes": _exception_details(exc),
        }
    rendered = json.dumps(result, indent=2, sort_keys=True)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    if not args.quiet:
        print(rendered)  # noqa: T201 - this file is an operator-facing CLI
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
