-- Create the evaluator stage before uploading the procedure bundle.
USE ROLE SIRA_SF_BUILD_ROLE;
USE WAREHOUSE SIRA_HACK_XS_WH;
USE SCHEMA SIRA_HACKATHON.DECISION;

CREATE STAGE IF NOT EXISTS CODE_STAGE
  DIRECTORY = (ENABLE = TRUE)
  COMMENT = 'Versioned evaluator package and pinned dependencies for Snowpark procedure.';
