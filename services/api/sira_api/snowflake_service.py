"""FastAPI-side adapter for Snowflake's governed decision evidence plane."""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from domain import content_hash

from .config import ApiSettings


class SnowflakeDecisionNotFound(LookupError):
    """Raised when a decision is absent or outside the caller's organization."""


class SnowflakeDecisionService:
    def __init__(self, settings: ApiSettings) -> None:
        self.settings = settings

    @property
    def enabled(self) -> bool:
        return self.settings.snowflake_enabled

    def _connect(self) -> Any:
        import snowflake.connector

        kwargs: dict[str, Any] = {
            "account": self.settings.snowflake_account,
            "user": self.settings.snowflake_user,
            "role": self.settings.snowflake_role,
            "warehouse": self.settings.snowflake_warehouse,
            "database": self.settings.snowflake_database,
            "application": "SIRA_SEIL",
            "login_timeout": 30,
            "network_timeout": 30,
            "session_parameters": {"QUERY_TAG": "sira-seil-hackathon"},
        }
        password = self.settings.snowflake_password.get_secret_value().strip()
        private_key = self.settings.snowflake_private_key.get_secret_value().strip()
        private_key_path = self.settings.snowflake_private_key_path.strip()
        if private_key_path:
            private_key = Path(private_key_path).read_text(encoding="utf-8")
        if private_key:
            from cryptography.hazmat.primitives import serialization

            normalized = private_key.replace("\\n", "\n").encode("utf-8")
            key = serialization.load_pem_private_key(normalized, password=None)
            kwargs["private_key"] = key.private_bytes(
                encoding=serialization.Encoding.DER,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption(),
            )
        else:
            kwargs["password"] = password
        return snowflake.connector.connect(**kwargs)

    @staticmethod
    def _dict_rows(cursor: Any) -> list[dict[str, Any]]:
        columns = [str(item[0]).casefold() for item in cursor.description or ()]
        return [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]

    async def create_decision(
        self,
        *,
        organization_id: str,
        context_version: int,
        mission_id: str | None,
        actor_id: str,
        idempotency_key: str,
    ) -> dict[str, Any]:
        return await asyncio.to_thread(
            self._create_decision,
            organization_id=organization_id,
            context_version=context_version,
            mission_id=mission_id,
            actor_id=actor_id,
            idempotency_key=idempotency_key,
        )

    def _create_decision(
        self,
        *,
        organization_id: str,
        context_version: int,
        mission_id: str | None,
        actor_id: str,
        idempotency_key: str,
    ) -> dict[str, Any]:
        connection = self._connect()
        try:
            cursor = connection.cursor()
            cursor.execute(
                "SELECT request_id FROM SIRA_HACKATHON.DECISION.REQUESTS "
                "WHERE organization_id = %s AND idempotency_key = %s",
                (organization_id, idempotency_key),
            )
            prior = cursor.fetchone()
            request_id = str(prior[0]) if prior else f"sfreq_{uuid4().hex}"
            if prior is None:
                cursor.execute(
                    "INSERT INTO SIRA_HACKATHON.DECISION.REQUESTS "
                    "(request_id, organization_id, company_id, mission_id, context_version, "
                    "created_by, idempotency_key) "
                    "VALUES (%s, %s, 'comp_consultco', %s, %s, %s, %s)",
                    (
                        request_id,
                        organization_id,
                        mission_id,
                        context_version,
                        actor_id,
                        idempotency_key,
                    ),
                )
            cursor.execute(
                "CALL SIRA_HACKATHON.DECISION.RUN_SIRA_DECISION(%s)",
                (request_id,),
            )
            raw = cursor.fetchone()[0]
            result = json.loads(raw) if isinstance(raw, str) else dict(raw)
            connection.commit()
            return self._hydrate(cursor, result)
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _hydrate(self, cursor: Any, result: dict[str, Any]) -> dict[str, Any]:
        run_id = str(result["run_id"])
        cursor.execute(
            "SELECT citation_id, citation_type, fact_id, document_id, chunk_id, "
            "page_number, exact_excerpt, source_hash "
            "FROM SIRA_HACKATHON.DECISION.CITATIONS WHERE run_id = %s "
            "ORDER BY citation_type, citation_id",
            (run_id,),
        )
        result["citations"] = self._dict_rows(cursor)
        return result

    async def get_decision(
        self, request_id: str, *, organization_id: str
    ) -> dict[str, Any] | None:
        return await asyncio.to_thread(
            self._get_decision, request_id, organization_id=organization_id
        )

    def _get_decision(
        self, request_id: str, *, organization_id: str
    ) -> dict[str, Any] | None:
        connection = self._connect()
        try:
            cursor = connection.cursor()
            cursor.execute(
                "SELECT run.output FROM SIRA_HACKATHON.DECISION.RUNS run "
                "JOIN SIRA_HACKATHON.DECISION.REQUESTS req "
                "ON req.request_id = run.request_id "
                "WHERE run.request_id = %s AND req.organization_id = %s "
                "ORDER BY run.created_at DESC LIMIT 1",
                (request_id, organization_id),
            )
            row = cursor.fetchone()
            if row is None:
                return None
            raw = row[0]
            result = json.loads(raw) if isinstance(raw, str) else dict(raw)
            return self._hydrate(cursor, result)
        finally:
            connection.close()

    async def approve(
        self,
        *,
        organization_id: str,
        decision_hash: str,
        actor_id: str,
        actor_role: str,
    ) -> dict[str, Any]:
        return await asyncio.to_thread(
            self._approve,
            organization_id=organization_id,
            decision_hash=decision_hash,
            actor_id=actor_id,
            actor_role=actor_role,
        )

    def _approve(
        self,
        *,
        organization_id: str,
        decision_hash: str,
        actor_id: str,
        actor_role: str,
    ) -> dict[str, Any]:
        connection = self._connect()
        try:
            cursor = connection.cursor()
            cursor.execute(
                "SELECT run.request_id, run.run_id FROM SIRA_HACKATHON.DECISION.RUNS run "
                "JOIN SIRA_HACKATHON.DECISION.REQUESTS req "
                "ON req.request_id = run.request_id "
                "WHERE run.decision_hash = %s AND req.organization_id = %s "
                "ORDER BY run.created_at DESC LIMIT 1",
                (decision_hash, organization_id),
            )
            decision = cursor.fetchone()
            if decision is None:
                raise SnowflakeDecisionNotFound
            request_id, run_id = map(str, decision)
            cursor.execute(
                "SELECT event_hash FROM SIRA_HACKATHON.DECISION.APPROVAL_LEDGER "
                "WHERE organization_id = %s ORDER BY occurred_at DESC LIMIT 1",
                (organization_id,),
            )
            prior = cursor.fetchone()
            previous_hash = str(prior[0]) if prior else None
            occurred_at = datetime.now(UTC).isoformat().replace("+00:00", "Z")
            event_id = f"approval_{uuid4().hex}"
            payload = {
                "event_id": event_id,
                "organization_id": organization_id,
                "request_id": request_id,
                "run_id": run_id,
                "decision_hash": decision_hash,
                "actor_id": actor_id,
                "actor_role": actor_role,
                "action": "APPROVED",
                "occurred_at": occurred_at,
                "previous_event_hash": previous_hash,
            }
            event_hash = content_hash(payload)
            cursor.execute(
                "INSERT INTO SIRA_HACKATHON.DECISION.APPROVAL_LEDGER "
                "(event_id, organization_id, request_id, run_id, decision_hash, actor_id, "
                "actor_role, action, occurred_at, previous_event_hash, event_hash) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, 'APPROVED', %s, %s, %s)",
                (
                    event_id,
                    organization_id,
                    request_id,
                    run_id,
                    decision_hash,
                    actor_id,
                    actor_role,
                    occurred_at,
                    previous_hash,
                    event_hash,
                ),
            )
            connection.commit()
            return {**payload, "event_hash": event_hash}
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()


__all__ = ["SnowflakeDecisionNotFound", "SnowflakeDecisionService"]
