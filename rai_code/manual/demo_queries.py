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

try:
    from .cars import (
        BomNode,
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
