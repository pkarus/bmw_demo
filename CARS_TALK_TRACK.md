# OEM Fleet Recall Propagation - Talk Track

20-minute speaker script for the five-act demo on `CARS_DEMO.FLEET`.
Internal customer: BMW. Audience-facing framing: "a major European
luxury OEM." See [BRIEF.md](BRIEF.md) > Naming convention. The data
inside the tables is realistic (real BMW WMIs, real model designators,
real Tier-1 supplier names) so the room can read concrete details
without ever seeing "BMW" on a slide.

## Opening (90 seconds)

> A defect notice from a Tier-1 supplier arrives on a Tuesday morning.
> By the end of the day, the after-sales head needs to know how many
> VINs are affected, which owners we have to write to, which service
> centres are about to be overrun, and whether we can finish the work
> before the regulator's completion window expires. Today this
> conversation happens across six systems: AIR for the supplier-to-part
> mapping, iLEAD for the part-to-VIN cohort, the dealer-network
> database for centre capacity, a spreadsheet for parts logistics,
> a separate spreadsheet for owner notification waves, and someone's
> head for the institutional rule that says VINs with a prior
> collision get pulled first.
>
> RelationalAI is one ontology over the same data, with five reasoners
> that share it. I'm going to show you five questions you cannot
> answer in a single SQL query, and one that you cannot answer in any
> sequence of SQL queries.

## Act 1 - Rules: recall SLA compliance audit (3 minutes)

**The question.** "Show me every Open recall on a VIN whose owner-
notification age has breached the campaign's completion window. Break
it out by campaign and by responsible centre."

**The expected answer.** 19 SLA-breached Open recalls across 4
campaigns. Continental MK C1 brake-booster firmware leads (8 cases),
Samsung SDI HV battery thermal next (7 cases, severity Code 1),
BorgWarner EGR cooler (3), Joyson airbag (1). By centre: BMW Munich
Service is most exposed because it owns the high-volume IBS firmware
work; Spartanburg next.

**What lands.** "The SQL for this is easy. Why is it on slide 1?"
Because the rule is in the ontology. `SLABreachedRecall` is a derived
concept: `Open AND age_days_at_demo > completion_days AND severity <= 2`.
Now watch what happens to it in Act 5 - when the operator adds a rule,
this audit reflects it without anyone re-writing the SQL.

**Speaker note - what if the count is wrong?** It will be exactly 19
on a clean load (verify via `prep_demo.py`). If you see a different
number, the data has drifted; run `bash data/load_to_snowflake.sh`
fresh and the seed=42 generator reproduces it.

## Act 2 - Graph: defect cascade (4 minutes)

**The question.** "Continental notified us this morning of an expanded
scope on the MK C1 brake-booster firmware defect. Walk the cascade:
supplier -> part -> bom node -> VIN -> owner -> service centre. Roll
up by region. Who do we have to notify, and where do they go?"

**The expected answer.** 67 affected VINs across three plant-date
cohorts: Munich (G21 LCI, G87, G26 from 2022-2024), Regensburg (X1
M35i, U11, iX1 from 2022-2024), Spartanburg (X1, iX1 from 2022-2024).
Regional rollup: EU dominant, NA second, LATAM minimal. Top centres
by exposure: Munich, Cologne, Hamburg.

**What lands.** Today this is a six-system join done by an analyst
who knows BMW AIR. With the ontology, it's six lines of PyRel. The
audience-natural moment: zoom into the Sankey diagram and point at
the Munich plant -> Cologne service centre edge. "This is the
operations call the dealer-network team has to make this week."

**Speaker note - if the audience asks "what if Continental expands
the part list".** Change the `part_id` argument from `PRT-IBS-ECU` to
`PRT-IBS-WIRE` (the harness). The cascade re-traverses in under a
second. The ontology is the cascade, not a precomputed query.

## Act 3 - Heuristic: per-VIN urgency ranking (3 minutes)

**The question.** "Of the ~120 Open recall jobs across all active
campaigns, give me the top 20 by urgency. Weights: mileage (utilisation),
notification age (calendar), prior accident severity (safety), distance
to nearest equipped centre (logistics)."

**The expected answer.** Top 20 mixes Regensburg X1 M35i units with
high mileage and prior collisions (the dangerous combination - a
defective brake booster on top of a previously damaged chassis) with
Dingolfing-built iX / i7 EVs from the HV-battery campaign.

**What lands.** The score lives on the ontology as a Property
(`RecallAssignment.urgency`). It is deterministic and auditable -
every weight is visible in `demo_queries.py`. A GNN would have
deeper signal but loses defensibility; the talk-track disclaimer is
"the Predictive reasoner is preview, here is the rule we'd use as a
fallback".

**Speaker note - if the audience asks about model bias.** Point at
the weights. They are public. The score is not a model, it's a rule.
The Predictive reasoner is on the roadmap and will be GNN-based; the
demo intentionally uses the auditable variant.

## Act 4 - Prescriptive: assign jobs to centres x 4 weeks (5 minutes)

**The question.** "Schedule the next four weeks of recall work. Each
open job goes to exactly one centre in exactly one week. Minimise
total urgency-weighted lateness vs. week 1. Constraints: per-centre
weekly technician-hour capacity, per-centre per-week parts stock for
each campaign, no VIN assigned to a centre without the required
tooling certification. Solve it."

**The expected answer.** HiGHS solves in under 60 seconds on the
named `cars_prescriptive_m` engine. OPTIMAL. About 100 jobs scheduled
(some campaigns/jobs have no feasible centre-week within the horizon
because of parts stock). Most US Spartanburg-built X-series go to
Dallas / Miami / LA / Spartanburg; the EU population spreads across
Munich / Cologne / Hamburg / Stuttgart / Frankfurt by closest-centre
and HV / IBS certification.

**What lands.** The constraints reference the ontology directly -
`tech_hours_available`, `on_hand_units`, `hv_certified` are not magic
numbers, they're Snowflake columns. Tooling-certification eligibility
is pre-filtered into `JobAssignment` rows by PyRel rules; the LP only
sees the feasible grid.

**Speaker note - if the audience asks "what's the binding
constraint".** Parts stock on the IBS campaign. Continental cannot
ship enough booster ECUs in the four-week horizon. The audience
should recognise this - it is what happens during a real campaign.

**Speaker note - the solve takes 60 seconds. Bridge with the
constraint diagram.** "While the solver runs, look at the
constraint structure. We have 5 active campaigns, 15 centres, 4 weeks,
~120 open jobs. The decision space is 7000 binary variables. The MIP
sees only the feasible ones because the ontology already filtered
out infeasible (centre, campaign) pairs."

## Act 5 - Persistent rule: institutional knowledge in the ontology (4 minutes)

**The question.** "Add this rule to the ontology and re-solve: any
Open recall on a VIN with a prior collision or rear-end accident is
prioritised. Force the prioritised VIN to be scheduled no later than
week 2 of the four-week horizon. Show me what changes."

**The expected answer.** Re-solve OPTIMAL in under 60 seconds.
~15 priority VINs (Open recall + prior accident). The reassignment
moves priority VINs from weeks 3 or 4 into weeks 1 or 2; other jobs
slip to make room. Total weighted lateness rises 5-10% (the rule
trades raw efficiency for safety, as intended).

**What lands - the whole demo lands here.** Today this rule lives
in a senior recall manager's head, a runbook PDF, or an Excel
override. The next manager who joins the team has to learn it from
the previous manager or rediscover it from incidents. By writing it
into the ontology as `PriorityVehicle(Vehicle)`, the rule:
- Reproduces in Act 1's SLA audit (prior-accident VINs now stand
  out in the breach list).
- Reproduces in Act 3's urgency score (the rule was already in there
  as the accident_severity weight - a coincidence we made
  deliberate).
- Reproduces in Act 4 / Act 5 of any future MIP that touches this
  model.
- Survives a personnel change.

**Speaker note - this is the closing moment.** Pause. Then: "We
just moved institutional knowledge from a person to a data model."

## Closing (60 seconds)

> Five reasoners. One ontology. One Snowflake schema. The supplier
> notification on Tuesday morning becomes 19 SLA-breach rows in Act 1,
> 67 cascade VINs in Act 2, a top-20 priority queue in Act 3, a
> 4-week schedule in Act 4, and a re-solved schedule with operator-
> level safety priorities in Act 5 - all from the same model with no
> code changes between acts. RelationalAI is what you put under
> Snowflake when the question has more than one shape.

## Demo-day cadence (cold and warm timing)

| Step | Cold (engines suspended) | Warm |
|---|---|---|
| Resume `cars_logic_l` (HIGHMEM_X64_L) | 3-5 min | 0 |
| Resume `cars_prescriptive_m` (HIGHMEM_X64_M) | 3-5 min | 0 |
| Act 1 (rules) | 30 s | 5 s |
| Act 2 (cascade) | 20 s | 3 s |
| Act 3 (urgency) | 30 s | 5 s |
| Act 4 (MIP solve) | 60-90 s | 30-60 s |
| Act 5 (re-solve) | 60 s | 30-60 s |
| **Total (after engine resume)** | **3-4 min** | **2 min** |

Always run `.venv/bin/python prep_demo.py` 10 minutes before showtime.
The script resumes the engines, validates the anchored numbers, and
pre-runs each query. The first solve is the slowest because HiGHS
caches its symbolic graph.

## Fallback notes

- **Solve is slow.** First-cold solve can hit 2-3 minutes. Talk
  through the constraint structure while it runs. Have the static
  PNG from `build/figures/act4_schedule.png` ready as a backup.
- **Engine fails to resume.** Run `bash data/reset_engines.sh` from
  the project root - it suspends, deletes, and recreates the named
  engines with the right sizes. Adds ~5 minutes.
- **Snowflake login expired.** Refresh the PAT in
  `~/.snowflake/pat_token`. Profile is `rai`; role for the demo is
  always `RAI_DEMO_CARS`.
- **The numbers look wrong.** Run `bash data/load_to_snowflake.sh`
  to rebuild from seed=42. Numbers reproduce exactly across runs.
- **Audience asks about Cortex agent.** The agent at
  `CARS_DEMO.RAI_AGENT.cars` answers the same questions in natural
  language. See `SNOWSIGHT_DEMO.md`.

## What this talk track deliberately omits

- The synthesised parts / BOM / supplier layer is acknowledged in
  one sentence ("synthesised on top of the real fleet records to
  show the cascade"). The audience does not need to know more.
- The VIN check-digit (position 9) is not verified against ISO 3779
  modulo-11. Hand-verify on demo day; the seed VINs are
  inherited from the customer's CSV.
- The Cortex agent registration (Phase 7) depends on Snowflake
  Intelligence being provisioned on the SE account. If it isn't,
  fall back to the `.venv/bin/python -m agent.deploy chat` CLI.
- The full ISO 3779 / NHTSA 49 CFR 577 / KBA Rueckruf code mapping is
  not shown - we say "severity Code 1" and "severity Code 2" without
  citing the regulation per slide.
