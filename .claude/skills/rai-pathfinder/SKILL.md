---
name: rai-pathfinder
description: Path queries on RAI/PyRel v1 models via `relationalai.semantics.std.paths`. Use when the question is about enumerating *which* paths connect entities (and what nodes/edges they traverse), not just whether two are connected. Covers what's solvable today, what's not yet implemented, what should never be attempted, and how to scan a model and propose path queries. Not for pure reachability / centrality / community / shortest-path — those belong to `rai-graph-analysis`.
---

# RAI Pathfinder — `path()` queries

## Summary

**What:** The `paths` library (codename Pathfinder) extends PyRel's native fixed-length traversal with **variable-length patterns** and **path enumeration**. `m.path(...)` builds a reusable `PathPattern`; `.repeat(min, max)` adds variable-length; `.all_paths()` materialises each match as a `PathTraversal` carrying length, ordered nodes, and ordered edge fields.

**When to use:**
- The question is about *which* paths connect entities, not just *whether* they connect.
- You need the ordered sequence of nodes and edges traversed (audit trail, multi-tier BOM, multi-leg routing).
- Endpoint pairs are validated by an external relation ("BY use case" — show me physical paths between domain-valid endpoint pairs).
- You need per-source aggregations (count of reachable, total hops) without a full graph reasoner.

**When NOT to use:**
- "Can A reach B?" (yes/no, no path detail) → `Graph.reachable()` in `rai-graph-analysis`.
- "What's the shortest path?" → `Graph.distance()` (until `paths.shortest_paths()` lands; today it raises `NotImplementedError`).
- "Which nodes are most central / clustered / in which community?" → `Graph` algorithms.
- "Are there cycles?" → `Graph.is_acyclic()`.
- The traversal is a known fixed length — bare `Concept.rel.rel.rel` chains are simpler and faster.
- The question is multi-edge in one path (two distinct relationships interleaved) — not yet supported.

**Overview:**
1. Inventory the model — which concepts can act as nodes, which structures are edges.
2. Classify the question against the capability matrix below.
3. If the edge is a junction concept, build an N-arity adapter relationship.
4. Pick the query shape (fixed / variable, count-only / enumeration, BY / no-BY).
5. Write, validate cardinality before materialising, then materialise.

---

## Quick Reference

```python
from relationalai.semantics.std.paths import path  # also exposed as model.path(...)
from relationalai.semantics.std.aggregates import count, sum

# Fixed-length (no path() needed — bare chain works):
Person.follows.follows.follows                              # exactly 3 hops

# Variable-length, enumerate all matches:
p = m.path(Person.follows.repeat(1, 3)).all_paths()         # PathPattern → unary Relationship

# Endpoint constraints — three equivalent forms (typed-ref is fastest):
src = Person.ref().filter_by(name="Alice")                  # Form A: typed ref (preferred)
m.path(src.follows.repeat(1, 3)).all_paths()

x = Person.ref()                                            # Form B: in-pattern .where
m.path(x, Person.follows.repeat(1, 3)).where(x.name == "Alice").all_paths()

x = Person.ref()                                            # Form C: outer where
m.where(x.name == "Alice", p := m.path(x, Person.follows.repeat(1, 3)).all_paths())

# BY use case — endpoints validated by an external relation:
src, dst = CriticalLoc.ref(), CriticalLoc.ref()
m.path(src, Loc.supply_edge.repeat(1, 5), dst) \
   .where(src.must_serve(dst)).all_paths()

# Reading a path:
df = m.where(p := m.path(...).all_paths()).select(
    p, p.length,
    p.nodes["index"], NodeConcept(p.nodes).id.alias("node_id"),
    p.relationship_fields["index"].alias("hop"),
    p.relationship_fields["field_index"],
    EdgeAuxConcept(p.relationship_fields).attr.alias("aux"),
).to_df()

# Count-only — cheap, run BEFORE enumerating:
m.select(
    count(paths := m.path(...).all_paths()).alias("paths"),
    sum(paths, paths.length).alias("hops"),
).inspect()

# Per-source aggregation:
x = Node.ref()
m.where(p := m.path(x, Node.edge.repeat(1, 2)).all_paths()) \
 .select(x.id, sum(p, p.length).per(x).alias("total_hops"))
```

| Method / attr | Purpose |
|---|---|
| `m.path(*args)` | Build `PathPattern`. Args alternate node ↔ edge. Single-step `Chain` only as edge. |
| `Chain.repeat(n)` / `repeat(min, max)` / `repeat(max=N)` | Variable-length on a chain. Source typed; intermediates **not** typed by the chain's source concept. |
| `path(...).repeat(N)` | Repeat an entire pattern. Every intermediate node typed by the pattern's source concept. |
| `.where(predicate)` | Post-filter on endpoints / external relations. Does NOT prune search. |
| `.all_paths()` | Materialise each match as a `PathTraversal`. |
| `PathTraversal.length` | Hop count. |
| `PathTraversal.nodes[index]` | Node at 0-indexed position. Re-type with `NodeConcept(p.nodes)`. |
| `PathTraversal.relationship_fields[index, field_index]` | Auxiliary field on N-arity edges (3+). `index` = hop, `field_index` = which middle field. |
| `count(p)`, `sum(p, p.length)`, `... | 0` | Standard aggregations apply. |

---

## Capability matrix

### Solvable today

| Pattern | Example |
|---|---|
| Fixed-length traversal | `m.path(Node.edge.repeat(3)).all_paths()` |
| Variable-length 1..N hops | `m.path(Node.edge.repeat(1, 5)).all_paths()` |
| Explicit src endpoint | `m.path(src, Node.edge.repeat(1, 3)).where(src.id == 1)` |
| Explicit dst endpoint | `m.path(Node.edge.repeat(1, 3), dst).where(dst.id == 9)` |
| Both endpoints | `m.path(src, Node.edge.repeat(1, 3), dst)` |
| Subconcept-typed endpoints | `start = Critical.ref(); m.path(start, ...).all_paths()` |
| BY external-relation endpoint validation | `.where(src.must_serve(dst))` joining external relation |
| N-arity edges (auxiliary fields preserved) | `f"{Loc:src} via {Lane:lane} to {Loc:dst}"` |
| Parallel N-arity edges (distinct paths) | Hash includes every non-src field — no collapse |
| Per-source aggregation | `sum(p, p.length).per(src_ref)` |
| Count-only / cardinality | `count(m.path(...).all_paths())` |
| Default-zero on empty result | `count(m.path(...).all_paths()) | 0` |
| `Chain.repeat()` source-only typing | `Criminal.follows.repeat(2)` — intermediates can be any `Person` |
| `path().repeat()` whole-pattern typing | `path(Criminal.follows).repeat(2)` — every intermediate must be `Criminal` |

### Wrong tool — use these instead

| Question | Use |
|---|---|
| "Can A reach B?" (boolean) | `Graph.reachable()` (`rai-graph-analysis`) |
| "Shortest path / distance?" | `Graph.distance()` (until `shortest_paths()` lands) |
| "Most central node?" | `Graph` centrality algorithms |
| "Connected components?" | `Graph.weakly_connected_component()` |
| "Is the graph acyclic?" | `Graph.is_acyclic()` (run BEFORE unbounded path repeats) |
| "How many neighbors?" | `aggs.count(distinct(...)).per(node)` — no graph needed |
| "Exactly N-hop paths" | Bare chain `node.rel.rel.rel` — `path()` is overkill |

### Not yet implemented (raises at call time)

These are on the roadmap but currently raise `NotImplementedError` or `ValueError`. **Do not attempt** — fail fast and tell the user.

| Pattern | Status | Workaround |
|---|---|---|
| Multiple edges in one `path()` — `path(a.follows, b.works_with)` | `NotImplementedError` | Encode as a single N-arity relationship |
| `path(x.edge, y).repeat(...)` with explicit dst | `NotImplementedError` | Move repeat inside: `path(x.edge.repeat(...), y)` |
| Nested or multiple repeats | `ValueError` | Pick one repeat |
| Multi-step chain inside `path()` — `path(a.follows.follows)` | `ValueError` | Use repeat: `path(a.follows.repeat(2))` |
| Unbounded repeats — `repeat(max=math.inf)` | Not supported | Use a finite cap (e.g., `repeat(1, 50)`) |
| Bare `Relationship` as edge | `ValueError` | Attach to concept attribute: `Person.follows`, not `follows_rel` |
| Adjacent node args — `path(x, y, edge)` | `NotImplementedError` | `path(x, edge).where(x == y)` |
| `Chain.repeat()` outside `path()` — `select(alice.follows.repeat(3))` | `ValueError` | Expand fixed: `select(alice.follows.follows.follows)` |
| `shortest_paths()` | `NotImplementedError` | Use `Graph.distance()` |
| `reverse()`, `undirected()` | `NotImplementedError` | Define reverse/bidirectional view as a derived relationship |
| Simple paths / acyclic / trail semantics | Not supported | Default is **walks** (repeats allowed). Cap repeat aggressively on cyclic graphs |

### Footguns — DO NOT attempt without explicit cap / fix

| Anti-pattern | Why it bites | Fix |
|---|---|---|
| Bare concept appearing twice in one `path()` — `path(Node, Node.edge, Node)` | All bare concepts unify into one variable → silently demands a self-loop → empty result | Use `.ref()` for any node referenced more than once |
| Variable bound inside `path().repeat()` referenced in outer scope | Will throw in future versions; today scope-confused | Move the constraint inside `path(...).where(...)`, or use `Chain.repeat()` instead |
| `.where()` clause to prune large search space | `.where()` is a post-filter — same paths are explored, then rejected | Move endpoint constraints to typed refs (`ref().filter_by(...)`); `.where()` does NOT speed up traversal |
| Cyclic graph + unbounded `repeat(max=N)` | Walks allow node/edge repeats — cycles cause exponential blow-up | Verify with `Graph.is_acyclic()`; cap `max` conservatively; run `count()` before `.all_paths()` |
| Aggregator-collapsing parallel N-arity edges before path query | Loses parallel-edge distinct paths and physical-bridge signal | Keep N-arity edges intact; aggregator semantics are for `Graph` reasoner, not `path()` |
| `repeat(N)` overshooting graph depth | Returns empty silently — not an error | Wrap aggregations in `\| 0`; sanity-check with a `count()` on smaller `repeat(max=...)` |

---

## Decision: `path()` vs `Graph` reasoner vs fixed-length chain

```
question asks for ordered node/edge sequence?
├── no  → does it need cycles / centrality / community / shortest path?
│        ├── yes → rai-graph-analysis
│        └── no  → bare PyRel chain or aggregation
└── yes → length known and fixed (≤4)?
         ├── yes → bare chain: Concept.rel.rel.rel  (no path() overhead)
         └── no  → variable length
                    ├── multi-edge in one walk?     → unsupported, redesign as N-arity edge
                    └── single edge type
                          ├── cyclic graph?
                          │     ├── yes → cap repeat tight; run count() first
                          │     └── no  → safe to enumerate
                          └── path()
```

---

## Workflow: scanning a model and proposing path queries

When given a model, walk this in order. Each step rejects or refines the candidate question.

### Step 1 — Inventory edge sources

Use `inspect.schema(model)` (see `rai-querying`) and look for:

| Signal | Where edges live |
|---|---|
| Self-referencing concept relationship — `Concept.rel(other_self)` | Direct edge; `path()` works on `Concept.rel.repeat(...)` directly |
| Junction concept with two FKs to the same node concept — `Bom(parent, component)`, `Lane(origin, destination)` | Need an N-arity adapter relationship (see Step 3) |
| Bipartite junction — `SupplierProduct(supplier, product)` | Project to one side via co-occurrence (graph), not `path()` |
| Intermediary concept with auxiliary fields — `Account.sent_to(Account, Transfer, Account)` | Already an N-arity edge — use `path()` directly |
| Hierarchy / DAG | Strong path candidate — usually safe for higher repeat counts |
| Network with cycles | Path candidate, but cap repeats tight |

If no edge source exists in the relevant concepts, no path query can be proposed — flag a model gap.

### Step 2 — Classify the question

A question is path-shaped if it answers any of:

- *"Show me the chain of intermediaries from X to Y."*
- *"For each pair (X, Y) that domain-validly should connect, do they actually connect physically, and how?"*
- *"How many distinct walks of length up to N exist from X?"*
- *"What's the maximum depth of the BOM rooted at X?"*
- *"Trace the supplier-disruption impact through component dependencies."*

If the question is about a single binary "yes/no", or about a metric (centrality, similarity), reroute to `rai-graph-analysis`.

### Step 3 — Build an adapter if needed

For junction-concept edges (most real-world models), declare an N-arity adapter:

```python
# Junction Lane(origin: Location, destination: Location, ...) → 3-arity edge
Location.connects = model.Relationship(
    f"{Location:origin} connects (via {Lane:lane}) to {Location:destination}")
o, d = Location.ref(), Location.ref()
model.where(
    Lane.origin == o, Lane.destination == d,
    (lane := Lane.ref()).filter_by(origin=o, destination=d) == lane,
).define(Location.connects(o, lane, d))
```

The auxiliary field (`Lane`) is preserved — `p.relationship_fields` will surface it.

### Step 4 — Pick the query shape

| Shape | When |
|---|---|
| Bare chain | Length is fixed and ≤ 4. No `path()` needed. |
| `path(edge.repeat(1, N))` no endpoints | "All walks up to length N from anywhere." Likely too broad — count first. |
| `path(src, edge.repeat(...))` | All walks from a specific source. |
| `path(edge.repeat(...), dst)` | All walks ending at a specific destination. |
| `path(src, edge.repeat(...), dst)` | Walks between specific endpoints — count cardinality first if both are sets. |
| `path(src, edge.repeat(...), dst).where(src.<external_rel>(dst))` | **BY pattern** — most powerful. Use whenever the user has a notion of valid endpoint pairs. |
| `count(p)` only | Always run before `.all_paths()` materialisation on real-size data. |
| `sum(p, p.length).per(src)` | Per-source depth / fan-out summaries. |

### Step 5 — Validate before materialising

1. **Acyclicity check** — `Graph.is_acyclic()` if the topology is uncertain.
2. **Cardinality count** — `count(...)` first; if 6-figures, tighten constraints.
3. **Smallest plausible repeat** — start with `repeat(1, 2)` and grow.
4. **Confirm endpoint constraints actually fire** — `.where()` post-filter doesn't prune; verify the typed-ref or filter form is the one written.

If any check fails, refuse to materialise and report the issue.

---

## Adapter patterns (junction → N-arity edge)

Three forms cover most of `supply_chain` and similar ontologies.

### A. Two-FK junction → 3-arity edge with junction as middle field

```python
# Lane(origin, destination) → 3-arity Location.connects
Location.connects = model.Relationship(
    f"{Location:origin} connects (via {Lane:lane}) to {Location:destination}")
o, d = Location.ref(), Location.ref()
model.where(
    Lane.origin == o, Lane.destination == d,
    (lane := Lane.ref()).filter_by(origin=o, destination=d) == lane,
).define(Location.connects(o, lane, d))
```

### B. Two-FK junction with no need for the junction itself → binary edge

```python
# BomEntry(parent, component) → binary Product.uses (drop qty_per_assembly)
Product.uses = model.Relationship(f"{Product:parent} uses {Product:component}")
parent, comp = Product.ref(), Product.ref()
model.where(BomEntry.parent == parent, BomEntry.component == comp).define(
    Product.uses(parent, comp))
```

### C. Bipartite junction → projected co-occurrence

`SupplierProduct(supplier, product)` doesn't define a Supplier→Supplier edge directly; project via shared product:

```python
# Two suppliers connected if they share at least one product
Supplier.shares_product_with = model.Relationship(
    f"{Supplier:a} shares product with {Supplier:b}")
a, b = Supplier.ref(), Supplier.ref()
model.where(
    SupplierProduct.supplier == a, SupplierProduct.product == Product.ref(),
    SupplierProduct.filter_by(supplier=b, product=Product.ref()),
    a != b,
).define(Supplier.shares_product_with(a, b))
```

For projections, prefer `rai-graph-analysis` co-occurrence patterns over path() — projections are usually about clusters and centrality, not enumeration.

---

## Footgun-free template for proposing queries

When proposing a path query, always present:

1. **The question in plain language** (one sentence).
2. **The adapter relationship** (full PyRel) — explicitly named so the user can copy-paste.
3. **A `count()`-only sanity check** — to run before materialising.
4. **The full enumeration query** — only after the count is reasonable.
5. **The repeat cap rationale** — why this `max`, not unbounded.
6. **A note on cycles** — DAG (safe) or cyclic (capped).

---

## Examples — `supply_chain` specifically

### Example 1 — Multi-tier BOM walk from a finished good

Question: "Starting from SKU `NW00041`, what does it transitively use, up to 4 levels deep?"

```python
# Adapter (binary, drop qty_per_assembly):
Product.uses = model.Relationship(f"{Product:parent} uses {Product:component}")
parent, comp = Product.ref(), Product.ref()
model.where(BomEntry.parent == parent, BomEntry.component == comp) \
     .define(Product.uses(parent, comp))

# Sanity check (count-only):
from relationalai.semantics.std.aggregates import count, sum as agg_sum
src = Product.ref().filter_by(sku="NW00041")
model.select(
    count(p := m.path(src.uses.repeat(1, 4)).all_paths()).alias("paths"),
    agg_sum(p, p.length).alias("hops"),
).inspect()

# Materialise once count is bounded:
df = model.where(p := model.path(src.uses.repeat(1, 4)).all_paths()) \
          .select(p, p.length, p.nodes["index"],
                  Product(p.nodes).sku.alias("sku")).to_df()
```

Cap rationale: BOMs are DAGs by construction; 4 levels covers all realistic finished-good→raw-material chains in this dataset. A cycle in BOM data would indicate a data quality bug.

### Example 2 — Plant→DC physical reachability validated by must-serve

Question: "For each plant–DC pair where the plant must serve the DC's region, what physical lane sequences exist (up to 4 hops)?"

```python
# Adapter (3-arity, lane preserved):
Location.connects = model.Relationship(
    f"{Location:origin} connects (via {Lane:lane}) to {Location:destination}")
# (define rule as in Adapter A above)

# Domain pairing — must-serve relation:
Location.must_serve = model.Relationship(
    f"{Location:plant} must serve {Location:dc}")
plant, dc = Location.ref(), Location.ref()
model.where(plant.type == "PLANT", dc.type == "DC", plant.region == dc.region) \
     .define(Location.must_serve(plant, dc))

# Count-first:
src, dst = Location.ref(), Location.ref()
model.select(count(
    p := model.path(src, Location.connects.repeat(1, 4), dst)
              .where(src.must_serve(dst)).all_paths()
)).inspect()

# Then materialise:
df = model.where(
    p := model.path(src, Location.connects.repeat(1, 4), dst)
              .where(src.must_serve(dst)).all_paths(),
).select(
    p, p.length,
    p.nodes["index"], Location(p.nodes).location_id.alias("loc"),
    p.relationship_fields["index"].alias("hop"),
    Lane(p.relationship_fields).lane_id.alias("lane"),
).to_df()
```

Cap rationale: lane network is cyclic (return routes); 4 hops covers realistic multi-leg routing without exploding the walk count. `count()` first because the cross-product of plants × DCs × lanes can blow up.

### Example 3 — Disruption impact through BOM (per-source aggregation)

Question: "For each component supplied by a high-risk supplier, how many distinct finished-good walks reach it within 3 levels?"

```python
# Reuse Product.uses adapter from Example 1.
# Per-source: how many length-≤3 ancestor walks point at each component supplied by a high-risk supplier?
high_risk_comp = Product.ref()
model.where(
    SupplierProduct.product == high_risk_comp,
    SupplierProduct.supplier.risk_score > 0.5,
).define(high_risk_comp_set := high_risk_comp)  # mark the set

ancestor = Product.ref()
df = model.where(
    p := model.path(ancestor, Product.uses.repeat(1, 3), high_risk_comp).all_paths(),
    n := agg_sum(p, p.length).per(high_risk_comp),
).select(high_risk_comp.sku.alias("at_risk_sku"),
         n.alias("ancestor_hop_total")).to_df()
```

Cap rationale: BOM acyclic, 3 levels typically captures finished-goods exposure on a battery-module-style hierarchy.

---

## Refusal / redirect rules

If the user asks for any of the following, **stop and redirect** rather than attempt:

- `shortest_paths()`, `reverse()`, `undirected()` — not implemented.
- Multi-edge paths in one `path(...)` — redesign as N-arity edge.
- Unbounded repeats / `max=math.inf` — require a finite cap.
- Path enumeration on a known cyclic graph without a cap — refuse and ask for a cap.
- Centrality / community / similarity dressed up as "find paths" — redirect to `rai-graph-analysis`.
- Bare `Relationship` (not attached to a concept) as edge — fix the model first.

When refusing, name the unsupported pattern and the workaround from the matrix.
