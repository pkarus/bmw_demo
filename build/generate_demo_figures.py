#!/usr/bin/env python3
"""Generate one PNG figure per demo act for RUNNING.html.

Run from project root after Phases 3-4 have produced fresh query
results:

    .venv/bin/python build/generate_demo_figures.py

Writes to build/figures/. PNGs are referenced as relative paths from
RUNNING.html.
"""
from __future__ import annotations
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FIGURES = Path(__file__).resolve().parent / "figures"
FIGURES.mkdir(exist_ok=True)
sys.path.insert(0, str(ROOT))

# Disarm PyRel's running-loop guard for sync solve() calls.
import relationalai.client as _ra_client
import relationalai.services.reasoners.client as _ra_reasoners_client
_noop = lambda *a, **k: None
_ra_client.raise_if_running_event_loop = _noop
_ra_reasoners_client.raise_if_running_event_loop = _noop

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from rai_code.manual import demo_queries


def _save(fig, name: str, width: int = 1100, height: int = 520) -> Path:
    path = FIGURES / f"{name}.png"
    fig.write_image(str(path), width=width, height=height, scale=2)
    print(f"  wrote {path.relative_to(ROOT)}")
    return path


def main():
    print("Generating demo figures into build/figures/")

    print("\nAct 1: SLA audit by campaign")
    df1 = demo_queries.q1_recall_sla_audit()
    fig = px.bar(
        df1, x="campaign", y="breached_open",
        color="severity",
        color_continuous_scale=[(0, "#c62828"), (0.5, "#ef6c00"), (1, "#f9a825")],
        range_color=(1, 3),
        title="SLA-breached Open recalls by campaign (severity 1 = stop driving, 2 = repair urgently)",
        text="breached_open", hover_data=["campaign_name"],
    )
    fig.update_traces(textposition="outside")
    fig.update_layout(xaxis_title="Campaign", yaxis_title="SLA-breached Open recalls")
    _save(fig, "act1_sla_by_campaign")

    df1b = demo_queries.q1b_breached_by_centre()
    fig = px.bar(
        df1b, x="centre", y="breached_open", color="country",
        title="SLA-breached Open recalls by responsible centre", text="breached_open",
    )
    fig.update_traces(textposition="outside")
    fig.update_layout(xaxis_tickangle=-30, yaxis_title="SLA-breached Open recalls")
    _save(fig, "act1_sla_by_centre")

    print("\nAct 2: Continental cascade")
    df2 = demo_queries.q2_continental_cascade()
    df2_rollup = demo_queries.q2_regional_rollup()
    df2_centres = demo_queries.q2_top_centres()
    fig = make_subplots(rows=1, cols=2, subplot_titles=("Regional rollup", "Top centres by affected VINs"))
    fig.add_trace(go.Bar(x=df2_rollup["rollup"], y=df2_rollup["affected_vins"], text=df2_rollup["affected_vins"], textposition="outside"), row=1, col=1)
    fig.add_trace(go.Bar(x=df2_centres["centre"], y=df2_centres["affected_vins"], text=df2_centres["affected_vins"], textposition="outside", marker_color="#e57373"), row=1, col=2)
    fig.update_xaxes(tickangle=-30, row=1, col=2)
    fig.update_layout(showlegend=False, title_text=f"Continental MK C1 cascade ({len(df2)} VINs)")
    _save(fig, "act2_cascade_rollup")

    print("\nAct 3: Urgency top-20")
    df3 = demo_queries.q3_urgency_top20()
    df3_plot = df3.copy()
    df3_plot["label"] = df3_plot["vin"].str[-6:] + " | " + df3_plot["model"].str.slice(0, 18) + " | " + df3_plot["campaign"]
    fig = px.bar(
        df3_plot.sort_values("urgency"), y="label", x="urgency", orientation="h",
        color="accident", color_discrete_sequence=px.colors.qualitative.Set2,
        title="Top-20 Open recalls by urgency score",
        text="urgency", hover_data=["plant", "mileage", "age_days", "distance_km"],
    )
    fig.update_traces(texttemplate="%{text:.2f}", textposition="outside")
    fig.update_layout(yaxis_title="Vehicle", xaxis_title="Urgency score (0..1)")
    _save(fig, "act3_urgency_top20", height=620)

    print("\nAct 4: Recall scheduling MIP")
    df4, si4 = demo_queries.q4_assign_recall_jobs()
    df4_pivot = df4.groupby(["centre", "week"]).size().reset_index(name="jobs")
    fig = px.bar(
        df4_pivot, x="centre", y="jobs", color="week",
        color_continuous_scale="Viridis",
        title=f"Recall job assignments by centre and week (Act 4 baseline; obj={si4.objective_value:.2f}, OPTIMAL)",
        barmode="stack",
    )
    fig.update_layout(xaxis_tickangle=-30, yaxis_title="Jobs scheduled")
    _save(fig, "act4_schedule")

    print("\nAct 5: Persistent rule re-solve")
    df5, si5 = demo_queries.q5_assign_recall_jobs_priority()
    wk4 = df4.groupby("week").size().reindex([1, 2, 3, 4], fill_value=0)
    wk5 = df5.groupby("week").size().reindex([1, 2, 3, 4], fill_value=0)
    fig = make_subplots(rows=1, cols=2, subplot_titles=("Jobs per week", "Objective: weighted lateness"))
    fig.add_trace(go.Bar(name="Act 4", x=wk4.index, y=wk4.values, marker_color="#5e81ac"), row=1, col=1)
    fig.add_trace(go.Bar(name="Act 5", x=wk5.index, y=wk5.values, marker_color="#bf616a"), row=1, col=1)
    fig.add_trace(go.Bar(name="objective", x=["Act 4", "Act 5"], y=[si4.objective_value, si5.objective_value], marker_color=["#5e81ac", "#bf616a"]), row=1, col=2)
    fig.update_xaxes(title_text="Week", row=1, col=1)
    fig.update_xaxes(title_text="Solve", row=1, col=2)
    fig.update_yaxes(title_text="Jobs scheduled", row=1, col=1)
    fig.update_yaxes(title_text="Total weighted lateness", row=1, col=2)
    fig.update_layout(barmode="group", title_text="Act 4 vs Act 5 - persistent rule effect")
    _save(fig, "act5_compare")

    print("\nAct 2b: vehicle cohort communities (Louvain graph)")
    nodes, edges = demo_queries.q7_vehicle_communities_nodes_and_edges()
    import networkx as nx
    G = nx.Graph()
    for vin in nodes["vin"]:
        G.add_node(vin)
    for _, r in edges.iterrows():
        G.add_edge(r["v1"], r["v2"], weight=int(r["shared_boms"]))
    pos = nx.spring_layout(G, seed=42, k=0.55, iterations=80, weight="weight")
    edge_x, edge_y = [], []
    for _, r in edges.iterrows():
        x0, y0 = pos[r["v1"]]
        x1, y1 = pos[r["v2"]]
        edge_x.extend([x0, x1, None])
        edge_y.extend([y0, y1, None])
    summary_df = demo_queries.q7_vehicle_communities()
    biggest = summary_df.iloc[0]
    fig = go.Figure(data=[
        go.Scatter(x=edge_x, y=edge_y, mode="lines",
                   line=dict(width=0.6, color="rgba(140,140,140,0.25)"),
                   hoverinfo="skip", showlegend=False),
        go.Scatter(
            x=[pos[v][0] for v in nodes["vin"]],
            y=[pos[v][1] for v in nodes["vin"]],
            mode="markers",
            marker=dict(
                size=[max(9, min(40, int(d) * 0.45 + 9)) for d in nodes["degree"]],
                color=nodes["community"].tolist(),
                colorscale="Turbo",
                showscale=True,
                colorbar=dict(title=dict(text="Community", side="right"), x=1.02, len=0.8),
                line=dict(width=0.6, color="white"),
                opacity=0.92,
            ),
            text=[
                f"<b>{r.vin}</b><br>{r.model}<br>plant: {r.plant} fuel: {r.fuel}<br>"
                f"mileage: {int(r.mileage):,} km<br>community: {r.community} degree: {int(r.degree)}<br>"
                f"campaigns: {int(r.campaign_count)} open recalls: {int(r.open_count)}<br>"
                f"accident: {r.accident}"
                for r in nodes.itertuples()
            ],
            hoverinfo="text",
            showlegend=False,
        ),
    ])
    fig.update_layout(
        title=(
            f"Vehicle cohort communities (Louvain on shared-BOM graph)<br>"
            f"<sup>{len(nodes)} VINs - {len(edges):,} edges - {int(nodes['community'].nunique())} communities. "
            f"Largest cluster: {int(biggest.vins)} VINs (dominant model: {biggest.dominant_model}).</sup>"
        ),
        template="plotly_dark",
        plot_bgcolor="#0f1115", paper_bgcolor="#0f1115",
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False, scaleanchor="y"),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        margin=dict(l=10, r=10, t=90, b=10),
    )
    _save(fig, "act2b_vehicle_communities", width=1300, height=820)

    print(f"\nAll figures written to {FIGURES.relative_to(ROOT)}/")


if __name__ == "__main__":
    main()
