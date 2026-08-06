-- 00_preflight.sql — Account capability gate for SIRA + SEIL Snowflake build
-- Run as ACCOUNTADMIN before any other scripts.
-- This script checks; it does not create or alter objects.

USE ROLE ACCOUNTADMIN;

-- 1. Account identity and region
SELECT CURRENT_ACCOUNT()  AS account_name,
       CURRENT_REGION()   AS region,
       CURRENT_ROLE()     AS role,
       CURRENT_USER()     AS user_name;

-- 2. Cross-region inference (needed for AI_PARSE_DOCUMENT outside native regions)
SHOW PARAMETERS LIKE 'CORTEX_ENABLED_CROSS_REGION' IN ACCOUNT;

-- 3. Check Python 3.12 runtime available
SELECT DISTINCT RUNTIME_VERSION
  FROM SNOWFLAKE.INFORMATION_SCHEMA.PACKAGES
 WHERE LANGUAGE = 'python'
   AND RUNTIME_VERSION = '3.12'
 LIMIT 1;

-- 4. Confirm rfc8785 is NOT available (we vendor it)
SELECT COUNT(*) AS rfc8785_available
  FROM SNOWFLAKE.INFORMATION_SCHEMA.PACKAGES
 WHERE PACKAGE_NAME = 'rfc8785'
   AND LANGUAGE = 'python';
-- Expected: 0 — we vendor the dependency into CODE_STAGE

-- 5. Confirm pydantic IS available for 3.12
SELECT PACKAGE_NAME, MAX(VERSION) AS latest_version
  FROM SNOWFLAKE.INFORMATION_SCHEMA.PACKAGES
 WHERE PACKAGE_NAME = 'pydantic'
   AND LANGUAGE = 'python'
   AND RUNTIME_VERSION = '3.12'
 GROUP BY PACKAGE_NAME;

-- 6. Confirm snowflake-snowpark-python availability
SELECT PACKAGE_NAME, MAX(VERSION) AS latest_version
  FROM SNOWFLAKE.INFORMATION_SCHEMA.PACKAGES
 WHERE PACKAGE_NAME = 'snowflake-snowpark-python'
   AND LANGUAGE = 'python'
   AND RUNTIME_VERSION = '3.12'
 GROUP BY PACKAGE_NAME;

-- 7. Credit usage check (current period)
SELECT SUM(CREDITS_USED) AS total_credits_used_today
  FROM SNOWFLAKE.ACCOUNT_USAGE.METERING_HISTORY
 WHERE START_TIME >= CURRENT_DATE();
