# DEMO_QUESTION_CATALOG.md - question archetypes per reasoner

Use this catalog at Phase 1 when you're inventing the N demo questions.
Each entry is a question SHAPE - a pattern that lands well in front of an
audience and showcases the named reasoner. Pick one shape per question,
adapt the domain.

## The injection rule (read this first)

For every question you pick from this catalog, write down the **exact
expected answer** before you move to Phase 2. The answer is what makes
the demo interesting; the data is engineered backwards to produce it.

- Don't write "Q1 will show some flights in violation". Write
  "Q1 will show KLG=7, AGS=5, DNATA=3, MENZIES=2".
- Don't write "Q4 will route through cheaper suppliers". Write
  "Q4 OPTIMAL routes 60% through Supplier B (Bangalore) and 40% through
  Supplier S (Suzhou), saving $412K over the status-quo split".
- Don't write "Q5 will change the answer". Write "Q5 with
  `PreservedFlight(KL691)` added drops KL691's delay from 22 min to 4
  min and pushes KL2014 from 8 min to 14 min".

These are the **anchored numbers**. Phase 2's data generator injects the
entities + relationships + cost structure that produce them exactly.
Phase 8's `prep_demo.py` gate asserts them as SQL. The talk track
quotes them verbatim. If any of these drift between sessions, the demo
lies; the script fails the gate; you fix the data, not the talk track.

## Rules (derived properties)

The "show me everywhere X is true" or "classify these into A vs B" pattern.
Lives entirely in `model.where(...).select(...).to_df()`.

| Shape | Example (supply chain) | Example (airplanes) |
|---|---|---|
| Threshold breach | "Where are we below safety stock right now?" | "Which flights are out of TOBT compliance?" |
| Classification | "Which products are single-sourced?" | "Which arrivals are widebody non-Schengen?" |
| Concentration / Pareto | "Which 5 suppliers cover 80% of spend?" | "Which 3 handlers cause most TOBT misses?" |
| Time-window aggregate | "How much forecast bias by family last quarter?" | "How many CTOTs were issued in the last 4 hours?" |

**Anti-pattern.** A rule that's actually just a SQL count - give it a
derived property that the ontology computes, not a one-shot aggregation.

## Graph

The "follow the chain" pattern. Reachability, paths, components,
centrality. Always built from concept-pair patterns via
`relationalai.semantics.std.paths` or the `Graph` builder.

| Shape | Example (supply chain) | Example (airplanes) |
|---|---|---|
| Multi-hop reachability | "What finished goods are exposed to high-risk supplier X?" (3-tier BOM walk) | "If KL1234 is late, what flights cascade?" (rotation + slot-block + stand) |
| Path with constraint | "Find the cheapest path supplier → DC for product P" | - |
| Centrality | "Which warehouse is most-central in the lane network?" | "Which stand has the most rotational pressure?" |
| Component / cluster | "Which products form a single co-shipped cluster?" | - |

**Anti-pattern.** A graph question that's really one hop - that's a join.
Need ≥2 hops or a transitive closure for it to feel like graph.

## Heuristic (deterministic fit-score)

The "rank by this score I just defined" pattern. Useful when the audience
expects "AI" but you don't have a real ML model handy. Express the score as
derived properties on the ontology.

| Shape | Example (supply chain) | Example (airplanes) |
|---|---|---|
| Risk score | "Rank DCs by closure-risk score (cost / utilisation)" | "Rank arrivals by MS5 gate-conflict risk" |
| Fit score | "Rank lanes by CO2-cost trade-off" | "Rank candidate stands by widebody-compatibility score" |

The airplanes demo's Act 3 is the canonical version - a fit-score that
combines time pressure, passenger weight, pier bonus, and WTC penalty. All
deterministic PyRel; no ML model.

**The talk track for these is "this is what an early-access predictive
reasoner would replace - we use a deterministic version for now."** That's
authorised by `airplanes_demo/CLAUDE.md`.

## Prescriptive (LP / MIP)

The "optimise X subject to Y" pattern. Uses
`relationalai.semantics.reasoners.prescriptive.Problem` and a `Solver`.

| Shape | Example (supply chain) | Example (airplanes) |
|---|---|---|
| Min-cost LP | "What's the cheapest sourcing split with a 70% supplier cap?" | - |
| 0/1 Knapsack | "Which POs to expedite given a $X budget?" | - |
| MIP scheduling | - | "Re-sequence TSATs in the storm window minimising weighted delay" (47 flights × 120 slots = 5.6K binaries) |
| Bin-packing / assignment | "Assign products to DCs minimising stockout risk" | "Assign flights to runways under wind constraint" |

**Anti-pattern.** A prescriptive problem with no real constraint - that's a
sort. The constraint is what makes it interesting.

**Solver expectations:**
- HiGHS is free and ships with PyRel - use for LP and small MIP.
- Gurobi via license for large MIP - but the demo data should be small
  enough that HiGHS is plenty.
- Solver status: assert `OPTIMAL`. If `INFEASIBLE` after re-formulation,
  the constraint set is over-defined - drop a soft constraint. If
  `TIME_LIMIT`, raise it via `/rai-prescriptive-solver-management`.

## Persistent rule

The "operator adds a business rule, ontology stores it, every downstream
query respects it" pattern. The killer demo moment - proves the model is
operationally alive.

Pattern (from `airplanes_demo/rai_code/manual/eham_acdm.py`):
1. Declare a concept `PreservedFlight(Flight)` - empty to start.
2. Author a derived property: `if flight in PreservedFlight, treat as
   high-priority in the LP objective`.
3. The Phase 4 query for this act is: "Re-solve the LP from Act 4, but
   first add `PreservedFlight(KL691)` to the model. Did the answer change?"
4. The answer changes because the LP now respects the new rule. Audience
   sees the operator's intent propagate through the whole stack.

| Shape | Example (supply chain) | Example (airplanes) |
|---|---|---|
| Preferred-entity rule | "Add 'never expedite < $50K POs' rule - re-solve knapsack" | "Add 'preserve KL flights with >80 pax connections' - re-solve MIP" |
| Forbidden-pairing rule | "Add 'never source SKU X from Supplier Y' - re-solve sourcing" | "Add 'never use Polderbaan between 22:00-06:00' - re-solve assignment" |

**The talk track move.** Add the rule live, watch the previously-optimal
answer flip. This is the moment that justifies RelationalAI over a
notebook-of-LPs approach.

## Predictive (GNN)

Skip unless intake Q4 explicitly asked for it. The skill is early access
(`/rai-predictive-modeling` and `/rai-predictive-training`) and neither
reference demo uses it - both substitute the deterministic heuristic above
when the talk track wants a "predictive" feel.

If you do use it: `airplanes_demo/CLAUDE.md` explicitly authorises the
fallback, so when in doubt fall back.

## Composing the N questions into a narrative

For N=3 (Snowsight short):
1. Rules - set the scene, expose a problem.
2. Graph - reveal the hidden dependency.
3. Prescriptive - fix it.

For N=5 (the airplanes shape):
1. Rules - TOBT compliance audit (problem exposure)
2. Graph - KL1234 cascade (hidden dependency)
3. Heuristic - MS5 gate-conflict ranking (predictive feel without GNN)
4. Prescriptive - TSAT re-sequence under storm (the big solve)
5. Persistent rule - preserve KL high-pax flights (operator authority)

For N=10 (the supply_chain shape):
- Three rules questions (safety stock breach, single-source exposure,
  forecast bias) - establish the data
- One graph question (BOM exposure)
- Two metrics / aggregation questions (CO2 lanes, inventory value trend)
- One temporal join (Suzhou shortage replay)
- Two prescriptive (LP sourcing split + knapsack expedite)
- One rules + metrics (DC closure candidates)

Pick the closest template, swap the domain.
