"""Run the frozen labelled conversation corpus through Amazon Bedrock."""

# ruff: noqa: T201 -- operator command emits only a sanitized report location and status.

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python" / "agents"))

from sira_agents.bedrock_runtime import BedrockConverseRuntime, create_bedrock_client  # noqa: E402
from sira_agents.cognitive_runtime import BedrockCognitiveRuntime  # noqa: E402
from sira_agents.conversation_eval import (  # noqa: E402
    ConversationEvalCorpus,
    evaluate_conversations,
)


async def _run(arguments: argparse.Namespace) -> dict[str, object]:
    corpus = ConversationEvalCorpus.model_validate_json(arguments.corpus.read_text("utf-8"))
    thresholds = yaml.safe_load(arguments.thresholds.read_text("utf-8"))["conversation"]
    runtime = BedrockCognitiveRuntime(
        BedrockConverseRuntime(
            client=create_bedrock_client(region=arguments.region, profile=arguments.profile),
            model_id=arguments.model,
            max_turns=3,
        )
    )
    results = [await evaluate_conversations(runtime, corpus) for _ in range(arguments.repetitions)]
    provider_turns = sum(result.total for result in results)
    passed = sum(result.passed for result in results)
    greeting_calls = sum(result.greeting_business_tool_calls for result in results)
    material_total = sum(result.material_questions for result in results)
    material_passed = sum(result.material_questions_compliant for result in results)
    task_success = passed / provider_turns if provider_turns else 0.0
    material_compliance = material_passed / material_total if material_total else 0.0
    status = (
        "PASS"
        if corpus.labelled_turns >= int(thresholds["minimum_labelled_turns"])
        and task_success >= float(thresholds["task_success_rate"])
        and greeting_calls == int(thresholds["greeting_business_tool_calls"])
        and material_compliance >= float(thresholds["material_question_compliance"])
        else "FAIL"
    )
    failures = [failure for result in results for failure in result.failures]
    return {
        "schema_version": 1,
        "status": status,
        "checked_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "provider": "amazon-bedrock",
        "region": arguments.region,
        "model": arguments.model,
        "unique_labelled_turns": corpus.labelled_turns,
        "provider_turns": provider_turns,
        "task_success_rate": task_success,
        "greeting_business_tool_calls": greeting_calls,
        "material_question_compliance": material_compliance,
        "failure_count": len(failures),
        "failures": failures,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--region", default="us-east-1")
    parser.add_argument("--profile")
    parser.add_argument("--model", default="us.amazon.nova-2-lite-v1:0")
    parser.add_argument("--repetitions", type=int, default=2, choices=range(1, 6))
    parser.add_argument(
        "--corpus", type=Path, default=ROOT / "evaluations" / "conversation-turns.v1.json"
    )
    parser.add_argument(
        "--thresholds", type=Path, default=ROOT / "evaluations" / "thresholds.v1.yaml"
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / ".artifacts" / "preflight" / "conversation-eval.json",
    )
    arguments = parser.parse_args()
    report = asyncio.run(_run(arguments))
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
    )
    print(json.dumps({"status": report["status"], "artifact": str(arguments.output)}))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
