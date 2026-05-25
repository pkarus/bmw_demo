# PIPELINE.md - the locked 9-phase pipeline

Every RelationalAI demo built from this template moves through these nine
phases in order. Each phase has explicit **exit criteria**. You do not move
to the next phase until the current phase is green.

Phase boundaries should also be `TaskCreate` task boundaries - one task per
phase, marked `in_progress` when you enter and `completed` when exit criteria
are met. Phase N+1 is `blockedBy` Phase N.

The reference demos are at:
- `/Users/piotrkraus/rai-repos/supply_chain_demo` (the 10-question shape)
- `/Users/piotrkraus/rai-repos/airplanes_demo` (the 5-act shape - newer, more polished)

When a phase says "copy the pattern from X", treat X as ground truth.
[REFERENCES.md](REFERENCES.md) maps every file in both demos to its phase.

---

## Phase 1 - Position RelationalAI in the domain

**Goal.** Decide what makes this domain a RelationalAI demo (vs. a plain
SQL demo). Land on the question shapes that justify each reasoner.

**Steps.**
1. Read `BRIEF.md` (the intake output).
2. **Invoke `/rai-discovery` for the ideation pass** (via Skill tool) and
   pass it the domain summary plus the reasoner mix from Q4 of intake.
   Discovery's job here is to surface candidate questions the data
   *could* answer across each reasoner family - more candidates than the
   final set so you can pick the strongest. See CLAUDE.md > "Discovery
   is the router" for what this skill does. Phase 4 will run discovery
   again per question; this pass is for breadth, not commitment.
3. Reference [DEMO_QUESTION_CATALOG.md](DEMO_QUESTION_CATALOG.md) for the
   archetypes that work cleanly in each reasoner family. Cross-check
   discovery's candidates against the catalog - the catalog is the bank
   of known-good shapes.
4. Draft `DEMO_QUESTIONS.md` (use `airplanes_demo/DEMO_QUESTIONS.md` as the
   shape - plain-English questions, one per act, each labelled with the
   reasoner type and what makes it interesting). Note the reasoner-family
   label is provisional; Phase 4's per-question discovery may re-classify.

**Exit criteria.**
- `DEMO_QUESTIONS.md` exists with N questions (N from intake Q3: 3, 5, or 10).
- Each question is tagged with its reasoner family.
- Each question has a one-sentence "why this is a RelationalAI question, not
  a SQL question" justification.
- **Each question has a hand-designed "expected answer".** Not a placeholder.
  A concrete shape with concrete named entities: "KLG handler shows 7 TOBT
  violations, AGS shows 5, DNATA 3, MENZIES 2" - not "some handlers will
  show violations". The expected answer is the talk-track moment. If you
  can't write it now, you don't understand the demo yet - iterate on the
  question.
- At least one question per reasoner family the user picked in intake Q4.
- The set as a whole tells a coherent narrative (Act 1 sets up the problem,
  Act 2 reveals a hidden dependency, Act 3 ranks risk, Act 4 prescribes,
  Act 5 adds a rule and re-solves - adapt the arc to N).

**Anti-patterns.**
- A graph question with only one hop (that's a join).
- A prescriptive question with no real constraint (that's a sort).
- A persistent-rule question that doesn't change the answer when added.
- "We'll see what the data shows." No - the data hasn't been generated
  yet. You decide what the answer should be at Phase 1; Phase 2 engineers
  the data to produce it. Reverse this and the talk track is at the mercy
  of the random number generator.

---

## Phase 2 - Invent and load data into Snowflake

**Goal.** Land a defensible dataset in Snowflake, small enough to be fast
(target: each query under 30 s warm) and rich enough to make every Phase 1
question land. **Engineer the data backwards from the expected answers
authored at Phase 1** - the talk track's "interesting" moments are
hand-injected, not discovered. The seed makes the chaff deterministic; the
load-bearing entities are placed by hand. The schema is **denormalised and
metadata-rich** because the agentic modeler reads it at Phase 3 to draft
the v0 ontology - see CLAUDE.md > "Snowflake modeling principles". Load
into the SE Snowflake account **as the demo role only** - see CLAUDE.md >
"Snowflake security harness".

**The inversion that matters.** The naive approach is "generate the data
with `seed=42`, run the queries, see what comes out, write the talk track
around whatever the queries return". This is backwards and fragile.
The correct approach: at Phase 1 you already wrote down "KLG = 7 TOBT
violations, KL1234 cascade hits 6 flights, the LP saves $X by routing
through Y instead of Z". Phase 2's job is to inject the named entities,
relationships, and edge cases that **produce exactly those answers**.
Random fill only goes in spots that don't surface in any query.

**Branch: seed data provided.** If intake Q2 indicated seed data exists
(CSV, DDL, PDF, an existing Snowflake table the user wants to demo
against), do not skip to generation. Do this first, then return to the
numbered steps below:

1. **Profile what you got.** For each table: row count, column dtypes,
   null rates, cardinalities, value distributions of categorical columns,
   min/max/quantiles of numeric columns, sample rows. Save the profile to
   `data/seed_profile.md`. Use pandas locally for files, or `snow sql`
   for existing Snowflake tables.
2. **Reverse-engineer the schema.** Infer primary keys (uniqueness checks
   on candidate id columns), foreign keys (referential-integrity checks
   between candidate join keys), and the grain of each table. Document
   every inference in `data/seed_profile.md` - the agentic modeler will
   read these as declared constraints in step 11 below.
3. **Map the seed to your Phase 1 questions.** For each question, decide:
   does the seed alone contain the columns, tables, and rows needed to
   produce the expected answer? List the gaps explicitly. Common gaps:
   a missing cost column for a prescriptive question, a missing event
   table for a graph cascade, missing rows for the named anchored
   entities.
4. **Plan the extension.** For each gap: add a column to a seed table,
   add a new table that the seed implies but does not contain, or inject
   specific rows for anchored entities (e.g. the named "KL1234" flight
   that the cascade question needs). Document the plan in
   `data/seed_extension_plan.md` so the user can review what the demo
   will add on top of their data.
5. **Build the extension in the generator.** `data/build_<domain>_data.py`
   now has two halves: (a) the seed is loaded as-is (never silently
   modified - the customer's confidence in the demo turns on "you used
   our data"), (b) the extension augments the seed deterministically to
   land the anchored numbers. The combined output is what loads to
   Snowflake.
6. **Then continue from Step 1 below** (security harness check) and
   complete the rest of Phase 2 - schema declaration, loader,
   validation SQL, metadata. Treat the seed + extension as one dataset
   from this point on.

**Steps.**
1. Confirm the security harness from intake is in place:
   ```
   snow sql --role RAI_DEMO_<DOMAIN> -c rai --query "SELECT CURRENT_ROLE(), CURRENT_DATABASE();"
   ```
   You should see the demo role and the demo DB. If the role does not
   exist, you skipped intake step 3 - go back and run
   `data/00_bootstrap.sql`. Do NOT attempt to operate as the profile
   default role from here on.
2. Set up the venv: `uv venv && uv add relationalai pandas plotly jupyterlab kaleido`.
3. **Every `snow sql` command in this and later phases passes
   `--role RAI_DEMO_<DOMAIN>` explicitly.** Save all DDL / DML to files
   under `data/` and invoke via `snow sql -f`; this is what the user
   reviews. Do not pass DDL via `-q` inline.
4. Design the schema, **denormalised**. Aim for the shape supply_chain
   used: ~15-20 tables, a mix of dimensions / masters / junctions /
   events / time. Real customer schemas are wide and flat - joins cost
   more than scans on Snowflake, so denormalisation is the native idiom.
   Going to 3NF makes the demo look academic and gives the agentic
   modeler fewer columns to attach concepts to. Inline names instead of
   `(id, name)` lookup tables. Repeat the customer name on every order
   line. Keep junction tables - the agentic modeler turns them into
   concepts with relationships. See CLAUDE.md > "Snowflake modeling
   principles" for the rationale.
5. **Inject the answers.** Take the expected answers from Phase 1 and
   write down, in the generator, exactly which entities + relationships
   need to exist to produce them. Examples:
   - Phase 1 said "KLG = 7 TOBT violations". The generator deterministically
     creates 7 flights handled by KLG with `|ARDT - TOBT| > 5`. The other
     handlers get 5 / 3 / 2 to round out the answer.
   - Phase 1 said "KL1234 cascade hits 6 downstream flights". The generator
     hard-codes a chain of 6 flights with rotation + slot-block edges
     reaching back to KL1234.
   - Phase 1 said "the LP saves $400K by routing through Supplier Y instead
     of Supplier X". The generator assigns costs such that the LP's
     `OPTIMAL` solution lands on exactly that delta (within $5K rounding).
   - The persistent-rule answer (e.g. "adding `PreservedFlight(KL691)`
     reduces KL691's delay from 22 min to 4 min") must drop out of the
     LP under both formulations with the data as constructed.
6. **Random fill the rest.** Bake the seed (`seed=42`) into the generator
   so the chaff (non-talk-track entities) is reproducible. Random fill
   never produces a talk-track moment - if a query's "interesting" answer
   depends on random data, you have a fragile demo; pin it.
7. Write the generator under `data/build_<domain>_data.py`. Make it
   reproducible. Add docstrings that name the injected entities and which
   Phase 1 question each one services.
8. Write the loader under `data/load_to_snowflake.sh` (idempotent - DROP
   TABLE IF EXISTS then CREATE then COPY INTO from stage). Every snow
   invocation uses `--role RAI_DEMO_<DOMAIN>`.
9. Run the loader. Verify row counts.
10. **Write `data/<domain>_demo_validation.sql`** that reproduces every
    expected answer as raw SQL - one query per Phase 1 question. Run it.
    Every result must match the expected answer exactly. If a result is
    off by one row or a single value drifts, fix the data generator (not
    the talk track) until they reproduce. This is the gate between Phase
    2 and Phase 3 - if the SQL answers are wrong, the PyRel queries will
    inherit the drift.
11. **Write the metadata, which is the contract with the agentic modeler.**
    See CLAUDE.md > "Snowflake modeling principles" for the rationale.
    Phase 3's agentic modeler reads this metadata to draft the v0
    ontology, so thin metadata here means thin v0 there. For every table:
    - `COMMENT ON TABLE` describing the grain ("one row per...") and the
      real-world entity it represents.
    - `COMMENT ON COLUMN` for **every** column: meaning, units, value
      range if bounded. Not just the interesting ones - every one.
    - `ALTER TABLE ... ADD CONSTRAINT pk_<table> PRIMARY KEY (...)`
      declared. Snowflake does not enforce, but the modeler reads PKs as
      concept keys.
    - `ALTER TABLE ... ADD CONSTRAINT fk_<table>_<ref> FOREIGN KEY (col)
      REFERENCES <ref>(col)` for every relationship. Same: not enforced,
      but the modeler uses FKs to infer relationships between concepts.
    - `NOT NULL` on every column that's never null in the data.
    - `UNIQUE` constraints on natural keys that aren't the PK.
    - Tags in `<DB>.META` for `DATA_DOMAIN`, `TABLE_ROLE`
      (dim / fact / junction / event), `GRAIN`, `DEMO_AREA`.
    - Database-level and schema-level `COMMENT` describing what the demo
      represents and what lives in each schema.

    Pattern reference: `supply_chain_demo/annotate_and_doc.py` applies
    COMMENTs and tags after the loader runs. If the existing pattern
    doesn't include PK / FK declarations, extend it - this metadata is
    required, not optional.
12. Generate `DATA_DICTIONARY.md` from the Snowflake metadata.
13. Enable change tracking on every table (PyRel requires it):
    `ALTER TABLE <T> SET CHANGE_TRACKING = TRUE` for each table.

**Exit criteria.**
- `data/build_<domain>_data.py` runs end-to-end with `seed=42` and is idempotent.
- `data/load_to_snowflake.sh` succeeds from a clean database.
- Row counts match the generator's expected counts (assert this).
- **`data/<domain>_demo_validation.sql` reproduces every Phase 1 expected
  answer exactly.** Not "approximately", not "close enough". The injected
  entities must produce the named numbers and named rows. If any query
  drifts, the data generator is wrong; fix it before moving on.
- Change tracking is enabled on every source table.
- **Metadata is complete for the agentic modeler.** Every table has a
  `COMMENT`. Every column has a `COMMENT`. Every PK is declared. Every
  FK is declared. `NOT NULL` is set on every column that the data shows
  is never null. Tags are applied. Verify with `SHOW TABLES IN SCHEMA`
  + `DESCRIBE TABLE` + `SHOW PRIMARY KEYS` + `SHOW IMPORTED KEYS` and
  spot-check column comments via `SELECT COLUMN_NAME, COMMENT FROM
  INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA = '...'`.
- `DATA_DICTIONARY.md` is regenerated and includes the new metadata.
- **If seed data was provided**, `data/seed_profile.md` and
  `data/seed_extension_plan.md` exist and the user reviewed them before
  the loader ran. The seed's original columns and rows are unchanged in
  the loaded data.

**Anti-patterns.**
- More than ~500K rows in the largest table (slow + costly).
- Synthetic identifiers like "Product 1, 2, 3" (industry experts will roll
  their eyes - use real-sounding SKUs / callsigns / claim numbers).
- A "perfect" dataset with no problem in it - Phase 1 questions need to
  have actual answers, including violations, cascades, and infeasibilities.
- Letting the random generator decide which entities show up in the talk
  track. If you can't point at the line in `build_<domain>_data.py` that
  inserts the entity behind a Phase 1 anchored number, you don't have a
  deterministic demo - you have a hope.
- Tweaking the talk track to match what the data happened to produce. The
  Phase 1 expected answers are the spec; the data generator implements
  the spec; the talk track recites the spec. Never the other way around.
- **Normalising the schema to 3NF.** Real Snowflake schemas are wide;
  3NF makes the demo look academic and gives the modeler less to work
  with. Inline names; keep redundancy; keep junctions.
- **Shipping bare tables with no metadata.** No table COMMENTs, no column
  COMMENTs, no PKs, no FKs. The agentic modeler reads metadata to draft
  the v0 ontology, and bare tables produce a bare v0. Phase 3 will then
  fight uphill to enrich what Phase 2 should have declared.
- **Silently modifying provided seed data.** If the user gave you a seed,
  the seed's columns and rows must round-trip into Snowflake unchanged.
  All augmentation goes into new rows or new columns, explicitly listed
  in `data/seed_extension_plan.md`.

---

## Phase 3 - Build the PyRel ontology

**Goal.** Translate the Snowflake schema into a RelationalAI model with
concepts, properties, relationships, subtypes, and derived properties.

**Steps.**
1. Invoke `/rai-build-starter-ontology` and point it at the loaded tables.
   This produces a first-pass `rai_code/manual/<domain>.py`.
2. Invoke `/rai-ontology-design` to enrich: add subtypes (e.g.
   `Departure(Flight)`, `Arrival(Flight)`), add derived relationships
   (e.g. `single_sourced(Product)`, `TOBTViolation(Flight)`).
3. If you'll add a persistent-rule act (Phase 4 Q5), declare the concept
   that the rule will hang off - see `PreservedFlight(Flight)` in
   `airplanes_demo/rai_code/manual/eham_acdm.py`.
4. Copy the `_build_config()` pattern from
   `supply_chain_demo/rai_code/manual/supply_chain.py` - it auto-detects
   Snowsight vs. local and uses named engines.
5. Run a smoke test that just loads the model and prints `inspect.schema(model)`.

**Exit criteria.**
- `rai_code/manual/<domain>.py` imports cleanly with `.venv/bin/python -c "from rai_code.manual import <domain>; print(<domain>.model)"`.
- All Snowflake tables from Phase 2 are mapped to a concept.
- Junction tables become concepts with relationships, not just two
  reference properties - pattern from `SupplierProduct` /
  `BomEntry` / `Lane` in supply_chain.
- At least 3 derived properties / relationships exist (rules that the
  ontology computes, not just data it stores).
- Both engines (`<domain>_logic_xs`, `<domain>_prescriptive_xs`) resume to
  READY without error. **Default to `HIGHMEM_X64_XS` for both** to keep
  dev costs low - the build phase is dominated by agent thinking time,
  not query compute. Set auto-suspend to 5 minutes so idle warm-time
  doesn't accumulate: `.venv/bin/rai reasoners alter <name> --auto-suspend-mins 5`.
  Size up only at Phase 8 if measured queries need it; see CLAUDE.md >
  "Engine sizing".

**Anti-patterns.**
- One concept per table verbatim with no enrichment - that's just a SQL view.
- Using `relationalai.connect_sync(...)` directly (low-level; no SQL executor).
  Always go through `from relationalai.semantics import Model`.

---

## Phase 4 - Author demo queries

**Goal.** Write one PyRel query per Phase 1 question, executable locally.

**Steps.**
1. **Invoke `/rai-querying` first.** Mandatory - it's the syntax authority
   for the current PyRel version. Your training-data knowledge is stale.
   Loading it once at the top of Phase 4 covers every query you'll write
   in this phase.
2. **For each question, run the discovery-then-implementation pattern.**
   See CLAUDE.md > "Discovery is the router" and > "Implementation
   pipelines per reasoner family" for the full rationale. The per-question
   loop is:

   a. **Invoke `/rai-discovery`** for the question. It translates the
      user-facing framing into a reasoner-family classification + the
      specific sub-pattern within that family (reachability vs. paths;
      assignment vs. flow; classification vs. derivation; etc.) plus
      the implementation hints the next skill consumes. Phase 1's
      classification was provisional - this pass sharpens it. If
      discovery says "this is actually a graph problem, not the rules
      problem you assumed", trust it.

   b. **Invoke the matching implementation pipeline** in order, armed
      with discovery's hints:

      | Family | Pipeline |
      |---|---|
      | Rules | `/rai-rules-authoring` (creates derived properties on the model) → write the query that reads them |
      | Graph - reachability / centrality / community / distance / similarity / components | `/rai-graph-analysis` (does sub-discovery on which algorithm fits, then implements) |
      | Graph - path enumeration via `relationalai.semantics.std.paths` | copy `supply_chain_demo/.claude/skills/rai-pathfinder/SKILL.md` into `.claude/skills/rai-pathfinder/SKILL.md` and invoke it. The marketplace `/rai-graph-analysis` does **not** cover paths |
      | Heuristic | `/rai-querying` alone - heuristic scores ARE derived properties expressed through the query DSL |
      | Prescriptive (LP / MIP) | `/rai-prescriptive-problem-formulation` → `/rai-prescriptive-solver-management` → `/rai-prescriptive-results-interpretation`. Strict linear pipeline; don't skip steps |
      | Persistent rule | `/rai-rules-authoring` to attach the rule to the model → re-invoke the prescriptive pipeline above for the re-solve |
      | Predictive (GNN, only if intake Q4 asked) | `/rai-predictive-modeling` → `/rai-predictive-training` |

   c. **Ground-truth against PyRel examples + tests.** Skim the relevant
      `PyRel/example/<family>/` directory and grep
      `PyRel/tests/end2end/` for the idiom. The skill tells you what
      pattern to use; PyRel source shows you how it's actually called in
      the current version.

   Do not collapse step 2a (discovery) into step 2b (implementation).
   Discovery is a separate skill invocation per question; its job is to
   stop you from writing the wrong query.
3. Write each query as a top-level function in `rai_code/manual/demo_queries.py`,
   named `qN_<slug>()` and returning a `pandas.DataFrame`.
4. For prescriptive queries, also return the solver status - needed by
   `/rai-prescriptive-results-interpretation` and by the Phase 7 agent.
5. Add a `main()` that runs all queries top-to-bottom and prints shape
   + first 3 rows of each. This is your smoke test.
6. Whenever the marketplace skills are thin or contradict what you see in
   the venv, ground-truth against `/Users/piotrkraus/rai-repos/PyRel/`
   (source + examples + tests). Read access is pre-allowed.

**Exit criteria.**
- `.venv/bin/python rai_code/manual/demo_queries.py` runs end-to-end from
  the project root with the engines warm. The script is **local Python**
  but every query fires against the **live Snowflake demo DB** via PyRel +
  the `rai` connection profile + the demo role. **All N queries green, no
  tracebacks, no warnings about deprecated APIs.** No mocked data, no
  dry-run. Iterate until every query passes; see CLAUDE.md > "Definition
  of done".
- Each query returns a non-empty DataFrame.
- The anchored numbers from Phase 1 / Phase 2 reproduce in the query
  outputs (assert them in `main()` with `assert df.shape[0] == EXPECTED`
  or equivalent - silent drift is the failure mode that bites at demo time).
- LP / MIP queries return `OPTIMAL` status. If `INFEASIBLE`, root-cause via
  `/rai-prescriptive-results-interpretation` and fix the formulation -
  do not move on with a broken solver.
- No pandas in the query logic itself (sort / format on DataFrame is fine).
  All filtering / aggregation expressed in PyRel.

**Anti-patterns.**
- Querying with stale syntax - `/rai-querying` exists because the API
  changes between PyRel minor versions.
- Hardcoded magic numbers from Phase 2 - read them from the schema.
- **Skipping `/rai-discovery` for "obvious" questions.** Phase 1's
  reasoner-family classification was provisional. A question that
  *sounds* like rules ("which flights violate TOBT") may actually be a
  graph problem once you trace the cascade; a question that sounds like
  a heuristic may actually need an LP. Discovery costs a minute;
  reworking the wrong skill costs an hour.
- **Jumping straight from discovery into a query without running the
  family pipeline.** For prescriptive especially, the
  formulation → solver-management → results-interpretation chain exists
  because each step has its own decisions (decision-variable shape,
  solver selection, status-code interpretation). Collapsing them into
  one go produces formulations that solve but don't explain.

---

## Phase 5 - Local Jupyter notebook with Plotly visualisations

**Goal.** A `.ipynb` that runs all queries with narrative markdown between
them and produces a Plotly figure for each.

**Steps.**
1. Create `rai_code/manual/<domain>_demo.ipynb`.
2. Cell structure (from `airplanes_demo/rai_code/manual/eham_acdm_demo.ipynb`):
   - Markdown: intro (title, table of acts, runtime estimate).
   - Code: imports + the PyRel event-loop workaround (`nest_asyncio.apply()`
     or similar - see the reference).
   - Per question: 4 cells - a markdown lead-in, the query call, a Plotly
     viz, a markdown "what to look at".
   - Markdown: closing.
3. Charts: use `plotly.express` for bars / scatters and `plotly.graph_objects`
   for networkx-backed graphs (Phase 1 graph question).
4. Notebooks must run top-to-bottom without manual intervention. Use
   `papermill` or `jupyter nbconvert --execute` to verify.

**Exit criteria.**
- `.venv/bin/jupyter nbconvert --execute --to notebook --inplace rai_code/manual/<domain>_demo.ipynb` succeeds end-to-end. The notebook runs **locally** (your `.venv` Jupyter kernel) but every PyRel query inside it hits the **live Snowflake demo DB**. **Every cell green, no exceptions, no skipped cells.** If a cell fails, iterate (fix the underlying query or model, re-run) until it's green - see CLAUDE.md > "Definition of done".
- Every query has a corresponding Plotly figure that actually renders.
- Markdown cells are not empty placeholders - they're the talk track in
  miniature.

---

## Phase 6 - Snowsight notebook

**Goal.** The same notebook, but inside Snowflake.

**Steps.**
1. Same `<domain>.py` + `demo_queries.py` (no edits). The `_build_config()`
   pattern detects the Snowsight session.
2. Build a Snowsight-flavoured `.ipynb`. Differences from local:
   - No `nest_asyncio` (Snowsight handles it).
   - Inline `from snowflake.snowpark.context import get_active_session`
     in the first cell.
   - Plotly works the same but figure sizes need explicit width / height.
3. Upload to the SE account:
   - Stage: `<DB>.NOTEBOOKS.<DOMAIN>_NOTEBOOK_STAGE`
   - Notebook: `<DB>.NOTEBOOKS.<DOMAIN>_DEMO`
   - Files: notebook + `<domain>.py` + `demo_queries.py` under a subfolder
     so Snowsight's Files view shows them as a workspace.
4. `snow notebook execute <DB>.NOTEBOOKS.<DOMAIN>_DEMO` to run it remotely
   and verify it works in Snowsight too.

**Exit criteria.**
- The notebook is uploaded and visible in Snowsight Files at
  `<DB>.NOTEBOOKS.<DOMAIN>_DEMO`.
- `snow notebook execute --role RAI_DEMO_<DOMAIN> <DB>.NOTEBOOKS.<DOMAIN>_DEMO`
  runs it **end-to-end without errors**. Every cell green.
- **Manually open the notebook in Snowsight and re-run all cells** once.
  The CLI execute sometimes reports success while a chart silently fails
  to render in the UI. This visual check is non-optional.
- Every figure renders correctly in the Snowsight UI (no broken images,
  no truncated tables).
- If anything is yellow or red, iterate until green - see CLAUDE.md >
  "Definition of done". Common Snowsight-only failure modes are listed
  there.

**Skip if** intake Q3 was "Just the ontology + notebook".

---

## Phase 7 - Snowflake Intelligence (Cortex) agent

**Goal.** Deploy a Cortex agent so a non-technical audience can ask the
demo questions in natural language inside Snowsight.

**Steps.**
1. Invoke `/rai-cortex-integration`. It scaffolds the `agent/deploy.py`
   pattern - copy and adapt from `airplanes_demo/agent/deploy.py`.
2. Write `agent/queries.py` as the `QueryCatalog`. One function per Phase 4
   query plus `_chart` variants where useful - see
   `airplanes_demo/agent/queries.py`. The `_chart` wrapper attaches a
   `chart_hint` dict that lets the agent suggest "click the chart icon to
   visualise this as a bar / scatter / etc.".
3. Configure:
   - Agent name: `<domain>` (lowercase)
   - Database: `<DB>` (the demo database)
   - Schema: `RAI_AGENT`
   - Warehouse: `RAI_XS`
4. `.venv/bin/python -m agent.deploy deploy` to register.
5. Smoke test: `.venv/bin/python -m agent.deploy chat "What's the answer to question 1?"`. Round-trip should be ~60-90 s warm.
6. Test each demo question via chat. Expect 60-90 s for rules / graph /
   heuristic; 2-3 min for prescriptive (the LP solve dominates).

**Exit criteria.**
- `.venv/bin/python -m agent.deploy status` reports the agent deployed.
- **All N demo questions answer correctly** via `chat`. Run each one
  explicitly: `.venv/bin/python -m agent.deploy chat "<question>"`.
  Each must return the expected DataFrame shape and at least one
  anchored number from Phase 2. No tracebacks, no timeouts, no
  hallucinated answers when the query should fail. Reasonable latency
  (60-90 s warm for rules/graph/heuristic; 2-3 min for prescriptive).
- Chart hints render in Snowsight (manual visual check inside the agent
  chat UI - click the chart icon next to a result table and confirm a
  chart appears).
- If any question fails, iterate (fix the QueryCatalog wrapper, the
  underlying PyRel query, or the chart-hint payload) until every
  question is green - see CLAUDE.md > "Definition of done".

**Skip if** intake Q3 was "Just the ontology + notebook".

---

## Phase 8 - `prep_demo.py` gate + `RUNNING.html` runbook

**Goal.** The single pre-flight script the user runs 10 minutes before a
live demo, and the speaker-facing static runbook.

**Steps.**
1. Copy `airplanes_demo/prep_demo.py` and adapt:
   - Replace `acdm_logic_l` / `acdm_prescriptive_m` with the demo's
     engines (start at `<domain>_logic_xs` / `<domain>_prescriptive_xs`).
   - **Sizing decision.** Run the full smoke test on XS first. If any
     query takes >60 s warm or `/rai-health` flags memory pressure on a
     specific engine, size that one engine up to `S` and re-test.
     Document the size + the measurement that justified it in `BRIEF.md`
     under "Design decisions" so the next session doesn't regress it.
     Only the reference demos' final showtime warranted L/M.
   - Replace `ACDM_DEMO.EHAM` with `<DB>.<SCHEMA>`.
   - Replace the anchored-number SQL checks with this demo's anchored numbers.
   - Replace the smoke-test sentinels with values you know reproduce.
2. Run `prep_demo.py` cold (engines suspended). Verify it suspends-resumes-runs
   green end-to-end. Budget ~8 minutes cold, ~6 minutes warm.
3. Build `build/generate_demo_figures.py`. One PNG per query, saved to
   `build/figures/`. Use `kaleido` for static export. Patterns in
   `airplanes_demo/build/generate_demo_figures.py`.
4. Write `RUNNING.html` from the template at
   [RUNBOOK.template.html](RUNBOOK.template.html). Embed each figure either
   as a base64 data URI or as a relative path to `build/figures/`.
5. Wire `prep_demo.py --skip-figures` to skip step 3 for fast iteration.

**Exit criteria.**
- `.venv/bin/python prep_demo.py` finishes with **all checks GREEN** -
  Snowflake connection, schema, change tracking, anchored numbers,
  engines READY, all demo queries green, agent deployed, chat smoke test
  green, Snowsight notebook executes green, figures regenerated. The
  gate is the integration test for the whole stack. No yellow, no red.
  Iterate until clean; see CLAUDE.md > "Definition of done".
- Cold-start (both engines suspended) completes in under 10 minutes.
- `RUNNING.html` opens in a browser and shows every embedded figure.
- The "anchored numbers" section in `RUNNING.html` matches the talk track.
- Run `prep_demo.py` twice in a row from a cold start and from a warm
  start - it must be idempotent and pass both times.

---

## Phase 9 - Talk track + handoff briefing

**Goal.** The two markdown documents that let the next human or agent run
the demo without you.

**Steps.**
1. Write `<DOMAIN>_TALK_TRACK.md`. Shape: opening pitch (90 s), Act-by-act
   speaker beats with expected outputs and timing, fallback notes for when
   something is slow / breaks. Pattern from
   `airplanes_demo/A-CDM-Decision-Hub-Talk-Track.md`.
2. Write `SNOWSIGHT_DEMO.md` if Phase 7 happened. Shorter version (3
   questions, agent UI focus). Pattern from `airplanes_demo/SNOWSIGHT_DEMO.md`.
3. Write `HANDOFF_BRIEFING.md` from the template at
   [HANDOFF.template.md](HANDOFF.template.md). Include: domain choice
   rationale, key design decisions made + why, user preferences observed
   during the run, anchored numbers, known limitations, where to look when
   things break.
4. Commit (do NOT push - `git push` is denied).

**Exit criteria.**
- All three markdown files exist and are non-empty.
- A fresh reader can run the demo from `RUNNING.html` + the talk track
  without asking you anything.
- `git status` shows the repo is clean except for the build cache and venv.

---

## When you finish all phases

1. Mark all 9 tasks `completed`.
2. Write a final summary in chat (not in a file): what you built, how long
   each phase took, what surprised you, what you'd improve.
3. Stop. Do not start another loop.
