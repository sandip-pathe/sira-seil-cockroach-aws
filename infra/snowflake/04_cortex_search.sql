-- 04_cortex_search.sql — Cortex Search service for seller evidence retrieval
-- Run as SIRA_SF_BUILD_ROLE after 03_evidence_pipeline.sql and data is loaded

USE ROLE SIRA_SF_BUILD_ROLE;
USE WAREHOUSE SIRA_HACK_XS_WH;
USE SCHEMA SIRA_HACKATHON.EVIDENCE;

-- ============================================================
-- CORTEX SEARCH SERVICE — indexes seller chunks only
-- Private buyer facts NEVER enter this index.
-- ============================================================
CREATE OR REPLACE CORTEX SEARCH SERVICE SELLER_EVIDENCE_SEARCH
  ON chunk_text
  ATTRIBUTES seller_id, product_id, document_id, page_number
  WAREHOUSE = SIRA_HACK_XS_WH
  TARGET_LAG = '1 day'
  AS (
    SELECT
        chunk_id,
        document_id,
        seller_id,
        product_id,
        page_number,
        section_path,
        chunk_text,
        chunk_hash
    FROM V_SEARCHABLE_SELLER_CHUNKS
  );
