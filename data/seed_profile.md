# seed_profile.md - BMW seed data profile

Retrofit. Written at template-reconcile time after Phase 2 had already
loaded. Profiles the two seed CSVs at `data/seed/` against the loaded
`CARS_DEMO.FLEET` tables.

## Files

| File | Rows | Cols | Encoding | Source |
|---|---|---|---|---|
| `data/seed/BMW_VEHICLES_V1.csv` | 325 | 23 | UTF-8 | Customer (BMW SE EMEA, original landing on `sfseeurope-demo531`) |
| `data/seed/BMW_VEHICLES_SERVICES.csv` | 762 | 8 | UTF-8 | Same |
| `data/seed/BMW_FLEET_ANALYSIS.tds` | n/a | n/a | XML | Tableau workbook descriptor pointing at the customer's Snowflake `BMW_DEMO.DFA` schema. Informational only - we do not run against that account. |

## `BMW_VEHICLES_V1.csv` (one row per VIN)

Inferred primary key: `VIN` (cardinality 325, 0% null).

| Column | Type | Null % | Cardinality | Notes |
|---|---|---|---|---|
| VIN | str | 0% | 325 | WBA-prefix BMW WMI. ISO 3779 shape. |
| SERIAL_NUMBER | str | 5.2% | 308 | Free-text. Some duplicates due to nulls. |
| MODEL | str | 0% | 23 | E.g. "X1 M35i xDrive (U11)", "i7 M70 xDrive", "G21 LCI 330i". Real BMW model designators. |
| FACTORY_PRODUCTION_LOCATION | str | 0% | 6 | Dingolfing 97, Spartanburg 75, Munich 58, Regensburg 53, San Luis Potosi 26, Leipzig 16. Maps directly to `dim_plant`. |
| ENGINE_TYPE | str | 0% | 16 | Real BMW engine codes (B48, B58, S58, electric drive). |
| FUEL_TYPE | str | 0% | 4 | Petrol / Diesel / Electric / Hybrid. |
| TRANSMISSION | str | 0% | 2 | Manual / Automatic. |
| CHASSIS_NUMBER | str | 5.2% | 308 | Free-text. |
| EMISSION_STANDARD | str | 0% | 2 | EURO 6e / EURO 6e-bis. |
| PRODUCTION_DATE | date-str | 0% | 132 | ISO format. |
| DELIVERY_DATE | date-str | 0% | 231 | ISO format. Always >= PRODUCTION_DATE. |
| FIRST_REGISTRATION_DATE | date-str | 0% | 235 | ISO format. Always >= DELIVERY_DATE. |
| CURRENT_OWNER | str | 0% | 1 | All values are `***MASKED***`. We synthesise per-VIN owner identity in the loader. |
| MILEAGE | int | 0% | 318 | km. min 0, median 77k, max 239k. |
| FUEL_CONSUMPTION | float | 0% | 60 | l/100km. |
| ACCIDENT_DATE | date-str | 83.1% | 47 | Null = no accident. |
| ACCIDENT_TYPE | str | 83.1% | 4 | Collision 21, Minor 13, Rear-end 13, Vandalism 8. Same null pattern as ACCIDENT_DATE. |
| REPAIR_COST | float | 7.7% | 56 | USD-equiv. |
| SERVICE_RECORDS | str | 5.2% | 2 | "Up to date" / "Behind". |
| RECALL_STATUS | str | 61.5% | 2 | Open 67 / Closed 58 / null 200. Null means "no campaign on this VIN" in the seed; the loader re-derives recall status from `recall_assignment` and the campaign-window rule, so the seed value is informational only. |
| PREVIOUS_OWNERS | float | 5.2% | 4 | 0..3. |
| POWER_OUTPUT_KW | int | 0% | 21 | |
| POWER_OUTPUT_PS | int | 0% | 21 | ~1.36 * KW; redundant with KW but kept for fidelity to the customer CSV. |

## `BMW_VEHICLES_SERVICES.csv` (one row per service event)

Inferred primary key: `SERVICE_EVENT_ID` (cardinality 762, 0% null).

Foreign key to vehicles: `VIN`. 300 of 302 unique VINs in services exist
in vehicles (overlap 99.3%). 2 services-only VINs are orphans relative to
the seed vehicles file - the loader filters these out (recorded under
"Seed surprises" below).

| Column | Type | Null % | Cardinality | Notes |
|---|---|---|---|---|
| SERVICE_EVENT_ID | int | 0% | 762 | Sequential int. |
| VIN | str | 0% | 302 | FK to vehicle.vin. 2 rows reference VINs not in the vehicles CSV. |
| SERVICE_DATE | date-str | 0% | 616 | ISO format. |
| SERVICE_TYPE | str | 0% | 6 | Inspection 172, Oil Service 167, Brake Service 144, Annual Service 141, Battery Service 137, Brake 1 (single typo - cleaned to "Brake Service" by the loader). |
| SERVICE_CENTER | str | 0% | 20 | 20 distinct names (US spelling). Maps to `dim_service_centre` after the loader resolves 5 trailing-whitespace duplicates and 15 distinct centres land in the dim. |
| SERVICE_COST | float | 0% | 455 | USD. |
| WARRANTY | bool | 0% | 2 | TRUE / FALSE. |
| NOTES | str | 0% | 5 | One of 5 stock notes ("Standard service", "Customer satisfied", etc). |

## Cross-file integrity

- 300 of 302 services-VINs exist in vehicles (99.3%).
- 23 vehicles never appear in services (no service event recorded).
- 2 services rows reference VINs not in the vehicles file (orphans). The
  loader filters these.

## Anchor entities required by Phase 1 questions

The talk track references real BMW shapes. The seed already contains
most of them; specific entities the seed does NOT contain are synthesised
by `data/build_cars_demo_data.py` and listed in `seed_extension_plan.md`.

Seed already contains:
- WBA-prefix VINs (325).
- Realistic BMW model designators (G21 LCI, U11, G87, G26, G60, G45, G07, iX, iX1, i5, i7, i4, X1, X3, X7, M2).
- 6 BMW plants matching real production sites (Dingolfing, Spartanburg, Munich, Regensburg, San Luis Potosi, Leipzig).
- Vehicle ages and mileage suitable for the Act 1 SLA-breach rule (some VINs > 4 years old and > 150k km).
- Accident history on ~17% of VINs (sufficient for Act 5's prior-accident priority rule).

## Seed surprises

- One service_type value `Brake` (singular) appears once in 762 rows. The
  loader treats it as `Brake Service`.
- 2 orphan service VINs (in services CSV, not in vehicles CSV). Loader
  filters them out so the FK from service_event.vin to vehicle.vin holds.
- All CURRENT_OWNER values are `***MASKED***`. The loader synthesises per-VIN
  owner identity (`owner` table with masked names and region codes).
- 5 trailing-whitespace variants of service centre names. The loader
  trims and resolves to 15 distinct centres.

## Notes on what is NOT in the seed

The seed has VINs, service events, and basic registration metadata. It
does NOT contain: suppliers, parts, bill-of-materials, recall campaigns
(as objects), service-centre capacity, parts inventory, owners, regions,
plants (as a table), or distance-to-centre. The extension plan
(`seed_extension_plan.md`) lists what was added on top.
