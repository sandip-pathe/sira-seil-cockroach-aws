-- 03_evidence_pipeline.sql — Seller document evidence stage, tables, and parsing
-- Run as SIRA_SF_BUILD_ROLE after 02_governed_tables.sql

USE ROLE SIRA_SF_BUILD_ROLE;
USE WAREHOUSE SIRA_HACK_XS_WH;
USE SCHEMA SIRA_HACKATHON.EVIDENCE;

-- ============================================================
-- INTERNAL STAGE for seller documents
-- ============================================================
CREATE STAGE IF NOT EXISTS SELLER_DOCS_STAGE
  ENCRYPTION = (TYPE = 'SNOWFLAKE_SSE')
  DIRECTORY = (ENABLE = TRUE)
  COMMENT = 'SSE stage required by AI_PARSE_DOCUMENT for synthetic seller documents.';

-- ============================================================
-- DOCUMENTS — metadata for each uploaded seller document
-- ============================================================
CREATE TABLE IF NOT EXISTS DOCUMENTS (
    document_id  VARCHAR(64)   NOT NULL PRIMARY KEY,
    seller_id    VARCHAR(64)   NOT NULL,
    product_id   VARCHAR(64)   NOT NULL,
    stage_path   VARCHAR(512)  NOT NULL,
    filename     VARCHAR(256)  NOT NULL,
    sha256       VARCHAR(64)   NOT NULL,
    version      INTEGER       NOT NULL DEFAULT 1,
    parsed_at    TIMESTAMP_NTZ
);

CREATE TABLE IF NOT EXISTS DOCUMENT_PARSE_RESULTS (
    parse_result_id VARCHAR(64)   NOT NULL PRIMARY KEY,
    document_id     VARCHAR(64)   NOT NULL REFERENCES DOCUMENTS(document_id),
    parser          VARCHAR(64)   NOT NULL,
    parser_mode     VARCHAR(32)   NOT NULL,
    raw_result      VARIANT       NOT NULL,
    parsed_at       TIMESTAMP_NTZ NOT NULL DEFAULT CURRENT_TIMESTAMP()
);

-- ============================================================
-- DOCUMENT_CHUNKS — page-aware parsed text chunks
-- ============================================================
CREATE TABLE IF NOT EXISTS DOCUMENT_CHUNKS (
    chunk_id      VARCHAR(64)   NOT NULL PRIMARY KEY,
    document_id   VARCHAR(64)   NOT NULL REFERENCES DOCUMENTS(document_id),
    page_number   INTEGER       NOT NULL,
    section_path  VARCHAR(256),
    chunk_text    VARCHAR(16000) NOT NULL,
    chunk_hash    VARCHAR(64)   NOT NULL,
    parse_result_id VARCHAR(64) REFERENCES DOCUMENT_PARSE_RESULTS(parse_result_id)
);

-- ============================================================
-- SELLER_CLAIM_BINDINGS — trust boundary typed limitations
-- ============================================================
CREATE TABLE IF NOT EXISTS SELLER_CLAIM_BINDINGS (
    claim_id        VARCHAR(64)   NOT NULL PRIMARY KEY,
    product_id      VARCHAR(64)   NOT NULL,
    claim_key       VARCHAR(128)  NOT NULL,
    operator        VARCHAR(32)   NOT NULL,
    typed_value     VARIANT       NOT NULL,
    chunk_id        VARCHAR(64)   NOT NULL REFERENCES DOCUMENT_CHUNKS(chunk_id),
    binding_status  VARCHAR(32)   NOT NULL DEFAULT 'REVIEWED',
    reviewer        VARCHAR(128)  NOT NULL,
    binding_hash    VARCHAR(64)   NOT NULL
);

-- ============================================================
-- V_SEARCHABLE_SELLER_CHUNKS — projection for Cortex Search
-- ============================================================
CREATE OR REPLACE VIEW V_SEARCHABLE_SELLER_CHUNKS AS
SELECT
    dc.chunk_id,
    dc.document_id,
    d.seller_id,
    d.product_id,
    dc.page_number,
    dc.section_path,
    dc.chunk_text,
    dc.chunk_hash
FROM DOCUMENT_CHUNKS dc
JOIN DOCUMENTS d ON dc.document_id = d.document_id;
