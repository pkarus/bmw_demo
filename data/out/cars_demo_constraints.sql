-- =====================================================================
-- CARS_DEMO - Primary key + foreign key + NOT NULL retrofit
-- Retrofit for missing constraints after initial load.
-- Snowflake does not enforce PK / FK / UNIQUE but the RelationalAI
-- agentic modeler reads them as concept keys / relationships at Phase 3.
-- =====================================================================

USE ROLE RAI_DEMO_CARS;
USE DATABASE CARS_DEMO;
USE SCHEMA FLEET;

-- ----- PKs missing from initial DDL -----------------------------------

ALTER TABLE bom_membership
    ADD CONSTRAINT pk_bom_membership PRIMARY KEY (bom_id, vin);

ALTER TABLE centre_capacity
    ADD CONSTRAINT pk_centre_capacity PRIMARY KEY (centre_id, week_index);

ALTER TABLE parts_stock
    ADD CONSTRAINT pk_parts_stock PRIMARY KEY (centre_id, campaign_id, week_index);

-- ----- Foreign keys ---------------------------------------------------

ALTER TABLE dim_part
    ADD CONSTRAINT fk_dim_part_supplier
    FOREIGN KEY (supplier_id) REFERENCES dim_supplier(supplier_id);

ALTER TABLE dim_bom_node
    ADD CONSTRAINT fk_dim_bom_node_part
    FOREIGN KEY (part_id) REFERENCES dim_part(part_id);

ALTER TABLE dim_plant
    ADD CONSTRAINT fk_dim_plant_region
    FOREIGN KEY (region_code) REFERENCES dim_region(region_code);

ALTER TABLE dim_service_centre
    ADD CONSTRAINT fk_dim_service_centre_region
    FOREIGN KEY (region_code) REFERENCES dim_region(region_code);

ALTER TABLE dim_recall_campaign
    ADD CONSTRAINT fk_dim_recall_campaign_supplier
    FOREIGN KEY (supplier_id) REFERENCES dim_supplier(supplier_id);

ALTER TABLE dim_recall_campaign
    ADD CONSTRAINT fk_dim_recall_campaign_part
    FOREIGN KEY (primary_part_id) REFERENCES dim_part(part_id);

ALTER TABLE owner
    ADD CONSTRAINT fk_owner_region
    FOREIGN KEY (region_code) REFERENCES dim_region(region_code);

ALTER TABLE owner
    ADD CONSTRAINT fk_owner_centre
    FOREIGN KEY (nearest_centre_id) REFERENCES dim_service_centre(centre_id);

ALTER TABLE vehicle
    ADD CONSTRAINT fk_vehicle_owner
    FOREIGN KEY (owner_id) REFERENCES owner(owner_id);

ALTER TABLE vehicle
    ADD CONSTRAINT fk_vehicle_region
    FOREIGN KEY (region_code) REFERENCES dim_region(region_code);

ALTER TABLE vehicle
    ADD CONSTRAINT fk_vehicle_centre
    FOREIGN KEY (nearest_centre_id) REFERENCES dim_service_centre(centre_id);

ALTER TABLE service_event
    ADD CONSTRAINT fk_service_event_vehicle
    FOREIGN KEY (vin) REFERENCES vehicle(vin);

ALTER TABLE bom_membership
    ADD CONSTRAINT fk_bom_membership_bom
    FOREIGN KEY (bom_id) REFERENCES dim_bom_node(bom_id);

ALTER TABLE bom_membership
    ADD CONSTRAINT fk_bom_membership_vehicle
    FOREIGN KEY (vin) REFERENCES vehicle(vin);

ALTER TABLE recall_assignment
    ADD CONSTRAINT fk_recall_assignment_vehicle
    FOREIGN KEY (vin) REFERENCES vehicle(vin);

ALTER TABLE recall_assignment
    ADD CONSTRAINT fk_recall_assignment_campaign
    FOREIGN KEY (campaign_id) REFERENCES dim_recall_campaign(campaign_id);

ALTER TABLE centre_capacity
    ADD CONSTRAINT fk_centre_capacity_centre
    FOREIGN KEY (centre_id) REFERENCES dim_service_centre(centre_id);

ALTER TABLE parts_stock
    ADD CONSTRAINT fk_parts_stock_centre
    FOREIGN KEY (centre_id) REFERENCES dim_service_centre(centre_id);

ALTER TABLE parts_stock
    ADD CONSTRAINT fk_parts_stock_campaign
    FOREIGN KEY (campaign_id) REFERENCES dim_recall_campaign(campaign_id);

-- ----- NOT NULL on natural-required columns ---------------------------
-- The PK columns are NOT NULL by virtue of the PK; these are the columns
-- the data shows are never null but were declared nullable in the load.

ALTER TABLE dim_part           MODIFY COLUMN supplier_id   SET NOT NULL;
ALTER TABLE dim_bom_node       MODIFY COLUMN part_id       SET NOT NULL;
ALTER TABLE dim_plant          MODIFY COLUMN region_code   SET NOT NULL;
ALTER TABLE dim_service_centre MODIFY COLUMN region_code   SET NOT NULL;
ALTER TABLE dim_recall_campaign MODIFY COLUMN supplier_id  SET NOT NULL;
ALTER TABLE dim_recall_campaign MODIFY COLUMN primary_part_id SET NOT NULL;
ALTER TABLE owner              MODIFY COLUMN region_code   SET NOT NULL;
ALTER TABLE owner              MODIFY COLUMN nearest_centre_id SET NOT NULL;
ALTER TABLE vehicle            MODIFY COLUMN owner_id      SET NOT NULL;
ALTER TABLE vehicle            MODIFY COLUMN region_code   SET NOT NULL;
ALTER TABLE vehicle            MODIFY COLUMN nearest_centre_id SET NOT NULL;
ALTER TABLE service_event      MODIFY COLUMN vin           SET NOT NULL;
ALTER TABLE recall_assignment  MODIFY COLUMN vin           SET NOT NULL;
ALTER TABLE recall_assignment  MODIFY COLUMN campaign_id   SET NOT NULL;
