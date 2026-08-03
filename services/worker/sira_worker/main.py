"""Runnable Temporal worker composition with fail-closed provider setup."""

from __future__ import annotations

import asyncio
import sys
from urllib.parse import urlsplit

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url

from integrations.merchants.rest import ControlledMerchantRestAdapter
from integrations.prava.rest import DEFAULT_PRAVA_CHECKOUT_HOSTS, PravaHostedRestAdapter
from persistence.database import Database, DatabaseSettings
from sira_worker.coordinator import PersistentCheckoutCoordinator
from sira_worker.outbox import (
    CHECKOUT_EVENT_TYPE,
    PRAVA_MCP_CHECKOUT_EVENT_TYPE,
    REVERSAL_EVENT_TYPE,
    CheckoutOutboxDispatcher,
)
from sira_worker.prava_mcp_coordinator import PersistentPravaMcpCoordinator
from sira_worker.temporal import build_worker, connect_temporal


class WorkerSetupError(RuntimeError):
    def __init__(self, missing: list[str]) -> None:
        self.missing = sorted(set(missing))
        super().__init__("worker provider configuration is incomplete")


def _https_host(value: str, setting: str) -> str:
    parsed = urlsplit(value)
    if (
        parsed.scheme.lower() != "https"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.fragment
    ):
        raise WorkerSetupError([f"{setting}_VALID_HTTPS_URL"])
    return parsed.hostname.lower()


class WorkerSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", populate_by_name=True)

    database_url: str = Field(default="", validation_alias="DATABASE_URL")
    temporal_address: str = Field(default="", validation_alias="TEMPORAL_ADDRESS")
    temporal_namespace: str = Field(default="default", validation_alias="TEMPORAL_NAMESPACE")
    temporal_api_key: SecretStr = Field(
        default=SecretStr(""), validation_alias="TEMPORAL_API_KEY"
    )
    temporal_tls: bool = Field(default=False, validation_alias="TEMPORAL_TLS")
    temporal_task_queue: str = Field(
        default="sira-checkout", validation_alias="TEMPORAL_TASK_QUEUE"
    )
    worker_organization_ids: str = Field(default="", validation_alias="WORKER_ORGANIZATION_IDS")
    prava_base_url: str = Field(default="", validation_alias="PRAVA_BASE_URL")
    prava_secret_key: SecretStr = Field(default=SecretStr(""), validation_alias="PRAVA_SECRET_KEY")
    prava_merchant_url: str = Field(default="", validation_alias="PRAVA_MERCHANT_URL")
    prava_callback_url: str = Field(default="", validation_alias="PRAVA_CALLBACK_URL")
    prava_hosted_checkout_hosts: str = Field(
        default="", validation_alias="PRAVA_HOSTED_CHECKOUT_HOSTS"
    )
    merchant_base_url: str = Field(default="", validation_alias="CONTROLLED_MERCHANT_BASE_URL")
    merchant_api_key: SecretStr = Field(
        default=SecretStr(""), validation_alias="CONTROLLED_MERCHANT_API_KEY"
    )
    merchant_id: str = Field(default="", validation_alias="CONTROLLED_MERCHANT_ID")
    prava_execution_mode: str = Field(default="legacy", validation_alias="PRAVA_EXECUTION_MODE")
    connector_encryption_key: SecretStr = Field(
        default=SecretStr(""), validation_alias="CONNECTOR_ENCRYPTION_KEY"
    )

    def require_configuration(self) -> None:
        values = {
            "DATABASE_URL": self.database_url,
            "TEMPORAL_ADDRESS": self.temporal_address,
            "TEMPORAL_NAMESPACE": self.temporal_namespace,
            "TEMPORAL_TASK_QUEUE": self.temporal_task_queue,
            "WORKER_ORGANIZATION_IDS": self.worker_organization_ids,
        }
        if self.prava_execution_mode == "mcp":
            values["CONNECTOR_ENCRYPTION_KEY"] = (
                self.connector_encryption_key.get_secret_value()
            )
        elif self.prava_execution_mode == "legacy":
            values.update(
                {
                    "PRAVA_BASE_URL": self.prava_base_url,
                    "PRAVA_SECRET_KEY": self.prava_secret_key.get_secret_value(),
                    "PRAVA_MERCHANT_URL": self.prava_merchant_url,
                    "PRAVA_CALLBACK_URL": self.prava_callback_url,
                    "CONTROLLED_MERCHANT_BASE_URL": self.merchant_base_url,
                    "CONTROLLED_MERCHANT_API_KEY": self.merchant_api_key.get_secret_value(),
                    "CONTROLLED_MERCHANT_ID": self.merchant_id,
                }
            )
        else:
            values["PRAVA_EXECUTION_MODE_MCP_OR_LEGACY"] = ""
        missing = [name for name, value in values.items() if not value.strip()]
        try:
            database_backend = make_url(self.database_url).get_backend_name()
        except Exception:
            database_backend = "invalid"
        if self.database_url.strip() and database_backend != "postgresql":
            missing.append("DATABASE_URL_POSTGRESQL")
        if self.temporal_tls and not self.temporal_api_key.get_secret_value().strip():
            missing.append("TEMPORAL_API_KEY")
        if missing:
            raise WorkerSetupError(missing)

    def organization_ids(self) -> tuple[str, ...]:
        values = tuple(
            value.strip() for value in self.worker_organization_ids.split(",") if value.strip()
        )
        if not values or len(set(values)) != len(values):
            raise WorkerSetupError(["WORKER_ORGANIZATION_IDS_UNIQUE"])
        return values


async def run_worker() -> None:
    settings = WorkerSettings()
    settings.require_configuration()
    database = Database(DatabaseSettings(database_url=settings.database_url))
    if database.engine.dialect.name != "postgresql":
        await database.close()
        raise WorkerSetupError(["DATABASE_ENGINE_POSTGRESQL"])
    prava = None
    merchant = None
    try:
        temporal = await connect_temporal(
            settings.temporal_address,
            namespace=settings.temporal_namespace,
            api_key=settings.temporal_api_key.get_secret_value(),
            tls=settings.temporal_tls,
        )
        if settings.prava_execution_mode == "legacy":
            api_host = _https_host(settings.prava_base_url, "PRAVA_BASE_URL")
            merchant_host = _https_host(settings.prava_merchant_url, "PRAVA_MERCHANT_URL")
            callback_host = _https_host(settings.prava_callback_url, "PRAVA_CALLBACK_URL")
            controlled_host = _https_host(
                settings.merchant_base_url, "CONTROLLED_MERCHANT_BASE_URL"
            )
            configured_checkout_hosts = {
                item.strip().lower()
                for item in settings.prava_hosted_checkout_hosts.split(",")
                if item.strip()
            }
            prava = PravaHostedRestAdapter(
                secret_key=settings.prava_secret_key.get_secret_value(),
                base_url=settings.prava_base_url,
                api_hosts=frozenset({api_host}),
                merchant_hosts=frozenset({merchant_host}),
                callback_hosts=frozenset({callback_host}),
                hosted_checkout_hosts=frozenset(
                    configured_checkout_hosts.union(DEFAULT_PRAVA_CHECKOUT_HOSTS)
                ),
            )
            merchant = ControlledMerchantRestAdapter(
                base_url=settings.merchant_base_url,
                api_key=settings.merchant_api_key.get_secret_value(),
                allowed_hosts=frozenset({controlled_host}),
            )
            coordinator = PersistentCheckoutCoordinator(
                database=database,
                prava=prava,
                merchant=merchant,
                merchant_adapter_id=settings.merchant_id,
            )
        else:
            coordinator = None
        prava_mcp = (
            PersistentPravaMcpCoordinator(
                database=database,
                root_secret=settings.connector_encryption_key.get_secret_value(),
            )
            if settings.prava_execution_mode == "mcp"
            else None
        )
        worker = build_worker(
            client=temporal,
            task_queue=settings.temporal_task_queue,
            coordinator=coordinator,
            prava_coordinator=prava_mcp,
        )
        dispatcher = CheckoutOutboxDispatcher(
            database=database,
            temporal=temporal,
            task_queue=settings.temporal_task_queue,
            merchant_adapter_id=settings.merchant_id or "legacy-disabled",
            organization_ids=settings.organization_ids(),
            event_types=(
                (CHECKOUT_EVENT_TYPE, REVERSAL_EVENT_TYPE)
                if settings.prava_execution_mode == "legacy"
                else (PRAVA_MCP_CHECKOUT_EVENT_TYPE,)
            ),
        )
        runtime_tasks = [
            asyncio.create_task(worker.run()),
            asyncio.create_task(dispatcher.run()),
        ]
        try:
            await asyncio.gather(*runtime_tasks)
        finally:
            for task in runtime_tasks:
                task.cancel()
            await asyncio.gather(*runtime_tasks, return_exceptions=True)
    finally:
        if prava is not None:
            await prava.aclose()
        if merchant is not None:
            await merchant.aclose()
        await database.close()


def main() -> int:
    try:
        asyncio.run(run_worker())
    except WorkerSetupError as error:
        sys.stderr.write("Worker setup blocked; configure: " + ", ".join(error.missing) + "\n")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
