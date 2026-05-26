# HANDOFF_BRIEFING.md - OEM fleet recall demo

A walk-on briefing for the next agent run or human SE who picks this
demo up cold. Read once; you should be able to run the talk track
from the runbook plus the prep gate without asking anyone questions.

## What this is

A five-act RelationalAI demo built on the airplanes_demo shape but
applied to vehicle-fleet recall propagation. Internal customer: BMW.
Audience-facing framing: "a major European luxury OEM" (see
[BRIEF.md](BRIEF.md) > Naming convention - the wrapper is
notionalised, the data inside the tables stays BMW-realistic).

The arc:
1. Rules - SLA audit for Open recalls past completion window.
2. Graph - cascade from a Tier-1 supplier defect to all affected VINs.
3. Heuristic - per-VIN urgency ranking on the open population.
4. Prescriptive - MIP assigns recall jobs to centres x weeks.
5. Persistent rule - operator-added priority rule re-solves the MIP.

## Snowflake objects

- Account: `ajb85638` (Snowflake SE US).
- Demo role: `RAI_DEMO_CARS`. Created by `data/00_bootstrap.sql`.
  Granted to user `piotr.kraus@relational.ai` and to SYSADMIN. The
  role can do anything in `CARS_DEMO` and nothing outside it.
- Database: `CARS_DEMO`. Owned by `RAI_DEMO_CARS`.
- Schemas:
  - `CARS_DEMO.FLEET` - 14 source tables (vehicles, owners, recalls,
    BOM, capacity, parts stock). Source of truth for the ontology.
  - `CARS_DEMO.RAI_AGENT` - the Cortex agent and its stored procedures
    (created by Phase 7's `agent/deploy.py`).
  - `CARS_DEMO.NOTEBOOKS` - Snowsight notebook + stage (Phase 6).
  - `CARS_DEMO.META` - `DATA_DOMAIN`, `TABLE_ROLE`, `GRAIN`,
    `DEMO_AREA` tags applied to every table.
- Warehouse: `RAI_XS` (auto-resume). Demo role has USAGE + OPERATE.
- RAI engines:
  - `cars_logic_l` - `HIGHMEM_X64_L` - rules / graph / heuristic.
  - `cars_prescriptive_m` - `HIGHMEM_X64_M` - LP/MIP.

## What's where in the repo

```
.
├── BRIEF.md                   demo spec (locked at intake)
├── DEMO_QUESTIONS.md          5 acts in plain English with reasoner tags
├── CARS_TALK_TRACK.md         20-minute speaker script
├── SNOWSIGHT_DEMO.md          shorter Cortex-agent-focused variant
├── HANDOFF_BRIEFING.md        this file
├── RUNNING.html               speaker-facing runbook with embedded figures
├── DATA_DICTIONARY.md         generated from data/annotate_and_doc.py
├── prep_demo.py               pre-flight gate (run 10 min before showtime)
├── data/
│   ├── 00_bootstrap.sql       once-only role + DB bootstrap (security harness)
│   ├── seed/                  BMW_VEHICLES_V1.csv + ..._SERVICES.csv + .tds
│   ├── build_cars_demo_data.py   synthetic generator (parts, BOM, suppliers,
│   │                              campaigns, owners, capacity, stock)
│   ├── load_to_snowflake.sh   loader (CSV PUT + COPY INTO)
│   ├── annotate_and_doc.py    COMMENTs + tags + DATA_DICTIONARY.md
│   └── out/                   generated artefacts (DDL, reference SQL, CSVs)
├── rai_code/
│   └── manual/
│       ├── cars.py            the PyRel ontology (15 concepts + derived rules)
│       ├── demo_queries.py    Q1..Q5 implementations
│       └── cars_demo.ipynb    local Jupyter notebook (Plotly + Sankey)
├── agent/                     Cortex agent (Phase 7)
└── build/
    └── figures/               static PNGs for RUNNING.html (Phase 8)
```

## Anchored numbers (every cell reproduces from raw SQL)

| Anchor | Value | SQL backing |
|---|---|---|
| Vehicles | 325 | `SELECT COUNT(*) FROM CARS_DEMO.FLEET.vehicle` |
| Service events | 762 | `SELECT COUNT(*) FROM CARS_DEMO.FLEET.service_event` |
| Owners | 282 | `SELECT COUNT(*) FROM CARS_DEMO.FLEET.owner` |
| BOM edges (vehicle x bom_node) | 531 | `SELECT COUNT(*) FROM CARS_DEMO.FLEET.bom_membership` |
| Recall assignments total | 254 | `SELECT COUNT(*) FROM CARS_DEMO.FLEET.recall_assignment` |
| Open recalls | 121 | `WHERE status='Open'` |
| SLA-breached Open (Act 1) | 19 | `WHERE status='Open' AND sla_breached=TRUE` |
| IBS-2024-A breaches | 8 | + `campaign_id='IBS-2024-A'` |
| HVB-2024-A breaches | 7 | + `campaign_id='HVB-2024-A'` |
| Continental MK C1 cascade (Act 2) | 67 VINs | `SUP-CONT` -> `PRT-IBS-ECU` -> BOM -> VIN |
| Regional rollup (Act 2) | EU 53, NA 12, LATAM 2 | + `dim_region` join |
| Priority VINs (Act 5) | 15 | Open recall + `accident_type IS NOT NULL` |
| Recall campaigns | 5 | `dim_recall_campaign` |
| Service centres | 15 | `dim_service_centre` |
| Suppliers | 11 | `dim_supplier` |
| Parts | 19 | `dim_part` |
| BOM nodes | 11 | `dim_bom_node` |
| Act 2b: vehicle cohort communities (Louvain) | structure stable; labels non-deterministic | `q7_vehicle_communities()` - graph-reasoner output |

`data/out/cars_demo_validation.sql` reproduces every anchor as a
standalone SQL query. `prep_demo.py` asserts all six talk-track
sentinels and exits non-zero if any drift.

The vehicle-cohort graph (Act 2b) adds a Graph-reasoner perspective on
the same data: vehicles connected by shared BOM nodes, Louvain
communities identify natural cohorts. Not an anchored number because
Louvain is non-deterministic, but the graph structure (number of
communities, dominant model per community) is stable. The notebook
renders this as a force-directed Plotly figure with nodes coloured by
community, sized by degree, and hover-rich (VIN, model, plant, fuel,
mileage, campaigns, open recalls, accident history).

## Domain choices and why

- **Notionalised wrapper, realistic data.** The audience is BMW
  industry experts. Scrubbing VINs to fake formats would have been a
  one-second tell. Decision: keep VINs / model designators / plant
  names / supplier names BMW-grade, notionalise only the wrapper
  (Snowflake objects, repo files, Cortex agent name, slide labels).
  See [BRIEF.md](BRIEF.md) > Naming convention.

- **MIP assignment over knapsack for Act 4.** The knapsack
  alternative (pick recall waves under a fixed weekly tech-hour
  budget) is one-dimensional and exhausts after Act 3. Assignment
  exposes 3 binding constraint families (technician hours, parts
  stock, tooling certification) and gives Act 5 a fourth-constraint
  attachment point.

- **Heuristic over GNN for Act 3.** The Predictive reasoner is
  preview. A deterministic weighted urgency score reproduces every
  time, runs in milliseconds, and is defensible to insurance and
  compliance reviewers. Same decision airplanes_demo made.

- **Coefficient materialisation on JobAssignment.** The prescriptive
  rewriter has a known bug where `decision_var * OtherConcept.property`
  inside an `aggs.sum()` fails with `AttributeError: 'Concept' object
  has no attribute '_short_name'`. Workaround: precompute the
  coefficients (urgency, labour_hours, week_index) as Properties on
  the same Concept the decision variable lives on (JobAssignment).
  Defined as derived rules in `rai_code/manual/cars.py` at the
  bottom. Workaround can be lifted if PyRel fixes the rewriter.

- **Source schema named `FLEET` not `DFA`.** The customer's existing
  Tableau workbook (`data/seed/BMW_FLEET_ANALYSIS.tds`) points at
  `BMW_DEMO.DFA` on `sfseeurope-demo531`. We notionalised: schema is
  `FLEET` (brand-neutral, operational). A `CREATE VIEW DFA.* AS
  SELECT * FROM FLEET.*` line can be added if the customer wants
  their .tds to point at our objects without changes.

- **Run on ajb85638, not sfseeurope-demo531.** The user's
  `~/.snowflake/connections.toml` has no sfseeurope-demo531 profile.
  Adding one is out of scope for an autonomous agent run. To migrate
  to BMW's EMEA SE account: provision the demo role + DB there, run
  the loader against that connection, redeploy the Cortex agent.
  ~4 commands total.

## User preferences observed during the build

- **No em-dashes anywhere.** Use "-" or commas; the user dislikes
  em-dashes in generated docs.
- **No emojis** in code or docs.
- **Notionalise the wrapper, keep the data realistic.** Confirmed
  during intake.
- **Audience is BMW experts.** Don't simplify the model designators
  or invent fake plant codes. The talk track says "a major OEM" but
  the data shows G21 LCI, U11, S58 etc.

## Known limitations and open questions

- **Real recall campaign IDs are notional.** The 5 campaigns
  (IBS-2024-A, HVB-2024-A, EGR-2023-B, AIRBAG-2022-A, STARTER-2024-A)
  are narrative-faithful but not pulled from NHTSA or KBA databases.
  Before customer demo, the next agent / human should swap in actual
  current campaign IDs from
  https://www.nhtsa.gov/recalls and https://www.kba-online.de/rueckrufe/.

- **Snowflake Intelligence on ajb85638 is not provisioned.** Phase 7
  agent registration requires `SNOWFLAKE_INTELLIGENCE.AGENTS`. The
  bootstrap SQL has the grant block commented out; uncomment and run
  the 4 grant lines if SI becomes available. Otherwise the agent
  works via `agent.deploy chat` CLI but does not surface in the
  Snowsight SI picker.

- **VIN check-digit (position 9) not validated against ISO 3779 mod-11.**
  Seed VINs are `WBA0000...` with synthetic serial portions. A pedant
  could compute the check digit and notice they fail. Acceptable
  given the synthetic-data disclaimer; replace with real BMW VINs if
  the customer asks.

- **Service-centre tooling certifications are assigned deterministically.**
  Munich, Cologne, Frankfurt, Hamburg, Stuttgart, Spartanburg, NYC,
  LA, Dallas, Miami get HV certification (the centres that handle
  the largest EV fleets). IBS certification is broader (12 of 15).
  Body shop is the narrowest (9 of 15). Monterrey lacks both HV and
  IBS - this is what makes Act 4 leave some jobs unscheduled. All
  assumptions documented in
  `data/build_cars_demo_data.py` around line 96.

## How to break it (failure modes and recovery)

- **Engine fails to resume.** Both engines are named; if `cars_logic_l`
  or `cars_prescriptive_m` is stuck in SUSPENDED for over 10 minutes,
  delete and let PyRel recreate:
  ```
  .venv/bin/rai reasoners delete cars_logic_l
  .venv/bin/rai reasoners delete cars_prescriptive_m
  ```
  Next run will recreate them. Adds 5-8 minutes cold.

- **Q4/Q5 returns INFEASIBLE.** Parts stock too tight. Check
  `parts_stock` table; if some campaign has zero stock at every
  centre x week, the LP can't place the campaign's jobs. Regenerate
  with `seed=42`:
  ```
  .venv/bin/python data/build_cars_demo_data.py
  bash data/load_to_snowflake.sh
  ```

- **Numbers drift.** Run `prep_demo.py` cold. If any anchored number
  is off, regenerate the data (as above). The `seed=42` reproduces
  exactly.

- **Cortex agent dies mid-demo.** Fall back to `.venv/bin/python -m
  agent.deploy chat "<question>"` from the laptop. Slow (~90s per
  answer) but functional. The agent code is at `agent/deploy.py`.

## Where to look when things break

- Snowflake errors: `snow sql --role RAI_DEMO_CARS -c rai -q ...`. Don't
  use the default profile role - it's broader than the demo needs.
- Engine errors: `.venv/bin/rai reasoners list` and look for cars
  engines. State should be READY before any query.
- PyRel errors: import `cars` first to load the ontology, then run
  the failing query in isolation. The ontology has 15 concepts and
  ~6 derived rules; if anything looks off in driver counts, check
  `data/out/cars_demo_validation.sql` against Snowflake.
- Snowflake metadata: `SHOW TAGS IN SCHEMA CARS_DEMO.META`. If tags
  are missing, re-run `data/annotate_and_doc.py`.

## What I would change next

1. Swap in real NHTSA / KBA campaign IDs for the 5 narrative
   campaigns.
2. Re-validate seed VIN check-digits (positions 9) against ISO 3779
   mod-11 and re-generate the VINs that fail.
3. Add Snowflake Intelligence grants once available on ajb85638.
4. Build a `data/reset_engines.sh` one-liner that suspends-deletes-
   recreates both engines (Currently has to be done by hand via
   `rai reasoners delete`).
5. Add a `SNOWSIGHT_MIGRATION.md` describing the 4 commands to lift
   the demo to BMW's EMEA SE account.
