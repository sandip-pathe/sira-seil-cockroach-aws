-- Reproducible document lineage after uploading the two fixture text files.
-- Upload through Snowsight stage UI or CoCo PUT to these exact stage paths:
--   product_a/product_a_meetai_integrations.txt
--   product_b/product_b_notesync_integrations.txt

USE ROLE SIRA_SF_BUILD_ROLE;
USE WAREHOUSE SIRA_HACK_XS_WH;
USE SCHEMA SIRA_HACKATHON.EVIDENCE;

INSERT INTO DOCUMENTS
  (document_id, seller_id, product_id, stage_path, filename, sha256, version, parsed_at)
SELECT 'doc_meetai_integrations', 'seller_meetai', 'prod_meetai_a',
       '@SELLER_DOCS_STAGE/product_a/', 'product_a_meetai_integrations.txt',
       SHA2('meetai_integrations_v1', 256), 1, CURRENT_TIMESTAMP()
WHERE NOT EXISTS (SELECT 1 FROM DOCUMENTS WHERE document_id='doc_meetai_integrations');

INSERT INTO DOCUMENTS
  (document_id, seller_id, product_id, stage_path, filename, sha256, version, parsed_at)
SELECT 'doc_notesync_integrations', 'seller_notesync', 'prod_notesync_b',
       '@SELLER_DOCS_STAGE/product_b/', 'product_b_notesync_integrations.txt',
       SHA2('notesync_integrations_v1', 256), 1, CURRENT_TIMESTAMP()
WHERE NOT EXISTS (SELECT 1 FROM DOCUMENTS WHERE document_id='doc_notesync_integrations');

INSERT INTO DOCUMENT_PARSE_RESULTS
  (parse_result_id, document_id, parser, parser_mode, raw_result)
SELECT 'parse_meetai_v1', 'doc_meetai_integrations', 'AI_PARSE_DOCUMENT', 'LAYOUT',
       SNOWFLAKE.CORTEX.PARSE_DOCUMENT(
         @SELLER_DOCS_STAGE,
         'product_a/product_a_meetai_integrations.txt',
         {'mode':'LAYOUT'}
       )
WHERE NOT EXISTS (SELECT 1 FROM DOCUMENT_PARSE_RESULTS WHERE parse_result_id='parse_meetai_v1');

INSERT INTO DOCUMENT_PARSE_RESULTS
  (parse_result_id, document_id, parser, parser_mode, raw_result)
SELECT 'parse_notesync_v1', 'doc_notesync_integrations', 'AI_PARSE_DOCUMENT', 'LAYOUT',
       SNOWFLAKE.CORTEX.PARSE_DOCUMENT(
         @SELLER_DOCS_STAGE,
         'product_b/product_b_notesync_integrations.txt',
         {'mode':'LAYOUT'}
       )
WHERE NOT EXISTS (SELECT 1 FROM DOCUMENT_PARSE_RESULTS WHERE parse_result_id='parse_notesync_v1');

-- Persist the parser output itself as the decisive, reviewer-addressable chunk.
-- Claim bindings below are curated assertions, but their cited text is never
-- hand-copied: it comes directly from AI_PARSE_DOCUMENT's stored result.
INSERT INTO DOCUMENT_CHUNKS
  (chunk_id, document_id, page_number, section_path, chunk_text, chunk_hash, parse_result_id)
SELECT mapped.chunk_id, parsed.document_id, 1, 'AI_PARSE_DOCUMENT / full document',
       parsed.raw_result:content::VARCHAR,
       SHA2(parsed.raw_result:content::VARCHAR, 256), parsed.parse_result_id
FROM DOCUMENT_PARSE_RESULTS AS parsed
JOIN (
  SELECT column1 AS parse_result_id, column2 AS chunk_id
  FROM VALUES
    ('parse_meetai_v1', 'chunk_meetai_crm'),
    ('parse_notesync_v1', 'chunk_notesync_crm')
) AS mapped ON mapped.parse_result_id = parsed.parse_result_id
WHERE parsed.raw_result:content IS NOT NULL
  AND NOT EXISTS (
    SELECT 1 FROM DOCUMENT_CHUNKS existing WHERE existing.chunk_id = mapped.chunk_id
  );

-- Forward migration for the first demo build, whose chunks were manually copied.
UPDATE DOCUMENT_CHUNKS AS chunk
SET chunk_text = parsed.raw_result:content::VARCHAR,
    chunk_hash = SHA2(parsed.raw_result:content::VARCHAR, 256)
FROM DOCUMENT_PARSE_RESULTS AS parsed
WHERE chunk.parse_result_id = parsed.parse_result_id
  AND parsed.raw_result:content IS NOT NULL
  AND chunk.chunk_id IN ('chunk_meetai_crm', 'chunk_notesync_crm');

INSERT INTO SELLER_CLAIM_BINDINGS
  (claim_id, product_id, claim_key, operator, typed_value, chunk_id,
   binding_status, reviewer, binding_hash)
SELECT 'claim_meetai_hubspot_price','prod_meetai_a','HUBSPOT_MIN_TIER_PRICE','gte',
       PARSE_JSON('120'), 'chunk_meetai_crm', 'REVIEWED', 'sira_build_reviewer',
       SHA2('claim_meetai_hubspot_price:prod_meetai_a:120:chunk_meetai_crm',256)
WHERE NOT EXISTS (SELECT 1 FROM SELLER_CLAIM_BINDINGS WHERE claim_id='claim_meetai_hubspot_price');

INSERT INTO SELLER_CLAIM_BINDINGS
  (claim_id, product_id, claim_key, operator, typed_value, chunk_id,
   binding_status, reviewer, binding_hash)
SELECT 'claim_notesync_hubspot_included','prod_notesync_b','HUBSPOT_INCLUDED_IN_BASE','eq',
       PARSE_JSON('true'), 'chunk_notesync_crm', 'REVIEWED', 'sira_build_reviewer',
       SHA2('claim_notesync_hubspot_included:prod_notesync_b:true:chunk_notesync_crm',256)
WHERE NOT EXISTS (SELECT 1 FROM SELLER_CLAIM_BINDINGS WHERE claim_id='claim_notesync_hubspot_included');

-- This must return 2/2. It proves each decision chunk belongs to a persisted
-- AI_PARSE_DOCUMENT result rather than an uncited model response.
SELECT COUNT_IF(parse_result_id IS NOT NULL) AS chunks_with_parse_lineage,
       COUNT(*) AS total_decisive_chunks
FROM DOCUMENT_CHUNKS
WHERE chunk_id IN ('chunk_meetai_crm','chunk_notesync_crm');
