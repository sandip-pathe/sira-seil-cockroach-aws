"""Run the labelled qualification set against the real Bedrock Converse runtime."""

# ruff: noqa: T201 -- the operator needs a credential-free result pointer.

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [
    str(ROOT / "python"),
    str(ROOT / "python" / "agents"),
    str(ROOT / "services" / "worker"),
]

from sira_agents.bedrock_runtime import (  # noqa: E402
    BedrockGuardrail,
    create_bedrock_client,
)
from sira_worker.bedrock_qualification_eval import (  # noqa: E402
    BedrockQualificationEvalCase,
    build_bedrock_qualification_report,
    evaluate_bedrock_qualification,
)


def _load_cases(path: Path) -> tuple[BedrockQualificationEvalCase, ...]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return tuple(BedrockQualificationEvalCase.model_validate(item) for item in payload["cases"])


async def _run(arguments: argparse.Namespace) -> dict[str, object]:
    client = create_bedrock_client(region=arguments.region, profile=arguments.profile)
    guardrail = None
    if arguments.guardrail_id or arguments.guardrail_version:
        if not arguments.guardrail_id or not arguments.guardrail_version:
            raise ValueError("guardrail ID and version must be supplied together")
        guardrail = BedrockGuardrail(arguments.guardrail_id, arguments.guardrail_version)
    results = await evaluate_bedrock_qualification(
        client=client,
        model_id=arguments.model,
        cases=_load_cases(arguments.corpus),
        guardrail=guardrail,
    )
    return build_bedrock_qualification_report(
        model_id=arguments.model,
        region=arguments.region,
        results=results,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile")
    parser.add_argument("--region", default="us-east-1")
    parser.add_argument("--model", default="us.amazon.nova-2-lite-v1:0")
    parser.add_argument("--guardrail-id")
    parser.add_argument("--guardrail-version")
    parser.add_argument(
        "--corpus",
        type=Path,
        default=ROOT / "evaluations" / "bedrock-qualification-cases.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / ".artifacts" / "preflight" / "bedrock-quality.json",
    )
    arguments = parser.parse_args()
    report = asyncio.run(_run(arguments))
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
                "case_count": report["case_count"],
                "metrics": report["metrics"],
            },
            sort_keys=True,
        )
    )
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
