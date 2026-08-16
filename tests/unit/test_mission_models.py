from __future__ import annotations

from sira_agents.mission_models import MissionTurnOutput


def test_artifact_only_output_uses_a_valid_operational_state() -> None:
    output = MissionTurnOutput.model_validate(
        {
            "kind": "research",
            "title": "Source-linked research",
            "authority": "OBSERVED",
            "payload": {"source_count": 2},
            "source_refs": [],
        }
    )

    assert output.mission_state == "SYNTHESIZING"
    assert output.stop_reason == "RESEARCH_PACKET_READY"
    assert [artifact.kind for artifact in output.artifacts] == ["research"]
