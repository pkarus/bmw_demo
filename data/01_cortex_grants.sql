-- 01_cortex_grants.sql
--
-- Cortex agent deployer-role grants. Run ONCE as the rai profile's
-- default role (ACCOUNTADMIN on ajb85638) before the first
-- `agent.deploy deploy`. Generated from `agent.deploy preflight` +
-- the rai-cortex-integration skill.
--
-- After these grants, ACCOUNTADMIN can deploy a Cortex agent to
-- SNOWFLAKE_INTELLIGENCE.AGENTS. The sprocs and stage live in
-- CARS_DEMO.RAI_AGENT (already owned by RAI_DEMO_CARS).

USE ROLE ACCOUNTADMIN;

-- 0. Ensure SNOWFLAKE_INTELLIGENCE.AGENTS exists. Snowflake doesn't
-- auto-create these; the convention is for an account admin to make
-- them once when first onboarding Cortex Agents.
CREATE DATABASE IF NOT EXISTS SNOWFLAKE_INTELLIGENCE
  COMMENT = 'Snowflake Intelligence agent catalog. Default location for Cortex Agents that should appear in the SI picker.';
CREATE SCHEMA IF NOT EXISTS SNOWFLAKE_INTELLIGENCE.AGENTS
  COMMENT = 'Cortex Agent registry.';

-- 1. RAI Native App + Cortex + Pypi roles
GRANT APPLICATION ROLE relationalai.rai_user           TO ROLE ACCOUNTADMIN;
GRANT DATABASE ROLE snowflake.cortex_user              TO ROLE ACCOUNTADMIN;
GRANT DATABASE ROLE snowflake.pypi_repository_user     TO ROLE ACCOUNTADMIN;
GRANT APPLICATION ROLE snowflake.ai_observability_events_lookup TO ROLE ACCOUNTADMIN;

-- 2. Deployment schema (CARS_DEMO.RAI_AGENT) - need CREATE STAGE / PROCEDURE
GRANT USAGE ON DATABASE CARS_DEMO                      TO ROLE ACCOUNTADMIN;
GRANT USAGE ON SCHEMA CARS_DEMO.RAI_AGENT              TO ROLE ACCOUNTADMIN;
GRANT CREATE STAGE     ON SCHEMA CARS_DEMO.RAI_AGENT   TO ROLE ACCOUNTADMIN;
GRANT CREATE PROCEDURE ON SCHEMA CARS_DEMO.RAI_AGENT   TO ROLE ACCOUNTADMIN;

-- 3. Snowflake Intelligence agent schema
GRANT USAGE ON DATABASE SNOWFLAKE_INTELLIGENCE         TO ROLE ACCOUNTADMIN;
GRANT USAGE ON SCHEMA SNOWFLAKE_INTELLIGENCE.AGENTS    TO ROLE ACCOUNTADMIN;
GRANT CREATE AGENT ON SCHEMA SNOWFLAKE_INTELLIGENCE.AGENTS TO ROLE ACCOUNTADMIN;

-- 4. Warehouse
GRANT USAGE ON WAREHOUSE RAI_XS                        TO ROLE ACCOUNTADMIN;

-- 5. RAI external egress integration (created by RAI Native App
-- install Step 4). If this errors with "does not exist", the install
-- step needs to be re-run.
GRANT USAGE ON INTEGRATION S3_RAI_INTERNAL_BUCKET_EGRESS_INTEGRATION
                                                       TO ROLE ACCOUNTADMIN;

-- 6. Verify
USE ROLE ACCOUNTADMIN;
SHOW DATABASES LIKE 'SNOWFLAKE_INTELLIGENCE';
