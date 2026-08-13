"""Credential-safe live smoke for the two Bedrock models used by SIRA/SEIL."""

# ruff: noqa: T201 -- this operator-facing smoke emits one credential-free JSON result.

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python" / "agents"))

from sira_agents.bedrock_runtime import (  # noqa: E402
    BedrockConverseRuntime,
    TitanEmbeddingClient,
    create_bedrock_client,
)
from sira_agents.runtime import AgentRole, AgentRunRequest  # noqa: E402


async def _run(*, region: str, profile: str | None, chat_model: str) -> None:
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
    print(
        json.dumps(
            {
                "chat_runtime": response.runtime,
                "chat_model": chat_model,
                "chat_output": response.output,
                "embedding_model": embedding.model_id,
                "embedding_dimensions": embedding.dimensions,
                "embedding_normalized": embedding.normalized,
            },
            sort_keys=True,
        )
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--region", default="us-east-1")
    parser.add_argument("--profile")
    parser.add_argument("--chat-model", default="amazon.nova-micro-v1:0")
    arguments = parser.parse_args()
    asyncio.run(
        _run(
            region=arguments.region,
            profile=arguments.profile,
            chat_model=arguments.chat_model,
        )
    )


if __name__ == "__main__":
    main()
