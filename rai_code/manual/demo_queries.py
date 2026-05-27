"""Demo queries Q1-Q5 from DEMO_QUESTIONS.md, implemented against the
manual ontology in cars.py. Five acts of the OEM-recall-propagation
talk track:

    Q1 Act 1 (Rules)        recall_sla_audit
    Q2 Act 2 (Graph)        continental_cascade
    Q3 Act 3 (Heuristic)    urgency_top20  (deterministic; predictive
                             reasoner is preview, see talk-track disclaimer)
    Q4 Act 4 (Prescriptive) assign_recall_jobs  (HiGHS MIP)
    Q5 Act 5 (Persistent)   assign_recall_jobs_priority

Run from project root:
    .venv/bin/python rai_code/manual/demo_queries.py
"""
from relationalai.semantics import Float, Integer, distinct
from relationalai.semantics.reasoners.prescriptive import Problem
from relationalai.semantics.reasoners.graph import Graph
from relationalai.semantics.std import aggregates as aggs
from relationalai.semantics.std.paths import path as rai_path

try:
    from .cars import (
        BomNode,
        CentreHandoff,
        JobAssignment,
        OpenRecall,
        Owner,
        Part,
        PartsStock,
        Plant,
        PriorAccident,
        PriorityVehicle,
        RecallAssignment,
        RecallCampaign,
        Region,
        SLABreachedRecall,
        ServiceCentre,
        ServiceEvent,
        Supplier,
        Vehicle,
        Week,
        CentreCapacity,
        in_bom,
        model,
    )
except ImportError:
    from cars import (
        BomNode,
        CentreHandoff,
        JobAssignment,
        OpenRecall,
        Owner,
        Part,
        PartsStock,
        Plant,
        PriorAccident,
        PriorityVehicle,
        RecallAssignment,
        RecallCampaign,
        Region,
        SLABreachedRecall,
        ServiceCentre,
        ServiceEvent,
        Supplier,
        Vehicle,
        Week,
        CentreCapacity,
        in_bom,
        model,
    )


# =============================================================================
# Q1. Act 1 - Rules: recall SLA compliance audit
#
# "Show me every Open recall on a VIN whose notification age has
#  breached the campaign's completion window. Break it out by campaign
#  and by responsible service centre."
# Rule: SLABreachedRecall is a derived concept on the model. PyRel
# re-derives it from the ontology (Open + age > completion_days +
# severity <= 2); the data layer pre-computed the same value, so this
# is a consistency cross-check too.
# =============================================================================
def q1_recall_sla_audit():
    """SLA-breached Open recalls grouped by campaign and by responsible
    centre (the owner's nearest centre). Pre-sorted by breach count."""
    df_by_campaign = (
        model.where(
            SLABreachedRecall(RecallAssignment),
            RecallAssignment.campaign == RecallCampaign,
        )
        .select(
            distinct(
                RecallCampaign.campaign_id.alias("campaign"),
                RecallCampaign.name.alias("campaign_name"),
                RecallCampaign.severity_code.alias("severity"),
                aggs.count(RecallAssignment).per(RecallCampaign).alias("breached_open"),
            )
        )
        .to_df()
        .sort_values("breached_open", ascending=False)
        .reset_index(drop=True)
    )
    if "breached_open" in df_by_campaign.columns:
        df_by_campaign["breached_open"] = [
            int(v) for v in df_by_campaign["breached_open"]
        ]
    if "severity" in df_by_campaign.columns:
        df_by_campaign["severity"] = [int(v) for v in df_by_campaign["severity"]]
    return df_by_campaign


def q1b_breached_by_centre():
    """SLA-breached Open recalls grouped by responsible service centre."""
    df = (
        model.where(
            SLABreachedRecall(RecallAssignment),
            RecallAssignment.vehicle == Vehicle,
            Vehicle.nearest_centre == ServiceCentre,
        )
        .select(
            distinct(
                ServiceCentre.name.alias("centre"),
                ServiceCentre.country.alias("country"),
                aggs.count(RecallAssignment).per(ServiceCentre).alias("breached_open"),
            )
        )
        .to_df()
        .sort_values("breached_open", ascending=False)
        .reset_index(drop=True)
    )
    if "breached_open" in df.columns:
        df["breached_open"] = [int(v) for v in df["breached_open"]]
    return df


# =============================================================================
# Q2. Act 2 - Graph: defect cascade from a supplier part
#
# "Continental notified us this morning of an expanded scope on the MK
#  C1 brake-booster firmware defect. Walk the cascade:
#  supplier -> part -> bom_node -> vehicle -> owner -> service centre
#  and roll up by region. Who do we have to notify, and where do they go?"
# =============================================================================
def q2_continental_cascade(supplier_id: str = "SUP-CONT",
                            part_id: str = "PRT-IBS-ECU"):
    """Affected VINs through the supplier->part->bom->vehicle traversal,
    plus regional rollup. Pure relational join over the ontology - no
    graph-reasoner needed because the cascade is single-direction with
    no transitive reachability."""
    df_vins = (
        model.where(
            Supplier.supplier_id == supplier_id,
            Part.supplier == Supplier,
            Part.part_id == part_id,
            BomNode.part == Part,
            in_bom(Vehicle, BomNode),
            Vehicle.owner == Owner,
            Vehicle.nearest_centre == ServiceCentre,
        )
        .select(
            distinct(
                Vehicle.vin.alias("vin"),
                Vehicle.model.alias("model"),
                Vehicle.factory.alias("plant"),
                Vehicle.production_date.alias("production_date"),
                Owner.country.alias("owner_country"),
                ServiceCentre.name.alias("nearest_centre"),
            )
        )
        .to_df()
        .reset_index(drop=True)
    )
    return df_vins


def q2_regional_rollup(supplier_id: str = "SUP-CONT",
                        part_id: str = "PRT-IBS-ECU"):
    """Same cascade rolled up by region rollup (EU / NA / LATAM)."""
    df = (
        model.where(
            Supplier.supplier_id == supplier_id,
            Part.supplier == Supplier,
            Part.part_id == part_id,
            BomNode.part == Part,
            in_bom(Vehicle, BomNode),
            Vehicle.nearest_centre == ServiceCentre,
            ServiceCentre.region == Region,
        )
        .select(
            distinct(
                Region.rollup.alias("rollup"),
                aggs.count(Vehicle).per(Region.rollup).alias("affected_vins"),
                aggs.count(distinct(ServiceCentre)).per(Region.rollup).alias("centres_engaged"),
            )
        )
        .to_df()
        .sort_values("affected_vins", ascending=False)
        .reset_index(drop=True)
    )
    for col in ("affected_vins", "centres_engaged"):
        if col in df.columns:
            df[col] = [int(v) for v in df[col]]
    return df


def q2_top_centres(supplier_id: str = "SUP-CONT",
                    part_id: str = "PRT-IBS-ECU"):
    """Top centres by affected-VIN volume for the cascade."""
    df = (
        model.where(
            Supplier.supplier_id == supplier_id,
            Part.supplier == Supplier,
            Part.part_id == part_id,
            BomNode.part == Part,
            in_bom(Vehicle, BomNode),
            Vehicle.nearest_centre == ServiceCentre,
        )
        .select(
            distinct(
                ServiceCentre.name.alias("centre"),
                ServiceCentre.country.alias("country"),
                aggs.count(Vehicle).per(ServiceCentre).alias("affected_vins"),
            )
        )
        .to_df()
        .sort_values("affected_vins", ascending=False)
        .reset_index(drop=True)
    )
    if "affected_vins" in df.columns:
        df["affected_vins"] = [int(v) for v in df["affected_vins"]]
    return df.head(10)


# =============================================================================
# Q3. Act 3 - Heuristic: per-VIN urgency ranking
#
# Compose a deterministic urgency score in PyRel as a derived Property
# on RecallAssignment (each Open assignment gets one). Score:
#   0.30 * mileage / 250000           (utilisation proxy)
#   0.25 * age_days_at_demo / 730     (notification age, ~2 years cap)
#   0.30 * accident_severity / 2.0    (safety)
#   0.15 * distance_km / 250          (logistics)
# Per the talk-track disclaimer this stands in for the GNN-based
# Predictive reasoner which is still preview.
# =============================================================================
# The RecallAssignment.urgency Property and its two rule branches
# (with-accident, without-accident) are declared in cars.py - they're
# part of the ontology so they materialise once. demo_queries just
# reads them.


def q3_urgency_top20():
    """Top-20 Open recall jobs by urgency score. The score lives on the
    ontology as RecallAssignment.urgency; the query just sorts by it."""
    df = (
        model.where(
            OpenRecall(RecallAssignment),
            RecallAssignment.vehicle == Vehicle,
            RecallAssignment.campaign == RecallCampaign,
        )
        .select(
            RecallAssignment.recall_id.alias("recall_id"),
            Vehicle.vin.alias("vin"),
            Vehicle.model.alias("model"),
            Vehicle.factory.alias("plant"),
            RecallCampaign.campaign_id.alias("campaign"),
            Vehicle.mileage.alias("mileage"),
            RecallAssignment.age_days_at_demo.alias("age_days"),
            Vehicle.distance_to_nearest_centre_km.alias("distance_km"),
            Vehicle.accident_type.alias("accident"),
            RecallAssignment.urgency.alias("urgency"),
        )
        .to_df()
        .sort_values("urgency", ascending=False)
        .head(20)
        .reset_index(drop=True)
    )
    for col in ("mileage", "age_days", "distance_km"):
        if col in df.columns:
            df[col] = [int(v) if v is not None else 0 for v in df[col]]
    if "urgency" in df.columns:
        df["urgency"] = [float(v) for v in df["urgency"]]
    return df


# =============================================================================
# Q4. Act 4 - Prescriptive: assign open recall jobs to centres x 4 weeks
#
# Decision: x[recall, centre, week] in {0,1} on every eligible
# JobAssignment row (cars.py pre-filters infeasibility by tooling
# certification).
# Constraints:
#   (a) Each open recall assigned to exactly one (centre, week).
#   (b) Per-centre per-week labour-hour capacity:
#       sum(x * labour_hours) over recalls at (c, w) <= tech_hours_available
#   (c) Per-centre per-campaign per-week parts-stock:
#       sum(x) over recalls of campaign at (c, w) <= on_hand_units
#   (d) (Act 5 only) Priority constraint: VINs in PriorityVehicle must
#       be scheduled in week 1 or 2 (not week 3 or 4).
# Objective: minimise sum(x * urgency * (week - 1)). Week 1 has zero
# lateness cost; later weeks scale up by urgency, so high-urgency jobs
# pull toward week 1 while low-urgency can slip to week 4.
# =============================================================================
def _build_scheduling_problem(priority_rule: bool = False):
    """Build the Act-4 problem (and optionally the Act-5 priority rule).
    Returns (df, solve_info)."""
    assign = JobAssignment.assign_priority if priority_rule else JobAssignment.assign_base
    problem = Problem(model, Float)

    # Decision variable: binary x on every JobAssignment row.
    problem.solve_for(
        assign,
        where=[],
        lower=0.0,
        upper=1.0,
        type="bin",
    )

    # (a) Each Open recall scheduled exactly once (exactly one centre x week).
    # The OpenRecall(_r) subtype predicate trips the prescriptive
    # rewriter on PyRel 1.7.1 (issue: rewriter line 521 classifies the
    # subtype-call as arithmetic and pulls a Concept into
    # _compile_arithmetic). Workaround: filter by status == "Open"
    # directly so the where-clause is a simple equality predicate.
    _r1 = RecallAssignment.ref()
    problem.satisfy(
        model.where(
            _r1.status == "Open",
        ).require(
            aggs.sum(assign)
            .where(JobAssignment.recall == _r1)
            .per(_r1) == 1
        ),
        name=["one-slot"],
    )

    # (b) Per-centre per-week labour-hour capacity.
    # sum_{j at (c,w)} assign * j.labour_hours <= capacity
    problem.satisfy(
        model.where(
            CentreCapacity.centre == ServiceCentre,
            CentreCapacity.week == Week,
        ).require(
            aggs.sum(assign * JobAssignment.labour_hours)
            .where(
                JobAssignment.centre == ServiceCentre,
                JobAssignment.week == Week,
            )
            .per(ServiceCentre, Week)
            <= CentreCapacity.tech_hours_available
        ),
        name=["labour-cap"],
    )

    # (c) Per-centre per-campaign per-week parts stock. The grouping
    # must include the campaign, so we still cross-bind RecallAssignment
    # -> RecallCampaign through the recall property, but the arithmetic
    # is just `sum(assign)` (no Property arithmetic across Concepts).
    problem.satisfy(
        model.where(
            PartsStock.centre == ServiceCentre,
            PartsStock.campaign == RecallCampaign,
            PartsStock.week == Week,
        ).require(
            aggs.sum(assign)
            .where(
                JobAssignment.centre == ServiceCentre,
                JobAssignment.week == Week,
                JobAssignment.recall == RecallAssignment,
                RecallAssignment.campaign == RecallCampaign,
            )
            .per(ServiceCentre, RecallCampaign, Week)
            <= PartsStock.on_hand_units
        ),
        name=["parts-stock"],
    )

    # (d) Act 5 only: priority VINs must be in week 1 or 2.
    # Uses the materialised RecallAssignment.priority_flag (1 if the
    # underlying Vehicle has a prior accident). The where-clause is a
    # single Property equality predicate to avoid the rewriter bug
    # that fires when multiple refs are joined in one where().
    if priority_rule:
        _r5 = RecallAssignment.ref()
        problem.satisfy(
            model.where(
                _r5.priority_flag == 1,
            ).require(
                aggs.sum(assign)
                .where(
                    JobAssignment.recall == _r5,
                    JobAssignment.week_index >= 3,
                )
                .per(_r5) == 0
            ),
            name=["priority-week"],
        )

    # Objective: minimise sum(x * urgency * (week - 1)). All operands
    # are JobAssignment Properties (urgency and week_index were
    # materialised in cars.py).
    problem.minimize(
        aggs.sum(
            assign * JobAssignment.urgency * (JobAssignment.week_index - 1)
        )
    )

    problem.solve("highs")
    si = problem.solve_info()

    # Read back assignments. The materialised assign is 0/1; >0.5 picks the
    # chosen rows. Pull the full join: recall -> vehicle -> campaign,
    # centre, week.
    df = (
        model.where(
            assign > 0.5,
            JobAssignment.recall == RecallAssignment,
            JobAssignment.centre == ServiceCentre,
            JobAssignment.week == Week,
            RecallAssignment.vehicle == Vehicle,
            RecallAssignment.campaign == RecallCampaign,
        )
        .select(
            RecallAssignment.recall_id.alias("recall_id"),
            Vehicle.vin.alias("vin"),
            Vehicle.factory.alias("plant"),
            RecallCampaign.campaign_id.alias("campaign"),
            ServiceCentre.name.alias("centre"),
            Week.week_index.alias("week"),
            RecallAssignment.urgency.alias("urgency"),
            RecallCampaign.typical_labour_hours.alias("hours"),
        )
        .to_df()
        .sort_values(["week", "urgency"], ascending=[True, False])
        .reset_index(drop=True)
    )
    for col in ("week",):
        if col in df.columns:
            df[col] = [int(v) for v in df[col]]
    for col in ("urgency", "hours"):
        if col in df.columns:
            df[col] = [float(v) if v is not None else 0.0 for v in df[col]]
    return df, si


def q4_assign_recall_jobs():
    """Act 4: schedule open recall jobs to (centre, week) without the
    priority rule."""
    return _build_scheduling_problem(priority_rule=False)


def q5_assign_recall_jobs_priority():
    """Act 5: same scheduling problem but with the persistent priority
    rule. Priority VINs (Open recall + prior accident) must be scheduled
    in weeks 1 or 2."""
    return _build_scheduling_problem(priority_rule=True)


# =============================================================================
# Q2 follow-up graph queries (Graph reasoner)
# Three additional graph constructions on the same ontology, each
# answering a different "structural" question the Cortex agent can
# pivot to after the headline Act 2 cascade. None of these change the
# 5-act narrative; they are extra surface for agent Q&A.
# =============================================================================

def _ensure_centre_coload_graph():
    """Undirected weighted graph of ServiceCentres. Two centres share an
    edge for every Open recall whose nearest_centre is one of them and
    whose campaign also has Open recalls on a vehicle nearest the other
    centre. Edge weight = count of co-exposed VINs. Cached on the
    `model` object so multiple algorithms can reuse it."""
    if hasattr(model, "_cars_centre_graph"):
        return model._cars_centre_graph
    from relationalai.semantics.std import floats as floats_mod
    g = Graph(model, directed=False, weighted=True, node_concept=ServiceCentre,
              aggregator="sum")
    # Edges: for each pair of distinct centres (c1, c2) that both serve at
    # least one Open recall on the same campaign, add an edge weighted by
    # the count of VINs the centres jointly cover. Implemented as a
    # co-occurrence over (vehicle.nearest_centre, recall.campaign).
    _r1 = RecallAssignment.ref()
    _r2 = RecallAssignment.ref()
    _v1 = Vehicle.ref()
    _v2 = Vehicle.ref()
    _c1 = ServiceCentre.ref()
    _c2 = ServiceCentre.ref()
    model.where(
        _r1.status == "Open",
        _r2.status == "Open",
        _r1.campaign == _r2.campaign,
        _r1.vehicle == _v1,
        _r2.vehicle == _v2,
        _v1.nearest_centre == _c1,
        _v2.nearest_centre == _c2,
        _c1.centre_id < _c2.centre_id,
    ).define(g.Edge.new(src=_c1, dst=_c2, weight=1.0))
    model._cars_centre_graph = g
    return g


def q6_centre_centrality():
    """Top service centres by eigenvector centrality on the co-exposure
    graph (two centres connected when they share an Open recall
    campaign via shared vehicle population). Identifies the structural
    hubs of the recall-absorbing network."""
    g = _ensure_centre_coload_graph()
    g.Node.coload_centrality = g.eigenvector_centrality()
    df = (
        model.select(
            ServiceCentre.centre_id.alias("centre_id"),
            ServiceCentre.name.alias("centre"),
            ServiceCentre.country.alias("country"),
            ServiceCentre.coload_centrality.alias("centrality"),
        )
        .to_df()
        .sort_values("centrality", ascending=False)
        .head(10)
        .reset_index(drop=True)
    )
    if "centrality" in df.columns:
        df["centrality"] = [float(v) if v is not None else 0.0 for v in df["centrality"]]
    return df


def _ensure_vehicle_cohort_graph():
    """Undirected weighted graph of Vehicles. Two vehicles share an
    edge if they share at least one BOM node. Edge weight = count of
    shared BOM nodes. Used for Louvain community detection: VINs that
    cluster together are exposed to the same supplier-defect cascades.

    Caches the graph AND runs Louvain once (the Property assignment is
    not idempotent so subsequent re-runs blow up).
    """
    if hasattr(model, "_cars_vehicle_graph"):
        return model._cars_vehicle_graph
    g = Graph(model, directed=False, weighted=True, node_concept=Vehicle,
              aggregator="sum")
    _v1 = Vehicle.ref()
    _v2 = Vehicle.ref()
    _b = BomNode.ref()
    model.where(
        in_bom(_v1, _b),
        in_bom(_v2, _b),
        _v1.vin < _v2.vin,
    ).define(g.Edge.new(src=_v1, dst=_v2, weight=1.0))
    # Louvain attached once; subsequent reads pull cached values from
    # the materialised Property.
    g.Node.cohort_community = g.louvain()
    model._cars_vehicle_graph = g
    return g


def q7_vehicle_communities():
    """Louvain communities on the vehicle-cohort graph. VINs that share
    BOM nodes cluster together. Result: each vehicle gets a community
    label; the demo returns the per-community count + an example
    model name per community. Non-deterministic by algorithm; report
    structure not exact IDs."""
    g = _ensure_vehicle_cohort_graph()
    df = (
        model.select(
            Vehicle.vin.alias("vin"),
            Vehicle.model.alias("model"),
            Vehicle.factory.alias("plant"),
            Vehicle.cohort_community.alias("community"),
        )
        .to_df()
        .reset_index(drop=True)
    )
    if "community" in df.columns:
        df["community"] = [int(v) for v in df["community"]]
    # Summarise: count + dominant model per community
    summary = (
        df.groupby("community")
        .agg(vins=("vin", "size"), dominant_model=("model", lambda s: s.mode().iloc[0] if not s.mode().empty else ""))
        .reset_index()
        .sort_values("vins", ascending=False)
        .reset_index(drop=True)
    )
    return summary


def q7_vehicle_communities_nodes_and_edges():
    """Return (nodes_df, edges_df) for the vehicle-cohort graph
    visualisation. Each node carries vin, model, plant, fuel_type,
    community label, mileage, accident_type, campaign count, and
    degree in the BOM-sharing graph. Each edge is a (vin1, vin2,
    shared_boms) tuple. The downstream notebook cell turns this into
    a colour-coded force-directed Plotly figure.

    Note: this query is expensive on the vehicle-cohort graph (~325
    nodes, several thousand edges). Cached on the model after first run.
    """
    g = _ensure_vehicle_cohort_graph()

    # Nodes: one row per Vehicle that participates in any BOM edge.
    _v = Vehicle.ref()
    _b = BomNode.ref()
    nodes = (
        model.where(in_bom(_v, _b))
        .select(
            distinct(
                _v.vin.alias("vin"),
                _v.model.alias("model"),
                _v.factory.alias("plant"),
                _v.fuel_type.alias("fuel"),
                _v.mileage.alias("mileage"),
                _v.cohort_community.alias("community"),
            )
        )
        .to_df()
        .reset_index(drop=True)
    )
    if "community" in nodes.columns:
        nodes["community"] = [int(c) for c in nodes["community"]]
    if "mileage" in nodes.columns:
        nodes["mileage"] = [int(m) if m is not None else 0 for m in nodes["mileage"]]

    # Per-vehicle: accident type, campaign count, open-recall count.
    # Cheap PyRel aggregates joined back as pandas merges.
    acc = (
        model.where(_v.vin, _v.accident_type)
        .select(_v.vin.alias("vin"), _v.accident_type.alias("accident"))
        .to_df()
        .reset_index(drop=True)
    )

    _r = RecallAssignment.ref()
    camps = (
        model.where(_r.vehicle == _v)
        .select(
            distinct(
                _v.vin.alias("vin"),
                aggs.count(distinct(_r.campaign)).per(_v.vin).alias("campaign_count"),
            )
        )
        .to_df()
        .reset_index(drop=True)
    )
    if "campaign_count" in camps.columns:
        camps["campaign_count"] = [int(c) for c in camps["campaign_count"]]

    open_count = (
        model.where(_r.vehicle == _v, _r.status == "Open")
        .select(
            distinct(
                _v.vin.alias("vin"),
                aggs.count(_r).per(_v.vin).alias("open_count"),
            )
        )
        .to_df()
        .reset_index(drop=True)
    )
    if "open_count" in open_count.columns:
        open_count["open_count"] = [int(c) for c in open_count["open_count"]]

    import pandas as pd
    nodes = nodes.merge(acc, on="vin", how="left")
    nodes = nodes.merge(camps, on="vin", how="left")
    nodes = nodes.merge(open_count, on="vin", how="left")
    nodes["accident"] = nodes["accident"].fillna("none")
    nodes["campaign_count"] = nodes["campaign_count"].fillna(0).astype(int)
    nodes["open_count"] = nodes["open_count"].fillna(0).astype(int)

    # Edges: re-query from in_bom + group-by per (v1, v2).
    _v1 = Vehicle.ref()
    _v2 = Vehicle.ref()
    _b2 = BomNode.ref()
    edges = (
        model.where(
            in_bom(_v1, _b2),
            in_bom(_v2, _b2),
            _v1.vin < _v2.vin,
        )
        .select(
            distinct(
                _v1.vin.alias("v1"),
                _v2.vin.alias("v2"),
                aggs.count(_b2).per(_v1.vin, _v2.vin).alias("shared_boms"),
            )
        )
        .to_df()
        .reset_index(drop=True)
    )
    if "shared_boms" in edges.columns:
        edges["shared_boms"] = [int(s) for s in edges["shared_boms"]]

    # Degree in the BOM-sharing graph: number of distinct neighbours.
    # Stack v1/v2 ends, count occurrences per VIN.
    end1 = edges[["v1"]].rename(columns={"v1": "vin"})
    end2 = edges[["v2"]].rename(columns={"v2": "vin"})
    ends = pd.concat([end1, end2], ignore_index=True)
    deg = ends.groupby("vin").size().rename("degree").reset_index()
    nodes = nodes.merge(deg, on="vin", how="left")
    nodes["degree"] = nodes["degree"].fillna(0).astype(int)

    return nodes, edges


def _ensure_campaign_to_centre_graph():
    """Directed weighted graph: RecallCampaign -> ServiceCentre. Edge
    weight = number of Open VINs in the campaign whose nearest_centre
    is the destination centre. Used for PageRank: centres with the
    highest inbound from many campaigns are the busiest network
    workshops."""
    if hasattr(model, "_cars_campaign_centre_graph"):
        return model._cars_campaign_centre_graph
    # Use Pattern 1 so we can mix the two node concepts on the same
    # graph. The graph reasoner accepts heterogeneous nodes as long as
    # they are bound via Edge.new.
    g = Graph(model, directed=True, weighted=True)
    _r = RecallAssignment.ref()
    _v = Vehicle.ref()
    _c = ServiceCentre.ref()
    _cmp = RecallCampaign.ref()
    # Register one node per campaign and one per centre. (The graph
    # reasoner auto-registers endpoints from Edge.new, but explicit
    # is cleaner for downstream queries.)
    model.where(
        _r.status == "Open",
        _r.campaign == _cmp,
        _r.vehicle == _v,
        _v.nearest_centre == _c,
    ).define(g.Edge.new(src=_cmp, dst=_c, weight=1.0))
    model._cars_campaign_centre_graph = g
    return g


def q8_centre_pagerank():
    """PageRank on the directed campaign -> centre graph (weighted by
    Open-VIN count). The top centres absorb the most cascading work
    summed across all 5 active recall campaigns. Pairs naturally with
    Act 4's scheduling MIP."""
    g = _ensure_campaign_to_centre_graph()
    g.Node.cascade_rank = g.pagerank()
    # Project back onto ServiceCentre only - filter out campaign
    # nodes by joining graph.Node to ServiceCentre.
    _c = ServiceCentre.ref()
    df = (
        model.where(g.Node == _c)
        .select(
            _c.name.alias("centre"),
            _c.country.alias("country"),
            g.Node.cascade_rank.alias("pagerank"),
        )
        .to_df()
        .sort_values("pagerank", ascending=False)
        .head(10)
        .reset_index(drop=True)
    )
    if "pagerank" in df.columns:
        df["pagerank"] = [float(v) if v is not None else 0.0 for v in df["pagerank"]]
    return df


# =============================================================================
# Q11. Pathfinder: enumerate centre referral chains
#
# Uses the N-arity edge ServiceCentre.refers_for(from, CentreHandoff,
# to) declared on the ontology in cars.py. The middle field is the
# CentreHandoff row, which carries (campaign, monthly_handoffs). We
# enumerate variable-length walks (1..3 hops) from a seed centre,
# optionally filtered to a single campaign so the chain has a
# coherent story.
# =============================================================================
def q11_handoff_chain_summary(seed_centre_id: str = "SC-MTY",
                              max_hops: int = 3,
                              campaign_filter: str = "IBS-2024-A"):
    """Demo-friendly summary of the Pathfinder result: count of
    distinct chains by length and the deepest reachable centre.
    Pairs with q11_handoff_chains for the full row-per-hop dump."""
    src = ServiceCentre.ref().filter_by(centre_id=seed_centre_id)
    # Form A: chain off the typed ref so the src actually constrains
    # the path source. Using ServiceCentre.refers_for separately would
    # leave src and the chain as independent variables.
    p = rai_path(src.refers_for.repeat(1, max_hops)).all_paths()
    df = (
        model.where(p)
        .select(
            p.length.alias("path_length"),
            p.nodes["index"].alias("hop"),
            ServiceCentre(p.nodes).centre_id.alias("centre"),
            CentreHandoff(p.relationship_fields).campaign.campaign_id.alias("hop_campaign"),
        )
        .to_df()
        .reset_index(drop=True)
    )
    if df.empty:
        return None
    df["path_length"] = [int(v) for v in df["path_length"]]
    df["hop"] = [int(v) for v in df["hop"]]
    if campaign_filter:
        df = df[df["hop_campaign"] == campaign_filter].reset_index(drop=True)
    # Summarise: per (path_length), how many distinct chains exist
    # and what is the deepest reachable centre at the final hop.
    # Distinct chains identified by tuple of centres along the way.
    chains = (
        df.sort_values(["path_length", "hop"])
          .groupby(["path_length"], as_index=False)
          .apply(lambda g: g, include_groups=False)
    )
    by_len = (
        df[df["hop"] == df["path_length"]]
          .groupby("path_length", as_index=False)
          .agg(distinct_endpoints=("centre", "nunique"),
               endpoints=("centre", lambda s: sorted(set(s))))
    )
    return by_len


def q11_handoff_chains(seed_centre_id: str = "SC-MTY",
                       max_hops: int = 3,
                       campaign_filter: str = "IBS-2024-A"):
    """For a given seed centre, enumerate the multi-hop referral chains
    it sits at the head of. Each row is one (path, hop): the hop
    index, the from/to centre at that hop, and the campaign carried
    in the auxiliary middle field. Multiple rows per path build the
    full chain.

    Demonstrates Pathfinder: variable-length traversal of an N-arity
    edge (centre via CentreHandoff to centre) with auxiliary middle-
    field accessed via PathTraversal.relationship_fields.
    """
    src = ServiceCentre.ref().filter_by(centre_id=seed_centre_id)
    # Form A: chain off the typed ref so the src actually constrains
    # the path source. Using ServiceCentre.refers_for separately would
    # leave src and the chain as independent variables.
    p = rai_path(src.refers_for.repeat(1, max_hops)).all_paths()

    # One row per (path, hop). Columns: path length, hop index,
    # from-centre at hop, to-centre at hop, campaign at hop.
    df = (
        model.where(p)
        .select(
            p.length.alias("path_length"),
            p.nodes["index"].alias("hop"),
            ServiceCentre(p.nodes).centre_id.alias("centre"),
            CentreHandoff(p.relationship_fields).campaign.campaign_id.alias("hop_campaign"),
        )
        .to_df()
        .reset_index(drop=True)
    )
    if df.empty:
        return None
    for c in ("path_length", "hop"):
        if c in df.columns:
            df[c] = [int(v) for v in df[c]]
    if campaign_filter:
        df = df[df["hop_campaign"] == campaign_filter].reset_index(drop=True)
    return df


# =============================================================================
# Q12. Multi-reasoner: Graph (Louvain) -> Prescriptive (MIP)
#
# The cleanest "multi-reasoner" demo moment: Louvain finds natural
# vehicle-cohort communities from the BOM-sharing graph (Q7). We
# then feed the community labels into a NEW MIP that minimises
# urgency-weighted lateness AND enforces fair load distribution
# across communities - no single community absorbs more than the
# `max_share` fraction of week-3+ jobs.
#
# Without this constraint, the MIP can dump an entire community to
# the late slots, leaving one cohort of owners systematically worse-
# off. The constraint is one line; the value lands because it's
# clearly a graph-then-prescriptive composition that you cannot
# replicate in plain SQL.
# =============================================================================
def q12_balanced_schedule(max_late_share: float = 0.40):
    """Multi-reasoner: take Louvain community labels (Graph) and use
    them as a constraint in the MIP (Prescriptive). For each
    community, the fraction of its jobs landing in weeks 3+ is capped
    at `max_late_share` (default 40%). Returns (df, solve_info,
    per_community_late_pct).
    """
    # Ensure Louvain has been materialised on the vehicle-cohort graph
    # by calling Q7's underlying helper.
    _ = _ensure_vehicle_cohort_graph()

    # Decision variable: JobAssignment.assign_balanced (declared at
    # module load in cars.py with a Float type so solve_for accepts it).
    assign = JobAssignment.assign_balanced

    problem = Problem(model, Float)
    problem.solve_for(assign, where=[], lower=0.0, upper=1.0, type="bin")

    # (a) Each Open recall scheduled exactly once.
    _r1 = RecallAssignment.ref()
    problem.satisfy(
        model.where(_r1.status == "Open").require(
            aggs.sum(assign).where(JobAssignment.recall == _r1).per(_r1) == 1
        ),
        name=["one-slot"],
    )

    # (b) Per-centre per-week labour-hour capacity.
    problem.satisfy(
        model.where(
            CentreCapacity.centre == ServiceCentre,
            CentreCapacity.week == Week,
        ).require(
            aggs.sum(assign * JobAssignment.labour_hours)
            .where(JobAssignment.centre == ServiceCentre,
                   JobAssignment.week == Week)
            .per(ServiceCentre, Week)
            <= CentreCapacity.tech_hours_available
        ),
        name=["labour-cap"],
    )

    # (c) Parts stock.
    problem.satisfy(
        model.where(
            PartsStock.centre == ServiceCentre,
            PartsStock.campaign == RecallCampaign,
            PartsStock.week == Week,
        ).require(
            aggs.sum(assign).where(
                JobAssignment.centre == ServiceCentre,
                JobAssignment.week == Week,
                JobAssignment.recall == RecallAssignment,
                RecallAssignment.campaign == RecallCampaign,
            ).per(ServiceCentre, RecallCampaign, Week)
            <= PartsStock.on_hand_units
        ),
        name=["parts-stock"],
    )

    # (d) THE multi-reasoner constraint. For each community label C,
    # late jobs in C <= max_late_share * total open recalls in C.
    # Total open recalls in C is data-derived (community sizes are
    # known after Louvain), so we compute the absolute cap in pandas
    # and pass per-community caps as constants. This keeps the LP
    # constraint single-aggregate and clean.
    #
    # The community label is materialised on RecallAssignment as
    # community_label = vehicle.cohort_community.
    if not hasattr(RecallAssignment, "community_label"):
        RecallAssignment.community_label = model.Property(
            f"{RecallAssignment} community_label {Integer:community_label}"
        )
    _cd_r = RecallAssignment.ref()
    _cd_v = Vehicle.ref()
    model.where(
        _cd_r.status == "Open",
        _cd_r.vehicle == _cd_v,
        _cd_v.cohort_community,
    ).define(_cd_r.community_label(_cd_v.cohort_community))

    # Query the community sizes so we can compute per-community caps.
    _sz_r = RecallAssignment.ref()
    sizes_df = (
        model.where(_sz_r.status == "Open", _sz_r.community_label)
        .select(
            distinct(
                _sz_r.community_label.alias("community"),
                aggs.count(_sz_r).per(_sz_r.community_label).alias("size"),
            )
        )
        .to_df()
    )
    sizes_df["community"] = [int(v) for v in sizes_df["community"]]
    sizes_df["size"] = [int(v) for v in sizes_df["size"]]
    # Cap per community = floor(max_late_share * size). Materialise as
    # a Property on Vehicle.cohort_community so the LP constraint can
    # read it as a single Property predicate.
    if not hasattr(RecallAssignment, "late_cap"):
        RecallAssignment.late_cap = model.Property(
            f"{RecallAssignment} late_cap {Integer:late_cap}"
        )
    # Define late_cap per RecallAssignment based on its community size.
    # Each recall in community C gets the same cap value = community
    # cap. The LP constraint then aggregates by community_label and
    # bounds by late_cap.
    for _, row in sizes_df.iterrows():
        cap = max(1, int(row["size"] * max_late_share))
        _cap_r = RecallAssignment.ref()
        model.where(
            _cap_r.community_label == int(row["community"]),
        ).define(_cap_r.late_cap(cap))

    # Constraint: sum of late assignments per community <= late_cap.
    # All Open recalls carry community_label + late_cap (defined above);
    # filter on status to keep the outer where clause to a single
    # equality predicate (the rewriter rejects raw Property predicates
    # in top-level where for require-aggregate constraints).
    _r = RecallAssignment.ref()
    problem.satisfy(
        model.where(_r.status == "Open").require(
            aggs.sum(assign).where(
                JobAssignment.recall == _r,
                JobAssignment.week_index >= 3,
            ).per(_r.community_label)
            <= _r.late_cap
        ),
        name=["community-balance"],
    )

    # Objective: minimise urgency * (week-1) - same as Q4/Q5.
    problem.minimize(
        aggs.sum(
            assign * JobAssignment.urgency * (JobAssignment.week_index - 1)
        )
    )

    problem.solve("highs")
    si = problem.solve_info()

    df = (
        model.where(
            assign > 0.5,
            JobAssignment.recall == RecallAssignment,
            JobAssignment.centre == ServiceCentre,
            JobAssignment.week == Week,
            RecallAssignment.vehicle == Vehicle,
            RecallAssignment.campaign == RecallCampaign,
        )
        .select(
            RecallAssignment.recall_id.alias("recall_id"),
            Vehicle.vin.alias("vin"),
            Vehicle.cohort_community.alias("community"),
            RecallCampaign.campaign_id.alias("campaign"),
            ServiceCentre.name.alias("centre"),
            Week.week_index.alias("week"),
            RecallAssignment.urgency.alias("urgency"),
        )
        .to_df()
        .sort_values(["week", "urgency"], ascending=[True, False])
        .reset_index(drop=True)
    )
    for col in ("week", "community"):
        if col in df.columns:
            df[col] = [int(v) for v in df[col]]
    if "urgency" in df.columns:
        df["urgency"] = [float(v) if v is not None else 0.0 for v in df["urgency"]]

    # Per-community late% summary
    by_comm = df.groupby("community").apply(
        lambda g: (g["week"] >= 3).sum() / len(g) if len(g) else 0,
        include_groups=False,
    ).reset_index().rename(columns={0: "late_share"})
    return df, si, by_comm


# =============================================================================
# Driver
# =============================================================================
def main():
    print("\n=== Q1: Recall SLA audit ===")
    df1 = q1_recall_sla_audit()
    print(df1.to_string(index=False))
    df1b = q1b_breached_by_centre()
    print("\nBy centre:")
    print(df1b.to_string(index=False))

    print("\n=== Q2: Continental MK C1 (IBS) cascade ===")
    df2_vins = q2_continental_cascade()
    print(f"affected VINs: {len(df2_vins)}")
    print(df2_vins.head(10).to_string(index=False))
    print("\nRegional rollup:")
    print(q2_regional_rollup().to_string(index=False))
    print("\nTop centres:")
    print(q2_top_centres().to_string(index=False))

    print("\n=== Q3: Urgency top-20 (heuristic) ===")
    df3 = q3_urgency_top20()
    print(df3.to_string(index=False))

    print("\n=== Q4: Recall scheduling MIP ===")
    df4, si4 = q4_assign_recall_jobs()
    print(
        f"status={si4.termination_status} "
        f"obj={si4.objective_value:.2f} "
        f"time={si4.solve_time_sec:.2f}s "
        f"jobs scheduled={len(df4)}"
    )
    print("By week:")
    if not df4.empty:
        print(df4.groupby("week").size().to_string())
    print("\nFirst 15 assignments:")
    print(df4.head(15).to_string(index=False))

    print("\n=== Q5: Same MIP + priority rule (persistent) ===")
    df5, si5 = q5_assign_recall_jobs_priority()
    print(
        f"status={si5.termination_status} "
        f"obj={si5.objective_value:.2f} "
        f"time={si5.solve_time_sec:.2f}s "
        f"jobs scheduled={len(df5)}"
    )
    if not df5.empty:
        print(df5.groupby("week").size().to_string())
    # Compare counts at week 1+2 vs week 3+4 to show the rule's effect.
    if not df4.empty and not df5.empty:
        late_4 = int((df4["week"] >= 3).sum())
        late_5 = int((df5["week"] >= 3).sum())
        delta_obj = si5.objective_value - si4.objective_value
        print(f"\nlate(week>=3): Act4={late_4} -> Act5={late_5}    obj delta: {delta_obj:+.2f}")


if __name__ == "__main__":
    main()
