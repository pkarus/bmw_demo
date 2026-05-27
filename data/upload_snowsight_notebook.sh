#!/usr/bin/env bash
# Upload cars_demo_snowsight.ipynb + cars.py + demo_queries.py to a
# Snowsight Notebook resource at CARS_DEMO.NOTEBOOKS.CARS_DEMO. Uses
# the demo role (no ACCOUNTADMIN escalation). Idempotent.
set -euo pipefail

CONN="${CONN:-rai}"
ROLE="${ROLE:-RAI_DEMO_CARS}"
DB="CARS_DEMO"
NB_SCHEMA="NOTEBOOKS"
NB_STAGE="CARS_NOTEBOOK_STAGE"
NB_NAME="CARS_DEMO"
NB_FOLDER="cars"

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"

NB_MAIN="cars_demo_snowsight.ipynb"
NB_SOURCES=(
  "$ROOT/rai_code/manual/cars_demo_snowsight.ipynb"
  "$ROOT/rai_code/manual/cars.py"
  "$ROOT/rai_code/manual/demo_queries.py"
)

echo "==> [1/4] Schema + stage"
snow sql -c "$CONN" --role "$ROLE" -q "
USE DATABASE $DB;
CREATE SCHEMA IF NOT EXISTS $NB_SCHEMA;
USE SCHEMA $NB_SCHEMA;
CREATE STAGE IF NOT EXISTS $NB_STAGE
  FILE_FORMAT = (TYPE = CSV SKIP_HEADER = 1
                 FIELD_OPTIONALLY_ENCLOSED_BY = '\"' NULL_IF = ('','NULL')
                 EMPTY_FIELD_AS_NULL = TRUE);
" >/dev/null

echo "==> [2/4] PUT (auto_compress=FALSE so Snowsight reads files directly)"
for f in "${NB_SOURCES[@]}"; do
  echo "  - $f"
  snow sql -c "$CONN" --role "$ROLE" -q "
USE DATABASE $DB; USE SCHEMA $NB_SCHEMA;
PUT file://$f @$DB.$NB_SCHEMA.$NB_STAGE/$NB_FOLDER/ AUTO_COMPRESS=FALSE OVERWRITE=TRUE;
" >/dev/null
done

echo "==> [3/4] CREATE OR REPLACE NOTEBOOK"
# SYSTEM\$BASIC_RUNTIME is the container runtime - same as airplanes_demo.
# Warehouse runtime's Anaconda channel doesn't include relationalai, so
# container runtime is required for PyRel-using notebooks. Headless
# `snow notebook execute` then needs a compute pool grant; the normal
# demo flow is: user opens the notebook in Snowsight, adds plotly +
# networkx via the Packages panel on first open, clicks Run All.
# IDLE_AUTO_SHUTDOWN_TIME_SECONDS = 1800 = 30 min matches the named
# engine idle setting so the demo session stays warm.
snow sql -c "$CONN" --role "$ROLE" -q "
USE DATABASE $DB; USE SCHEMA $NB_SCHEMA;
CREATE OR REPLACE NOTEBOOK $DB.$NB_SCHEMA.$NB_NAME
  FROM '@$DB.$NB_SCHEMA.$NB_STAGE/$NB_FOLDER'
  MAIN_FILE = '$NB_MAIN'
  QUERY_WAREHOUSE = RAI_XS
  COMPUTE_POOL = CARS_DEMO_NB_POOL
  RUNTIME_NAME = 'SYSTEM\$BASIC_RUNTIME'
  IDLE_AUTO_SHUTDOWN_TIME_SECONDS = 1800
  COMMENT = 'OEM fleet recall propagation - 5-act PyRel demo. Stage folder: $NB_FOLDER/';
" >/dev/null

echo "==> [4/4] ALTER NOTEBOOK ADD LIVE VERSION FROM LAST"
snow sql -c "$CONN" --role "$ROLE" -q "
USE DATABASE $DB; USE SCHEMA $NB_SCHEMA;
ALTER NOTEBOOK $DB.$NB_SCHEMA.$NB_NAME ADD LIVE VERSION FROM LAST;
"

echo "==> Done. Open in Snowsight: Notebooks -> $DB -> $NB_SCHEMA -> $NB_NAME"
