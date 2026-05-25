# BRIEF.md - demo specification

> Filled in by the agent during the intake protocol ([INTAKE.md](INTAKE.md)).
> Once written, this file is the single source of truth for the demo's
> identity (domain, names, scope, audience) for every downstream phase.

## Domain

**Pitch (one phrase):** _e.g. "pharma cold-chain logistics"_

**Why RelationalAI here, in one paragraph:** _what reasoner types are
naturally present in this domain - graph dependencies, rule cascades,
optimisation under constraint - that would be awkward in pure SQL._

## Inputs

- [ ] Schema (CSV / DDL / PDF): _path or "none"_
- [ ] Problem statement document: _path or "none"_
- [ ] Existing Snowflake database to demo against: _name or "none"_
- [ ] Otherwise: invent the data from domain knowledge

If a schema or problem doc was provided, paste a 5-line summary of what's
in it here:

> _summary_

## Scope

- **Length / depth:** _10 min / 3 Qs · 20 min / 5 acts · 30 min / 10 Qs · ontology-only_
- **Number of demo questions:** _N_
- **Reasoners showcased:** _rules · graph · heuristic · prescriptive · persistent rule · predictive (GNN)_
- **Cortex agent (Phase 7):** _yes / no_
- **Runbook + prep_demo gate (Phase 8):** _yes / no_

## Audience

_e.g. "Snowflake SE peers - technical, RAI-familiar" or "Pharma industry
experts - skeptical of synthetic data, will challenge cold-chain rate
assumptions"_

**Implication for data rigor:** _e.g. "use real ICAO milestones and
published 22% CTOT rate" or "stay loose, this audience won't dig"._

## Names (derived, lock these now)

| Thing | Value |
|---|---|
| Model name (PyRel) | `<snake_case_domain>` |
| Database name (Snowflake) | `PK_<DOMAIN_UPPER>` |
| **Demo role (security harness)** | `RAI_DEMO_<DOMAIN_UPPER>` |
| Schema for sources | `<DB>.<SCHEMA>` (typically same as DB or `EHAM`-style sub-schema) |
| Schema for agent | `<DB>.RAI_AGENT` |
| Logic engine | `<model>_logic_xs` (HIGHMEM_X64_XS, auto-suspend 5 min) |
| Prescriptive engine | `<model>_prescriptive_xs` (HIGHMEM_X64_XS, auto-suspend 5 min) |
| Notebook stage | `<DB>.NOTEBOOKS.<DOMAIN>_NOTEBOOK_STAGE` |
| Snowsight notebook | `<DB>.NOTEBOOKS.<DOMAIN>_DEMO` |
| Cortex agent | `<domain>` (lowercase) |

## Snowflake security harness

> Filled in during intake step 3 (bootstrap). The role + DB created here are
> the only Snowflake objects the agent ever touches outside of the demo
> itself. See CLAUDE.md > "Snowflake security harness" for the full model.

- **Bootstrap SQL run:** `data/00_bootstrap.sql` (committed to the repo for
  review). Run on: _date_ as: _profile default role_ against: _account_.
- **Demo role:** `RAI_DEMO_<DOMAIN_UPPER>`. Granted to user
  _CURRENT_USER_ and to ROLE SYSADMIN.
- **Demo database:** `PK_<DOMAIN_UPPER>`, owned by the demo role.
- **RelationalAI Native App:** _app name_. Granted application roles:
  _list of app role names_.
- **Snowflake Intelligence:** `CREATE AGENT` on
  `SNOWFLAKE_INTELLIGENCE.AGENTS` granted.
- **Warehouse:** `RAI_XS` with `USAGE` + `OPERATE` only (no MODIFY).

**Confirmed limitations of the demo role:**
- Cannot CREATE / DROP / ALTER any user.
- Cannot CREATE / DROP / ALTER any database, schema, table, or warehouse
  outside `PK_<DOMAIN_UPPER>`.
- Cannot create programmatic access tokens (PATs).
- Cannot GRANT or REVOKE any privilege.
- Cannot modify the RelationalAI native app or any integration.

**To tear down the demo entirely** (manual, by the user, not the agent):
```sql
USE ROLE ACCOUNTADMIN;
DROP DATABASE IF EXISTS PK_<DOMAIN_UPPER>;
DROP ROLE IF EXISTS RAI_DEMO_<DOMAIN_UPPER>;
```

## Anchored numbers

> **Phase 1 designs these. Phase 2 engineers the data to produce them.**
> They are the specific named entities and counts the talk track will
> hinge on - hand-injected by the data generator, not discovered after
> the fact. The pattern is `airplanes_demo/CLAUDE.md`'s "Anchored numbers"
> table: every cell reproduces from raw SQL in
> `data/<domain>_demo_validation.sql`, and `prep_demo.py` asserts every
> one. If a row drifts, you fix the data generator, not the row.

| Question | Expected answer | SQL source |
|---|---|---|
| Q1 (Rules) | _e.g. KLG=7, AGS=5, DNATA=3, MENZIES=2_ | `<domain>_demo_validation.sql` line N |
| Q2 (Graph) | _e.g. KL1234 cascade reaches 6 flights (KL1235, KL0407, KL1402, KL1601, HV5821, AF1241)_ | line M |
| Q3 (Heuristic) | _e.g. top-5 fit scores: KL0203 (0.91), DL0036 (0.87), ..._ | line O |
| Q4 (Prescriptive) | _e.g. LP OPTIMAL, total weighted delay = 187 min, KL691 delayed 22 min_ | line P |
| Q5 (Persistent rule) | _e.g. with PreservedFlight(KL691), KL691 delay drops 22 -> 4 min; KL2014 shifts 8 -> 14 min_ | line Q |

## Phase log

> Append a one-paragraph entry after each phase exits green. Keeps a
> tidy trail for the handoff document at Phase 9.

### Phase 1 - Positioning
_pending_

### Phase 2 - Data
_pending_

### Phase 3 - Ontology
_pending_

### Phase 4 - Queries
_pending_

### Phase 5 - Local notebook
_pending_

### Phase 6 - Snowsight notebook
_pending_

### Phase 7 - Cortex agent
_pending_

### Phase 8 - Gate + runbook
_pending_

### Phase 9 - Talk track + handoff
_pending_

## Design decisions

> Anything you decided that was non-obvious - schema grain, why you picked
> a particular reasoner for a particular question, why you ruled out a
> question, why the anchored numbers are what they are. This becomes the
> backbone of `HANDOFF_BRIEFING.md` at Phase 9.

### Engine sizing

> Default is `HIGHMEM_X64_XS` for both engines (see CLAUDE.md > "Engine
> sizing"). Any deviation MUST be justified by a measurement here.

- **Logic engine size:** `XS` (default). If sized up, paste the
  `prep_demo.py` timing or `/rai-health` output that justified it.
- **Prescriptive engine size:** `XS` (default). Same rule.
- **Auto-suspend:** 5 minutes for both. Lower if dev sessions are short
  bursts; higher only for live demo-day to avoid cold-start mid-show.

## Open questions

> Things you couldn't resolve and proceeded around. Surface in the final
> summary.

## Autonomy issues

> Times the pre-tuned permissions interrupted you when they shouldn't have,
> or vice versa. Helps tune the template settings.
