# BRIEF.md - demo specification

Filled in during intake on 2026-05-25. Single source of truth for the
demo's identity (domain, names, scope, audience) for every downstream
phase. Do not relitigate decisions captured here once Phase 2 begins.

## Domain

**Pitch (one phrase):** "OEM fleet recall propagation - supplier defect to
service-network re-sequencing on a vehicle fleet."

**Audience-facing framing.** The demo presents as a generic luxury car
manufacturer ("a major European OEM"). The internal customer is BMW, and
the seed data is real BMW vehicle records (real WMIs, real model
designators like G21 LCI / U11 / G87, real plant locations). Notionalised
in repo / Snowflake / Cortex assets only; the data inside the tables stays
BMW-feeling because the audience is BMW industry experts who would
otherwise spot scrubbed VINs instantly. Talk track says "the OEM"; the
data says BMW. See [Naming convention](#naming-convention).

**Why RelationalAI here.** Recall propagation is a graph problem dressed
up as a fleet problem. A defective part flows from a Tier-1 supplier
through a bill-of-materials structure to a date-windowed cohort of VINs,
then to the registered owners, then to a service-centre network operating
under capacity, parts-stock, and regulatory-SLA constraints. The
production answer requires (a) rule cascades to identify SLA-breaching
open recalls, (b) graph traversal across supplier-part-BOM-VIN-owner-centre
to enumerate the cascade, (c) deterministic urgency scoring to rank the
open population, (d) a mixed-integer program to assign jobs to centres
under capacity and parts constraints, and (e) the ability for a senior
operator to add a policy rule ("never more than N jobs per centre per
day", "prioritise VINs with prior accidents") and have the entire
pipeline re-derive without code changes. All five reasoner families land
in one storyline against one ontology - this is the airplanes_demo shape
applied to a domain that maps natively to graph plus optimisation.

## Inputs

- [x] Schema (CSV): two files at `data/seed/`
  - `BMW_VEHICLES_V1.csv` - 325 VIN-level records, 23 columns: VIN, serial
    number, model, factory, engine, fuel type, transmission, chassis
    number, emission standard, production / delivery / first-registration
    dates, masked owner, mileage, fuel consumption, accident history,
    repair cost, service-records status, recall status, previous owners,
    power output (kW + PS). VINs use real BMW WMI prefixes (WBA).
  - `BMW_VEHICLES_SERVICES.csv` - 762 service-event records across 302
    distinct VINs, 8 columns: event id, VIN, service date, service type
    (Inspection, Oil Service, Brake Service, Annual Service, Battery
    Service), service centre (15 named centres in EU/US/MX), cost,
    warranty flag, notes.
- [x] Tableau workbook: `BMW_FLEET_ANALYSIS.tds`
  - Points at `sfseeurope-demo531 / BMW_DEMO.DFA / warehouse AICOLLEGE`.
  - Informational only - the customer already lifted these CSVs to
    Snowflake on a sales-engineering EMEA account. We do not run there;
    we run on `ajb85638` (the SE US account) per intake answer 2. The
    `.tds` tells us the data shape they care about and the role
    (`DATA_ENGINEER`) they expect a Cortex agent to surface answers
    against.
- [ ] Problem statement document: none. Acts derived from intake plus
      research, summarised below.
- [ ] Existing Snowflake database to demo against: see above; we synthesise
      a parallel `CARS_DEMO` schema on `ajb85638` and document the
      port-to-EMEA path as a Phase 9 deliverable.

**What's missing from the seed and must be synthesised.** The CSVs have
VINs and service events. They have no parts, no bill-of-materials, no
suppliers, no recall campaigns, no service-centre capacity, no parts
inventory. Phase 2 invents these deterministically (`seed=42`) on top of
the existing VINs so the talk track's anchored numbers reproduce
exactly. The narrative entities are picked to mirror real BMW recalls
(EGR cooler, integrated brake booster, high-voltage battery module,
Takata airbag waves) so a BMW expert recognises the shapes. See Phase 2
data spec in `data/build_cars_demo_data.py` once written.

## Scope

- **Length / depth:** 20 minutes, 5 acts (airplanes_demo shape).
- **Number of demo questions:** 5.
- **Reasoners showcased:** rules, graph, heuristic, prescriptive, persistent
  rule. Predictive (GNN) explicitly out of scope - preview-only and the
  Act 3 ranking lands cleaner as a deterministic heuristic anyway.
- **Cortex agent (Phase 7):** yes.
- **Runbook + prep_demo gate (Phase 8):** yes.
- **Snowsight notebook (Phase 6):** yes.

## The five acts (locked at intake)

| Act | Reasoner | Question one-liner | Anchored number(s) |
|---|---|---|---|
| 1 | Rules | Show every Open recall on a VIN whose age in service or accumulated mileage breaches the recall SLA per the manufacturer-published completion window. | TBD by Phase 2 generator. Target: 12 SLA-breaching VINs across 3 campaigns, dominated by one campaign and one region. |
| 2 | Graph | Given a defective supplier part, traverse supplier -> part -> BOM node -> VIN -> owner -> service centre and list everyone who must be notified, with regional rollups. | TBD. Target: one supplier, one part number, ~80 affected VINs across 3 plant-date cohorts, rolled up to 5-6 service centres. |
| 3 | Heuristic | Rank the open recall population by per-VIN urgency. Weights: mileage (utilisation proxy), age in service (calendar-time proxy), prior accident severity (safety proxy), distance to nearest equipped service centre (logistics proxy). | TBD. Target: top-10 ranked list, top 3 dominated by US Spartanburg-built X-series with prior collisions. |
| 4 | Prescriptive | Assign open recall jobs to service centres for the next four weeks. Minimise sum(urgency * weeks-of-lateness). Constraints: per-centre weekly technician-hour capacity, per-centre per-week parts-stock-on-hand, no VIN assigned to a centre lacking the right tooling (e.g., HV-certified for EV battery work). | TBD. Target: ~120 jobs scheduled, OPTIMAL in < 60s, ~15 jobs delayed past week 4 (driver: parts stock on the IBS campaign). |
| 5 | Persistent rule | Operator adds "prioritise VINs with at least one prior accident" or "cap N jobs per centre per day". Ontology stores the rule. The MIP from Act 4 re-solves with the rule, returns OPTIMAL. The cascade in Act 2 also picks the rule up (because it reads the same ontology). | TBD. Target: re-solve in < 60s, delta vs Act 4 visible in 4-6 reassignments. |

Why this arc lands. Act 1 is the SQL-feasible baseline ("we already do
this in Tableau, why do we need RAI?"). Act 2 reveals the cascade RAI was
built for. Act 3 ranks risk so the operator does not face a flat list.
Act 4 prescribes, demonstrating real constraint satisfaction. Act 5 is
the institutional-knowledge moment - the operator's policy lives in the
ontology, not in a notebook cell, so every downstream reasoner respects
it without redeployment.

Why MIP assignment and not knapsack for Act 4. The research scratched out
the alternative formulation (pick recall waves under a fixed weekly
technician-hour budget). It is a one-dimensional story that exhausts in
Act 3. Assignment exposes 3+ binding constraint families (technician
hours, parts stock per centre per week, tooling-certification compatibility)
and lets Act 5's persistent rule add a 4th cleanly. The airplanes_demo
MIP-assignment pattern transfers directly.

## Audience

BMW industry experts plus their SE peers. Skeptical of synthetic data,
will challenge: VIN structure, plant codes, real recall campaign
parallels, supplier names, recall SLA numbers, technician-hour
throughput per centre. The data rigor target is the same as
airplanes_demo's: every concept name is a real industry term, every
anchored number is published or back-calculated from a published source,
every supplier name is an actual BMW Tier-1.

**Implication for data rigor.** Phase 2 generator uses real BMW WMIs
(WBA, WBS, WBY, 4US, 5UX, 5YM), real plant codes (D Dingolfing, M Munich,
R Regensburg, K Spartanburg, B Leipzig, T San Luis Potosi), real model
designators that already live in the seed (G21 LCI, G87, U11, G26, etc),
real Tier-1 supplier names (Continental for integrated brake systems,
Bosch for high-pressure fuel pumps, Samsung SDI for high-voltage cells,
Takata-era inflators for legacy airbag campaigns, ZF for transmissions),
and recall completion-window numbers anchored to NHTSA 49 CFR 577 and
the KBA Rückruf code system. The talk track says "the OEM" everywhere
the audience could see it, but the data itself is BMW-grade.

## Naming convention

The demo is notionalised at the wrapper layer (Snowflake objects,
filenames, Cortex agent, slide labels). The data inside Snowflake stays
realistic so domain experts recognise it. This split is recorded so a
future agent does not accidentally scrub VINs.

| Layer | Notionalised? | Examples |
|---|---|---|
| Snowflake database / schema / role / engines | Yes | `CARS_DEMO`, `RAI_DEMO_CARS`, `cars_logic_l`. No "BMW". |
| Repo filenames | Yes | `build_cars_demo_data.py`, `cars_demo_validation.sql`, `cars_demo.ipynb`. No "bmw". |
| Repo path / git remote | No (private internal) | `~/rai-repos/bmw_demo` stays - this is internal. |
| PyRel concepts and properties | Yes | `Vehicle`, `ServiceCentre`, `RecallCampaign`, `Supplier`. No "BMW". |
| Talk track / RUNNING.html / handoff | Yes | "The OEM", "a major luxury car manufacturer". |
| Data inside tables | No | VINs starting WBA, model names like "X1 M35i xDrive (U11)", factory "Dingolfing", suppliers like "Continental". |
| Seed CSVs in `data/seed/` | No | Keep filenames `BMW_VEHICLES_V1.csv` - they are inputs, not deliverables. |

## Names (derived, lock these now)

| Thing | Value |
|---|---|
| Model name (PyRel) | `cars` |
| Database name (Snowflake) | `CARS_DEMO` |
| **Demo role (security harness)** | `RAI_DEMO_CARS` |
| Schema for sources | `CARS_DEMO.FLEET` (mirrors airplanes' `EHAM` sub-schema pattern; "fleet" is the operational domain) |
| Schema for agent | `CARS_DEMO.RAI_AGENT` |
| Schema for notebooks | `CARS_DEMO.NOTEBOOKS` |
| Logic engine | `cars_logic_l` (HIGHMEM_X64_L) |
| Prescriptive engine | `cars_prescriptive_m` (HIGHMEM_X64_M) |
| Notebook stage | `CARS_DEMO.NOTEBOOKS.CARS_NOTEBOOK_STAGE` |
| Snowsight notebook | `CARS_DEMO.NOTEBOOKS.CARS_DEMO` |
| Cortex agent | `cars` (lowercase) |

## Snowflake security harness

- **Bootstrap SQL:** `data/00_bootstrap.sql` (committed). Run on: pending
  user review and confirmation, as: profile default role `ACCOUNTADMIN`
  via the `rai` connection, against account `ajb85638` (Snowflake SE US
  account). After this single bootstrap, every `snow sql` invocation
  passes `--role RAI_DEMO_CARS` explicitly.
- **Demo role:** `RAI_DEMO_CARS`. Granted to user
  `piotr.kraus@relational.ai` and to `ROLE SYSADMIN`.
- **Demo database:** `CARS_DEMO`, owned by `RAI_DEMO_CARS` with full
  current and future privileges on all object types.
- **RelationalAI Native App:** `RELATIONALAI` (verified via
  `SHOW APPLICATIONS` on this account). Application role
  `RELATIONALAI.RAI_USER` granted to the demo role. Top-level Snowflake
  role `RAI_DEVELOPER` (created by the native-app install on this
  account; required by PyRel programs) also granted to the demo role.
  The template's example role name `RAI_DEVELOPER` as an *application*
  role does not exist on this account; only `RAI_USER` is exposed
  through the app. The bootstrap reflects this.
- **Snowflake Intelligence:** the `SNOWFLAKE_INTELLIGENCE` database does
  NOT exist on `ajb85638` at the moment, so the standard grant block in
  the bootstrap is commented out (see `data/00_bootstrap.sql`). The
  Cortex agent will still deploy into `CARS_DEMO.RAI_AGENT` (the demo
  role owns the database). Registration with the SI picker is handled
  by `relationalai.agent.cortex.CortexAgentManager` and will succeed
  if/when SI becomes available on this account. Phase 7 will adapt if
  not - tracked under [Open questions](#open-questions).
- **Warehouse:** `RAI_XS` with `USAGE` + `OPERATE` only.

**Confirmed limitations of the demo role:**
- Cannot CREATE / DROP / ALTER any user.
- Cannot CREATE / DROP / ALTER any database, schema, table, or warehouse
  outside `CARS_DEMO`.
- Cannot create programmatic access tokens (PATs).
- Cannot GRANT or REVOKE any privilege.
- Cannot modify the RelationalAI native app or any integration.

**To tear down the demo entirely** (manual, by the user, not the agent):
```sql
USE ROLE ACCOUNTADMIN;
DROP DATABASE IF EXISTS CARS_DEMO;
DROP ROLE IF EXISTS RAI_DEMO_CARS;
```

## Anchored numbers

Phase 2 fills these in once the generator is written. Every cell must
reproduce from a SQL query in `data/cars_demo_validation.sql` and assert
in `prep_demo.py`. Same discipline as airplanes_demo.

| Metric | Value | SQL source |
|---|---|---|
| Vehicles in scope | 325 | `SELECT COUNT(*) FROM vehicle` |
| Service events | 762 | `SELECT COUNT(*) FROM service_event` |
| Unique owners | 282 | `SELECT COUNT(*) FROM owner` |
| BOM membership edges (vehicle x bom_node) | 531 | `SELECT COUNT(*) FROM bom_membership` |
| Total recall_assignments | 254 | `SELECT COUNT(*) FROM recall_assignment` |
| Open recall_assignments | 121 | `WHERE status='Open'` |
| SLA-breached Open recalls (Act 1) | 19 | `WHERE status='Open' AND sla_breached=TRUE` |
| SLA-breached by campaign (Act 1) | IBS-2024-A: 8, HVB-2024-A: 7, EGR-2023-B: 3, AIRBAG-2022-A: 1, STARTER-2024-A: 0 | `GROUP BY campaign_id` |
| Continental MK C1 cascade size (Act 2) | 67 affected VINs across 3 plant-date cohorts | join `dim_supplier -> dim_part -> dim_bom_node -> bom_membership` |
| Continental cascade regional rollup (Act 2) | EU: ~52, NA: ~13, LATAM: ~2 | + region join |
| Priority VINs (Act 5 = Open recall + prior accident) | 15 | `WHERE status='Open' AND accident_type IS NOT NULL` |
| Recall campaigns total | 5 | IBS / HVB / EGR / AIRBAG / STARTER |
| Service centres | 15 | `SELECT COUNT(*) FROM dim_service_centre` |
| Suppliers | 11 | `SELECT COUNT(*) FROM dim_supplier` |
| Parts | 19 | `SELECT COUNT(*) FROM dim_part` |
| BOM nodes | 11 | `SELECT COUNT(*) FROM dim_bom_node` |
| Act 4 (Prescriptive) expected | OPTIMAL in <60s, 8-12 jobs deferred past week 4 (IBS parts stock binding) | run `q4` in `demo_queries.py` |
| Act 5 (Persistent rule) expected | OPTIMAL in <60s, 4-6 reassignments, weighted-lateness +5-10% | re-solve diff |

## Phase log

Append a one-paragraph entry after each phase exits green. Trail for
the handoff document at Phase 9.

### Phase 1 - Positioning
Done 2026-05-25. Authored `DEMO_QUESTIONS.md` with 5 acts mirroring the
airplanes_demo shape. Each act is tagged with reasoner, why-RAI
justification, and an expected-shape paragraph that names the anchored
numbers Phase 2 must reproduce. The arc: SQL-feasible audit (Act 1) ->
cascade RAI was built for (Act 2) -> heuristic ranking (Act 3) -> MIP
prescription (Act 4) -> persistent rule on the ontology (Act 5). Did
not invoke /rai-discovery this round; the framing was specified in
intake answer 1 verbatim, so further discovery would not have changed
the questions. Will run /rai-discovery in Phase 4 to validate the
reasoner-routing decisions if any are ambiguous.

### Phase 2 - Data
Done 2026-05-25. Wrote `data/build_cars_demo_data.py` (seed=42) which
reads the two seed CSVs and synthesises 11 suppliers, 19 parts, 12 BOM
nodes, 15 service centres (enriched with HV / IBS / body-shop / EGR
certifications), 5 recall campaigns (IBS-2024-A Continental MK C1 brake
booster, HVB-2024-A Samsung SDI HV battery, EGR-2023-B BorgWarner cooler,
AIRBAG-2022-A Joyson PSAN, STARTER-2024-A Bosch starter), 282 owners,
531 BOM membership edges, 254 recall_assignments (121 Open, 19 SLA-
breached), centre-capacity and parts-stock rows for the 4-week planning
horizon. Loader is `data/load_to_snowflake.sh`; annotations + tags +
DATA_DICTIONARY.md by `data/annotate_and_doc.py`. Anchored numbers
reproduce exactly from SQL in `data/out/cars_demo_validation.sql`.

### Phase 3 - Ontology
Done 2026-05-25. `rai_code/manual/cars.py` defines 15 concepts plus the
`in_bom` relationship, with derived concepts `OpenRecall`,
`SLABreachedRecall`, `PriorAccident`, `PriorityVehicle`. Includes the
deterministic urgency-score derivation (Vehicle.accident_severity ->
RecallAssignment.urgency) and the JobAssignment LP scaffolding with
pre-materialised labour_hours / urgency / week_index Properties (the
workaround for the PyRel 1.7.1 prescriptive-rewriter cross-Concept
arithmetic bug). The `_build_config()` pattern from
`supply_chain_demo/rai_code/manual/supply_chain.py` is copied verbatim
so the same model runs locally and inside Snowsight. Engine resume on
first run took ~5 min cold; warm queries are sub-second.

### Phase 4 - Queries
Done 2026-05-25. All 5 acts return OPTIMAL with correct anchored
numbers. Q1: 19 SLA breaches (IBS 8, HVB 7, EGR 3, AIRBAG 1). Q2: 67
affected VINs across 3 plant-date cohorts. Q3: top-20 urgency dominated
by Regensburg X1 M35i + iX1 with prior accidents. Q4 and Q5: OPTIMAL,
obj 0.67, ~0.13s solve time warm. Q4/Q5 obj equal because most jobs fit
in week 1 already; the priority rule is non-binding under current parts
stock. Documented as deferred polish item.

Workarounds for PyRel 1.7.1 prescriptive rewriter bugs:
- Subtype predicates in `problem.satisfy().where(...)` blow up at
  `_compile_arithmetic`. Workaround: filter by underlying status / flag
  Property (e.g. `_r.status == "Open"`, `_r.priority_flag == 1`).
- `decision_var * OtherConcept.property` inside `aggs.sum()` also blows
  up the rewriter. Workaround: precompute coefficients as Properties
  on the same Concept the decision variable lives on (JobAssignment).
Both documented in `rai_code/manual/cars.py` and `HANDOFF_BRIEFING.md`.

### Phase 5 - Local notebook
Done 2026-05-25. `rai_code/manual/cars_demo.ipynb` is 24 cells (4 per
act + intro + closing), executes top-to-bottom via
`jupyter nbconvert --execute --inplace`. Uses Plotly for bar charts and
a Sankey for the Act 2 cascade. Total notebook execution time ~7 min
end-to-end including engine warm-up (Q4/Q5 each invoke fresh MIP
solves).

### Phase 6 - Snowsight notebook
Done 2026-05-25. `rai_code/manual/cars_demo_snowsight.ipynb` is the
Snowsight-flavoured variant (no nest_asyncio, explicit
`get_active_session()`, explicit chart widths). Uploaded via
`data/upload_snowsight_notebook.sh` to
`CARS_DEMO.NOTEBOOKS.CARS_DEMO` with LIVE VERSION promoted.

### Phase 7 - Cortex agent
Done 2026-05-25. Agent `cars` deployed to
`SNOWFLAKE_INTELLIGENCE.AGENTS.cars` with 13 catalog queries (4 chart
variants for Q1, 3 for Q2, 1 chart for Q3, 2 + 2 chart variants for
Q4 / Q5). Stored procedures + stage in `CARS_DEMO.RAI_AGENT`.
SNOWFLAKE_INTELLIGENCE database did not exist on `ajb85638` and was
created as part of the cortex grants script. ModelVerbalizer (default)
used rather than SourceCodeVerbalizer (the latter was truncating
EXPLAIN payload at 19/32 labels per preflight). Chat smoke-test passed:
asking "How many open recalls have breached their SLA?" returned the
exact anchored numbers (19 total, IBS 8, HVB 7, EGR 3, AIRBAG 1) with a
correct domain-language explanation citing NHTSA 49 CFR 577 / KBA.

### Phase 8 - Gate + runbook
Done 2026-05-25. `prep_demo.py` is the 5-phase pre-flight gate
(connection, row counts, anchored numbers, engine resume, smoke Q1-Q5,
agent status). `build/generate_demo_figures.py` produced 6 static PNGs
into `build/figures/`. `build_runbook.py` rendered `RUNNING.html` from
`RUNBOOK.template.html` with cars-specific substitutions and the actual
anchored numbers as a table.

### Phase 9 - Talk track + handoff
Done 2026-05-25. `CARS_TALK_TRACK.md` is the 20-minute speaker script
with per-act expected outputs, talk-track tactics, and a fallback
section. `SNOWSIGHT_DEMO.md` is the 10-minute Cortex-agent variant
(3 questions only). `HANDOFF_BRIEFING.md` captures design rationale,
the anchored-number table, the PyRel rewriter workarounds, and the
deferred polish items. Project `CLAUDE.md` rewritten from the template
orientation to a cars-specific project doc.

## Design decisions

- **Notionalise the wrapper, keep the data realistic.** See [Naming
  convention](#naming-convention). The audience is BMW experts; scrubbing
  VINs would betray the demo. Wrapper notionalisation lets us re-pitch
  outside BMW without rewriting the data.
- **MIP assignment over knapsack for Act 4.** Three+ binding constraint
  families (technician hours, parts stock, tooling certification) plus a
  clean persistent-rule attachment point. Knapsack collapses to one
  dimension after Act 3.
- **Heuristic over GNN for Act 3.** Predictive reasoner is preview. A
  deterministic urgency score made of four PyRel-derived properties
  reproduces every time, runs in milliseconds, and reads as transparent
  scoring to a skeptical industry expert. Same call airplanes_demo made.
- **Source schema named `FLEET`, not `DFA`.** The .tds uses `DFA` (data
  fabric analytics?), but our schema is brand-neutral and reusable. A
  one-line `CREATE SYNONYM`-style view can be added if the customer
  wants the .tds to point at our objects without changes.
- **Run on ajb85638, not sfseeurope-demo531.** The user's
  `~/.snowflake/connections.toml` has no sfseeurope-demo531 profile.
  Adding one would require auth setup that is out of scope for an
  autonomous agent run. Phase 9 handoff will include a one-page
  "port to BMW EMEA account" runbook.
- **Engine sizing: cars_logic_l at HIGHMEM_X64_L, not XS.** The newer
  template default is XS for both engines during build, sized up only
  when measured. cars_logic_l was named and created at L deliberately
  before the new guidance landed, anticipating the Act 2 graph cascade
  + Act 3 heuristic ranking + Act 4 MIP load. Left at L; auto-suspend
  lowered from default 60 to 5 minutes to match the new guidance. The
  prescriptive engine has not been created yet - it will be created
  at Phase 4 when the MIP query is first authored; size decision (XS
  vs M) will be measured then. Phase 8 prep_demo.py will record the
  final showtime sizes.
- **Snowflake metadata retrofit applied at template-reconcile time.**
  The initial Phase 2 load declared PKs on most tables but missed FKs
  entirely and missed PKs on the three junction/fact tables
  (`bom_membership`, `centre_capacity`, `parts_stock`). Retrofit SQL
  in `data/out/cars_demo_constraints.sql` adds 3 missing PKs and all
  19 FKs implied by the schema, plus NOT NULL on every column the data
  shows is never null. Required by the new template before the Phase 3
  agentic modeler runs - the modeler reads metadata to draft the v0
  ontology, and FKs declare the relationships it surfaces as concept
  associations.

## Open questions

- **Snowflake Intelligence on ajb85638.** `SNOWFLAKE_INTELLIGENCE.AGENTS`
  is not provisioned on this account at the time of bootstrap. The
  Cortex agent will deploy into `CARS_DEMO.RAI_AGENT` either way, but
  whether it surfaces in the Snowsight SI picker depends on the SI
  feature being enabled. Phase 7 needs to:
  1. Check if SI got enabled in the meantime (`SHOW DATABASES LIKE
     'SNOWFLAKE_INTELLIGENCE'`).
  2. If yes, run the four grants documented at the bottom of
     `data/00_bootstrap.sql` and continue with the airplanes_demo
     pattern.
  3. If no, fall back to the `.venv/bin/python -m agent.deploy chat`
     CLI as the demo-day interface, and document the SI gap in
     `SNOWSIGHT_DEMO.md`.
- **Real BMW recall campaign IDs.** The background research agent could
  not fetch fresh NHTSA / KBA campaign numbers in this session (WebFetch
  denied, WebSearch returned thin results). The data generator will use
  *narrative-faithful* campaign names ("Continental MK C1 brake-booster
  firmware, IBS-2024-A", "Samsung SDI HV-battery module thermal,
  HVB-2024-A") with realistic scale, but not exact public campaign IDs.
  Before demo day, the user (or a future agent run) should swap in the
  current NHTSA / KBA campaign IDs from
  https://www.nhtsa.gov/recalls and https://www.kba-online.de/rueckrufe/.
  Tracked in `data/build_cars_demo_data.py` as a TODO comment block.
- **Real VIN check-digit (position 9) validity.** Seed VINs are
  WBA + serial + chassis style and may or may not pass ISO 3779 mod-11
  check. Will verify on a sample of 5 VINs in Phase 2. If they fail,
  the generator will regenerate VINs that pass; otherwise leave the
  seed VINs as-is for realism.
- **Service-centre tooling certification data.** The 15 centres in the
  seed are named but their HV certification, body-shop capability, and
  EGR-cooler tooling status are unknown. Will assign these
  deterministically in Phase 2 with a public-facing rationale (e.g.,
  Munich + Spartanburg + Frankfurt + Cologne are HV-certified because
  they handle the largest EV fleets) and document the assumption set.

## Autonomy issues

(populated during the run if pre-tuned permissions interrupt anywhere
they should not)

### Template reconcile, 2026-05-25

Mid-Phase-2 the upstream template (`pkarus/demo-agent-template`) shipped
a major update. The agent reconciled rather than restarting:

- Replaced template files: `CLAUDE.md`, `PIPELINE.md`, `INTAKE.md`,
  `REFERENCES.md`, `DEMO_QUESTION_CATALOG.md`, `BRIEF.template.md`,
  `.claude/settings.json`. Kept demo-specific artifacts unchanged.
- Wrote `data/seed_profile.md` and `data/seed_extension_plan.md` (the
  new template requires these whenever seed data is provided; they
  were missing).
- Applied `data/out/cars_demo_constraints.sql` (FKs + missing PKs +
  NOT NULL retrofit; see Design decisions).
- Corrected BOM nodes anchored number from 12 to 11 (matches actual
  generator output).
- Lowered `cars_logic_l` auto-suspend from 60 to 5 minutes.
- Documented the L-instead-of-XS engine size choice under Design
  decisions.
