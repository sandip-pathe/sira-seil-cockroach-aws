"""Executable AWS worker processes for qualification dispatch and execution."""

from __future__ import annotations

import asyncio
import logging
import os
import socket
from typing import Annotated, Any, Literal, cast

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict
from sira_agents.bedrock_runtime import (
    BedrockGuardrail,
    TitanEmbeddingClient,
    create_bedrock_client,
)
from sqlalchemy.engine import make_url

from integrations.automated_reasoning import BedrockAutomatedReasoningReviewer
from integrations.aws_services import SqsFifoPublisher, create_aws_client
from persistence.database import Database, DatabaseSettings
from sira_worker.changefeed_consumer import ChangefeedHintConsumer, SqsHintClient
from sira_worker.outbox_dispatcher import dispatch_batch
from sira_worker.qualification import QualificationWorker
from sira_worker.queue_consumer import QualificationQueueConsumer, SqsConsumerClient

logger = logging.getLogger(__name__)
_QUALIFICATION_EVENTS = frozenset({"QUALIFICATION_MISSION_READY"})


class WorkerSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", populate_by_name=True)

    worker_mode: Literal["dispatcher", "qualification", "changefeed"] = Field(
        default="qualification", validation_alias="SIRA_WORKER_MODE"
    )
    worker_database_url: SecretStr = Field(validation_alias="SIRA_WORKER_DATABASE_URL")
    catalog_database_url: SecretStr = Field(
        default=SecretStr(""), validation_alias="SIRA_CATALOG_DATABASE_URL"
    )
    organization_ids: Annotated[tuple[str, ...], NoDecode] = Field(
        default=(), validation_alias="WORKER_ORGANIZATION_IDS"
    )
    aws_region: str = Field(default="us-east-1", validation_alias="AWS_REGION")
    aws_profile: str | None = Field(default=None, validation_alias="AWS_PROFILE")
    queue_url: str = Field(validation_alias="SIRA_SQS_QUEUE_URL")
    chat_model_id: str = Field(
        default="us.amazon.nova-2-lite-v1:0", validation_alias="BEDROCK_CHAT_MODEL_ID"
    )
    embedding_model_id: str = Field(
        default="amazon.titan-embed-text-v2:0",
        validation_alias="BEDROCK_EMBEDDING_MODEL_ID",
    )
    guardrail_id: str = Field(default="", validation_alias="BEDROCK_GUARDRAIL_ID")
    guardrail_version: str = Field(default="DRAFT", validation_alias="BEDROCK_GUARDRAIL_VERSION")
    log_level: str = Field(default="INFO", validation_alias="LOG_LEVEL")
    idle_delay_seconds: float = Field(default=2.0, ge=0.1, le=30)
    app_env: Literal["development", "test", "production"] = Field(
        default="development", validation_alias="APP_ENV"
    )

    @field_validator("organization_ids", mode="before")
    @classmethod
    def parse_organizations(cls, value: object) -> object:
        if isinstance(value, str):
            return tuple(item.strip() for item in value.split(",") if item.strip())
        return value

    @field_validator("aws_profile", mode="before")
    @classmethod
    def empty_profile_is_default_chain(cls, value: object) -> object:
        return None if value is None or str(value).strip() == "" else value

    def assert_safe_runtime(self) -> None:
        if self.app_env != "production":
            return
        urls = {"SIRA_WORKER_DATABASE_URL": self.worker_database_url.get_secret_value()}
        if self.worker_mode == "qualification":
            urls["SIRA_CATALOG_DATABASE_URL"] = self.catalog_database_url.get_secret_value()
        for name, value in urls.items():
            try:
                backend = make_url(value).get_backend_name()
            except Exception:
                backend = "invalid"
            if backend != "cockroachdb":
                raise ValueError(f"production requires a CockroachDB {name}")


def _database(url: SecretStr) -> Database:
    return Database(DatabaseSettings(database_url=url.get_secret_value()))


async def _run_dispatcher(settings: WorkerSettings) -> None:
    database = _database(settings.worker_database_url)
    client = create_aws_client("sqs", region=settings.aws_region, profile=settings.aws_profile)
    publisher = SqsFifoPublisher(client=cast(Any, client), queue_url=settings.queue_url)
    try:
        while True:
            published = 0
            organization_ids = tuple(
                sorted(set(settings.organization_ids) | set(await database.organization_ids()))
            )
            for organization_id in organization_ids:
                result = await dispatch_batch(
                    database,
                    publisher,
                    organization_id=organization_id,
                    event_types=_QUALIFICATION_EVENTS,
                )
                published += result.published
            if published == 0:
                await asyncio.sleep(settings.idle_delay_seconds)
    finally:
        await database.close()


async def _run_qualification_worker(settings: WorkerSettings) -> None:
    if not settings.catalog_database_url.get_secret_value():
        raise ValueError("qualification worker requires SIRA_CATALOG_DATABASE_URL")
    worker_database = _database(settings.worker_database_url)
    catalog_database = _database(settings.catalog_database_url)
    sqs_client = create_aws_client("sqs", region=settings.aws_region, profile=settings.aws_profile)
    bedrock_client = create_bedrock_client(region=settings.aws_region, profile=settings.aws_profile)
    guardrail = (
        BedrockGuardrail(settings.guardrail_id, settings.guardrail_version)
        if settings.guardrail_id.strip()
        else None
    )
    worker = QualificationWorker(
        worker_database=worker_database,
        catalog_database=catalog_database,
        embedding_client=TitanEmbeddingClient(
            client=bedrock_client,
            model_id=settings.embedding_model_id,
        ),
        bedrock_client=bedrock_client,
        model_id=settings.chat_model_id,
        lease_owner=f"{socket.gethostname()}:{os.getpid()}",
        guardrail=guardrail,
        reasoning_reviewer=(
            BedrockAutomatedReasoningReviewer(
                client=bedrock_client,
                guardrail_identifier=settings.guardrail_id,
                guardrail_version=settings.guardrail_version,
            )
            if guardrail is not None and settings.guardrail_version != "DRAFT"
            else None
        ),
    )
    consumer = QualificationQueueConsumer(
        client=cast(SqsConsumerClient, sqs_client),
        queue_url=settings.queue_url,
        database=worker_database,
        worker=worker,
    )
    try:
        while True:
            try:
                await consumer.poll_once()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Qualification message failed; SQS will redeliver it")
                await asyncio.sleep(settings.idle_delay_seconds)
    finally:
        await worker_database.close()
        await catalog_database.close()


async def _run_changefeed_worker(settings: WorkerSettings) -> None:
    database = _database(settings.worker_database_url)
    sqs_client = create_aws_client("sqs", region=settings.aws_region, profile=settings.aws_profile)
    consumer = ChangefeedHintConsumer(
        client=cast(SqsHintClient, sqs_client),
        queue_url=settings.queue_url,
        database=database,
        organization_ids=settings.organization_ids,
    )
    try:
        while True:
            try:
                await consumer.poll_once()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Changefeed hint failed; SQS will redeliver it")
                await asyncio.sleep(settings.idle_delay_seconds)
    finally:
        await database.close()


async def run() -> None:
    settings = WorkerSettings()
    settings.assert_safe_runtime()
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    logger.info("Starting SIRA worker mode=%s", settings.worker_mode)
    if settings.worker_mode == "dispatcher":
        await _run_dispatcher(settings)
    elif settings.worker_mode == "qualification":
        await _run_qualification_worker(settings)
    else:
        await _run_changefeed_worker(settings)


def main() -> None:
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        logger.info("Worker stopped")


if __name__ == "__main__":
    main()
