from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]


def test_v1_evaluation_thresholds_are_frozen() -> None:
    document = yaml.safe_load(
        (ROOT / "evaluations" / "thresholds.v1.yaml").read_text(encoding="utf-8")
    )

    assert document["schema_version"] == "1.0.0"
    assert document["status"] == "frozen"
    assert document["change_control"] == "adr_and_founder_approval"
    assert document["deterministic"] == {
        "authority_pass_rate": 1.0,
        "transition_pass_rate": 1.0,
        "tenant_party_leakage_count": 0,
        "disclosure_pass_rate": 1.0,
        "eligibility_pass_rate": 1.0,
        "approval_pass_rate": 1.0,
        "effect_invariant_pass_rate": 1.0,
    }
    assert document["conversation"] == {
        "minimum_labelled_turns": 50,
        "task_success_rate": 0.90,
        "greeting_business_tool_calls": 0,
        "material_question_compliance": 1.0,
    }
    assert document["retrieval"] == {
        "recall_at_5": 0.90,
        "mrr_at_5": 0.80,
        "citation_precision": 0.98,
        "grounded_claim_support": 0.95,
        "unauthorized_retrievals": 0,
    }
    assert document["matching"]["hard_gate_accuracy"] == 1.0
    assert document["matching"]["private_value_leakage_count"] == 0
    assert document["bedrock"]["minimum_provider_turns"] == 100
    assert document["bedrock"]["structured_output_validity"] == 0.99
    assert document["performance"]["reference_case_max_usd"] == 0.50
    assert document["browser"] == {"critical_violations": 0, "serious_violations": 0}
    assert document["concurrency"] == {
        "evidence_change_races": 100,
        "current_decisions_per_race": 1,
        "direct_replacements_per_race": 1,
        "maximum_effects_per_race": 1,
    }
