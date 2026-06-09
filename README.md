# OEM Fleet Recall-Propagation Demo

A RelationalAI demo of OEM fleet recall propagation, built for a BMW audience
("a major European luxury OEM" in the audience-facing framing). A single `cars`
PyRel ontology over `CARS_DEMO.FLEET` on Snowflake (325 vehicles, 762 service
events) backs four reasoner families plus a persistent rule, and the same model
is served through a Snowflake Intelligence (Cortex) agent. The data, the rules,
the graph edges, the optimization model, and the agent all reference one `cars`
model, so the operator rule added in Act 5 is about ten lines of PyRel that
propagate to every downstream reasoner.

## The five acts

| Act | Reasoner        | Question                                                                  |
|-----|-----------------|---------------------------------------------------------------------------|
| 1   | Rules           | Recall SLA compliance audit (severity Code 1/2 past the completion window)|
| 2   | Graph           | Defect cascade from the Continental MK C1 brake-booster (supplier to VIN) |
| 3   | Heuristic       | Per-VIN urgency ranking, top 20                                           |
| 4   | Prescriptive    | MIP assigns 121 Open jobs to 15 service centres over 4 weeks (HiGHS)      |
| 5   | Persistent rule | Operator adds a "prioritise prior-accident VINs" rule; the ontology stores it and the MIP re-solves |

## Run it

```bash
# Pre-flight gate (run ~10 min before a demo): resumes the RAI engines,
# validates the anchored numbers, smokes Q1-Q5, and checks the SI agent.
.venv/bin/python prep_demo.py

# Smoke-test the ontology and all 5 act queries:
.venv/bin/python rai_code/manual/demo_queries.py

# Local notebook (Plotly + a supplier-to-VIN Sankey):
.venv/bin/jupyter lab rai_code/manual/cars_demo.ipynb

# Cortex agent in Snowflake Intelligence:
.venv/bin/python -m agent.deploy deploy
.venv/bin/python -m agent.deploy chat "How many SLA-breached recalls?"
```

For a no-setup overview, open [RUNNING.html](RUNNING.html) in any browser: a
self-contained run map with every act figure embedded.

## What's in here

```
CARS_TALK_TRACK.md                 the 20-minute speaker script
DEMO_QUESTIONS.md                  the 5 acts as plain-English questions
SNOWSIGHT_DEMO.md                  10-minute Cortex agent variant
BRIEF.md                           the demo spec (locked at intake)
prep_demo.py                       the pre-flight gate
rai_code/manual/
  cars.py                          the PyRel ontology (15 concepts + derived rules)
  demo_queries.py                  the 5 act queries
  cars_demo.ipynb                  local notebook
  cars_demo_snowsight.ipynb        Snowsight notebook
agent/
  deploy.py, queries.py            Cortex agent deploy + the query catalog
data/
  00_bootstrap.sql                 one-time: RAI_DEMO_CARS role + CARS_DEMO database
  build_cars_demo_data.py          deterministic generator (seed=42)
  load_to_snowflake.sh             idempotent loader
  annotate_and_doc.py              Snowflake metadata + DATA_DICTIONARY.md
  out/                             generated DDL / reference / validation SQL
build/generate_demo_figures.py     result figures for RUNNING.html
```

[CLAUDE.md](CLAUDE.md) is the full orientation: Snowflake state, the scoped
`RAI_DEMO_CARS` role, reasoner engine names and sizes, measured timings, the
anchored demo numbers, and the PyRel rewriter workarounds used in the
formulation.

## The data

325 vehicles and 762 service events, generated deterministically (seed=42) and
loaded into `CARS_DEMO.FLEET` on the sales-engineering Snowflake account.
Anchored numbers (19 SLA-breached Open recalls, a 67-VIN Continental cascade, 15
priority VINs, and so on) reproduce exactly from
`data/out/cars_demo_validation.sql`. Recreate the dataset with
`bash data/load_to_snowflake.sh`.

## Requirements

- A `rai` connection profile in `~/.snowflake/connections.toml` (account
  `ajb85638`, warehouse `RAI_XS`) and the RelationalAI Native App installed on
  the account.
- Python 3.13 and [uv](https://docs.astral.sh/uv/); the `snow` CLI.
- One-time: review and run `data/00_bootstrap.sql` (creates the scoped role
  `RAI_DEMO_CARS` and the `CARS_DEMO` database), then
  `bash data/load_to_snowflake.sh`.

## Note

This is a sales-engineering demo. The Snowflake objects, repo files, and Cortex
agent use a generic "cars" wrapper; the values inside the tables are
BMW-realistic (real WMIs, model designators, and Tier-1 supplier names) because
the audience knows the domain, but the dataset is synthetic and is not BMW
operational data.
