# seed_extension_plan.md - what the demo adds on top of the BMW seed

Retrofit. Written at template-reconcile time after `data/build_cars_demo_data.py`
had already extended the seed; reverse-engineered from the loaded DDL
(`data/out/cars_demo_ddl.sql`) and the generator source. The original
seed columns and rows round-trip unchanged into `CARS_DEMO.FLEET.VEHICLE`
and `CARS_DEMO.FLEET.SERVICE_EVENT`; everything else is added.

## Tables that ARE the seed (unchanged columns, optional appended columns)

### `vehicle` (325 rows = seed row count)

All 23 seed columns are loaded verbatim. The loader appends 5 synthesised
columns:

| Synthesised column | Source | Why |
|---|---|---|
| `owner_id` | Deterministic, seed=42 | Seed CURRENT_OWNER is `***MASKED***` for every VIN. We synthesise an owner-id keyed by VIN. |
| `region_code` | Inferred from FACTORY_PRODUCTION_LOCATION + owner-distribution-policy | Q2 cascade needs regional rollup. |
| `owner_country` | Same | Same. |
| `nearest_centre_id` | Deterministic, seed=42, weighted by region | Q3 heuristic distance penalty + Q4 MIP eligibility. |
| `distance_to_nearest_centre_km` | Same | Q3 distance penalty. |

### `service_event` (760 rows = 762 seed - 2 orphan VINs)

All 8 seed columns are loaded verbatim. The loader drops 2 rows whose
VIN does not exist in the vehicles seed (FK integrity).

## Tables the demo ADDS (not in the seed at all)

These tables don't exist in the seed CSVs. The generator invents them
deterministically (seed=42) to land the Phase 1 anchored numbers. All
named entities (campaign IDs, supplier names, part numbers) are
"narrative-faithful" - they mirror real BMW Tier-1 + recall shapes
without claiming to be exact public NHTSA/KBA campaign numbers (see
`BRIEF.md > Open questions`).

| Table | Rows | What it contains | Why added |
|---|---|---|---|
| `dim_supplier` | 11 | Continental, Bosch, ZF, Samsung SDI, Brembo, Mahle, Magna, Hella, Lear, Aptiv, Takata-era. | Act 2 cascade origin. |
| `dim_region` | 7 | EU regions + NA + LATAM rollup buckets. | Act 2 rollup. |
| `dim_plant` | 6 | One row per FACTORY_PRODUCTION_LOCATION value in the seed. | Joins plant to region. |
| `dim_part` | 19 | Parts mapped to suppliers. | Act 2 cascade middle hop. |
| `dim_bom_node` | 11 | Bill-of-materials nodes tying parts to model-fragment + plant + production-date-window cohorts. | Act 2 cascade routing layer. Per-plant per-date-window granularity is what makes the recall problem real. |
| `bom_membership` | 531 | Junction: vehicle x bom_node. | Act 2 the actual VIN-level cascade. |
| `dim_service_centre` | 15 | Service centres from the seed's SERVICE_CENTER column + tooling-certification flags (`hv_certified`, `ibs_certified`, `body_shop`, `has_egr_tooling`). | Act 4 tooling-eligibility constraint. |
| `dim_recall_campaign` | 5 | IBS-2024-A (Continental brake-booster firmware), HVB-2024-A (Samsung SDI HV battery thermal), EGR-2023-B (older diesel EGR cooler), AIRBAG-2022-A (legacy Takata inflator), STARTER-2024-A. | Acts 1, 3, 4, 5. |
| `owner` | 282 | Synthesised owner identities. ~85% one-VIN, rest fleet. | Act 2 last hop in the cascade. |
| `recall_assignment` | 254 | (VIN, campaign) per-vehicle-per-campaign open work item with status, dates, age_days_at_demo, sla_breached flag. | Acts 1, 3, 4, 5. |
| `centre_capacity` | 60 | 15 centres x 4 weeks of technician-hour budget. | Act 4 MIP capacity constraint. |
| `parts_stock` | 172 | (centre, campaign, week) on-hand units. Continental IBS-2024-A stock is deliberately short - drives the Act 4 deferred-job story. | Act 4 MIP parts constraint. |

## Anchored numbers the extension is built to reproduce

From `BRIEF.md > Anchored numbers`. Each one corresponds to a deterministic
choice in `data/build_cars_demo_data.py`.

| Metric | Value | What the generator does to produce it |
|---|---|---|
| Vehicles | 325 | Loads seed verbatim. |
| Service events | 762 | Loads seed verbatim (2 orphans filtered). |
| Owners | 282 | Synthesises ~282 owners with the 85/15 split. |
| BOM membership edges | 531 | Picks bom_node per VIN based on model + plant + production-date window. |
| Recall assignments | 254 | Per-campaign distribution: IBS 80 / HVB 60 / EGR 50 / AIRBAG 40 / STARTER 24. |
| Open recall assignments | 121 | ~48% open across campaigns. |
| SLA-breached Open recalls (Act 1) | 19 | Hand-injected age + mileage combinations that exceed each campaign's completion_days window. |
| SLA-breached by campaign | IBS:8 / HVB:7 / EGR:3 / AIRBAG:1 / STARTER:0 | Distribution above is the target. |
| Continental MK C1 cascade size (Act 2) | 67 affected VINs | Continental IBS-2024-A part assigned to 3 plant-date cohorts via dim_bom_node + bom_membership picks. |
| Cascade regional rollup | EU:52 / NA:13 / LATAM:2 | Cohort plants chosen to land this split. |
| Priority VINs (Act 5: Open + prior accident) | 15 | Open-recall assignments overlap with accident_type IS NOT NULL on 15 VINs. |
| Recall campaigns | 5 | Listed above. |
| Service centres | 15 | Cleaned from seed SERVICE_CENTER values. |
| Suppliers | 11 | Listed above. |
| Parts | 19 | Listed above. |
| BOM nodes | 11 | Listed above (BRIEF.md table had 12; corrected to 11). |

## What the seed CSVs are NOT touched for

- No row in `vehicle` is dropped (all 325 round-trip).
- No seed column value is mutated. Synthesised columns are appended, not
  overwritten.
- No row in `service_event` is mutated. 2 orphan-VIN rows are filtered
  (see `seed_profile.md > Seed surprises`).

## Open questions about the extension

- Real BMW recall campaign IDs from current NHTSA / KBA registers are not
  used (web access denied during the build session). Campaign names are
  narrative-faithful only - see `BRIEF.md > Open questions`.
- Service-centre tooling-certification flags (`hv_certified`,
  `ibs_certified`, `body_shop`, `has_egr_tooling`) are assigned
  deterministically with a stated rationale (Munich + Spartanburg +
  Frankfurt + Cologne HV-certified because they serve the largest EV
  fleets). Open for user confirmation - see `BRIEF.md > Open questions`.
- VIN check-digit validity (ISO 3779 position 9 mod-11) of the seed VINs
  was not verified. Open issue tracked in `BRIEF.md`.
