#!/usr/bin/env bash
# Load CARS_DEMO synthetic data into Snowflake under RAI_DEMO_CARS.
# Idempotent: re-running rebuilds tables (CREATE OR REPLACE in DDL) and
# reloads via COPY INTO (the staged files are overwritten).
#
# Usage:
#     bash data/load_to_snowflake.sh
#     CONN=NDSOEBE-... bash data/load_to_snowflake.sh
set -euo pipefail

CONN="${CONN:-rai}"
ROLE="${ROLE:-RAI_DEMO_CARS}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUT="$HERE/out"

echo "==> Using snow connection: $CONN, role: $ROLE"

if [ ! -d "$OUT" ]; then
  echo "FATAL: $OUT does not exist. Run .venv/bin/python data/build_cars_demo_data.py first."
  exit 1
fi

echo "==> [1/5] DDL: schema + tables"
snow sql -c "$CONN" --role "$ROLE" -f "$OUT/cars_demo_ddl.sql" >/dev/null

echo "==> [2/5] Reference data: suppliers, plants, parts, BOM, centres, campaigns, owners, capacity, parts-stock"
snow sql -c "$CONN" --role "$ROLE" -f "$OUT/cars_demo_reference.sql" >/dev/null

echo "==> [3/5] Stage + PUT (vehicles, services, bom, recall)"
snow sql -c "$CONN" --role "$ROLE" -q "USE DATABASE CARS_DEMO; USE SCHEMA FLEET; CREATE STAGE IF NOT EXISTS cars_demo_stage FILE_FORMAT = (TYPE = CSV SKIP_HEADER = 1 FIELD_OPTIONALLY_ENCLOSED_BY = '\"' NULL_IF = ('','NULL') EMPTY_FIELD_AS_NULL = TRUE);" >/dev/null

for f in cars_demo_vehicles.csv cars_demo_services.csv cars_demo_bom.csv cars_demo_recall.csv; do
  snow sql -c "$CONN" --role "$ROLE" -q "PUT file://$OUT/$f @CARS_DEMO.FLEET.cars_demo_stage AUTO_COMPRESS=TRUE OVERWRITE=TRUE;" >/dev/null
done

echo "==> [4/5] COPY INTO vehicle / service_event / bom_membership / recall_assignment"
snow sql -c "$CONN" --role "$ROLE" -q "
USE DATABASE CARS_DEMO; USE SCHEMA FLEET;
TRUNCATE TABLE vehicle;
TRUNCATE TABLE service_event;
TRUNCATE TABLE bom_membership;
TRUNCATE TABLE recall_assignment;
COPY INTO vehicle FROM @cars_demo_stage/cars_demo_vehicles.csv.gz FILE_FORMAT = (TYPE = CSV SKIP_HEADER = 1 FIELD_OPTIONALLY_ENCLOSED_BY = '\"' NULL_IF = ('','NULL') EMPTY_FIELD_AS_NULL = TRUE) ON_ERROR = ABORT_STATEMENT;
COPY INTO service_event FROM @cars_demo_stage/cars_demo_services.csv.gz FILE_FORMAT = (TYPE = CSV SKIP_HEADER = 1 FIELD_OPTIONALLY_ENCLOSED_BY = '\"' NULL_IF = ('','NULL') EMPTY_FIELD_AS_NULL = TRUE) ON_ERROR = ABORT_STATEMENT;
COPY INTO bom_membership FROM @cars_demo_stage/cars_demo_bom.csv.gz FILE_FORMAT = (TYPE = CSV SKIP_HEADER = 1 FIELD_OPTIONALLY_ENCLOSED_BY = '\"' NULL_IF = ('','NULL') EMPTY_FIELD_AS_NULL = TRUE) ON_ERROR = ABORT_STATEMENT;
COPY INTO recall_assignment FROM @cars_demo_stage/cars_demo_recall.csv.gz FILE_FORMAT = (TYPE = CSV SKIP_HEADER = 1 FIELD_OPTIONALLY_ENCLOSED_BY = '\"' NULL_IF = ('','NULL') EMPTY_FIELD_AS_NULL = TRUE) ON_ERROR = ABORT_STATEMENT;
" >/dev/null

echo "==> [5/5] Enable change tracking + final counts"
snow sql -c "$CONN" --role "$ROLE" -q "
USE DATABASE CARS_DEMO; USE SCHEMA FLEET;
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
  (SELECT COUNT(*) FROM vehicle) AS vehicles,
  (SELECT COUNT(*) FROM service_event) AS services,
  (SELECT COUNT(*) FROM owner) AS owners,
  (SELECT COUNT(*) FROM bom_membership) AS bom_edges,
  (SELECT COUNT(*) FROM recall_assignment) AS recalls,
  (SELECT COUNT(*) FROM recall_assignment WHERE status = 'Open') AS open_recalls,
  (SELECT COUNT(*) FROM recall_assignment WHERE sla_breached = TRUE) AS sla_breached
;
"

echo "==> Done. Validate further with:  snow sql -c $CONN --role $ROLE -f $OUT/cars_demo_validation.sql"
