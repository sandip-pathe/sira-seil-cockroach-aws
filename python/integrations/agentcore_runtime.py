"""Amazon Bedrock AgentCore Runtime adapter for bounded product experiments."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Protocol, cast

from sira_agents.experiment import ExperimentResult, ExperimentSpec
from sira_agents.guardrails import validate_agent_payload

from domain import content_hash


class AgentCoreRuntimeError(RuntimeError):
    """The remote runtime failed or returned data outside the experiment contract."""


class AgentCoreClient(Protocol):
    def invoke_agent_runtime(self, **kwargs: Any) -> Mapping[str, Any]: ...


def create_agentcore_client(*, region: str, profile: str | None = None) -> AgentCoreClient:
    """Build a client from a local profile or the ECS task-role credential chain."""

    import boto3  # type: ignore[import-untyped]
    from botocore.config import Config  # type: ignore[import-untyped]

    if not region.strip():
        raise ValueError("AWS region is required")
    session = boto3.Session(profile_name=profile) if profile else boto3.Session()
    return cast(
        AgentCoreClient,
        session.client(
            "bedrock-agentcore",
            region_name=region,
            config=Config(
                connect_timeout=5,
                read_timeout=1_800,
                retries={"mode": "standard", "max_attempts": 3},
            ),
        ),
    )


def _read_response_body(response: Mapping[str, Any], max_bytes: int) -> bytes:
    body = response.get("response")
    if body is None:
        raise AgentCoreRuntimeError("AgentCore response body is missing")
    if hasattr(body, "read"):
        payload = bytes(body.read(max_bytes + 1))
    elif isinstance(body, (bytes, bytearray)):
        payload = bytes(body)
    else:
        try:
            payload = b"".join(bytes(chunk) for chunk in body)
        except (TypeError, ValueError) as error:
            raise AgentCoreRuntimeError("AgentCore response body is unreadable") from error
    if len(payload) > max_bytes:
        raise AgentCoreRuntimeError("AgentCore response exceeded the experiment output budget")
    return payload


@dataclass(slots=True)
class AgentCoreExperimentRunner:
    """Run a stateless experiment in AgentCore; CockroachDB remains authoritative."""

    client: AgentCoreClient = field(repr=False)
    runtime_arn: str
    qualifier: str = "DEFAULT"

    def __post_init__(self) -> None:
        if not self.runtime_arn.startswith("arn:aws:bedrock-agentcore:"):
            raise ValueError("a Bedrock AgentCore Runtime ARN is required")

    async def run(self, spec: ExperimentSpec) -> ExperimentResult:
        request = {
            "contract": "sira.product-experiment.v1",
            "experiment": spec.model_dump(mode="json"),
        }
        validate_agent_payload(request, seller_visible=False)
        encoded = json.dumps(request, sort_keys=True, separators=(",", ":")).encode("utf-8")
        session_id = f"sira-experiment-{content_hash(request).split(':', 1)[1][:32]}"

        def invoke() -> Mapping[str, Any]:
            return self.client.invoke_agent_runtime(
                agentRuntimeArn=self.runtime_arn,
                qualifier=self.qualifier,
                runtimeSessionId=session_id,
                contentType="application/json",
                accept="application/json",
                payload=encoded,
            )

        try:
            response = await asyncio.wait_for(
                asyncio.to_thread(invoke), timeout=spec.timeout_seconds
            )
            raw = _read_response_body(response, spec.max_output_bytes)
            document = json.loads(raw)
            if not isinstance(document, dict):
                raise AgentCoreRuntimeError("AgentCore response must be a JSON object")
            document.pop("artifact_hash", None)
            artifact_hash = content_hash(document)
            return ExperimentResult.model_validate({**document, "artifact_hash": artifact_hash})
        except AgentCoreRuntimeError:
            raise
        except TimeoutError as error:
            raise AgentCoreRuntimeError("AgentCore experiment timed out") from error
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError, TypeError) as error:
            raise AgentCoreRuntimeError(
                "AgentCore response violated the experiment result contract"
            ) from error
