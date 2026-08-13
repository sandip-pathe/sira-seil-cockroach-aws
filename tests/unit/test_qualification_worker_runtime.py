from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any, cast

import pytest
from pydantic import SecretStr
from sira_worker import runtime as worker_runtime
from sira_worker.qualification import (
    MissionInput,
    QualificationAgentDecision,
    QualificationCriterion,
    QualificationWorker,
    _validate_grounded_decision,
    retrieve_qualification_candidates,
)

from integrations.automated_reasoning import AutomatedReasoningReview
from persistence.database import Database
from persistence.qualification_catalog import VectorCandidate
from persistence.qualification_repository import AttemptLease, FinalizationResult
from persistence.repositories import PersistenceConflict


class FakeDatabase:
    def __init__(self) -> None:
        self.closed = False

    @asynccontextmanager
    async def transaction(self, _organization_id: str) -> Any:
        yield object()

    async def close(self) -> None:
        self.closed = True


class FakeEmbedding:
    async def embed(self, text: str) -> SimpleNamespace:
        assert text
        return SimpleNamespace(
            vector=(1.0,) + (0.0,) * 1023,
            model_id="amazon.titan-embed-text-v2:0",
        )


def _settings(**overrides: object) -> worker_runtime.WorkerSettings:
    values: dict[str, object] = {
        "worker_mode": "qualification",
        "worker_database_url": SecretStr("postgresql://worker"),
        "catalog_database_url": SecretStr("postgresql://catalog"),
        "queue_url": "https://sqs.example/qualification.fifo",
        "organization_ids": ("org_a",),
        "idle_delay_seconds": 0.1,
    }
    values.update(overrides)
    return worker_runtime.WorkerSettings(**values)


def _candidate(product_id: str) -> VectorCandidate:
    return VectorCandidate(
        organization_id=f"seller_{product_id}",
        product_id=product_id,
        bundle_id=f"bundle_{product_id}",
        bundle_digest=f"sha256:{product_id:0<64}"[:71],
        embedding_id=f"embedding_{product_id}",
        content_hash=f"sha256:{product_id:0<64}"[:71],
        model_id="amazon.titan-embed-text-v2:0",
        cosine_distance=0.1,
    )


def _mission() -> MissionInput:
    return MissionInput(
        mission_id="qmission_0123456789abcdef0123456789abcdef",
        organization_id="org_buyer",
        trace_id="trace-1",
        buyer_context={"company": "Buyer"},
        brief={
            "category": "meeting-intelligence",
            "goal": "Choose a meeting intelligence platform",
            "seller_visible_requirements": {"hosting_region": "EU"},
        },
        policy={"human_approval": True},
    )


def test_worker_settings_normalize_profiles_and_organizations() -> None:
    settings = _settings(organization_ids=" org_a,org_b ,, ", aws_profile=" ")
    assert settings.organization_ids == ("org_a", "org_b")
    assert settings.aws_profile is None
    assert "meeting-intelligence" in _mission().retrieval_text()


def test_production_worker_requires_cockroach_for_every_database_role() -> None:
    with pytest.raises(ValueError, match="SIRA_WORKER_DATABASE_URL"):
        _settings(app_env="production").assert_safe_runtime()

    with pytest.raises(ValueError, match="SIRA_CATALOG_DATABASE_URL"):
        _settings(
            app_env="production",
            worker_database_url=SecretStr("cockroachdb+asyncpg://worker@db/sira"),
        ).assert_safe_runtime()

    _settings(
        app_env="production",
        worker_database_url=SecretStr("cockroachdb+asyncpg://worker@db/sira"),
        catalog_database_url=SecretStr("cockroachdb+asyncpg://catalog@db/sira"),
    ).assert_safe_runtime()


@pytest.mark.asyncio
async def test_marketplace_retrieval_reuses_embedding_and_dvi_contract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database = cast(Database, FakeDatabase())

    async def search(_session: object, **kwargs: object) -> tuple[VectorCandidate, ...]:
        assert kwargs["category"] == "meeting-intelligence"
        assert kwargs["visibility"] == "PUBLIC"
        assert kwargs["limit"] == 5
        assert len(cast(tuple[float, ...], kwargs["query_vector"])) == 1024
        return (_candidate("product-a"),)

    monkeypatch.setattr("sira_worker.qualification.search_published_candidates", search)
    result = await retrieve_qualification_candidates(
        catalog_database=database,
        embedding_client=cast(Any, FakeEmbedding()),
        organization_id="org_buyer",
        category="meeting-intelligence",
        query="EU hosted meeting notes",
        visibility="PUBLIC",
        limit=5,
    )
    assert result.category == "meeting-intelligence"
    assert result.candidates[0].product_id == "product-a"


@pytest.mark.asyncio
async def test_dispatcher_requires_scope_and_closes_database(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with pytest.raises(ValueError, match="WORKER_ORGANIZATION_IDS"):
        await worker_runtime._run_dispatcher(_settings(organization_ids=()))

    database = FakeDatabase()
    dispatched: list[str] = []

    async def dispatch(*_args: object, organization_id: str, **_kwargs: object) -> SimpleNamespace:
        dispatched.append(organization_id)
        raise asyncio.CancelledError

    monkeypatch.setattr(worker_runtime, "_database", lambda _url: cast(Database, database))
    monkeypatch.setattr(worker_runtime, "create_aws_client", lambda *_args, **_kwargs: object())
    monkeypatch.setattr(worker_runtime, "SqsFifoPublisher", lambda **_kwargs: object())
    monkeypatch.setattr(worker_runtime, "dispatch_batch", dispatch)

    with pytest.raises(asyncio.CancelledError):
        await worker_runtime._run_dispatcher(_settings())
    assert dispatched == ["org_a"]
    assert database.closed is True


@pytest.mark.asyncio
async def test_qualification_runtime_requires_catalog_and_closes_both_databases(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with pytest.raises(ValueError, match="SIRA_CATALOG_DATABASE_URL"):
        await worker_runtime._run_qualification_worker(
            _settings(catalog_database_url=SecretStr(""))
        )

    databases = [FakeDatabase(), FakeDatabase()]
    monkeypatch.setattr(
        worker_runtime,
        "_database",
        lambda _url: cast(Database, databases.pop(0)),
    )
    monkeypatch.setattr(worker_runtime, "create_aws_client", lambda *_args, **_kwargs: object())
    monkeypatch.setattr(worker_runtime, "create_bedrock_client", lambda **_kwargs: object())

    class CancellingConsumer:
        def __init__(self, **_kwargs: object) -> None:
            pass

        async def poll_once(self) -> int:
            raise asyncio.CancelledError

    monkeypatch.setattr(worker_runtime, "QualificationQueueConsumer", CancellingConsumer)
    worker_database = FakeDatabase()
    catalog_database = FakeDatabase()
    database_values = iter((worker_database, catalog_database))
    monkeypatch.setattr(
        worker_runtime,
        "_database",
        lambda _url: cast(Database, next(database_values)),
    )

    with pytest.raises(asyncio.CancelledError):
        await worker_runtime._run_qualification_worker(
            _settings(guardrail_id="guardrail-1", guardrail_version="1")
        )
    assert worker_database.closed is catalog_database.closed is True


@pytest.mark.asyncio
async def test_run_mission_replaces_stale_work_then_completes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database = cast(Database, FakeDatabase())
    worker = QualificationWorker(
        worker_database=database,
        catalog_database=database,
        embedding_client=cast(Any, FakeEmbedding()),
        bedrock_client=cast(Any, object()),
        model_id="amazon.nova-micro-v1:0",
        lease_owner="worker-test",
    )
    candidates = (_candidate("product-a"), _candidate("product-b"))
    prepared: list[str] = []
    finalizations = iter(
        (
            FinalizationResult("STALE", "attempt-1", replacement_attempt_id="attempt-2"),
            FinalizationResult("COMPLETED", "attempt-2", decision_id="decision-1"),
        )
    )

    async def load(*_args: object, **_kwargs: object) -> MissionInput:
        return _mission()

    async def search(*_args: object, **_kwargs: object) -> tuple[VectorCandidate, ...]:
        return candidates

    async def prepare(
        _self: QualificationWorker,
        _mission_input: MissionInput,
        _candidates: object,
    ) -> str:
        attempt_id = f"attempt-{len(prepared) + 1}"
        prepared.append(attempt_id)
        return attempt_id

    async def claim(
        _self: QualificationWorker, _organization_id: str, attempt_id: str
    ) -> AttemptLease:
        return AttemptLease(
            attempt_id,
            1,
            "worker-test",
            datetime.now(UTC) + timedelta(minutes=5),
        )

    async def evaluate(*_args: object, **_kwargs: object) -> QualificationAgentDecision:
        return QualificationAgentDecision(
            recommended_product_id="product-a",
            summary="Current evidence supports this product.",
            cited_dependency_ids=["dependency-a"],
            confidence="0.9",
        )

    async def finalize(*_args: object, **_kwargs: object) -> FinalizationResult:
        return next(finalizations)

    monkeypatch.setattr(QualificationWorker, "_load_mission", load)
    monkeypatch.setattr("sira_worker.qualification.search_published_candidates", search)
    monkeypatch.setattr(QualificationWorker, "_prepare_attempt", prepare)
    monkeypatch.setattr(QualificationWorker, "_claim_and_snapshot", claim)
    monkeypatch.setattr(QualificationWorker, "_evaluate", evaluate)
    monkeypatch.setattr(QualificationWorker, "_finalize", finalize)

    result = await worker.run_mission(organization_id="org_buyer", mission_id=_mission().mission_id)
    assert result.state == "COMPLETED"
    assert result.attempts == ("attempt-1", "attempt-2")
    assert result.decision_id == "decision-1"


@pytest.mark.asyncio
async def test_run_mission_rejects_insufficient_candidates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database = cast(Database, FakeDatabase())
    worker = QualificationWorker(
        worker_database=database,
        catalog_database=database,
        embedding_client=cast(Any, FakeEmbedding()),
        bedrock_client=cast(Any, object()),
        model_id="model",
        lease_owner="worker",
    )

    async def load(*_args: object, **_kwargs: object) -> MissionInput:
        return _mission()

    async def search(*_args: object, **_kwargs: object) -> tuple[VectorCandidate, ...]:
        return (_candidate("product-a"),)

    monkeypatch.setattr(QualificationWorker, "_load_mission", load)
    monkeypatch.setattr("sira_worker.qualification.search_published_candidates", search)
    with pytest.raises(PersistenceConflict, match="too few current candidates"):
        await worker.run_mission(organization_id="org_buyer", mission_id=_mission().mission_id)


@pytest.mark.asyncio
async def test_evaluate_requires_every_candidate_evidence_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    candidates = (_candidate("product-a"), _candidate("product-b"))
    final = {
        "recommended_product_id": "product-a",
        "summary": "Product A best satisfies the current requirements.",
        "cited_dependency_ids": ["dependency-a", "dependency-b"],
        "criteria": [
            {
                "criterion": "EU hosting",
                "result": "PASS",
                "rationale": "The pinned source says EU hosting is available.",
                "cited_dependency_ids": ["dependency-a"],
            }
        ],
        "confidence": 0.92,
    }

    class Bedrock:
        def __init__(self) -> None:
            self.calls = 0

        def converse(self, **_kwargs: object) -> dict[str, Any]:
            self.calls += 1
            if self.calls == 1:
                return {
                    "stopReason": "tool_use",
                    "output": {
                        "message": {
                            "role": "assistant",
                            "content": [
                                {
                                    "toolUse": {
                                        "toolUseId": f"tool-{index}",
                                        "name": "retrieve_product_evidence",
                                        "input": {"product_id": candidate.product_id},
                                    }
                                }
                                for index, candidate in enumerate(candidates)
                            ],
                        }
                    },
                    "usage": {},
                }
            return {
                "stopReason": "end_turn",
                "output": {
                    "message": {
                        "role": "assistant",
                        "content": [{"text": json.dumps(final)}],
                    }
                },
                "usage": {},
            }

    async def evidence(
        _self: QualificationWorker,
        _organization_id: str,
        _attempt_id: str,
        product_id: str,
    ) -> dict[str, object]:
        return {
            "product_id": product_id,
            "catalog": [],
            "evidence": [
                {
                    "dependency_id": f"dependency-{product_id[-1]}",
                    "facts": {"eu_hosting": product_id == "product-a"},
                }
            ],
        }

    database = cast(Database, FakeDatabase())
    bedrock = Bedrock()
    worker = QualificationWorker(
        worker_database=database,
        catalog_database=database,
        embedding_client=cast(Any, FakeEmbedding()),
        bedrock_client=cast(Any, bedrock),
        model_id="amazon.nova-micro-v1:0",
        lease_owner="worker-test",
    )
    monkeypatch.setattr(QualificationWorker, "_evidence_for_product", evidence)
    evaluation = await worker._evaluate(
        _mission(),
        AttemptLease("attempt-1", 1, "worker-test", datetime.now(UTC)),
        candidates,
    )
    assert evaluation.decision.recommended_product_id == "product-a"
    assert evaluation.automated_reasoning is None
    assert bedrock.calls == 2


@pytest.mark.asyncio
async def test_evaluate_records_reasoning_review_without_granting_authority(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Reviewer:
        async def review_safely(self, *, query: str, claim: str) -> AutomatedReasoningReview:
            assert "procurement_policy" in query
            assert "recommended_product_id" in claim
            return AutomatedReasoningReview(
                outcome="CONSISTENT",
                findings=(),
                evaluated_units=1,
                input_hash="sha256:" + "a" * 64,
            )

    final = {
        "recommended_product_id": "product-a",
        "summary": "Product A fits.",
        "cited_dependency_ids": ["dependency-a", "dependency-b"],
        "criteria": [],
        "confidence": 0.8,
    }

    class Bedrock:
        def __init__(self) -> None:
            self.calls = 0

        def converse(self, **_kwargs: object) -> dict[str, Any]:
            self.calls += 1
            candidates = ["product-a", "product-b"]
            if self.calls == 1:
                return {
                    "stopReason": "tool_use",
                    "output": {
                        "message": {
                            "role": "assistant",
                            "content": [
                                {
                                    "toolUse": {
                                        "toolUseId": f"tool-{index}",
                                        "name": "retrieve_product_evidence",
                                        "input": {"product_id": product_id},
                                    }
                                }
                                for index, product_id in enumerate(candidates)
                            ],
                        }
                    },
                    "usage": {},
                }
            return {
                "stopReason": "end_turn",
                "output": {
                    "message": {
                        "role": "assistant",
                        "content": [{"text": json.dumps(final)}],
                    }
                },
                "usage": {},
            }

    async def evidence(
        _self: QualificationWorker,
        _organization_id: str,
        _attempt_id: str,
        product_id: str,
    ) -> dict[str, object]:
        return {
            "product_id": product_id,
            "catalog": [],
            "evidence": [{"dependency_id": f"dependency-{product_id[-1]}", "facts": {}}],
        }

    database = cast(Database, FakeDatabase())
    worker = QualificationWorker(
        worker_database=database,
        catalog_database=database,
        embedding_client=cast(Any, FakeEmbedding()),
        bedrock_client=cast(Any, Bedrock()),
        model_id="amazon.nova-micro-v1:0",
        lease_owner="worker-test",
        reasoning_reviewer=cast(Any, Reviewer()),
    )
    monkeypatch.setattr(QualificationWorker, "_evidence_for_product", evidence)
    evaluation = await worker._evaluate(
        _mission(),
        AttemptLease("attempt-1", 1, "worker-test", datetime.now(UTC)),
        (_candidate("product-a"), _candidate("product-b")),
    )
    assert evaluation.automated_reasoning is not None
    assert evaluation.automated_reasoning.authoritative is False


def test_grounded_decision_validator_rejects_out_of_scope_model_claims() -> None:
    valid = QualificationAgentDecision(
        recommended_product_id="product-a",
        summary="Product A fits the pinned requirement.",
        cited_dependency_ids=["evidence-a"],
        criteria=[
            QualificationCriterion(
                criterion="EU hosting",
                result="PASS",
                rationale="Pinned evidence confirms EU hosting.",
                cited_dependency_ids=["evidence-a"],
            )
        ],
        confidence="0.9",
    )
    scope = frozenset({"product-a", "product-b"})
    dependencies = {"evidence-a": "product-a", "evidence-b": "product-b"}
    _validate_grounded_decision(valid, allowed_products=scope, dependency_products=dependencies)

    cases = (
        (
            valid.model_copy(update={"recommended_product_id": "product-x"}),
            "outside the candidate set",
        ),
        (
            valid.model_copy(update={"cited_dependency_ids": ["invented"]}),
            "outside the pinned dependency set",
        ),
        (
            valid.model_copy(update={"cited_dependency_ids": ["evidence-b"]}),
            "lacks product-specific evidence",
        ),
        (
            valid.model_copy(
                update={
                    "criteria": [
                        QualificationCriterion(
                            criterion="Price",
                            result="PASS",
                            rationale="The source contains a price.",
                            cited_dependency_ids=["evidence-b"],
                        )
                    ]
                }
            ),
            "criterion citations",
        ),
    )
    for decision, message in cases:
        with pytest.raises(PersistenceConflict, match=message):
            _validate_grounded_decision(
                decision,
                allowed_products=scope,
                dependency_products=dependencies,
            )


def test_qualification_criteria_require_rationale_and_unique_citations() -> None:
    with pytest.raises(ValueError, match="require rationale and citations"):
        QualificationCriterion(criterion="EU hosting", result="PASS")
    with pytest.raises(ValueError, match="must be unique"):
        QualificationCriterion(
            criterion="EU hosting",
            result="PASS",
            rationale="Two identical citations are invalid.",
            cited_dependency_ids=["evidence-a", "evidence-a"],
        )
    unknown = QualificationCriterion(criterion="SOC 2", result="UNKNOWN")
    assert unknown.cited_dependency_ids == []
