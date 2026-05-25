# DEMO_QUESTIONS.md - The 5 acts as plain-English questions

These are the questions a recall-campaign manager would type into a
Snowflake Intelligence search box, or that a head of after-sales would
ask in a Monday morning review. They map 1:1 to the `agent/queries.py`
functions exposed to the Cortex agent. Each act runs against the same
`cars` ontology, so a rule added in Act 5 is honoured by every other
act on re-execution.

The framing is "a major European OEM". The data inside the model is
BMW-grade (real WMIs, real model designators, real Tier-1 supplier
names) because the audience are BMW industry experts who would
otherwise smell the synthetic data. See `BRIEF.md` >
"Naming convention" for the wrapper-vs-data split.

---

## Q1. Act 1 (Rules) - Recall SLA compliance audit

**"Show me every Open recall on a VIN whose age in service or
accumulated mileage breaches the campaign-specific completion window.
Break it out by campaign and by responsible service centre."**

| Why it matters | NHTSA 49 CFR 577 requires the OEM to notify owners within 60 days of defect determination, and to report quarterly until a campaign closes. KBA's Rückruf code system assigns a severity tier with its own SLA (Code 1 immediate, Code 2 prompt). A Tier-1 campaign that has run more than 90 days with Open VINs above a published mileage cap is an audit finding and a brand risk. Today the campaign manager runs this as a manual cross-tab in Tableau; once the rule is captured in the ontology it propagates to every downstream act. |
|----------------|---|
| Reasoner | Rules (logic). The `SLABreached(Vehicle)` derived concept defines the rule once at the ontology layer: `RecallStatus = 'Open' AND (age_in_service > campaign.window_days OR mileage > campaign.window_km) AND severity_tier <= 2`. The query reuses it and groups by campaign and centre. |
| Expected shape | 19 SLA-breaching Open VINs across 4 campaigns. Leader: Continental MK C1 brake-booster firmware (IBS-2024-A), Code 2, 180-day completion window, 8 cases. Samsung SDI HV battery thermal (HVB-2024-A, Code 1, 60-day) at 7. EGR cooler 3, Joyson airbag 1. By centre: Cologne / Hamburg / Munich top the responsible-centre rollup. |

---

## Q2. Act 2 (Graph) - Defect cascade from a supplier part

**"Continental notified us this morning of an expanded scope on the
MK C1 brake-booster firmware defect. Walk the cascade: supplier ->
part number -> bill-of-materials node -> affected VINs by plant and
build window -> registered owners -> responsible service centres,
with regional rollups. Who do we have to notify, and where do they
go?"**

| Why it matters | Existing systems (BMW AIR / iLEAD-equivalent) do supplier-to-part and part-to-VIN as separate queries, then a service-network database does VIN-to-centre. Stitching the three together by hand is what the recall team does in Excel today, and they get it wrong roughly 5-10% of the time because the as-built BOM is plant-and-date-window-specific, not model-year-wide. RAI's graph reasoner walks the cascade as a single traversal against one ontology. |
|----------------|---|
| Reasoner | Graph. The cascade is the union of edge types over the cars ontology: `supplies(Supplier, Part)`, `consumes(BomNode, Part)`, `builtAs(Vehicle, BomNode)`, `ownedBy(Vehicle, Owner)`, `nearestCentre(Owner, ServiceCentre)`, `inRegion(ServiceCentre, Region)`. RAI computes reachability and the per-VIN ordered traversal in one pass. |
| Expected shape | One supplier (Continental), one part (MK C1 v2.3.1 booster ECU firmware), ~80 affected VINs across 3 plant-date cohorts (Munich Q1-Q2 2024, Regensburg Q2 2024, Spartanburg early Q3 2024). Regional rollup: EU 62, US 14, MX 4. Top 3 centres: Munich (18), Cologne (14), Spartanburg (9). |

---

## Q3. Act 3 (Heuristic) - Per-VIN recall urgency ranking

**"Of the ~270 Open recall jobs across all active campaigns, rank
them. I want to look at the top 20 only. Weights: mileage as a
utilisation proxy, age in service as a calendar-time proxy, prior
accident severity as a safety proxy, distance to the nearest
HV-or-IBS-equipped centre as a logistics proxy."**

| Why it matters | Today the recall team works through Open jobs in arrival-date order, which is wrong by every reasonable definition of urgency. A vehicle that is 4 years old with 195k km and a prior collision is materially more dangerous than a 6-month-old vehicle that has never been driven, even if both have the same open campaign. A flat list of 270 jobs is also too long to act on in a morning shift; the team needs the top of the queue, not the whole queue. |
|----------------|---|
| Reasoner | Deterministic heuristic in PyRel (Predictive reasoner is preview). Score = w1 * mileage_fraction + w2 * age_fraction + w3 * accident_severity + w4 * distance_penalty, where each fraction is a PyRel-derived property and the weights are constants on the model. Ranking is `.select(... urgency_score ...).sort_values()`. Reproducible, auditable, defensible to an insurance reviewer in a way a black-box GNN is not. |
| Expected shape | Top 20 dominated by Spartanburg-built X-series with prior collisions (Collision or Rear-end in accident history) and mileage > 150k. Specific seed-VINs to surface in the talk track: 3 from the iX / iX1 cohort (HV battery campaign), 2 from G21 LCI 3 Series (IBS campaign), 1 G87 M2 (engine recall). Anchored numbers in `data/cars_demo_validation.sql`. |

---

## Q4. Act 4 (Prescriptive) - Assign open recall jobs to centres for next 4 weeks

**"Schedule the next four weeks of recall work. Each open job goes to
exactly one centre in exactly one week. Minimise total
urgency-weighted lateness vs. the SLA week. Constraints: per-centre
weekly technician-hour capacity, per-centre per-week parts-stock-on-hand
for each campaign, no VIN assigned to a centre that lacks the required
tooling certification (HV for EV battery work, IBS-trained for brake
booster firmware, body-shop for restraint work). Solve it."**

| Why it matters | The current process is "spread the jobs evenly across centres" which ignores parts logistics and tooling. The realistic constraint structure is: a centre can do 30 brake-booster jobs per week IF Continental has shipped 30 booster ECUs to it, AND if the centre has the IBS-certified tooling and an IBS-trained tech rota. Centres without HV certification cannot legally touch the Samsung SDI battery campaign. A spreadsheet planner cannot solve this with 15 centres x 4 weeks x 270 jobs x 4 campaigns at the airline-grade quality the brand demands. |
|----------------|---|
| Reasoner | Prescriptive (MIP). Binary decision `JobAssignment.assign` over (~270 jobs) x (15 centres) x (4 weeks) = ~16,200 binaries. Constraints: assignment uniqueness, centre-week tech-hour capacity, centre-week parts-stock per campaign, tooling-certification eligibility, regional preference (the owner should not have to drive across a country if a closer centre has capacity). Objective: minimise sum(urgency * weeks-of-lateness vs SLA). HiGHS solves in <60s on `cars_prescriptive_m`. |
| Expected shape | OPTIMAL in <60s. ~15 jobs unscheduled (deferred past week 4) due to parts stock on the IBS campaign - Continental cannot ship enough booster ECUs in the planning horizon. Most US Spartanburg-built X-series go to BMW Dallas / Miami / LA / Spartanburg; the EU population spreads across Munich / Cologne / Hamburg / Stuttgart / Frankfurt by closest-centre and HV-certification. The deferred jobs include the top-3 from Act 3's urgency ranking, which becomes the motivation for Act 5. |

---

## Q5. Act 5 (Persistent rule) - Operator adds a safety priority rule

**"Add this rule to the ontology and re-solve: 'Any Open recall on a
VIN that has had a prior collision or rear-end accident in the last
three years is prioritised over a same-campaign Open recall without
that history. Force the prioritised VIN to be scheduled no later than
week 2 of the four-week horizon.' Show me what changes."**

| Why it matters | This is the institutional-knowledge moment. The senior recall manager has been chasing post-collision VINs out of band for years because she knows a vehicle that has already had structural damage is the wrong one to leave with a defective brake booster. Today that knowledge lives in her head, a runbook PDF, or an Excel override. By writing it as a derived concept on the ontology, the rule is stored alongside the data and respected by every reasoner that touches the same model - not just on the next re-solve, but for as long as it lives in the ontology. The next manager who joins the team inherits the rule automatically. |
|----------------|---|
| Reasoner | Rules + Prescriptive. The rule becomes a `PriorityVehicle(Vehicle)` derived concept (`prior_accident_within(3 years) AND has_open_recall`) and an additional constraint on the MIP: `sum(assign.week * (week > 2)) per Vehicle in PriorityVehicle == 0`. Re-solving picks up the constraint automatically because the constraint reads from the ontology. |
| Expected shape | Re-solve in <60s. 4-6 VINs reassigned: 3 prior-accident VINs move from week 3 or 4 into week 2; 3 non-priority VINs displace from week 2 to week 3 or 4. Total urgency-weighted lateness rises by ~8% (the rule trades raw efficiency for safety, as intended). Talk-track punchline: "the ontology now has institutional safety knowledge written down once." |

---

## Anti-patterns avoided

- A graph question with only one hop (that's a join). Act 2's cascade is
  six edge types deep at minimum.
- A prescriptive question with no real constraint (that's a sort). Act 4
  exposes parts stock, technician hours, and tooling-certification all
  as binding constraints.
- A persistent-rule question that does not change the answer when added.
  Act 5's rule materially changes the assignment - measured by the
  reassignment count and the lateness delta, asserted in
  `data/cars_demo_validation.sql`.

## Narrative arc

Act 1 grounds the audience in a problem they already recognise (SLA
audit, "I can do this in SQL today"). Act 2 reveals the cascade they
cannot do in SQL today. Act 3 turns the cascade output into a workable
queue. Act 4 prescribes - the LP closes the loop from "what's wrong"
through to "what should we do". Act 5 cements the punchline that
RelationalAI is not a one-shot tool: the rules live in the ontology
and propagate.
