"""Run the checked-in qualification trust-boundary evaluation corpus."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [
    str(ROOT / "python"),
    str(ROOT / "python" / "agents"),
    str(ROOT / "services" / "worker"),
]

from sira_worker.qualification import QualificationAgentDecision  # noqa: E402
from sira_worker.qualification_eval import (  # noqa: E402
    QualificationEvalCase,
    run_qualification_eval,
)

CORPUS = ROOT / "evaluations" / "qualification-agent-cases.json"
REPORT = ROOT / "evaluations" / "qualification-agent-report.json"


def _load() -> tuple[QualificationEvalCase, ...]:
    payload = json.loads(CORPUS.read_text(encoding="utf-8"))
    cases: list[QualificationEvalCase] = []
    for item in payload["cases"]:
        item = dict(item)
        cases.append(
            QualificationEvalCase(
                id=str(item["id"]),
                expected=item["expected"],
                allowed_products=frozenset(item["allowed_products"]),
                dependency_products=dict(item["dependency_products"]),
                decision=QualificationAgentDecision.model_validate(item["decision"]),
            )
        )
    return tuple(cases)


def _report() -> dict[str, Any]:
    results = run_qualification_eval(_load())
    passed = sum(result.passed for result in results)
    return {
        "schema_version": 1,
        "evaluation": "qualification-agent-grounding-boundary",
        "deterministic": True,
        "provider_calls": 0,
        "case_count": len(results),
        "passed_count": passed,
        "pass_rate": passed / len(results) if results else 0,
        "threshold": 1.0,
        "status": "PASS" if passed == len(results) else "FAIL",
        "cases": [
            {
                "id": result.case_id,
                "expected": result.expected,
                "actual": result.actual,
                "passed": result.passed,
            }
            for result in results
        ],
        "limitations": [
            "This report tests deterministic trust-boundary enforcement, not live model quality.",
            "Live Bedrock fit and groundedness evaluation remains a separate provider gate.",
        ],
    }


def main() -> int:
    report = _report()
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if "--check" in sys.argv:
        if not REPORT.exists() or REPORT.read_text(encoding="utf-8") != rendered:
            sys.stdout.write(
                "Qualification evaluation report drift; run the script without --check.\n"
            )
            return 1
    else:
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        REPORT.write_text(rendered, encoding="utf-8", newline="\n")
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
