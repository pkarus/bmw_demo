-- =====================================================================
-- CARS_DEMO - Validation queries (anchored numbers from BRIEF.md)
-- =====================================================================
-- Run after loading and verify the expected counts. Each query backs
-- one talk-track number that prep_demo.py will assert.
USE ROLE RAI_DEMO_CARS;
USE DATABASE CARS_DEMO;
USE SCHEMA FLEET;

-- Sanity: top-line counts.
-- Expected: 325 vehicles, 762 services, 254 recalls,
--           531 bom edges, 121 Open
--           recalls across all campaigns.
SELECT
  (SELECT COUNT(*) FROM vehicle) AS vehicles,
  (SELECT COUNT(*) FROM service_event) AS services,
  (SELECT COUNT(*) FROM recall_assignment) AS recalls,
  (SELECT COUNT(*) FROM bom_membership) AS bom_edges,
  (SELECT COUNT(*) FROM recall_assignment WHERE status = 'Open') AS open_recalls;

-- Q1 (Act 1 audit): SLA-breached Open recalls by campaign
-- Expected dominant campaign: IBS-2024-A
SELECT
  campaign_id,
  COUNT(*) AS sla_breached_open
FROM recall_assignment
WHERE status = 'Open'
  AND sla_breached = TRUE
GROUP BY campaign_id
ORDER BY sla_breached_open DESC;

-- Q1: SLA-breached Open recalls by responsible service centre
-- Expected leader: BMW Munich Service
WITH responsible_centre AS (
  SELECT r.recall_id, r.campaign_id, v.vin, v.nearest_centre_id, sc.name AS centre_name
  FROM recall_assignment r
  JOIN vehicle v ON v.vin = r.vin
  JOIN dim_service_centre sc ON sc.centre_id = v.nearest_centre_id
  WHERE r.status = 'Open' AND r.sla_breached = TRUE
)
SELECT centre_name, COUNT(*) AS sla_breached_open
FROM responsible_centre
GROUP BY centre_name
ORDER BY sla_breached_open DESC;

-- Q2 (Act 2 cascade): affected VINs from supplier Continental
-- Expected: ~80 VINs, the IBS-2024-A campaign population
WITH cascade AS (
  SELECT DISTINCT bm.vin
  FROM dim_supplier s
  JOIN dim_part      p   ON p.supplier_id = s.supplier_id
  JOIN dim_bom_node  b   ON b.part_id     = p.part_id
  JOIN bom_membership bm ON bm.bom_id     = b.bom_id
  WHERE s.supplier_id = 'SUP-CONT'
    AND p.part_id = 'PRT-IBS-ECU'
)
SELECT COUNT(*) AS affected_vins FROM cascade;

-- Q2: same cascade rolled up by region (EU / NA / LATAM)
SELECT r.rollup, COUNT(DISTINCT bm.vin) AS affected_vins, COUNT(DISTINCT v.nearest_centre_id) AS centres_engaged
FROM dim_supplier s
JOIN dim_part      p   ON p.supplier_id = s.supplier_id
JOIN dim_bom_node  b   ON b.part_id     = p.part_id
JOIN bom_membership bm ON bm.bom_id     = b.bom_id
JOIN vehicle       v   ON v.vin         = bm.vin
JOIN dim_service_centre sc ON sc.centre_id = v.nearest_centre_id
JOIN dim_region    r   ON r.region_code = sc.region_code
WHERE s.supplier_id = 'SUP-CONT' AND p.part_id = 'PRT-IBS-ECU'
GROUP BY r.rollup
ORDER BY affected_vins DESC;

-- Q3 (Act 3 heuristic): a SQL sketch of the urgency-score top-20.
-- The PyRel version computes the same with derived properties; this
-- SQL ensures the candidate population and dominant cohort match.
WITH open_recalls AS (
  SELECT r.vin, r.campaign_id,
         v.mileage,
         DATEDIFF('day', v.first_registration_date, '2026-05-25') AS age_days,
         CASE WHEN v.accident_type IS NULL OR v.accident_type = '' THEN 0
              WHEN v.accident_type IN ('Minor','Vandalism') THEN 1
              WHEN v.accident_type IN ('Rear-end','Collision') THEN 2
              ELSE 0 END AS accident_severity,
         v.distance_to_nearest_centre_km AS distance_km,
         v.factory
  FROM recall_assignment r
  JOIN vehicle v ON v.vin = r.vin
  WHERE r.status = 'Open'
)
SELECT vin, campaign_id, factory, mileage, age_days, accident_severity, distance_km,
       (0.30 * (mileage / 250000.0)
      + 0.25 * (age_days / 2200.0)
      + 0.30 * (accident_severity / 2.0)
      + 0.15 * (distance_km / 250.0)) AS urgency_score
FROM open_recalls
ORDER BY urgency_score DESC
LIMIT 20;

-- Q4 (Act 4): pre-solve sanity. Total open jobs vs. total available
-- (tech_hours / typical_labour_hours) across the 4-week horizon.
-- Expected: tech-hours capacity is plenty; parts stock is the
-- binding constraint (especially IBS-2024-A).
SELECT
  c.campaign_id,
  COUNT(*) AS open_jobs,
  c.typical_labour_hours,
  (SELECT SUM(on_hand_units) FROM parts_stock ps WHERE ps.campaign_id = c.campaign_id) AS total_stock_4wk
FROM recall_assignment r
JOIN dim_recall_campaign c ON c.campaign_id = r.campaign_id
WHERE r.status = 'Open'
GROUP BY c.campaign_id, c.typical_labour_hours;

-- Q5 (Act 5): population of priority VINs (open recall + prior accident).
SELECT COUNT(DISTINCT r.vin) AS priority_vins
FROM recall_assignment r
JOIN vehicle v ON v.vin = r.vin
WHERE r.status = 'Open'
  AND v.accident_type IS NOT NULL
  AND v.accident_type <> '';
