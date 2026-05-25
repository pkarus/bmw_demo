# SNOWSIGHT_DEMO.md - Cortex Agent variant

10-minute demo variant that lives entirely inside Snowsight. Three
questions, agent UI focus. Use this when the audience is
non-technical or you only have the room for one screen-share.

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
