-- 06_snowpark_evaluator.sql — CODE_STAGE and procedure registration
-- Run after 06_code_stage.sql and bundle upload.

USE ROLE SIRA_SF_BUILD_ROLE;
USE WAREHOUSE SIRA_HACK_XS_WH;
USE SCHEMA SIRA_HACKATHON.DECISION;

-- ============================================================
-- CODE_STAGE — holds the evaluator package and vendored deps
-- ============================================================
-- Build infra/snowflake/dist/sira_snowflake_evaluator.zip with
-- scripts/build_snowflake_bundle.ps1, then upload it with:
-- PUT file://<repo>/infra/snowflake/dist/sira_snowflake_evaluator.zip
--   @CODE_STAGE AUTO_COMPRESS=FALSE OVERWRITE=TRUE;

CREATE OR REPLACE PROCEDURE RUN_SIRA_DECISION(request_id VARCHAR)
  RETURNS VARIANT
  LANGUAGE PYTHON
  RUNTIME_VERSION = '3.12'
  PACKAGES = ('snowflake-snowpark-python')
  IMPORTS = ('@CODE_STAGE/sira_snowflake_evaluator.zip')
  HANDLER = 'snowpark_handler.run_sira_decision'
  EXECUTE AS OWNER;

-- The procedure executes as its owner; the app role can invoke but cannot alter it.
GRANT USAGE ON PROCEDURE SIRA_HACKATHON.DECISION.RUN_SIRA_DECISION(VARCHAR)
  TO ROLE SIRA_SF_APP_ROLE;
