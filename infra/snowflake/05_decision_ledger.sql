-- 05_decision_ledger.sql — Decision execution, citations, approval, and audit
-- Run as SIRA_SF_BUILD_ROLE after 03_evidence_pipeline.sql

USE ROLE SIRA_SF_BUILD_ROLE;
USE WAREHOUSE SIRA_HACK_XS_WH;
USE SCHEMA SIRA_HACKATHON.DECISION;

-- ============================================================
-- REQUESTS — decision request initiation
-- ============================================================
CREATE TABLE IF NOT EXISTS REQUESTS (
    request_id       VARCHAR(64)   NOT NULL PRIMARY KEY,
    organization_id  VARCHAR(128)  NOT NULL DEFAULT 'org_hackathon_demo',
    company_id       VARCHAR(64)   NOT NULL,
    mission_id       VARCHAR(64),
    context_version  INTEGER       NOT NULL,
    created_by       VARCHAR(128)  NOT NULL,
    created_at       TIMESTAMP_NTZ NOT NULL DEFAULT CURRENT_TIMESTAMP(),
    idempotency_key  VARCHAR(128)  NOT NULL,
    UNIQUE (organization_id, idempotency_key)
);

-- Safe forward migration for accounts bootstrapped before tenant scoping was added.
ALTER TABLE REQUESTS ADD COLUMN IF NOT EXISTS organization_id VARCHAR(128)
    DEFAULT 'org_hackathon_demo';

-- ============================================================
-- INPUT_SNAPSHOTS — frozen source bundle at decision time
-- ============================================================
CREATE TABLE IF NOT EXISTS INPUT_SNAPSHOTS (
    snapshot_id    VARCHAR(64)   NOT NULL PRIMARY KEY,
    request_id     VARCHAR(64)   NOT NULL REFERENCES REQUESTS(request_id),
    source_bundle  VARIANT       NOT NULL,
    fact_ids       ARRAY         NOT NULL,
    claim_ids      ARRAY         NOT NULL,
    chunk_ids      ARRAY         NOT NULL,
    input_hash     VARCHAR(72)   NOT NULL,
    created_at     TIMESTAMP_NTZ NOT NULL DEFAULT CURRENT_TIMESTAMP()
);

-- ============================================================
-- RUNS — evaluator execution results
-- ============================================================
CREATE TABLE IF NOT EXISTS RUNS (
    run_id              VARCHAR(64)   NOT NULL PRIMARY KEY,
    request_id          VARCHAR(64)   NOT NULL REFERENCES REQUESTS(request_id),
    snapshot_id         VARCHAR(64)   NOT NULL REFERENCES INPUT_SNAPSHOTS(snapshot_id),
    evaluator_version   VARCHAR(32)   NOT NULL,
    git_sha             VARCHAR(40),
    input_hash          VARCHAR(72)   NOT NULL,
    decision_hash       VARCHAR(72)   NOT NULL,
    selected_product_id VARCHAR(64),
    status              VARCHAR(32)   NOT NULL,
    reason_codes        ARRAY         NOT NULL,
    counterfactual      VARIANT,
    output              VARIANT       NOT NULL,
    query_id            VARCHAR(64),
    created_at          TIMESTAMP_NTZ NOT NULL DEFAULT CURRENT_TIMESTAMP()
);

-- ============================================================
-- CITATIONS — links from a run to evidence sources
-- ============================================================
CREATE TABLE IF NOT EXISTS CITATIONS (
    citation_id    VARCHAR(64)   NOT NULL PRIMARY KEY,
    run_id         VARCHAR(64)   NOT NULL REFERENCES RUNS(run_id),
    citation_type  VARCHAR(32)   NOT NULL,
    fact_id        VARCHAR(64),
    document_id    VARCHAR(64),
    chunk_id       VARCHAR(64),
    page_number    INTEGER,
    exact_excerpt  VARCHAR(4000),
    source_hash    VARCHAR(72)   NOT NULL
);

-- ============================================================
-- APPROVAL_LEDGER — append-only, hash-chained approval events
-- No UPDATE or DELETE granted to app role.
-- ============================================================
CREATE TABLE IF NOT EXISTS APPROVAL_LEDGER (
    event_id             VARCHAR(64)   NOT NULL PRIMARY KEY,
    organization_id      VARCHAR(128)  NOT NULL DEFAULT 'org_hackathon_demo',
    request_id           VARCHAR(64),
    run_id               VARCHAR(64),
    decision_hash        VARCHAR(72)   NOT NULL,
    actor_id             VARCHAR(128)  NOT NULL,
    actor_role           VARCHAR(64)   NOT NULL,
    action               VARCHAR(32)   NOT NULL,
    occurred_at          TIMESTAMP_NTZ NOT NULL DEFAULT CURRENT_TIMESTAMP(),
    previous_event_hash  VARCHAR(72),
    event_hash           VARCHAR(72)   NOT NULL
);

-- Safe forward migration for accounts bootstrapped before scoped approvals.
ALTER TABLE APPROVAL_LEDGER ADD COLUMN IF NOT EXISTS organization_id VARCHAR(128)
    DEFAULT 'org_hackathon_demo';
ALTER TABLE APPROVAL_LEDGER ADD COLUMN IF NOT EXISTS request_id VARCHAR(64);
ALTER TABLE APPROVAL_LEDGER ADD COLUMN IF NOT EXISTS run_id VARCHAR(64);

-- ============================================================
-- V_AUDIT_TRAIL — read projection for audit queries
-- ============================================================
CREATE OR REPLACE VIEW V_AUDIT_TRAIL AS
SELECT
    req.request_id,
    req.organization_id,
    req.company_id,
    req.context_version,
    req.created_at     AS request_time,
    snap.snapshot_id,
    snap.input_hash,
    snap.fact_ids,
    snap.claim_ids,
    run.run_id,
    run.evaluator_version,
    run.decision_hash,
    run.selected_product_id,
    run.status          AS decision_status,
    run.reason_codes,
    run.counterfactual,
    run.query_id,
    run.created_at      AS decision_time,
    cit.citation_id,
    cit.citation_type,
    cit.fact_id         AS cited_fact_id,
    cit.document_id     AS cited_document_id,
    cit.chunk_id        AS cited_chunk_id,
    cit.page_number     AS cited_page,
    cit.exact_excerpt,
    appr.event_id       AS approval_event_id,
    appr.actor_id       AS approver,
    appr.action         AS approval_action,
    appr.event_hash     AS approval_hash,
    appr.occurred_at    AS approval_time
FROM REQUESTS req
LEFT JOIN INPUT_SNAPSHOTS snap ON req.request_id = snap.request_id
LEFT JOIN RUNS run ON snap.snapshot_id = run.snapshot_id
LEFT JOIN CITATIONS cit ON run.run_id = cit.run_id
LEFT JOIN APPROVAL_LEDGER appr
  ON run.run_id = appr.run_id
 AND req.request_id = appr.request_id
 AND req.organization_id = appr.organization_id;
