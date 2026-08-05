from __future__ import annotations

import pytest
from pydantic import ValidationError
from sira_agents.experiment import ExperimentSpec


def test_experiment_requires_replayable_evidence() -> None:
    spec = ExperimentSpec(
        candidate_id="product_fixture_a",
        fixture_id="meeting_transcript_v1",
        procedure=["Import fixture", "Measure action-item extraction"],
        environment={"locale": "en-US", "seats": 10},
        success_signals=[
            {
                "name": "action_item_recall",
                "measurement": "Compare output to labelled fixture",
                "success_threshold": ">= 0.9",
            }
        ],
        replay_command=["evaluate", "meeting_transcript_v1"],
    )

    assert spec.egress_hosts == []
    assert spec.success_signals[0].name == "action_item_recall"


def test_experiment_rejects_embedded_credentials() -> None:
    with pytest.raises(ValidationError):
        ExperimentSpec(
            candidate_id="product_fixture_a",
            fixture_id="fixture",
            procedure=["Use api_key from payload"],
            environment={},
            success_signals=[{"name": "ok", "measurement": "observe", "success_threshold": "true"}],
            replay_command=["run"],
        )
