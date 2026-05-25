# CLAUDE.md - project orientation for the CARS_DEMO recall-propagation demo

Entry point for anyone (Claude or human) opening this repo cold. The
narrative spine is [CARS_TALK_TRACK.md](CARS_TALK_TRACK.md); this file
links the moving parts.

## What this is

A RelationalAI demo of OEM fleet recall propagation. Internal
customer: BMW. Audience-facing framing: "a major European luxury OEM"
(see [BRIEF.md](BRIEF.md) > Naming convention - the wrapper is
notionalised, the data inside the tables stays BMW-realistic).

A single `cars` PyRel ontology over `CARS_DEMO.FLEET` backs four
reasoners plus a Snowflake Intelligence agent:

| Act | Reasoner       | Question                                                                  |
|-----|----------------|---------------------------------------------------------------------------|
| 1   | Rules          | Recall SLA compliance audit (severity Code 1/2 past completion window)    |
| 2   | Graph          | Defect cascade from Continental MK C1 brake-booster (supplier -> VIN)     |
| 3   | Heuristic      | Per-VIN urgency ranking, top 20                                           |
| 4   | Prescriptive   | MIP assigns 121 Open jobs to 15 centres over 4 weeks (HiGHS)              |
| 5   | Persistent rule | Operator adds 'prioritise prior-accident VINs' rule; ontology stores it; MIP re-solves |

The data, rules, graph edges, optimization model, and the Cortex agent
all reference the same `cars` model. The persistent rule in Act 5 is
~10 lines of PyRel that propagate to every downstream reasoner.

## Repository layout

```
.
├── CARS_TALK_TRACK.md                      # 20-minute speaker script
├── DEMO_QUESTIONS.md                       # 5 acts as plain-English Qs
├── SNOWSIGHT_DEMO.md                       # 10-minute Cortex agent variant
├── HANDOFF_BRIEFING.md                     # design rationale + open questions
├── BRIEF.md                                # demo spec (locked at intake)
├── RUNNING.html                            # speaker runbook with embedded figures
├── DATA_DICTIONARY.md                      # auto-generated from annotate_and_doc.py
├── prep_demo.py                            # pre-flight gate (run 10 min before showtime)
├── build_runbook.py                        # renders RUNNING.html from RUNBOOK.template.html
├── data/
│   ├── 00_bootstrap.sql                    # one-time: RAI_DEMO_CARS role + CARS_DEMO database
│   ├── 01_cortex_grants.sql                # one-time: Cortex agent deployer grants
│   ├── seed/                               # the two real BMW CSVs + the .tds
│   ├── build_cars_demo_data.py             # seed=42 generator (suppliers, BOM, recall layer)
│   ├── load_to_snowflake.sh                # idempotent loader
│   ├── annotate_and_doc.py                 # COMMENTs + tags + DATA_DICTIONARY.md
│   ├── upload_snowsight_notebook.sh        # PUT + CREATE NOTEBOOK
│   └── out/                                # generated DDL / reference / CSVs / validation SQL
├── rai_code/
│   └── manual/
│       ├── cars.py                         # THE ontology (15 concepts + derived rules)
│       ├── demo_queries.py                 # 5 act queries (Q1-Q5)
│       ├── cars_demo.ipynb                 # local Jupyter notebook (executed)
│       └── cars_demo_snowsight.ipynb       # Snowsight variant
├── agent/
│   ├── deploy.py                           # CortexAgentManager wrapper + CLI
│   └── queries.py                          # QueryCatalog with chart hints
├── build/
│   ├── generate_demo_figures.py            # produces PNGs for RUNNING.html
│   └── figures/                            # act1..act5 PNGs (regenerate before a demo)
└── .venv/                                  # uv venv, Python 3.13
```

## Snowflake state

- Connection: `snow` profile `rai`, account `ajb85638`.
- Demo role: `RAI_DEMO_CARS` (created by `data/00_bootstrap.sql`).
  Every `snow sql` call passes `--role RAI_DEMO_CARS` explicitly. The
  one exception is `data/01_cortex_grants.sql` which grants the
  deployer (ACCOUNTADMIN) the Cortex perms - run via the rai default
  profile.
- Warehouse: `RAI_XS` (auto-resume, ~5s).
- Database: `CARS_DEMO`. Schemas:
  - `CARS_DEMO.FLEET`: 14 source tables (vehicles, owners, recalls,
    BOM, capacity, parts stock). 325 vehicles, 762 service events.
  - `CARS_DEMO.RAI_AGENT`: Cortex agent sprocs + stage.
  - `CARS_DEMO.NOTEBOOKS`: Snowsight notebook + stage.
  - `CARS_DEMO.META`: classification tags (DATA_DOMAIN, TABLE_ROLE,
    GRAIN, DEMO_AREA).
- Change tracking enabled on every source table (PyRel CDC).
- The Cortex agent is registered in `SNOWFLAKE_INTELLIGENCE.AGENTS`
  as `cars`. SNOWFLAKE_INTELLIGENCE was created at deploy time
  (Snowflake doesn't auto-create it on this account).

## Reasoner engines

- `cars_logic_l` (HIGHMEM_X64_L) - rules + graph + heuristic + ad-hoc queries.
- `cars_prescriptive_m` (HIGHMEM_X64_M) - LP/MIP (Acts 4 and 5).

Both are named so they persist across runs. Configured in
`rai_code/manual/cars.py` (`_build_config()`) and referenced by the
Cortex agent at runtime - the same warm engines back the notebook AND
the deployed agent.

## How to run

```bash
# Pre-flight gate (run 10 min before showtime; resumes engines,
# validates anchored numbers, smokes Q1-Q5, checks the agent).
.venv/bin/python prep_demo.py

# Smoke-test the ontology + all 5 queries (no agent, no notebook):
.venv/bin/python rai_code/manual/demo_queries.py

# Run the local notebook (Plotly + Sankey):
.venv/bin/jupyter lab rai_code/manual/cars_demo.ipynb

# Cortex agent lifecycle:
.venv/bin/python -m agent.deploy preflight                 # probe grants
.venv/bin/python -m agent.deploy setup-sql --deployer-role ACCOUNTADMIN
.venv/bin/python -m agent.deploy deploy                    # create
.venv/bin/python -m agent.deploy chat "How many SLA-breached recalls?"
.venv/bin/python -m agent.deploy status
.venv/bin/python -m agent.deploy teardown                  # remove (WARNS about SI history loss)

# Regenerate figures for RUNNING.html:
.venv/bin/python build/generate_demo_figures.py
.venv/bin/python build_runbook.py

# Upload Snowsight notebook:
bash data/upload_snowsight_notebook.sh
```

## Timing (measured warm; cold adds 5-10 min for engine resume)

| Stage | Warm |
|---|---|
| `snow` connection test | <1s |
| Row-count + anchored-number validation (12 tables + 6 sentinels) | ~10s |
| Resume `cars_logic_l` (already READY) | 0s |
| Resume `cars_prescriptive_m` (already READY) | 0s |
| Q1 SLA audit | ~5s |
| Q2 Continental cascade | ~3s |
| Q3 urgency top-20 | ~5s |
| Q4 MIP solve | ~0.5s |
| Q5 MIP re-solve | ~0.5s |
| `prep_demo.py` end-to-end (warm) | ~3 min |

Cold start (both engines suspended at start of day) adds ~5 min for
the prescriptive engine first-use plus ~3-5 min for the logic engine.

## Anchored numbers

These reproduce exactly under `data/out/cars_demo_validation.sql`. If
the gate is green, all of these are live.

| Metric | Value |
|---|---|
| Vehicles | 325 |
| Service events | 762 |
| Owners | 282 |
| BOM edges (vehicle x bom_node) | 531 |
| Recall assignments total | 254 |
| Open recalls | 121 |
| SLA-breached Open (Act 1 total) | 19 |
| SLA-breached by campaign | IBS 8, HVB 7, EGR 3, AIRBAG 1 |
| Continental MK C1 cascade (Act 2) | 67 VINs |
| Regional rollup (Act 2) | EU 53, NA 12, LATAM 2 |
| Priority VINs (Act 5: Open recall + prior accident) | 15 |
| Recall campaigns | 5 |
| Service centres | 15 |
| Suppliers | 11 |

## Conventions and gotchas

- **No em-dashes anywhere.** Use "-" or commas.
- **Synthetic-data wrapper, real data inside.** Snowflake objects, repo
  files, Cortex agent name are all generic ("cars"). The data inside
  the tables uses real BMW WMIs, real model designators (G21 LCI, U11,
  G87), real Tier-1 supplier names (Continental, Bosch, Samsung SDI,
  BorgWarner, Joyson) because the audience is BMW industry experts.
- **`_build_config()`** auto-detects Snowsight vs local. Same notebook
  file can run in both with different cell-1 imports
  (`cars_demo.ipynb` for local, `cars_demo_snowsight.ipynb` for SI).
- **JobAssignment-only LP arithmetic.** The prescriptive rewriter in
  PyRel 1.7.1 fails on `decision_var * OtherConcept.property` inside
  `aggs.sum()`. Workaround: precompute coefficients (`labour_hours`,
  `urgency`, `week_index`) as Properties on JobAssignment itself. See
  the bottom of `rai_code/manual/cars.py`.
- **Subtype predicates in `problem.satisfy()` trigger a rewriter bug.**
  Workaround: filter by the underlying status/property (e.g.
  `_r.status == "Open"` instead of `OpenRecall(_r)`). Same applies to
  PriorityVehicle: filter via the materialised `priority_flag` Property
  on RecallAssignment.
- **Engine naming matters.** Named engines persist across sessions;
  nameless engines tear down between runs. Both reasoners are named.
- **Talk-track Act 3 is heuristic, not GNN.** The Predictive reasoner
  is preview. The score is a deterministic weighted sum living on the
  ontology as `RecallAssignment.urgency`. Talk track explicitly
  authorises this fallback.

## Where to look when something breaks

- Validation SQL: `data/out/cars_demo_validation.sql`. Run against
  Snowflake to confirm anchored numbers are intact.
- Smoke test: `.venv/bin/python rai_code/manual/demo_queries.py` runs
  all 5 queries and prints results.
- Agent status: `.venv/bin/python -m agent.deploy status`.
- Engine state: `.venv/bin/rai reasoners list | grep -i cars`.
- Snowflake metadata: `SHOW TAGS IN SCHEMA CARS_DEMO.META`. If
  missing, re-run `data/annotate_and_doc.py`.
- Stuck or wrong numbers: `bash data/load_to_snowflake.sh` rebuilds
  from seed=42; reproduces exactly.

## Open follow-ups (deferred)

- Tighten the Act 4 / Act 5 contrast. Currently both solve to
  obj=0.67 because most jobs already fit in week 1; the priority
  rule is non-binding. Reduce IBS-2024-A or HVB-2024-A parts stock
  per centre per week to push more jobs into week 2-4 in Act 4.
- Swap notional recall campaign IDs for actual NHTSA/KBA campaign
  IDs once the demo audience is known.
- Validate seed VIN check-digits (position 9) against ISO 3779 mod-11.
- Tune the agent description to fit within EXPLAIN payload budget (a
  single cosmetic preflight warning today).
