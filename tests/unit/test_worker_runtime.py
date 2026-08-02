from __future__ import annotations

from collections.abc import Coroutine
from datetime import timedelta
from types import SimpleNamespace
from typing import Any

import pytest
from sira_worker import activities, temporal, workflows
from sira_worker import main as worker_main
from sira_worker.contracts import (
    CheckoutActivityResult,
    FulfillmentActivityResult,
    IsolatedCheckoutActivityInput,
    PurchaseCheckoutWorkflowInput,
    ReconcileActivityInput,
    SafeFulfillmentStatus,
    SafeMerchantOutcome,
    VerifyFulfillmentActivityInput,
    WorkflowFailureActivityInput,
)
from temporalio.exceptions import ApplicationError

from integrations.errors import ProviderError, ProviderErrorCode


def _activity_input() -> IsolatedCheckoutActivityInput:
    return IsolatedCheckoutActivityInput(
        organization_id="org_consultco",
        purchase_intent_id="pi_demo",
        intent_hash="sha256:demo",
        prava_session_id="ses_demo",
        merchant_adapter_id="merchant_demo",
        idempotency_key="checkout_demo_v1",
    )


def _reconcile_input() -> ReconcileActivityInput:
    return ReconcileActivityInput(
        organization_id="org_consultco",
        purchase_intent_id="pi_demo",
        intent_hash="sha256:demo",
        prava_session_id="ses_demo",
        merchant_adapter_id="merchant_demo",
        idempotency_key="checkout_demo_v1",
        transaction_reference="txn_demo",
    )


def _checkout_result(
    *,
    outcome: SafeMerchantOutcome = SafeMerchantOutcome.APPROVED,
    reconciliation_required: bool = False,
) -> CheckoutActivityResult:
    return CheckoutActivityResult(
        purchase_intent_id="pi_demo",
        prava_session_id="ses_demo",
        prava_order_id="order_demo",
        transaction_reference="txn_demo",
        merchant_outcome=outcome,
        merchant_order_id="merchant_order_demo"
        if outcome is SafeMerchantOutcome.APPROVED
        else None,
        provider_reported=not reconciliation_required,
        reconciliation_required=reconciliation_required,
    )


def _fulfillment_result() -> FulfillmentActivityResult:
    return FulfillmentActivityResult("pi_demo", SafeFulfillmentStatus.VERIFIED)


def _configured_settings() -> worker_main.WorkerSettings:
    return worker_main.WorkerSettings(
        _env_file=None,
        database_url="postgresql+asyncpg://worker@db.test/sira",
        temporal_address="temporal.test:7233",
        temporal_namespace="test-namespace",
        temporal_task_queue="test-checkout",
        worker_organization_ids="org_consultco,org_second",
        prava_base_url="https://api.prava.test",
        prava_secret_key="p",  # pragma: allowlist secret
        prava_merchant_url="https://merchant.prava.test/checkout",
        prava_callback_url="https://callback.sira.test/prava",
        prava_hosted_checkout_hosts="EXTRA.PRAVA.TEST, extra-two.prava.test",
        merchant_base_url="https://merchant-api.test",
        merchant_api_key="m",  # pragma: allowlist secret
        merchant_id="merchant_fixture_d",
    )


def test_worker_configuration_fails_closed_and_validates_https_hosts() -> None:
    settings = worker_main.WorkerSettings(_env_file=None)
    with pytest.raises(worker_main.WorkerSetupError) as captured:
        settings.require_configuration()

    assert captured.value.missing == sorted(
        [
            "CONTROLLED_MERCHANT_API_KEY",
            "CONTROLLED_MERCHANT_BASE_URL",
            "CONTROLLED_MERCHANT_ID",
            "DATABASE_URL",
            "PRAVA_BASE_URL",
            "PRAVA_CALLBACK_URL",
            "PRAVA_MERCHANT_URL",
            "PRAVA_SECRET_KEY",
            "TEMPORAL_ADDRESS",
            "WORKER_ORGANIZATION_IDS",
        ]
    )
    assert str(captured.value) == "worker provider configuration is incomplete"
    assert worker_main._https_host("https://API.Prava.Test/v1", "PRAVA_BASE_URL") == (
        "api.prava.test"
    )
    for invalid_url in (
        "http://api.prava.test",
        "https://user@api.prava.test",
        "https://api.prava.test/#fragment",
        "not-a-url",
    ):
        with pytest.raises(worker_main.WorkerSetupError) as invalid:
            worker_main._https_host(invalid_url, "PRAVA_BASE_URL")
        assert invalid.value.missing == ["PRAVA_BASE_URL_VALID_HTTPS_URL"]

    sqlite_settings = _configured_settings()
    sqlite_settings.database_url = "sqlite+aiosqlite:///:memory:"
    with pytest.raises(worker_main.WorkerSetupError) as noncanonical:
        sqlite_settings.require_configuration()
    assert noncanonical.value.missing == ["DATABASE_URL_POSTGRESQL"]


@pytest.mark.asyncio
async def test_worker_rejects_a_non_postgres_constructed_engine(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _configured_settings()
    closed = False

    class WrongDialectDatabase:
        def __init__(self, database_settings: object) -> None:
            del database_settings
            self.engine = SimpleNamespace(dialect=SimpleNamespace(name="sqlite"))

        async def close(self) -> None:
            nonlocal closed
            closed = True

    monkeypatch.setattr(worker_main, "WorkerSettings", lambda: settings)
    monkeypatch.setattr(worker_main, "Database", WrongDialectDatabase)

    with pytest.raises(worker_main.WorkerSetupError) as captured:
        await worker_main.run_worker()

    assert captured.value.missing == ["DATABASE_ENGINE_POSTGRESQL"]
    assert closed is True


@pytest.mark.asyncio
async def test_run_worker_assembles_production_boundaries_and_always_closes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _configured_settings()
    events: list[str] = []
    captured: dict[str, Any] = {}

    class FakeDatabase:
        def __init__(self, database_settings: object) -> None:
            captured["database_settings"] = database_settings
            self.engine = SimpleNamespace(dialect=SimpleNamespace(name="postgresql"))

        async def close(self) -> None:
            events.append("database.close")

    class FakePrava:
        def __init__(self, **kwargs: Any) -> None:
            captured["prava"] = kwargs

        async def aclose(self) -> None:
            events.append("prava.close")

    class FakeMerchant:
        def __init__(self, **kwargs: Any) -> None:
            captured["merchant"] = kwargs

        async def aclose(self) -> None:
            events.append("merchant.close")

    class FakeWorker:
        async def run(self) -> None:
            events.append("worker.run")
            raise RuntimeError("worker stopped")

    class FakeDispatcher:
        def __init__(self, **kwargs: Any) -> None:
            captured["dispatcher"] = kwargs

        async def run(self) -> None:
            events.append("dispatcher.run")

    async def fake_connect(target: str, *, namespace: str) -> object:
        captured["temporal_connect"] = (target, namespace)
        return object()

    def fake_coordinator(**kwargs: Any) -> object:
        captured["coordinator"] = kwargs
        return object()

    def fake_build_worker(**kwargs: Any) -> FakeWorker:
        captured["worker"] = kwargs
        return FakeWorker()

    monkeypatch.setattr(worker_main, "WorkerSettings", lambda: settings)
    monkeypatch.setattr(worker_main, "Database", FakeDatabase)
    monkeypatch.setattr(worker_main, "PravaHostedRestAdapter", FakePrava)
    monkeypatch.setattr(worker_main, "ControlledMerchantRestAdapter", FakeMerchant)
    monkeypatch.setattr(worker_main, "connect_temporal", fake_connect)
    monkeypatch.setattr(worker_main, "PersistentCheckoutCoordinator", fake_coordinator)
    monkeypatch.setattr(worker_main, "build_worker", fake_build_worker)
    monkeypatch.setattr(worker_main, "CheckoutOutboxDispatcher", FakeDispatcher)

    with pytest.raises(RuntimeError, match="worker stopped"):
        await worker_main.run_worker()

    assert captured["temporal_connect"] == ("temporal.test:7233", "test-namespace")
    assert captured["prava"]["api_hosts"] == frozenset({"api.prava.test"})
    assert captured["prava"]["merchant_hosts"] == frozenset({"merchant.prava.test"})
    assert captured["prava"]["callback_hosts"] == frozenset({"callback.sira.test"})
    assert {"extra.prava.test", "extra-two.prava.test"} <= captured["prava"][
        "hosted_checkout_hosts"
    ]
    assert captured["merchant"]["allowed_hosts"] == frozenset({"merchant-api.test"})
    assert captured["coordinator"]["merchant_adapter_id"] == "merchant_fixture_d"
    assert captured["worker"]["task_queue"] == "test-checkout"
    assert captured["dispatcher"]["organization_ids"] == ("org_consultco", "org_second")
    assert events == [
        "worker.run",
        "dispatcher.run",
        "prava.close",
        "merchant.close",
        "database.close",
    ]


def test_worker_main_reports_only_missing_setting_names(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    calls = 0

    def fake_run(coroutine: Coroutine[Any, Any, None]) -> None:
        nonlocal calls
        calls += 1
        coroutine.close()
        if calls == 1:
            raise worker_main.WorkerSetupError(["PRAVA_SECRET_KEY", "DATABASE_URL"])

    monkeypatch.setattr(worker_main.asyncio, "run", fake_run)

    assert worker_main.main() == 2
    assert capsys.readouterr().err == (
        "Worker setup blocked; configure: DATABASE_URL, PRAVA_SECRET_KEY\n"
    )
    assert worker_main.main() == 0


def test_temporal_worker_builds_registered_workflow_and_activities(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}
    sentinel = object()

    class FakeWorker:
        def __init__(self, client: object, **kwargs: Any) -> None:
            captured["client"] = client
            captured.update(kwargs)

    monkeypatch.setattr(temporal, "Worker", FakeWorker)

    with pytest.raises(ValueError, match="task_queue must not be empty"):
        temporal.build_worker(client=sentinel, task_queue=" ", coordinator=object())  # type: ignore[arg-type]

    worker = temporal.build_worker(
        client=sentinel,  # type: ignore[arg-type]
        task_queue="checkout-test",
        coordinator=object(),  # type: ignore[arg-type]
    )
    assert isinstance(worker, FakeWorker)
    assert captured["client"] is sentinel
    assert captured["task_queue"] == "checkout-test"
    assert captured["workflows"] == [workflows.PurchaseCheckoutWorkflow]
    assert [item.__name__ for item in captured["activities"]] == [
        "execute_isolated_checkout",
        "reconcile_checkout",
        "verify_fulfillment",
        "fail_checkout_workflow",
    ]


@pytest.mark.asyncio
async def test_temporal_connection_validates_names_and_delegates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, str]] = []
    sentinel = object()

    class FakeClient:
        @staticmethod
        async def connect(target: str, *, namespace: str) -> object:
            calls.append((target, namespace))
            return sentinel

    monkeypatch.setattr(temporal, "Client", FakeClient)

    for target, namespace in (("", "default"), ("temporal.test:7233", " ")):
        with pytest.raises(ValueError, match="Temporal target and namespace are required"):
            await temporal.connect_temporal(target, namespace=namespace)

    assert await temporal.connect_temporal("temporal.test:7233", namespace="testing") is sentinel
    assert calls == [("temporal.test:7233", "testing")]


@pytest.mark.asyncio
async def test_workflow_returns_direct_checkout_without_reconciliation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, object, dict[str, Any]]] = []

    async def fake_execute(name: str, request: object, **kwargs: Any) -> object:
        calls.append((name, request, kwargs))
        return (
            _fulfillment_result()
            if name == "sira.verify_fulfillment"
            else _checkout_result()
        )

    monkeypatch.setattr(workflows.workflow, "execute_activity", fake_execute)
    request = PurchaseCheckoutWorkflowInput(
        organization_id="org_consultco",
        purchase_intent_id="pi_demo",
        intent_hash="sha256:demo",
        prava_session_id="ses_demo",
        merchant_adapter_id="merchant_demo",
        idempotency_key="checkout_demo_v1",
    )

    result = await workflows.PurchaseCheckoutWorkflow().run(request)

    assert result.merchant_outcome is SafeMerchantOutcome.APPROVED
    assert result.merchant_order_id == "merchant_order_demo"
    assert result.reconciliation_required is False
    assert [call[0] for call in calls] == [
        "sira.execute_isolated_checkout",
        "sira.verify_fulfillment",
    ]
    assert calls[0][1] == request.activity_input()
    assert calls[0][2]["retry_policy"].maximum_attempts == 1
    assert calls[1][1] == VerifyFulfillmentActivityInput(
        organization_id="org_consultco",
        purchase_intent_id="pi_demo",
        merchant_order_id="merchant_order_demo",
    )


@pytest.mark.asyncio
async def test_workflow_records_safe_failure_after_fulfillment_retries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, object, dict[str, Any]]] = []

    async def fake_execute(name: str, request: object, **kwargs: Any) -> object:
        calls.append((name, request, kwargs))
        if name == "sira.execute_isolated_checkout":
            return _checkout_result()
        if name == "sira.verify_fulfillment":
            raise ApplicationError("safe failure", non_retryable=False)
        return None

    monkeypatch.setattr(workflows.workflow, "execute_activity", fake_execute)
    request = PurchaseCheckoutWorkflowInput(
        organization_id="org_consultco",
        purchase_intent_id="pi_demo",
        intent_hash="sha256:demo",
        prava_session_id="ses_demo",
        merchant_adapter_id="merchant_demo",
        idempotency_key="checkout_demo_v1",
    )

    with pytest.raises(ApplicationError):
        await workflows.PurchaseCheckoutWorkflow().run(request)

    assert [call[0] for call in calls] == [
        "sira.execute_isolated_checkout",
        "sira.verify_fulfillment",
        "sira.fail_checkout_workflow",
    ]
    assert calls[-1][1] == WorkflowFailureActivityInput(
        organization_id="org_consultco",
        purchase_intent_id="pi_demo",
        safe_code="FULFILLMENT_RETRY_EXHAUSTED",
    )


@pytest.mark.asyncio
async def test_workflow_reconciles_uncertain_checkout_before_returning(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, object, dict[str, Any]]] = []
    results = iter(
        [
            _checkout_result(
                outcome=SafeMerchantOutcome.UNKNOWN,
                reconciliation_required=True,
            ),
            _checkout_result(),
        ]
    )

    async def fake_execute(name: str, request: object, **kwargs: Any) -> object:
        calls.append((name, request, kwargs))
        if name == "sira.verify_fulfillment":
            return _fulfillment_result()
        return next(results)

    monkeypatch.setattr(workflows.workflow, "execute_activity", fake_execute)
    request = PurchaseCheckoutWorkflowInput(
        organization_id="org_consultco",
        purchase_intent_id="pi_demo",
        intent_hash="sha256:demo",
        prava_session_id="ses_demo",
        merchant_adapter_id="merchant_demo",
        idempotency_key="checkout_demo_v1",
    )

    result = await workflows.PurchaseCheckoutWorkflow().run(request)

    assert result.merchant_outcome is SafeMerchantOutcome.APPROVED
    assert [call[0] for call in calls] == [
        "sira.execute_isolated_checkout",
        "sira.reconcile_checkout",
        "sira.verify_fulfillment",
    ]
    assert calls[1][1] == _reconcile_input()
    assert calls[1][2]["retry_policy"].maximum_attempts == 5


@pytest.mark.asyncio
async def test_workflow_schedules_authoritative_reconciliation_until_exhausted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, object, dict[str, Any]]] = []
    sleeps: list[timedelta] = []
    unresolved = _checkout_result(
        outcome=SafeMerchantOutcome.UNKNOWN,
        reconciliation_required=True,
    )

    async def fake_execute(name: str, request: object, **kwargs: Any) -> object:
        calls.append((name, request, kwargs))
        if name == "sira.fail_checkout_workflow":
            return None
        return unresolved

    async def fake_sleep(delay: timedelta) -> None:
        sleeps.append(delay)

    monkeypatch.setattr(workflows.workflow, "execute_activity", fake_execute)
    monkeypatch.setattr(workflows.workflow, "sleep", fake_sleep)
    request = PurchaseCheckoutWorkflowInput(
        organization_id="org_consultco",
        purchase_intent_id="pi_demo",
        intent_hash="sha256:demo",
        prava_session_id="ses_demo",
        merchant_adapter_id="merchant_demo",
        idempotency_key="checkout_demo_v1",
    )

    result = await workflows.PurchaseCheckoutWorkflow().run(request)

    assert result.reconciliation_required is True
    assert [call[0] for call in calls].count("sira.reconcile_checkout") == 5
    assert [item.total_seconds() for item in sleeps] == [15, 60, 300, 900]
    assert calls[-1][0] == "sira.fail_checkout_workflow"
    assert calls[-1][1] == WorkflowFailureActivityInput(
        organization_id="org_consultco",
        purchase_intent_id="pi_demo",
        safe_code="CHECKOUT_RECONCILIATION_INCOMPLETE",
    )


@pytest.mark.asyncio
async def test_activities_return_safe_coordinator_results() -> None:
    direct = _checkout_result()
    reconciled = _checkout_result()

    class SuccessfulCoordinator:
        async def execute_isolated_checkout(
            self, request: IsolatedCheckoutActivityInput
        ) -> CheckoutActivityResult:
            assert request == _activity_input()
            return direct

        async def reconcile_checkout(
            self, request: ReconcileActivityInput
        ) -> CheckoutActivityResult:
            assert request == _reconcile_input()
            return reconciled

    worker_activities = activities.CheckoutActivities(SuccessfulCoordinator())
    assert await worker_activities.execute_isolated_checkout(_activity_input()) is direct
    assert await worker_activities.reconcile_checkout(_reconcile_input()) is reconciled


@pytest.mark.asyncio
async def test_activities_fail_closed_when_coordinator_returns_no_result() -> None:
    class EmptyCoordinator:
        async def execute_isolated_checkout(self, request: IsolatedCheckoutActivityInput) -> None:
            del request

        async def reconcile_checkout(self, request: ReconcileActivityInput) -> None:
            del request

    worker_activities = activities.CheckoutActivities(EmptyCoordinator())  # type: ignore[arg-type]
    with pytest.raises(ApplicationError) as checkout_error:
        await worker_activities.execute_isolated_checkout(_activity_input())
    with pytest.raises(ApplicationError) as reconcile_error:
        await worker_activities.reconcile_checkout(_reconcile_input())

    assert checkout_error.value.type == "CHECKOUT_ACTIVITY_REDACTED_FAILURE"
    assert checkout_error.value.non_retryable is True
    assert reconcile_error.value.type == "RECONCILIATION_ACTIVITY_REDACTED_FAILURE"
    assert reconcile_error.value.non_retryable is True


@pytest.mark.asyncio
@pytest.mark.parametrize("retryable", [False, True])
async def test_reconciliation_preserves_only_safe_provider_error_metadata(
    retryable: bool,
) -> None:
    class ProviderFailureCoordinator:
        async def execute_isolated_checkout(
            self, request: IsolatedCheckoutActivityInput
        ) -> CheckoutActivityResult:
            del request
            raise ProviderError(
                provider="prava",
                operation="checkout",
                code=ProviderErrorCode.TIMEOUT,
                retryable=True,
            )

        async def reconcile_checkout(
            self, request: ReconcileActivityInput
        ) -> CheckoutActivityResult:
            del request
            raise ProviderError(
                provider="prava",
                operation="reconcile",
                code=ProviderErrorCode.TIMEOUT,
                retryable=retryable,
            )

    worker_activities = activities.CheckoutActivities(ProviderFailureCoordinator())
    with pytest.raises(ApplicationError) as checkout_error:
        await worker_activities.execute_isolated_checkout(_activity_input())
    with pytest.raises(ApplicationError) as reconcile_error:
        await worker_activities.reconcile_checkout(_reconcile_input())

    assert checkout_error.value.type == ProviderErrorCode.TIMEOUT.value
    assert checkout_error.value.non_retryable is True
    assert reconcile_error.value.type == ProviderErrorCode.TIMEOUT.value
    assert reconcile_error.value.non_retryable is (not retryable)
    assert checkout_error.value.__cause__ is None
    assert reconcile_error.value.__cause__ is None


@pytest.mark.asyncio
async def test_reconciliation_redacts_unexpected_exception_details() -> None:
    sensitive_value = "unexpected-sensitive-provider-detail"

    class ExplodingCoordinator:
        async def execute_isolated_checkout(
            self, request: IsolatedCheckoutActivityInput
        ) -> CheckoutActivityResult:
            del request
            return _checkout_result()

        async def reconcile_checkout(
            self, request: ReconcileActivityInput
        ) -> CheckoutActivityResult:
            del request
            raise RuntimeError(sensitive_value)

    worker_activities = activities.CheckoutActivities(ExplodingCoordinator())
    with pytest.raises(ApplicationError) as captured:
        await worker_activities.reconcile_checkout(_reconcile_input())

    assert captured.value.type == "RECONCILIATION_ACTIVITY_REDACTED_FAILURE"
    assert captured.value.non_retryable is True
    assert sensitive_value not in str(captured.value)
    assert sensitive_value not in repr(captured.value)
    assert captured.value.__context__ is None
    assert captured.value.__cause__ is None
