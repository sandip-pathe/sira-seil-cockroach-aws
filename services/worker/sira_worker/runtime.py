"""Run durable qualification work in a regular Python worker process."""

from __future__ import annotations

import asyncio
import logging
import os
import socket
from datetime import UTC, datetime

from openai import AsyncOpenAI
from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from sira_agents.openai_runtime import OpenAIEmbeddingClient

from persistence.database import Database, DatabaseSettings
from sira_worker.outbox_events import load_unpublished, mark_published
from sira_worker.qualification import QualificationWorker
from sira_worker.queue_consumer import QualificationEventProcessor

logger = logging.getLogger(__name__)


class WorkerSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", populate_by_name=True)

    worker_database_url: SecretStr = Field(validation_alias="SIRA_WORKER_DATABASE_URL")
    catalog_database_url: SecretStr = Field(validation_alias="SIRA_CATALOG_DATABASE_URL")
    openai_api_key: SecretStr = Field(validation_alias="OPENAI_API_KEY")
    chat_model: str = Field(default="gpt-4.1-mini", validation_alias="OPENAI_CHAT_MODEL")
    embedding_model: str = Field(
        default="text-embedding-3-small", validation_alias="OPENAI_EMBEDDING_MODEL"
    )
    log_level: str = Field(default="INFO", validation_alias="LOG_LEVEL")
    idle_delay_seconds: float = Field(
        default=2.0, ge=0.1, le=30, validation_alias="SIRA_WORKER_IDLE_DELAY_SECONDS"
    )


def _database(url: SecretStr) -> Database:
    return Database(DatabaseSettings(database_url=url.get_secret_value()))


async def run() -> None:
    settings = WorkerSettings()
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    worker_database = _database(settings.worker_database_url)
    catalog_database = _database(settings.catalog_database_url)
    openai_client = AsyncOpenAI(api_key=settings.openai_api_key.get_secret_value(), timeout=90)
    worker = QualificationWorker(
        worker_database=worker_database,
        catalog_database=catalog_database,
        embedding_client=OpenAIEmbeddingClient(
            client=openai_client,
            model_id=settings.embedding_model,
        ),
        openai_client=openai_client,
        model_id=settings.chat_model,
        lease_owner=f"{socket.gethostname()}:{os.getpid()}",
    )
    # The same validator and CockroachDB receipt table protect retries. The Python
    # worker reads pending events directly from the durable outbox.
    processor = QualificationEventProcessor(
        database=worker_database,
        worker=worker,
    )
    event_types = frozenset({"QUALIFICATION_MISSION_READY"})
    try:
        logger.info("Starting Python qualification worker")
        while True:
            processed = 0
            try:
                for organization_id in await worker_database.organization_ids():
                    envelopes = await load_unpublished(
                        worker_database,
                        organization_id=organization_id,
                        event_types=event_types,
                    )
                    for envelope in envelopes:
                        body = envelope.body().decode("utf-8")
                        await processor.process_body(body)
                        await mark_published(
                            worker_database,
                            envelope=envelope,
                            published_at=datetime.now(UTC),
                        )
                        processed += 1
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Qualification event failed; it remains pending in the outbox")
                await asyncio.sleep(settings.idle_delay_seconds)
                continue
            if processed == 0:
                await asyncio.sleep(settings.idle_delay_seconds)
    finally:
        await openai_client.close()
        await worker_database.close()
        await catalog_database.close()


def main() -> None:
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        logger.info("Worker stopped")


if __name__ == "__main__":
    main()
