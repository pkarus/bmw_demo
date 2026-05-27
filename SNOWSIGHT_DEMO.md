# SNOWSIGHT_DEMO.md - Cortex Agent variant + browser-based e2e verification

10-minute demo variant that lives entirely inside Snowsight. Three
questions, agent UI focus. Use this when the audience is
non-technical or you only have the room for one screen-share.

## E2E verification flow (the user's browser, ~5 min)

This is the canonical "does it work in Snowflake" check. Two URLs to
hit, both on `app.snowflake.com/NDSOEBE/rai_sales_engineering_aws_us_west_2`:

1. **The notebook** at
   <https://app.snowflake.com/NDSOEBE/rai_sales_engineering_aws_us_west_2/#/notebooks/CARS_DEMO.NOTEBOOKS.CARS_DEMO>.
   - First open: click **Packages** in the toolbar and add `plotly`,
     `networkx`, and `relationalai==1.7.1`. The container runtime (the
     same one airplanes_demo uses) doesn't auto-resolve these.
   - Click **Run All**. Engine resume + Q4 / Q5 / Q7 solves take
     ~3-5 minutes warm; ~10 min cold.
   - Expected: Act 1 shows 19 SLA breaches, Act 2 shows 67 Continental
     cascade VINs, Act 3 top 20 dominated by Regensburg X1 M35i with
     prior collisions, Act 4 + Act 5 OPTIMAL at obj=0.67, Act 2b shows
     4 Louvain communities over 190 VINs.

2. **The Cortex agent** at **AI & ML > Agents > CARS_DEMO.RAI_AGENT >
   cars** (or via the Snowflake Intelligence picker if the
   account-wide SI catalog is enabled).
   - Open the Chat tab. Try the three questions from the next section.
   - Each round-trip is ~60-90 s warm. The first cold question
     resumes both `cars_logic_l` and `cars_prescriptive_m` and runs
     ~3 min.
   - Smoke verified end-to-end on 2026-05-25 - the agent returned the
     19 SLA-breaches with the exact per-campaign breakdown (IBS 8,
     HVB 7, EGR 3, AIRBAG 1) and the NHTSA 49 CFR 577 / KBA framing.

If neither the notebook nor the agent surfaces in the UI, the
underlying RAI sprocs in `CARS_DEMO.RAI_AGENT` still work via raw SQL:
`CALL CARS_DEMO.RAI_AGENT.RAI_DISCOVER_MODELS();` returns the model
catalog.

## Engine settings (set durable; safe to ignore unless you're tuning)

- Both engines (`cars_logic_l`, `cars_prescriptive_m`) have
  `auto_suspend_mins = 30`. Set once via
  `.venv/bin/rai reasoners alter --name <engine> --type <Logic|Prescriptive> --auto-suspend-mins 30`.
- The Snowsight notebook has `IDLE_AUTO_SHUTDOWN_TIME_SECONDS = 1800`
  (30 min). Set on each `CREATE OR REPLACE NOTEBOOK` by the upload
  script.
- All three idle settings line up so a single 30-min coffee break
  doesn't tear the warm session down.


## Prerequisites

- Snowflake Intelligence enabled on the account (Snowsight UI:
  `Studio -> Intelligence`).
- `cars` Cortex agent deployed (see Phase 7).
- Cars `cars_logic_l` and `cars_prescriptive_m` engines READY.

If Snowflake Intelligence is not provisioned on `ajb85638`, the agent
can still be queried via `.venv/bin/python -m agent.deploy chat
"<question>"` from a laptop terminal. The UX is lower but the answers
are identical.

## Setup (5 minutes before the demo)

1. Snowsight: open the `cars` agent under Studio -> Intelligence.
2. Confirm both engines are READY in the RAI Native App panel.
3. Optional: pre-warm by sending a "hi" message and waiting for the
   ack. This shaves the first-question latency.

## The three questions

These are the same Acts 1, 2, 4 from the full talk track, abbreviated
to the cleanest single-shot phrasings.

### Q1: SLA audit

> "Which open recalls are past their completion window? Show me the
> count by campaign."

Expected answer: a 4-row table.
- IBS-2024-A: 8 breached
- HVB-2024-A: 7
- EGR-2023-B: 3
- AIRBAG-2022-A: 1

What lands: a question that would take 6 SQL joins surfaced in
natural language against the same ontology.

### Q2: Cascade

> "Continental flagged a defect in the MK C1 brake booster ECU. Show
> me every VIN affected, broken down by region."

Expected answer:
- Total: 67 VINs
- EU: 53
- NA: 12
- LATAM: 2

What lands: the cross-system join (supplier -> part -> BOM ->
vehicle -> owner -> region) executed by a single natural-language
question.

### Q3: MIP schedule (the longest one)

> "Schedule the next four weeks of open recall jobs to service
> centres. Minimise urgency-weighted lateness, respect tooling
> certifications and parts stock. How many jobs deferred past week 4?"

Expected answer: ~10-20 jobs deferred, driven by parts stock on
IBS-2024-A. Solve runs in 60-90 seconds.

What lands: a MIP solver invoked from natural language with
constraints that reference the ontology, not hardcoded numbers.

## Fallback if the agent is unreachable

Pivot to the local Jupyter notebook
(`rai_code/manual/cars_demo.ipynb`). The same three questions live
in cells with explanatory markdown and pre-rendered Plotly figures.

## What to NOT do in this variant

- Don't add Act 5 (persistent rule) - it does not yet round-trip
  cleanly through the agent UI. Save it for the full notebook
  variant.
- Don't ask follow-up clarifications across questions - the agent's
  conversation memory is single-turn for now. State the question
  fully each time.
- Don't paste the SQL the agent generates back to the audience.
  Some of it references RAI internal stored procedures and will not
  resolve to plain Snowflake objects.

## Closing

> "These three questions, all from natural language, all hitting one
> ontology with three reasoners underneath. The campaign manager
> never opens a notebook."
