-- 02_notebook_compute_pool.sql
--
-- Create a dedicated compute pool for the cars_demo Snowsight
-- notebook. Container-runtime notebooks need a compute pool to
-- execute (the warehouse only handles SQL inside the notebook, not
-- the Python kernel). Run ONCE as the rai profile's default role
-- (ACCOUNTADMIN on ajb85638).

USE ROLE ACCOUNTADMIN;

CREATE COMPUTE POOL IF NOT EXISTS CARS_DEMO_NB_POOL
  MIN_NODES = 1
  MAX_NODES = 1
  INSTANCE_FAMILY = CPU_X64_XS
  AUTO_RESUME = TRUE
  AUTO_SUSPEND_SECS = 1800
  COMMENT = 'Notebook runtime for the cars_demo BMW recall propagation demo. Auto-suspends at 30 min idle to match the named-engine and notebook-idle settings.';

GRANT USAGE ON COMPUTE POOL CARS_DEMO_NB_POOL TO ROLE RAI_DEMO_CARS;
GRANT MONITOR ON COMPUTE POOL CARS_DEMO_NB_POOL TO ROLE RAI_DEMO_CARS;

-- Attach the pool to the existing notebook resource.
ALTER NOTEBOOK CARS_DEMO.NOTEBOOKS.CARS_DEMO SET COMPUTE_POOL = CARS_DEMO_NB_POOL;

-- Confirm
SHOW COMPUTE POOLS LIKE 'CARS_DEMO_NB_POOL';
