USE ROLE SIRA_SF_BUILD_ROLE;
USE WAREHOUSE SIRA_HACK_XS_WH;

INSERT INTO SIRA_HACKATHON.DECISION.REQUESTS
  (request_id, organization_id, company_id, mission_id, context_version, created_by, idempotency_key)
SELECT 'sfreq_demo_v1','org_hackathon_demo','comp_consultco','msn_snowflake_demo_v1',1,
       'hackathon_demo','snowflake-causal-v1'
WHERE NOT EXISTS (
  SELECT 1 FROM SIRA_HACKATHON.DECISION.REQUESTS WHERE request_id='sfreq_demo_v1'
);

CALL SIRA_HACKATHON.DECISION.RUN_SIRA_DECISION('sfreq_demo_v1');

INSERT INTO SIRA_HACKATHON.DECISION.REQUESTS
  (request_id, organization_id, company_id, mission_id, context_version, created_by, idempotency_key)
SELECT 'sfreq_demo_v2','org_hackathon_demo','comp_consultco','msn_snowflake_demo_v2',2,
       'hackathon_demo','snowflake-causal-v2'
WHERE NOT EXISTS (
  SELECT 1 FROM SIRA_HACKATHON.DECISION.REQUESTS WHERE request_id='sfreq_demo_v2'
);

CALL SIRA_HACKATHON.DECISION.RUN_SIRA_DECISION('sfreq_demo_v2');

-- Required causal result: v1 -> NoteSync, v2 -> MeetAI.
SELECT req.context_version, run.selected_product_id, run.input_hash,
       run.decision_hash, run.counterfactual
FROM SIRA_HACKATHON.DECISION.REQUESTS req
JOIN SIRA_HACKATHON.DECISION.RUNS run USING (request_id)
WHERE req.request_id IN ('sfreq_demo_v1','sfreq_demo_v2')
ORDER BY req.context_version;

-- Required audit result: private facts, exact seller chunks, and approval hash.
SELECT request_id, context_version, selected_product_id, decision_hash,
       cited_fact_id, cited_document_id, cited_chunk_id, cited_page,
       exact_excerpt, approval_action, approval_hash
FROM SIRA_HACKATHON.DECISION.V_AUDIT_TRAIL
WHERE request_id IN ('sfreq_demo_v1','sfreq_demo_v2')
ORDER BY context_version, citation_type, citation_id;

ALTER WAREHOUSE SIRA_HACK_XS_WH SUSPEND;
