#!/usr/bin/env python3
"""Render RUNNING.html from RUNBOOK.template.html with cars-specific
substitutions. Run after build/generate_demo_figures.py.

Figures under build/figures/ are gitignored, so we inline them as
base64 data URIs. The committed RUNNING.html then travels with a fresh
clone and renders standalone (no missing images)."""
from __future__ import annotations
import base64
import re
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parent
TEMPLATE = ROOT / "RUNBOOK.template.html"
OUT = ROOT / "RUNNING.html"
FIGURES_DIR = ROOT / "build" / "figures"

SUBS = {
    "DOMAIN_TITLE": "OEM Fleet Recall Propagation",
    "DOMAIN_SUBTITLE": "RelationalAI demo for a major European luxury OEM.",
    "DOMAIN": "cars",
    "N": "5",
    "LOGIC_ENGINE": "cars_logic_l",
    "PRESCRIPTIVE_ENGINE": "cars_prescriptive_m",
    "DATABASE": "CARS_DEMO.FLEET",
    "AGENT_NAME": "cars",
    "LAST_GENERATED": datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),

    "ACT1_TITLE": "Recall SLA compliance audit",
    "ACT1_WHY": "Per NHTSA 49 CFR 577 / KBA Rueckruf, Code-1 and Code-2 recalls must complete within the campaign window measured from owner-notification date. The rule lives in the ontology as <code>SLABreachedRecall</code> - a derived concept that re-runs against the current data automatically.",
    "ACT1_BEAT": "Expected output: 19 SLA-breached Open recalls. Leader: IBS-2024-A (Continental MK C1 brake-booster firmware, 8 cases). Severity Code 1 cases (HVB-2024-A, 7) matter most per VIN. By centre, Cologne / Hamburg / Munich are the most exposed.",
    "ACT1_SLUG": "sla_by_campaign",
    "ACT1_SI_PROMPT": "Which open recalls are past their completion window? Show me the count by campaign.",

    "ACT2_TITLE": "Continental MK C1 defect cascade",
    "ACT2_WHY": "Supplier-to-VIN propagation today is a six-system stitch (BMW AIR -> iLEAD -> dealer-network DB). The ontology walks it in a single PyRel query that joins supplier -> part -> bom_node -> vehicle -> owner -> service centre.",
    "ACT2_BEAT": "Expected output: 67 affected VINs across three plant-date cohorts (Munich, Regensburg, Spartanburg). Regional rollup: EU 53, NA 12, LATAM 2. Top centres: Hamburg, Frankfurt, Berlin, Munich. The Sankey shows the cascade visually.",
    "ACT2_SLUG": "cascade_rollup",
    "ACT2_SI_PROMPT": "Continental flagged a defect in the MK C1 brake booster ECU. Show me every VIN affected, broken down by region.",

    "ACT2B_SI_PROMPT": "Run Louvain community detection on the vehicle-cohort graph - two VINs share an edge when they share a BOM node. Show me the clusters and their dominant model.",

    "ACT3_TITLE": "Per-VIN urgency ranking (top 20)",
    "ACT3_WHY": "Score = w1*mileage + w2*notification_age + w3*accident_severity + w4*distance_to_centre. All weights and all inputs are PyRel-derived properties. Auditable, defensible, reproducible across runs.",
    "ACT3_BEAT": "Top of the queue mixes Regensburg X1 M35i + iX1 units with high mileage and prior collisions, plus Dingolfing iX / i7 EVs from the HVB campaign. Visible accident_severity column makes the safety argument explicit.",
    "ACT3_SLUG": "urgency_top20",
    "ACT3_SI_PROMPT": "Rank the open recall jobs by urgency. Weight mileage, notification age, prior accident severity, and distance to the nearest equipped centre. Show me the top 20.",

    "ACT4_TITLE": "MIP: assign recall jobs to centres x 4 weeks",
    "ACT4_WHY": "HiGHS MIP. Decision: x[recall, centre, week] binary. Constraints: per-centre weekly technician hours, per-centre per-campaign per-week parts stock, tooling-certification eligibility (HV / IBS / body shop). Objective: sum(x * urgency * (week-1)).",
    "ACT4_BEAT": "Expected: OPTIMAL in under 60 seconds (warm). All 121 Open jobs scheduled. The binding constraint in practice is parts stock on the IBS campaign (Continental can't ship enough booster ECUs in 4 weeks). EU jobs cluster in DE centres; US in Spartanburg / Dallas / NYC / LA.",
    "ACT4_SLUG": "schedule",
    "ACT4_SI_PROMPT": "Schedule the next four weeks of open recall jobs to service centres. Minimise urgency-weighted lateness, respect tooling certifications and parts stock. How many jobs deferred past week 4?",

    "ACT5_TITLE": "Persistent rule: prior-accident VINs go to week 1 or 2",
    "ACT5_WHY": "The rule is captured once as <code>RecallAssignment.priority_flag</code> on the ontology. Adding it triggers a re-solve under the new constraint <code>sum(assign at week>=3) == 0</code> for priority VINs. The rule survives the session - the next agent / SE / human inherits it.",
    "ACT5_BEAT": "Expected: re-solve OPTIMAL in under 60s. 4-6 reassignments (priority VINs move into weeks 1 or 2; other jobs absorb the slip). Total weighted lateness rises ~5-10% - the rule trades raw efficiency for safety, as intended.",
    "ACT5_SLUG": "compare",
    "ACT5_SI_PROMPT": "Add this rule to the ontology and re-solve: any open recall on a VIN with a prior collision in the last three years must be scheduled in week 1 or 2. Show me what changed.",

    "METRIC_1_NAME":   "Vehicles in scope",
    "METRIC_1_VALUE":  "325",
    "METRIC_1_NOTES":  "Source: BMW_VEHICLES_V1.csv (real BMW WMI prefixes).",
    "METRIC_2_NAME":   "Service events",
    "METRIC_2_VALUE":  "762",
    "METRIC_2_NOTES":  "Source: BMW_VEHICLES_SERVICES.csv (302 distinct VINs).",
}


_IMG_SRC_RE = re.compile(r'src="(build/figures/[^"]+\.png)"')


def _inline_figure(match: re.Match) -> str:
    rel = match.group(1)
    path = ROOT / rel
    if not path.exists():
        print(f"  WARN: missing figure {rel} - leaving as relative src")
        return match.group(0)
    data = base64.b64encode(path.read_bytes()).decode("ascii")
    return f'src="data:image/png;base64,{data}"'


def main():
    tpl = TEMPLATE.read_text()
    out = tpl
    for k, v in SUBS.items():
        out = out.replace("{{" + k + "}}", v)
    # Insert additional anchored-number rows after METRIC_2.
    extra_rows = """        <tr><td>Open recalls</td><td>121</td><td><code>WHERE status='Open'</code></td></tr>
        <tr><td>SLA-breached Open (Act 1)</td><td>19</td><td>IBS-2024-A 8, HVB-2024-A 7, EGR-2023-B 3, AIRBAG-2022-A 1</td></tr>
        <tr><td>Continental MK C1 cascade (Act 2)</td><td>67 VINs</td><td>EU 53, NA 12, LATAM 2 - three plant-date cohorts</td></tr>
        <tr><td>Vehicle cohort communities (Act 2b)</td><td>190 VINs, 4 communities</td><td>Louvain on shared-BOM graph (non-deterministic labels; sizes stable)</td></tr>
        <tr><td>Priority VINs (Act 5)</td><td>15</td><td>Open recall + prior accident</td></tr>
        <tr><td>Recall campaigns</td><td>5</td><td>IBS / HVB / EGR / AIRBAG / STARTER</td></tr>
        <tr><td>Service centres</td><td>15</td><td>EU 8 + US 6 + MX 1</td></tr>
        <tr><td>BOM membership edges</td><td>531</td><td>vehicle x bom_node junctions</td></tr>"""

    # Act 2b card is now baked into the template directly; no
    # injection needed here.
    out = out.replace(
        "        <!-- add rows as needed -->",
        extra_rows + "\n        <!-- add rows as needed -->",
    )
    out, n_inlined = _IMG_SRC_RE.subn(_inline_figure, out)
    OUT.write_text(out)
    print(f"Wrote {OUT} ({n_inlined} figures inlined as base64)")


if __name__ == "__main__":
    main()
