-- 00_bootstrap.sql
--
-- One-shot bootstrap for the CARS_DEMO (BMW internal name) RelationalAI
-- demo. Creates a demo-specific role, the demo database, and grants the
-- role exactly the privileges it needs and no more. After this script
-- runs, every subsequent snow sql command in this repo passes
-- --role RAI_DEMO_CARS explicitly. Snowflake itself blocks the demo role
-- from touching anything outside CARS_DEMO.
--
-- Substitutions already applied:
--   DEMO_DB          = CARS_DEMO
--   DEMO_ROLE        = RAI_DEMO_CARS
--   DEMO_WAREHOUSE   = RAI_XS
--   CURRENT_USER     = "piotr.kraus@relational.ai"
--   RAI_APP_NAME     = RELATIONALAI
--
-- Account: ajb85638 (Snowflake SE US). The user reviews this file and
-- runs it once via:
--   snow sql -c rai -f data/00_bootstrap.sql
--
-- See CLAUDE.md > "Snowflake security harness" for the full model.

USE ROLE ACCOUNTADMIN;

-- 1. Demo-specific role
CREATE ROLE IF NOT EXISTS RAI_DEMO_CARS
  COMMENT = 'Scoped role for the CARS_DEMO demo (internal: BMW recall propagation). Created by demo-agent-template intake.';
GRANT ROLE RAI_DEMO_CARS TO USER "piotr.kraus@relational.ai";
GRANT ROLE RAI_DEMO_CARS TO ROLE SYSADMIN;

-- 2. Demo database, fully owned by the demo role
CREATE DATABASE IF NOT EXISTS CARS_DEMO
  COMMENT = 'Demo database for CARS_DEMO (internal: BMW recall propagation). Created by demo-agent-template intake.';
GRANT OWNERSHIP ON DATABASE CARS_DEMO TO ROLE RAI_DEMO_CARS COPY CURRENT GRANTS;
GRANT ALL ON DATABASE CARS_DEMO TO ROLE RAI_DEMO_CARS;
GRANT ALL ON ALL SCHEMAS IN DATABASE CARS_DEMO TO ROLE RAI_DEMO_CARS;
GRANT ALL ON FUTURE SCHEMAS IN DATABASE CARS_DEMO TO ROLE RAI_DEMO_CARS;
GRANT ALL ON ALL TABLES IN DATABASE CARS_DEMO TO ROLE RAI_DEMO_CARS;
GRANT ALL ON FUTURE TABLES IN DATABASE CARS_DEMO TO ROLE RAI_DEMO_CARS;
GRANT ALL ON ALL VIEWS IN DATABASE CARS_DEMO TO ROLE RAI_DEMO_CARS;
GRANT ALL ON FUTURE VIEWS IN DATABASE CARS_DEMO TO ROLE RAI_DEMO_CARS;
GRANT ALL ON ALL STAGES IN DATABASE CARS_DEMO TO ROLE RAI_DEMO_CARS;
GRANT ALL ON FUTURE STAGES IN DATABASE CARS_DEMO TO ROLE RAI_DEMO_CARS;
GRANT ALL ON ALL FUNCTIONS IN DATABASE CARS_DEMO TO ROLE RAI_DEMO_CARS;
GRANT ALL ON FUTURE FUNCTIONS IN DATABASE CARS_DEMO TO ROLE RAI_DEMO_CARS;
GRANT ALL ON ALL PROCEDURES IN DATABASE CARS_DEMO TO ROLE RAI_DEMO_CARS;
GRANT ALL ON FUTURE PROCEDURES IN DATABASE CARS_DEMO TO ROLE RAI_DEMO_CARS;
GRANT ALL ON ALL FILE FORMATS IN DATABASE CARS_DEMO TO ROLE RAI_DEMO_CARS;
GRANT ALL ON FUTURE FILE FORMATS IN DATABASE CARS_DEMO TO ROLE RAI_DEMO_CARS;
-- NOTEBOOK is a Snowflake object type that does NOT support GRANT ON
-- ALL / GRANT ON FUTURE (Snowflake error 0A000 "Unsupported feature").
-- The role already owns the database via the OWNERSHIP grant above, so
-- it can CREATE / ALTER / DROP NOTEBOOKS inside any schema in CARS_DEMO
-- with no further grant needed. Schema-level CREATE NOTEBOOK is included
-- in the per-schema privilege bundle from GRANT ALL ON ALL SCHEMAS.

-- 3. Warehouse usage (USAGE + OPERATE only; no MODIFY so the role
-- cannot ALTER or DROP the warehouse)
GRANT USAGE ON WAREHOUSE RAI_XS TO ROLE RAI_DEMO_CARS;
GRANT OPERATE ON WAREHOUSE RAI_XS TO ROLE RAI_DEMO_CARS;

-- 4. RelationalAI Native App access
-- On ajb85638 the app is named RELATIONALAI. Verified via:
--   SHOW APPLICATIONS LIKE '%RAI%';
--   SHOW APPLICATION ROLES IN APPLICATION RELATIONALAI;
-- The app exposes RAI_USER (not RAI_DEVELOPER) as an application role.
-- The Snowflake-account role RAI_DEVELOPER also exists at top level
-- (installed by the native app at install time) and is what PyRel
-- programs in the reference demos rely on. Grant both.
GRANT APPLICATION ROLE RELATIONALAI.RAI_USER TO ROLE RAI_DEMO_CARS;
GRANT ROLE RAI_DEVELOPER TO ROLE RAI_DEMO_CARS;

-- 5. Snowflake Intelligence (Cortex agent deployment)
-- The SNOWFLAKE_INTELLIGENCE database does NOT exist on ajb85638 at this
-- time, so the standard grant block is intentionally omitted. The agent
-- itself will be deployed into CARS_DEMO.RAI_AGENT (which the demo role
-- already owns); registration with the Snowflake Intelligence picker is
-- handled by relationalai.agent.cortex.CortexAgentManager if/when the
-- SNOWFLAKE_INTELLIGENCE database becomes available. See BRIEF.md
-- "Open questions" for the Phase 7 plan if SI is still missing.
-- If SI is later enabled on this account, run:
--   USE ROLE ACCOUNTADMIN;
--   GRANT USAGE ON DATABASE SNOWFLAKE_INTELLIGENCE TO ROLE RAI_DEMO_CARS;
--   GRANT USAGE ON SCHEMA SNOWFLAKE_INTELLIGENCE.AGENTS TO ROLE RAI_DEMO_CARS;
--   GRANT CREATE AGENT ON SCHEMA SNOWFLAKE_INTELLIGENCE.AGENTS TO ROLE RAI_DEMO_CARS;

-- 6. Smoke-verify the role
USE ROLE RAI_DEMO_CARS;
USE DATABASE CARS_DEMO;
USE WAREHOUSE RAI_XS;
SELECT CURRENT_ROLE() AS role, CURRENT_DATABASE() AS db, CURRENT_WAREHOUSE() AS wh;

-- 7. What this role explicitly does NOT have
-- (no DDL outside CARS_DEMO, no USER mutations, no PAT creation, no
-- account-level grants, no warehouse creation, no role mutations).
-- Snowflake denies these by default for any non-ACCOUNTADMIN /
-- SECURITYADMIN role - this script never grants them.

-- End of bootstrap. From this point on, every snow sql command runs as:
--   snow sql --role RAI_DEMO_CARS -c rai -q '...'
-- or
--   snow sql --role RAI_DEMO_CARS -c rai -f path/to/file.sql
