-- =====================================================================
-- CARS_DEMO - Snowflake load orchestration
-- =====================================================================
USE ROLE RAI_DEMO_CARS;
USE DATABASE CARS_DEMO;
USE SCHEMA FLEET;

CREATE STAGE IF NOT EXISTS cars_demo_stage
  FILE_FORMAT = (TYPE = CSV SKIP_HEADER = 1
                 FIELD_OPTIONALLY_ENCLOSED_BY = '"'
                 NULL_IF = ('','NULL') EMPTY_FIELD_AS_NULL = TRUE);

-- The shell loader will PUT the four CSVs (vehicles, services, bom,
-- recall) onto this stage and then COPY INTO each table. See
-- data/load_to_snowflake.sh.

COPY INTO vehicle FROM @cars_demo_stage/cars_demo_vehicles.csv.gz
  FILE_FORMAT = (TYPE = CSV SKIP_HEADER = 1 FIELD_OPTIONALLY_ENCLOSED_BY = '"'
                 NULL_IF = ('','NULL') EMPTY_FIELD_AS_NULL = TRUE);

COPY INTO service_event FROM @cars_demo_stage/cars_demo_services.csv.gz
  FILE_FORMAT = (TYPE = CSV SKIP_HEADER = 1 FIELD_OPTIONALLY_ENCLOSED_BY = '"'
                 NULL_IF = ('','NULL') EMPTY_FIELD_AS_NULL = TRUE);

COPY INTO bom_membership FROM @cars_demo_stage/cars_demo_bom.csv.gz
  FILE_FORMAT = (TYPE = CSV SKIP_HEADER = 1 FIELD_OPTIONALLY_ENCLOSED_BY = '"'
                 NULL_IF = ('','NULL') EMPTY_FIELD_AS_NULL = TRUE);

COPY INTO recall_assignment FROM @cars_demo_stage/cars_demo_recall.csv.gz
  FILE_FORMAT = (TYPE = CSV SKIP_HEADER = 1 FIELD_OPTIONALLY_ENCLOSED_BY = '"'
                 NULL_IF = ('','NULL') EMPTY_FIELD_AS_NULL = TRUE);

-- Change tracking is required by PyRel CDC.
ALTER TABLE dim_supplier         SET CHANGE_TRACKING = TRUE;
ALTER TABLE dim_region           SET CHANGE_TRACKING = TRUE;
ALTER TABLE dim_plant            SET CHANGE_TRACKING = TRUE;
ALTER TABLE dim_part             SET CHANGE_TRACKING = TRUE;
ALTER TABLE dim_bom_node         SET CHANGE_TRACKING = TRUE;
ALTER TABLE dim_service_centre   SET CHANGE_TRACKING = TRUE;
ALTER TABLE dim_recall_campaign  SET CHANGE_TRACKING = TRUE;
ALTER TABLE owner                SET CHANGE_TRACKING = TRUE;
ALTER TABLE vehicle              SET CHANGE_TRACKING = TRUE;
ALTER TABLE service_event        SET CHANGE_TRACKING = TRUE;
ALTER TABLE bom_membership       SET CHANGE_TRACKING = TRUE;
ALTER TABLE recall_assignment    SET CHANGE_TRACKING = TRUE;
ALTER TABLE centre_capacity      SET CHANGE_TRACKING = TRUE;
ALTER TABLE parts_stock          SET CHANGE_TRACKING = TRUE;
ALTER TABLE centre_handoff       SET CHANGE_TRACKING = TRUE;

SELECT
  (SELECT COUNT(*) FROM dim_supplier)         AS suppliers,
  (SELECT COUNT(*) FROM dim_plant)            AS plants,
  (SELECT COUNT(*) FROM dim_part)             AS parts,
  (SELECT COUNT(*) FROM dim_bom_node)         AS bom_nodes,
  (SELECT COUNT(*) FROM dim_service_centre)   AS centres,
  (SELECT COUNT(*) FROM dim_recall_campaign)  AS campaigns,
  (SELECT COUNT(*) FROM owner)                AS owners,
  (SELECT COUNT(*) FROM vehicle)              AS vehicles,
  (SELECT COUNT(*) FROM service_event)        AS services,
  (SELECT COUNT(*) FROM bom_membership)       AS bom_edges,
  (SELECT COUNT(*) FROM recall_assignment)    AS recalls,
  (SELECT COUNT(*) FROM centre_capacity)      AS capacity_rows,
  (SELECT COUNT(*) FROM centre_handoff)       AS handoffs,
  (SELECT COUNT(*) FROM parts_stock)          AS stock_rows;
