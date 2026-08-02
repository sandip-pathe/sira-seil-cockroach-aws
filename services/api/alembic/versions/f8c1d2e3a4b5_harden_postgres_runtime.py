"""harden PostgreSQL runtime invariants

Revision ID: f8c1d2e3a4b5
Revises: e7b4c2d8f105
Create Date: 2026-08-02 20:15:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "f8c1d2e3a4b5"
down_revision: str | None = "e7b4c2d8f105"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_JSONB_COLUMNS = (
    ("decision_simulations", "input_payload", False),
    ("decision_simulations", "result_payload", False),
    ("decision_source_snapshots", "payload", False),
    ("engagements", "seller_visible_requirement_brief", False),
    ("outcome_checkpoints", "preference_proposal", True),
)


def _install_engagement_update_guard() -> None:
    op.execute(
        sa.text(
            """
            CREATE OR REPLACE FUNCTION enforce_engagement_party_update()
            RETURNS trigger
            LANGUAGE plpgsql
            AS $$
            DECLARE
                tenant_id text := NULLIF(current_setting('app.organization_id', true), '');
            BEGIN
                IF TG_OP = 'INSERT' THEN
                    IF tenant_id IS DISTINCT FROM NEW.organization_id THEN
                        RAISE EXCEPTION 'only the buyer tenant may create an engagement'
                            USING ERRCODE = '42501';
                    END IF;
                    IF NEW.buyer_consented
                       OR NEW.seller_consented
                       OR NEW.buyer_consent_actor_id IS NOT NULL
                       OR NEW.seller_consent_actor_id IS NOT NULL
                       OR NEW.contact_exchange IS NOT NULL
                       OR NEW.status IN (
                           'BUYER_CONSENT_PENDING',
                           'SELLER_CONSENT_PENDING',
                           'INTRODUCTION_READY'
                       ) THEN
                        RAISE EXCEPTION 'new engagements must start without consent or contacts'
                            USING ERRCODE = '42501';
                    END IF;
                    RETURN NEW;
                END IF;

                IF ROW(
                    NEW.id,
                    NEW.organization_id,
                    NEW.purchase_request_id,
                    NEW.requirement_brief_id,
                    NEW.requirement_brief_version,
                    NEW.requirement_brief_hash,
                    NEW.candidate_id,
                    NEW.seller_organization_id,
                    NEW.expected_buyer_actor_id,
                    NEW.expected_seller_actor_id,
                    NEW.grant_scope,
                    NEW.grant_hash,
                    NEW.seller_visible_requirement_brief,
                    NEW.granted_at,
                    NEW.created_at
                ) IS DISTINCT FROM ROW(
                    OLD.id,
                    OLD.organization_id,
                    OLD.purchase_request_id,
                    OLD.requirement_brief_id,
                    OLD.requirement_brief_version,
                    OLD.requirement_brief_hash,
                    OLD.candidate_id,
                    OLD.seller_organization_id,
                    OLD.expected_buyer_actor_id,
                    OLD.expected_seller_actor_id,
                    OLD.grant_scope,
                    OLD.grant_hash,
                    OLD.seller_visible_requirement_brief,
                    OLD.granted_at,
                    OLD.created_at
                ) THEN
                    RAISE EXCEPTION 'engagement binding fields are immutable'
                        USING ERRCODE = '42501';
                END IF;

                IF tenant_id = OLD.seller_organization_id
                   AND tenant_id <> OLD.organization_id THEN
                    IF NEW.buyer_consented IS DISTINCT FROM OLD.buyer_consented
                       OR NEW.buyer_consent_actor_id
                          IS DISTINCT FROM OLD.buyer_consent_actor_id
                       OR NEW.grant_status IS DISTINCT FROM OLD.grant_status THEN
                        RAISE EXCEPTION 'seller cannot change buyer-owned engagement state'
                            USING ERRCODE = '42501';
                    END IF;
                ELSIF tenant_id = OLD.organization_id THEN
                    IF NEW.seller_consented IS DISTINCT FROM OLD.seller_consented
                       OR NEW.seller_consent_actor_id
                          IS DISTINCT FROM OLD.seller_consent_actor_id THEN
                        RAISE EXCEPTION 'buyer cannot change seller-owned engagement state'
                            USING ERRCODE = '42501';
                    END IF;
                ELSIF tenant_id IS NOT NULL THEN
                    RAISE EXCEPTION 'tenant is not an engagement party'
                        USING ERRCODE = '42501';
                END IF;

                IF NEW.buyer_consented
                   IS DISTINCT FROM (NEW.buyer_consent_actor_id IS NOT NULL)
                   OR (
                       NEW.buyer_consented
                       AND NEW.buyer_consent_actor_id
                           IS DISTINCT FROM NEW.expected_buyer_actor_id
                   ) THEN
                    RAISE EXCEPTION 'buyer consent provenance is invalid'
                        USING ERRCODE = '42501';
                END IF;
                IF NEW.seller_consented
                   IS DISTINCT FROM (NEW.seller_consent_actor_id IS NOT NULL)
                   OR (
                       NEW.seller_consented
                       AND NEW.seller_consent_actor_id
                           IS DISTINCT FROM NEW.expected_seller_actor_id
                   ) THEN
                    RAISE EXCEPTION 'seller consent provenance is invalid'
                        USING ERRCODE = '42501';
                END IF;

                IF NEW.status = 'DECLINED' THEN
                    IF NEW.contact_exchange IS NOT NULL THEN
                        RAISE EXCEPTION 'declined engagements cannot expose contacts'
                            USING ERRCODE = '23514';
                    END IF;
                ELSIF NEW.buyer_consented AND NEW.seller_consented THEN
                    IF NEW.status <> 'INTRODUCTION_READY'
                       OR NEW.contact_exchange IS DISTINCT FROM jsonb_build_object(
                           'buyer', NEW.expected_buyer_actor_id,
                           'seller', NEW.expected_seller_actor_id
                       ) THEN
                        RAISE EXCEPTION 'mutual consent must produce canonical contacts'
                            USING ERRCODE = '23514';
                    END IF;
                ELSIF NEW.buyer_consented THEN
                    IF NEW.status <> 'SELLER_CONSENT_PENDING'
                       OR NEW.contact_exchange IS NOT NULL THEN
                        RAISE EXCEPTION 'seller consent remains pending'
                            USING ERRCODE = '23514';
                    END IF;
                ELSIF NEW.seller_consented THEN
                    IF NEW.status <> 'BUYER_CONSENT_PENDING'
                       OR NEW.contact_exchange IS NOT NULL THEN
                        RAISE EXCEPTION 'buyer consent remains pending'
                            USING ERRCODE = '23514';
                    END IF;
                ELSIF NEW.status IN (
                    'BUYER_CONSENT_PENDING',
                    'SELLER_CONSENT_PENDING',
                    'INTRODUCTION_READY'
                ) OR NEW.contact_exchange IS NOT NULL THEN
                    RAISE EXCEPTION 'consent state cannot expose contacts'
                        USING ERRCODE = '23514';
                END IF;

                RETURN NEW;
            END;
            $$
            """
        )
    )
    op.execute(sa.text("DROP TRIGGER IF EXISTS engagement_party_update_guard ON engagements"))
    op.execute(
        sa.text(
            """
            CREATE TRIGGER engagement_party_update_guard
            BEFORE INSERT OR UPDATE ON engagements
            FOR EACH ROW
            EXECUTE FUNCTION enforce_engagement_party_update()
            """
        )
    )


def upgrade() -> None:
    connection = op.get_bind()
    if connection.dialect.name != "postgresql":
        return

    for table_name, column_name, nullable in _JSONB_COLUMNS:
        op.alter_column(
            table_name,
            column_name,
            existing_type=sa.JSON(),
            type_=postgresql.JSONB(astext_type=sa.Text()),
            existing_nullable=nullable,
            postgresql_using=f"{column_name}::jsonb",
        )
    op.alter_column(
        "outbox_events",
        "event_key",
        existing_type=sa.String(length=128),
        type_=sa.String(length=255),
        existing_nullable=False,
    )
    _install_engagement_update_guard()


def downgrade() -> None:
    connection = op.get_bind()
    if connection.dialect.name != "postgresql":
        return

    op.execute(sa.text("DROP TRIGGER IF EXISTS engagement_party_update_guard ON engagements"))
    op.execute(sa.text("DROP FUNCTION IF EXISTS enforce_engagement_party_update()"))
    op.alter_column(
        "outbox_events",
        "event_key",
        existing_type=sa.String(length=255),
        type_=sa.String(length=128),
        existing_nullable=False,
    )
    for table_name, column_name, nullable in reversed(_JSONB_COLUMNS):
        op.alter_column(
            table_name,
            column_name,
            existing_type=postgresql.JSONB(astext_type=sa.Text()),
            type_=sa.JSON(),
            existing_nullable=nullable,
            postgresql_using=f"{column_name}::json",
        )
