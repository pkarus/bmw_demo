# REFERENCES.md - file-by-file map into the two reference demos

Two complete RelationalAI demos live as sibling directories. The template
does NOT ship Python stubs - instead, every phase tells you which reference
file to model your work on. This page is that lookup.

```
/Users/piotrkraus/rai-repos/supply_chain_demo  ← 10 questions, LP + knapsack
/Users/piotrkraus/rai-repos/airplanes_demo     ← 5 acts, MIP + persistent rule (newer, more polished)
```

When in doubt, **airplanes_demo is the more mature reference.** Use it for
shape; pick from supply_chain_demo for the variants it captures that
airplanes_demo doesn't (annotate-and-doc, declare-constraints, the
extend-data scenario shaping).

## By phase

### Phase 1 - Position RAI in domain
- `airplanes_demo/DEMO_QUESTIONS.md` - 5 acts as plain-English questions,
  each tagged with reasoner + why-it-matters. **Copy this shape.**
- `supply_chain_demo/DEMO_QUESTIONS.md` - 10-question variant.
- `airplanes_demo/A-CDM-Decision-Hub-Talk-Track.md` - what a polished talk
  track looks like once you've authored the questions.

### Phase 2 - Data
- `airplanes_demo/data/build_eham_demo_data.py` - synthetic generator,
  `seed=42`, hard-coded narrative entities. **The defensible-against-experts
  pattern.**
- `airplanes_demo/data/load_to_snowflake.sh` - 5-step idempotent loader
  (DDL, refs, masters, stage+PUT, COPY INTO).
- `supply_chain_demo/build_pk_supply_chain.py` - alternative loader pattern
  (DDL + INSERT directly, no CSV).
- `supply_chain_demo/extend_data.py` - adds optimisation-relevant columns
  after the base load. Useful when your base schema is mostly correct but
  needs cost / capacity fields for Phase 4 prescriptive.
- `supply_chain_demo/annotate_and_doc.py` - Snowflake-native metadata
  (COMMENTs + tags) + auto-generates `DATA_DICTIONARY.md`. **Run a variant
  of this in Phase 2 step 8.**
- `supply_chain_demo/declare_constraints.py` - PK/FK metadata (not enforced
  but documents intent).
- `supply_chain_demo/sf.py` - ad-hoc SQL runner. Useful as a smoke utility.
- `airplanes_demo/data/out/eham_demo_validation.sql` - the SQL that
  reproduces the anchored numbers. **Always write one of these.**

### Phase 3 - Ontology
- `supply_chain_demo/rai_code/manual/supply_chain.py` - the full
  17-concept ontology. **The `_build_config()` pattern that works in both
  local Python and Snowsight notebooks lives here. Copy it verbatim, change
  the engine names.**
- `airplanes_demo/rai_code/manual/eham_acdm.py` - same shape, plus the
  `PreservedFlight(Flight)` derived concept that backs the Act 5 persistent
  rule. Use this if your demo has a persistent-rule act.

### Phase 4 - Queries
- `supply_chain_demo/rai_code/manual/demo_queries.py` - 10 demo functions:
  rules with aggregation (Q1, Q4, Q10), temporal join (Q3), graph paths
  (Q9), LP (Q7), knapsack (Q8).
- `airplanes_demo/rai_code/manual/demo_queries.py` - 5 acts: rules (Q1),
  graph reachability (Q2), heuristic scoring (Q3 - deterministic fit-score
  used because GNN reasoner is still preview), MIP (Q4), persistent rule
  re-solve (Q5).
- `supply_chain_demo/.claude/skills/rai-pathfinder/SKILL.md` - local
  project skill (~417 lines) documenting `relationalai.semantics.std.paths`.
  **Read before writing graph queries.**

### Phase 5 - Local notebook
- `airplanes_demo/rai_code/manual/eham_acdm_demo.ipynb` - ~22 cells, 5-act
  Plotly visualisations, markdown narrative between. **Mirror this cell
  structure.**
- `supply_chain_demo/rai_code/manual/supply_chain_demo.ipynb` - same idea,
  10 questions, self-contained Snowflake Notebook-compatible.

### Phase 6 - Snowsight notebook
- `supply_chain_demo/rai_code/manual/supply_chain_demo.ipynb` - written to
  work in BOTH local Jupyter AND Snowsight (single file, no fork). PyRel's
  `ConfigFromActiveSession` makes this possible.
- `airplanes_demo` has a separate Snowsight upload via `prep_demo.py
  --skip-figures` - see the stage upload block.

### Phase 7 - Cortex agent
- `airplanes_demo/agent/deploy.py` - newer, more polished.
  `CortexAgentManager` + `ToolRegistry` + CLI verbs (`deploy`, `update`,
  `status`, `chat`, `teardown`). **Use this as the template.**
- `airplanes_demo/agent/queries.py` - `QueryCatalog` with `_wrap_chart`
  helper for Snowsight one-click visualisation. **Copy the chart-hint
  pattern.**
- `supply_chain_demo/agent/deploy.py` - older variant of the same shape.

### Phase 8 - Gate + runbook
- `airplanes_demo/prep_demo.py` - **the** reference. 708 lines, ~8 checks,
  `CheckResult` dataclass, colour-coded output, `--skip-figures
  --skip-chat --skip-snowsight --redeploy` flags. Cold start runs in ~8
  minutes. Copy and parameterise.
- `airplanes_demo/build/generate_demo_figures.py` - 5 Plotly figures
  exported as PNG via `kaleido`. Used by `RUNNING.html`.
- `airplanes_demo/RUNNING.html` - speaker-facing runbook with embedded
  PNGs, phase tabs, colour-coded reasoner badges.
- `supply_chain_demo/RUNNING.html` - alternative runbook style (less
  visual, more checklist).

### Phase 9 - Talk track + handoff
- `airplanes_demo/A-CDM-Decision-Hub-Talk-Track.md` - full talk track,
  ~700 lines, code disclaimers + speaker beats + timing.
- `airplanes_demo/SNOWSIGHT_DEMO.md` - shorter 3-question Snowsight
  variant.
- `airplanes_demo/HANDOFF_BRIEFING.md` - domain rationale + key decisions
  + user preferences + file map. **The canonical handoff shape.**

## CLAUDE.md files

Both demos have their own `CLAUDE.md` at the repo root. They are written
for an agent that has *already finished* the demo build - they document
"here's how everything fits together" for the next person.

- `airplanes_demo/CLAUDE.md` - 200 lines, includes a measured timing table
  (cold vs warm), demo-day cadence, where-to-look-when-things-break.
- `supply_chain_demo/CLAUDE.md` - 80 lines, lighter, focuses on repo layout
  + Python env + Snowflake conventions + PyRel notes.

At Phase 9, write a similar `CLAUDE.md` for *this* demo. Use airplanes_demo
as the model - its timing table format is the right one because it's
measured, not aspirational.

## What NOT to copy

- The exact concept names. They're domain-specific.
- The exact engine names and sizes - the reference demos sized up to
  `_logic_l` / `_prescriptive_m` for warm showtime performance. Your
  template default is `<model>_logic_xs` / `<model>_prescriptive_xs` at
  `HIGHMEM_X64_XS` to keep dev costs low. Size up only when measured
  (see CLAUDE.md > "Engine sizing"). When you grep the reference demos
  and see `acdm_logic_l` or `supply_chain_logic_l`, that's a final tune,
  not a starting point.
- The hard-coded anchored numbers. Pick your own in Phase 2 and back them
  with your own validation SQL.
- The `supply_chain_demo/rai_code/modeler/` directory - it's empty; was
  reserved for an experiment that didn't happen.

## What both demos have but the template doesn't

- A real venv at `.venv/` (you'll create yours in Phase 2).
- A populated `build/` cache (you'll regenerate on first PyRel run).
- A `~/.snowflake/connections.toml` profile named `rai` - already on this
  machine, no action needed.

## The PyRel local checkout (`/Users/piotrkraus/rai-repos/PyRel`)

Third reference, alongside the two demos. Source-of-truth for API
signatures, runnable examples for every reasoner family, and tests-as-docs.
Read access is pre-allowed in `.claude/settings.json`. Use it when the
marketplace skills are thin or out of date.

| Path | When to read | Notes |
|---|---|---|
| `PyRel/src/relationalai/semantics/std/paths/` | Phase 4 graph-path questions | The pathfinder source. Pre-GA. The `rai-pathfinder` project-local skill in `supply_chain_demo/.claude/skills/` is the friendly companion. |
| `PyRel/src/relationalai/semantics/reasoners/prescriptive/` | Phase 4 LP/MIP, Phase 7 agent setup for solver tools | `Problem`, `Solver`, decision-variable wiring all live here. |
| `PyRel/src/relationalai/semantics/` | Anywhere you need a canonical API signature | Includes `Model`, `Concept`, `Property`, `aggs`, `rank`, `top`, `inspect`. |
| `PyRel/example/paths/` | Before authing a path-query | Each example is a small runnable program. |
| `PyRel/example/prescriptive/` | Before authing an LP/MIP question | Same. |
| `PyRel/example/cortex/` | Phase 7 (Cortex agent) | Reference deployment patterns. |
| `PyRel/tests/end2end/` | When grepping for unfamiliar idioms | Each test is documentation. Especially useful when a marketplace skill says "use X" but doesn't show how. |
| `PyRel/tests/reasoners/` | Reasoner-specific debugging | Narrower than end2end, often more illustrative. |
| `PyRel/docs/` | When public docs at docs.relational.ai are stale | Less polished but more current than the public site. |
| `PyRel/notes/` | Pre-GA feature design context | Internal notes - useful when working on features that haven't shipped yet. |

The installed `relationalai` in your `.venv/` may lag the checkout. Verify
with `uv pip show relationalai` and compare to `PyRel/pyproject.toml`. If
the gap matters, install from the checkout: `uv pip install -e /Users/piotrkraus/rai-repos/PyRel`.

## Project-local skills (the pre-GA pattern)

Marketplace skills cover GA features. For pre-GA features, the reference
demos add a project-local skill at `.claude/skills/<skill-name>/SKILL.md`.
Claude Code picks these up from the active project automatically.

Canonical example:
`supply_chain_demo/.claude/skills/rai-pathfinder/SKILL.md` - 417-line
authoritative reference for `relationalai.semantics.std.paths`
(pre-GA path enumeration). Capability matrix, footgun list, query
templates. The marketplace `/rai-graph-analysis` skill does NOT cover this.

When your demo uses a pre-GA feature, replicate the pattern:
1. Create `.claude/skills/<feature>/SKILL.md` in your repo.
2. Write the rules / footguns / templates the next session will need.
3. Grep PyRel source + tests to back up every claim.
4. The next agent session inherits it automatically.

That's the entire mapping. Don't reinvent anything that's in either
reference demo or in PyRel without a reason - all three went through
several iterations to get to their current shape.
