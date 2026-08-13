"""Credential-safe live smoke for the two Bedrock models used by SIRA/SEIL."""

# ruff: noqa: T201 -- this operator-facing smoke emits one credential-free JSON result.

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python" / "agents"))

from sira_agents.bedrock_runtime import (  # noqa: E402
    BedrockConverseRuntime,
    TitanEmbeddingClient,
    create_bedrock_client,
)
from sira_agents.runtime import AgentRole, AgentRunRequest  # noqa: E402


async def _run(*, region: str, profile: str | None, chat_model: str) -> dict[str, object]:
    client = create_bedrock_client(region=region, profile=profile)
    embedding = await TitanEmbeddingClient(client=client).embed(
        "SIRA qualifies B2B software using current seller evidence."
    )
    response = await BedrockConverseRuntime(client=client, model_id=chat_model).run(
        AgentRunRequest(
            role=AgentRole.SIRA,
            instructions="Confirm the runtime contract in one compact object.",
            prompt="Return status ok and provider bedrock.",
            model_context={"smoke_test": True},
        )
    )
    chat_contract_valid = response.output == {"provider": "bedrock", "status": "ok"}
    embedding_contract_valid = embedding.dimensions == 1024 and embedding.normalized
    normalized_output = json.dumps(response.output, sort_keys=True, separators=(",", ":"))
    return {
        "schema_version": 1,
        "status": "PASS" if chat_contract_valid and embedding_contract_valid else "FAIL",
        "checked_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "region": region,
        "provider_call_count": 2,
        "chat_runtime": response.runtime,
        "chat_model": chat_model,
        "chat_contract_valid": chat_contract_valid,
        "chat_output_sha256": "sha256:" + sha256(normalized_output.encode("utf-8")).hexdigest(),
        "embedding_model": embedding.model_id,
        "embedding_dimensions": embedding.dimensions,
        "embedding_normalized": embedding.normalized,
        "guardrail_status": "NOT_RUN",
        "limitations": [
            (
                "Guardrail intervention requires a deployed project Guardrail and is checked "
                "separately."
            ),
            (
                "This smoke proves provider contracts, not the labelled qualification quality "
                "threshold."
            ),
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--region", default="us-east-1")
    parser.add_argument("--profile")
    parser.add_argument("--chat-model", default="amazon.nova-micro-v1:0")
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / ".artifacts" / "preflight" / "bedrock.json",
    )
    arguments = parser.parse_args()
    report = asyncio.run(
        _run(
            region=arguments.region,
            profile=arguments.profile,
            chat_model=arguments.chat_model,
        )
    )
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(
        json.dumps(
            {
                "status": report["status"],
                "artifact": str(arguments.output),
                "provider_call_count": report["provider_call_count"],
            },
            sort_keys=True,
        )
    )
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
