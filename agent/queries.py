"""Pre-canned demo queries exposed to the Cortex agent via QueryCatalog.

Each function is module-level, takes zero arguments, and returns a
pandas DataFrame OR a dict with `records` + `chart_hint` (the agent's
generic-tool path accepts either; dict results pass through unchanged).

Two flavours per question:
- `<name>` returns the full table (good for "show me everything").
- `<name>_chart` returns a tighter 2-3 column DataFrame plus a
  chart_hint dict shaped for Snowsight's auto-visualizer. The hint
  tells the agent what chart to suggest in its text reply.
"""
from rai_code.manual.demo_queries import (
    q1_recall_sla_audit,
    q1b_breached_by_centre,
    q2_continental_cascade,
    q2_regional_rollup,
    q2_top_centres,
    q3_urgency_top20,
    q4_assign_recall_jobs,
    q5_assign_recall_jobs_priority,
)


def _wrap_chart(df, *, chart_type, x, y, title, color=None):
    """Wrap a DataFrame with a chart hint the agent can mention in its
    text reply. The agent's LLM sees `chart_hint` in the tool output and
    proposes the visualisation; the user clicks Snowsight's chart icon
    to render it from the same records."""
    hint = {"type": chart_type, "x": x, "y": y, "title": title}
    if color:
        hint["color"] = color
    return {"records": df.to_dict(orient="records"), "chart_hint": hint}


# =============================================================================
# Q1 - Recall SLA audit (rules)
# =============================================================================
def recall_sla_audit_by_campaign():
    """Act 1. Open recalls whose owner-notification age has breached
    the campaign's completion window, grouped by campaign. NHTSA 49 CFR
    577 and KBA Rueckruf semantics: severity Code 1 (stop driving) and
    Code 2 (repair urgently) campaigns are subject to a defined
    completion window starting at owner notification. Columns:
    campaign, campaign_name, severity, breached_open."""
    return q1_recall_sla_audit()


def recall_sla_audit_by_campaign_chart():
    """Act 1 chart variant. campaign + breached_open + bar-chart hint."""
    df = q1_recall_sla_audit()[["campaign", "breached_open"]]
    return _wrap_chart(
        df, chart_type="bar", x="campaign", y="breached_open",
        title="SLA-breached Open recalls by campaign",
    )


def recall_sla_audit_by_centre():
    """Act 1 alternate slice. Same SLA-breach set rolled up by the
    owner's nearest service centre - i.e. the centre that has to absorb
    the work. Columns: centre, country, breached_open."""
    return q1b_breached_by_centre()


def recall_sla_audit_by_centre_chart():
    df = q1b_breached_by_centre()[["centre", "breached_open"]]
    return _wrap_chart(
        df, chart_type="bar", x="centre", y="breached_open",
        title="SLA-breached Open recalls by responsible centre",
    )


# =============================================================================
# Q2 - Continental cascade (graph)
# =============================================================================
def continental_cascade_full():
    """Act 2. Defect cascade from supplier Continental + part
    PRT-IBS-ECU (MK C1 brake-booster ECU firmware). Traverses
    supplier -> part -> bom_node -> vehicle -> owner -> service centre.
    Returns one row per affected VIN with plant, production date,
    owner country, and nearest centre."""
    return q2_continental_cascade()


def continental_cascade_regional_chart():
    """Act 2 regional rollup. Returns affected VINs and centres engaged
    per region rollup (EU / NA / LATAM) plus a bar chart hint."""
    df = q2_regional_rollup()
    return _wrap_chart(
        df, chart_type="bar", x="rollup", y="affected_vins",
        title="Continental MK C1 cascade - affected VINs by region",
    )


def continental_cascade_centres_chart():
    """Act 2 by centre. Top centres that have to absorb the work, with
    a bar chart hint."""
    df = q2_top_centres()
    return _wrap_chart(
        df, chart_type="bar", x="centre", y="affected_vins",
        title="Continental MK C1 cascade - top centres by exposure",
    )


# =============================================================================
# Q3 - Urgency ranking (heuristic)
# =============================================================================
def urgency_top20():
    """Act 3. Top 20 Open recall jobs by deterministic urgency score.
    Score weights mileage (utilisation), notification age, prior
    accident severity, and distance to nearest equipped centre. The
    scoring formula lives on the ontology as RecallAssignment.urgency."""
    return q3_urgency_top20()


def urgency_top20_chart():
    """Chart variant: VIN + urgency only, with a bar chart hint."""
    df = q3_urgency_top20()[["vin", "urgency"]]
    return _wrap_chart(
        df, chart_type="bar", x="vin", y="urgency",
        title="Top-20 Open recalls by urgency score",
    )


# =============================================================================
# Q4 / Q5 - MIP scheduling (prescriptive + persistent rule)
# =============================================================================
def schedule_recall_jobs():
    """Act 4. HiGHS MIP. Assigns every Open recall job to a (centre,
    week) within a 4-week horizon. Minimises total urgency-weighted
    lateness vs week 1, subject to per-centre tech-hour capacity,
    per-centre per-campaign parts-stock, and tooling-certification
    eligibility (HV / IBS / body shop). Returns one row per scheduled
    job with centre, week, urgency, hours."""
    df, _si = q4_assign_recall_jobs()
    return df


def schedule_recall_jobs_chart():
    """Act 4 chart variant: jobs grouped by (centre, week) as a stacked
    bar chart."""
    df, _si = q4_assign_recall_jobs()
    pivot = df.groupby(["centre", "week"]).size().reset_index(name="jobs")
    return _wrap_chart(
        pivot, chart_type="bar", x="centre", y="jobs", color="week",
        title="Recall jobs scheduled by centre and week (Act 4 baseline)",
    )


def schedule_recall_jobs_priority():
    """Act 5. Same MIP as Act 4 but with the persistent operator rule:
    any Open recall on a VIN with a prior collision or rear-end
    accident must be scheduled in week 1 or 2. The rule is captured
    once on the ontology as RecallAssignment.priority_flag; the LP
    constraint references it directly."""
    df, _si = q5_assign_recall_jobs_priority()
    return df


def schedule_recall_jobs_priority_chart():
    """Act 5 chart variant."""
    df, _si = q5_assign_recall_jobs_priority()
    pivot = df.groupby(["centre", "week"]).size().reset_index(name="jobs")
    return _wrap_chart(
        pivot, chart_type="bar", x="centre", y="jobs", color="week",
        title="Recall jobs scheduled by centre and week (Act 5 with priority rule)",
    )
