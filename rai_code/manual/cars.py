"""CARS_DEMO - manually-built ontology over CARS_DEMO.FLEET.

Concepts:
    Dim:         Supplier, Region, Plant, Part, BomNode, ServiceCentre,
                 RecallCampaign
    Master:      Owner, Vehicle
    Events:      ServiceEvent, RecallAssignment
    Junctions:   BomMembership (Vehicle x BomNode), CentreCapacity
                 (ServiceCentre x Week), PartsStock (Centre x Campaign x
                 Week), JobAssignment (RecallAssignment x Centre x Week)
    Derived:     OpenRecall(RecallAssignment), SLABreached(RecallAssignment),
                 PriorAccident(Vehicle), PriorityVehicle(Vehicle - the
                 Act 5 persistent rule concept)

Run from project root:
    .venv/bin/python rai_code/manual/cars.py

The `_build_config()` pattern is copied verbatim from
supply_chain_demo/rai_code/manual/supply_chain.py - it auto-detects
Snowsight vs local and pins the named engines.
"""
from relationalai.semantics import (
    Boolean, Date, Float, Integer, Model, String,
)
from relationalai.semantics.std import aggregates as aggs


_LOGIC_NAME, _LOGIC_SIZE = "cars_logic_l", "HIGHMEM_X64_L"
_PRESC_NAME, _PRESC_SIZE = "cars_prescriptive_m", "HIGHMEM_X64_M"

# Both engines have auto-suspend set to 30 minutes (set once via:
#   .venv/bin/rai reasoners alter --name cars_logic_l       --type Logic        --auto-suspend-mins 30
#   .venv/bin/rai reasoners alter --name cars_prescriptive_m --type Prescriptive --auto-suspend-mins 30
# This is a native-app-level setting; PyRel's create_config() does not
# override it, so the value sticks across model loads.


def _build_config():
    """Auto-discover config (active Snowpark session inside Snowflake, or
    the snow CLI's connections.toml locally), then pin reasoners to named
    engines."""
    try:
        from snowflake.snowpark.context import get_active_session  # type: ignore
        get_active_session()
        from relationalai.config import ConfigFromActiveSession
        cfg = ConfigFromActiveSession()
    except Exception:
        from relationalai.config import create_config
        cfg = create_config()
    cfg.reasoners.logic.name = _LOGIC_NAME
    cfg.reasoners.logic.size = _LOGIC_SIZE
    cfg.reasoners.prescriptive.name = _PRESC_NAME
    cfg.reasoners.prescriptive.size = _PRESC_SIZE
    return cfg


model = Model("cars", config=_build_config())


# =============================================================================
# CONCEPTS
# =============================================================================

# --- dimensions
Supplier = model.Concept("Supplier", identify_by={"supplier_id": String})
Region = model.Concept("Region", identify_by={"region_code": String})
Plant = model.Concept("Plant", identify_by={"plant_code": String})
Part = model.Concept("Part", identify_by={"part_id": String})
BomNode = model.Concept("BomNode", identify_by={"bom_id": String})
ServiceCentre = model.Concept("ServiceCentre", identify_by={"centre_id": String})
RecallCampaign = model.Concept("RecallCampaign", identify_by={"campaign_id": String})

# --- master
Owner = model.Concept("Owner", identify_by={"owner_id": String})
Vehicle = model.Concept("Vehicle", identify_by={"vin": String})

# --- events
ServiceEvent = model.Concept("ServiceEvent", identify_by={"service_event_id": String})
RecallAssignment = model.Concept("RecallAssignment", identify_by={"recall_id": String})

# --- junctions (planning-horizon weeks)
Week = model.Concept("Week", identify_by={"week_index": Integer})
CentreCapacity = model.Concept(
    "CentreCapacity",
    identify_by={"centre": ServiceCentre, "week": Week},
)
PartsStock = model.Concept(
    "PartsStock",
    identify_by={"centre": ServiceCentre, "campaign": RecallCampaign, "week": Week},
)

# --- 3-way ternary: centre handoffs by campaign. Captures the
# historical referral pattern - when centre F is overcommitted on
# campaign K (parts shortage, cert gap), it forwards vehicles to
# centre T. Same (F, T) carries different volumes per campaign, so
# the natural grain is (from_centre, to_centre, campaign). Used by
# Pathfinder (Q11) for chain enumeration and by Q12 as graph input
# to the MIP.
CentreHandoff = model.Concept(
    "CentreHandoff",
    identify_by={
        "from_centre": ServiceCentre,
        "to_centre": ServiceCentre,
        "campaign": RecallCampaign,
    },
)

# --- BOM membership: Vehicle x BomNode junction
# Represented as a relationship; many-to-many.
in_bom = model.Relationship(
    f"{Vehicle} is in {BomNode:bom}", short_name="in_bom"
)

# --- Decision-variable junction: RecallAssignment x ServiceCentre x Week
JobAssignment = model.Concept(
    "JobAssignment",
    identify_by={"recall": RecallAssignment, "centre": ServiceCentre, "week": Week},
)


# =============================================================================
# PROPERTIES
# =============================================================================

# --- Supplier
Supplier.name = model.Property(f"{Supplier} called {String:name}")
Supplier.tier = model.Property(f"{Supplier} has {Integer:tier}")
Supplier.country = model.Property(f"{Supplier} has {String:country}")
Supplier.specialty = model.Property(f"{Supplier} has {String:specialty}")
Supplier.warranty_share_pct = model.Property(
    f"{Supplier} has {Integer:warranty_share_pct}"
)

# --- Region
Region.name = model.Property(f"{Region} called {String:name}")
Region.rollup = model.Property(f"{Region} has {String:rollup}")
Region.country_codes = model.Property(f"{Region} has {String:country_codes}")

# --- Plant
Plant.name = model.Property(f"{Plant} called {String:name}")
Plant.country = model.Property(f"{Plant} has {String:country}")
Plant.region = model.Property(f"{Plant} in {Region:region}")
Plant.weekly_output = model.Property(f"{Plant} has {Integer:weekly_output}")

# --- Part
Part.supplier = model.Property(f"{Part} supplied by {Supplier:supplier}")
Part.name = model.Property(f"{Part} called {String:name}")
Part.category = model.Property(f"{Part} has {String:category}")
Part.unit_cost_usd = model.Property(f"{Part} has {Integer:unit_cost_usd}")

# --- BomNode
BomNode.part = model.Property(f"{BomNode} uses {Part:part}")
BomNode.description = model.Property(f"{BomNode} has {String:description}")
BomNode.applies_to_model_codes = model.Property(
    f"{BomNode} has {String:applies_to_model_codes}"
)
BomNode.applies_to_plants = model.Property(
    f"{BomNode} has {String:applies_to_plants}"
)
BomNode.applies_from = model.Property(f"{BomNode} applies_from {Date:applies_from}")
BomNode.applies_to = model.Property(f"{BomNode} applies_to {Date:applies_to}")

# --- ServiceCentre
ServiceCentre.name = model.Property(f"{ServiceCentre} called {String:name}")
ServiceCentre.country = model.Property(f"{ServiceCentre} has {String:country}")
ServiceCentre.region = model.Property(f"{ServiceCentre} in {Region:region}")
ServiceCentre.hv_certified = model.Property(f"{ServiceCentre} has {Boolean:hv_certified}")
ServiceCentre.ibs_certified = model.Property(f"{ServiceCentre} has {Boolean:ibs_certified}")
ServiceCentre.body_shop = model.Property(f"{ServiceCentre} has {Boolean:body_shop}")
ServiceCentre.weekly_tech_hours = model.Property(
    f"{ServiceCentre} has {Integer:weekly_tech_hours}"
)
ServiceCentre.has_egr_tooling = model.Property(
    f"{ServiceCentre} has {Boolean:has_egr_tooling}"
)

# --- RecallCampaign
RecallCampaign.name = model.Property(f"{RecallCampaign} called {String:name}")
RecallCampaign.supplier = model.Property(
    f"{RecallCampaign} from {Supplier:supplier}"
)
RecallCampaign.primary_part = model.Property(
    f"{RecallCampaign} primary {Part:primary_part}"
)
RecallCampaign.severity_code = model.Property(
    f"{RecallCampaign} has {Integer:severity_code}"
)
RecallCampaign.completion_days = model.Property(
    f"{RecallCampaign} has {Integer:completion_days}"
)
RecallCampaign.announced_on = model.Property(
    f"{RecallCampaign} announced_on {Date:announced_on}"
)
RecallCampaign.requires_hv_cert = model.Property(
    f"{RecallCampaign} has {Boolean:requires_hv_cert}"
)
RecallCampaign.requires_ibs_cert = model.Property(
    f"{RecallCampaign} has {Boolean:requires_ibs_cert}"
)
RecallCampaign.requires_body_shop = model.Property(
    f"{RecallCampaign} has {Boolean:requires_body_shop}"
)
RecallCampaign.typical_labour_hours = model.Property(
    f"{RecallCampaign} has {Float:typical_labour_hours}"
)
RecallCampaign.description = model.Property(
    f"{RecallCampaign} has {String:description}"
)

# --- Owner
Owner.masked_name = model.Property(f"{Owner} called {String:masked_name}")
Owner.region = model.Property(f"{Owner} in {Region:region}")
Owner.country = model.Property(f"{Owner} has {String:country}")
Owner.nearest_centre = model.Property(
    f"{Owner} nearest {ServiceCentre:nearest_centre}"
)
Owner.distance_km = model.Property(f"{Owner} has {Integer:distance_km}")
Owner.prior_accident_history = model.Property(
    f"{Owner} has {Boolean:prior_accident_history}"
)

# --- Vehicle
Vehicle.serial_number = model.Property(f"{Vehicle} has {String:serial_number}")
Vehicle.model = model.Property(f"{Vehicle} has {String:model}")
Vehicle.factory = model.Property(f"{Vehicle} has {String:factory}")
Vehicle.engine_type = model.Property(f"{Vehicle} has {String:engine_type}")
Vehicle.fuel_type = model.Property(f"{Vehicle} has {String:fuel_type}")
Vehicle.transmission = model.Property(f"{Vehicle} has {String:transmission}")
Vehicle.chassis_number = model.Property(f"{Vehicle} has {String:chassis_number}")
Vehicle.emission_standard = model.Property(f"{Vehicle} has {String:emission_standard}")
Vehicle.production_date = model.Property(f"{Vehicle} production_date {Date:production_date}")
Vehicle.delivery_date = model.Property(f"{Vehicle} delivery_date {Date:delivery_date}")
Vehicle.first_registration_date = model.Property(
    f"{Vehicle} first_registration_date {Date:first_registration_date}"
)
Vehicle.mileage = model.Property(f"{Vehicle} has {Integer:mileage}")
Vehicle.fuel_consumption = model.Property(f"{Vehicle} has {Float:fuel_consumption}")
Vehicle.accident_date = model.Property(f"{Vehicle} accident_date {Date:accident_date}")
Vehicle.accident_type = model.Property(f"{Vehicle} has {String:accident_type}")
Vehicle.repair_cost = model.Property(f"{Vehicle} has {Float:repair_cost}")
Vehicle.service_records = model.Property(f"{Vehicle} has {String:service_records}")
Vehicle.recall_status_raw = model.Property(f"{Vehicle} has {String:recall_status_raw}")
Vehicle.previous_owners = model.Property(f"{Vehicle} has {Integer:previous_owners}")
Vehicle.power_output_kw = model.Property(f"{Vehicle} has {Integer:power_output_kw}")
Vehicle.power_output_ps = model.Property(f"{Vehicle} has {Integer:power_output_ps}")
Vehicle.owner = model.Property(f"{Vehicle} owned by {Owner:owner}")
Vehicle.region = model.Property(f"{Vehicle} in {Region:region}")
Vehicle.owner_country = model.Property(f"{Vehicle} has {String:owner_country}")
Vehicle.nearest_centre = model.Property(
    f"{Vehicle} nearest {ServiceCentre:nearest_centre}"
)
Vehicle.distance_to_nearest_centre_km = model.Property(
    f"{Vehicle} has {Integer:distance_to_nearest_centre_km}"
)

# --- Vehicle derived: urgency-score inputs
Vehicle.accident_severity = model.Property(f"{Vehicle} has {Integer:accident_severity}")
Vehicle.urgency_score = model.Property(f"{Vehicle} has {Float:urgency_score}")

# --- ServiceEvent
ServiceEvent.vehicle = model.Property(f"{ServiceEvent} on {Vehicle:vehicle}")
ServiceEvent.service_date = model.Property(
    f"{ServiceEvent} service_date {Date:service_date}"
)
ServiceEvent.service_type = model.Property(f"{ServiceEvent} has {String:service_type}")
ServiceEvent.service_centre = model.Property(
    f"{ServiceEvent} at_centre {String:service_centre}"
)
ServiceEvent.service_cost = model.Property(f"{ServiceEvent} has {Float:service_cost}")
ServiceEvent.warranty = model.Property(f"{ServiceEvent} has {Boolean:warranty}")
ServiceEvent.notes = model.Property(f"{ServiceEvent} has {String:notes}")

# --- RecallAssignment
RecallAssignment.vehicle = model.Property(
    f"{RecallAssignment} for {Vehicle:vehicle}"
)
RecallAssignment.campaign = model.Property(
    f"{RecallAssignment} on {RecallCampaign:campaign}"
)
RecallAssignment.status = model.Property(f"{RecallAssignment} has {String:status}")
RecallAssignment.announced_on = model.Property(
    f"{RecallAssignment} announced_on {Date:announced_on}"
)
RecallAssignment.notified_on = model.Property(
    f"{RecallAssignment} notified_on {Date:notified_on}"
)
RecallAssignment.closed_on = model.Property(
    f"{RecallAssignment} closed_on {Date:closed_on}"
)
RecallAssignment.age_days_at_demo = model.Property(
    f"{RecallAssignment} has {Integer:age_days_at_demo}"
)
RecallAssignment.mileage_at_assign = model.Property(
    f"{RecallAssignment} has {Integer:mileage_at_assign}"
)
RecallAssignment.sla_breached = model.Property(
    f"{RecallAssignment} has {Boolean:sla_breached}"
)

# --- Week
Week.week_label = model.Property(f"{Week} has {String:week_label}")

# --- CentreCapacity
CentreCapacity.tech_hours_available = model.Property(
    f"{CentreCapacity} has {Integer:tech_hours_available}"
)

# --- PartsStock
PartsStock.on_hand_units = model.Property(
    f"{PartsStock} has {Integer:on_hand_units}"
)

# --- CentreHandoff (3-way ternary)
CentreHandoff.monthly_handoffs = model.Property(
    f"{CentreHandoff} has {Integer:monthly_handoffs}"
)

# --- JobAssignment decision variable
# `assign_base` for Act 4 (no persistent rule); `assign_priority` for
# Act 5 (with priority constraint). Two Properties because a Problem
# may only own one Property at a time.
JobAssignment.assign_base = model.Property(
    f"{JobAssignment} assign_base {Float:assign_base}"
)
JobAssignment.assign_priority = model.Property(
    f"{JobAssignment} assign_priority {Float:assign_priority}"
)
# Third decision-variable property for Q12 (multi-reasoner: Louvain
# communities feed into MIP). Declared at module load so the typed
# Float surface registers before solve_for() is called.
JobAssignment.assign_balanced = model.Property(
    f"{JobAssignment} assign_balanced {Float:assign_balanced}"
)
# Pre-computed urgency and labour-hour coefficients per JobAssignment.
# These are materialised in the ontology so the prescriptive LP's
# arithmetic operands all live on a single Concept (JobAssignment),
# which avoids a known cross-Concept arithmetic rewrite bug in the
# prescriptive reasoner's rewriter.
JobAssignment.urgency = model.Property(
    f"{JobAssignment} urgency {Float:urgency}"
)
JobAssignment.labour_hours = model.Property(
    f"{JobAssignment} labour_hours {Float:labour_hours}"
)
JobAssignment.week_index = model.Property(
    f"{JobAssignment} week_index {Integer:week_index}"
)


# --- Derived flags
OpenRecall = model.Concept("OpenRecall", extends=[RecallAssignment])
SLABreachedRecall = model.Concept("SLABreachedRecall", extends=[RecallAssignment])
PriorAccident = model.Concept("PriorAccident", extends=[Vehicle])
PriorityVehicle = model.Concept("PriorityVehicle", extends=[Vehicle])


# =============================================================================
# SOURCE TABLES
# =============================================================================
DB = "CARS_DEMO.FLEET"


class Sources:
    supplier   = model.Table(f"{DB}.DIM_SUPPLIER")
    region     = model.Table(f"{DB}.DIM_REGION")
    plant      = model.Table(f"{DB}.DIM_PLANT")
    part       = model.Table(f"{DB}.DIM_PART")
    bom_node   = model.Table(f"{DB}.DIM_BOM_NODE")
    centre     = model.Table(f"{DB}.DIM_SERVICE_CENTRE")
    campaign   = model.Table(f"{DB}.DIM_RECALL_CAMPAIGN")
    owner      = model.Table(f"{DB}.OWNER")
    vehicle    = model.Table(f"{DB}.VEHICLE")
    service    = model.Table(f"{DB}.SERVICE_EVENT")
    bom_member = model.Table(f"{DB}.BOM_MEMBERSHIP")
    recall     = model.Table(f"{DB}.RECALL_ASSIGNMENT")
    capacity   = model.Table(f"{DB}.CENTRE_CAPACITY")
    stock      = model.Table(f"{DB}.PARTS_STOCK")
    handoff    = model.Table(f"{DB}.CENTRE_HANDOFF")


# =============================================================================
# LOAD: dim tables
# =============================================================================
model.define(
    sup := Supplier.new(supplier_id=Sources.supplier.SUPPLIER_ID),
    sup.name(Sources.supplier.NAME),
    sup.tier(Sources.supplier.TIER),
    sup.country(Sources.supplier.COUNTRY),
    sup.specialty(Sources.supplier.SPECIALTY),
    sup.warranty_share_pct(Sources.supplier.WARRANTY_SHARE_PCT),
)

model.define(
    rg := Region.new(region_code=Sources.region.REGION_CODE),
    rg.name(Sources.region.NAME),
    rg.rollup(Sources.region.ROLLUP),
    rg.country_codes(Sources.region.COUNTRY_CODES),
)

model.define(
    pl := Plant.new(plant_code=Sources.plant.PLANT_CODE),
    pl.name(Sources.plant.NAME),
    pl.country(Sources.plant.COUNTRY),
    pl.weekly_output(Sources.plant.WEEKLY_OUTPUT),
)
# Plant.region FK bound separately so a NULL doesn't drop the row.
model.define(
    Plant.filter_by(plant_code=Sources.plant.PLANT_CODE).region(
        Region.filter_by(region_code=Sources.plant.REGION_CODE)
    )
)

model.define(
    pt := Part.new(part_id=Sources.part.PART_ID),
    pt.name(Sources.part.NAME),
    pt.category(Sources.part.CATEGORY),
    pt.unit_cost_usd(Sources.part.UNIT_COST_USD),
)
model.define(
    Part.filter_by(part_id=Sources.part.PART_ID).supplier(
        Supplier.filter_by(supplier_id=Sources.part.SUPPLIER_ID)
    )
)

model.define(
    bn := BomNode.new(bom_id=Sources.bom_node.BOM_ID),
    bn.description(Sources.bom_node.DESCRIPTION),
    bn.applies_to_model_codes(Sources.bom_node.APPLIES_TO_MODEL_CODES),
    bn.applies_to_plants(Sources.bom_node.APPLIES_TO_PLANTS),
    bn.applies_from(Sources.bom_node.APPLIES_FROM),
    bn.applies_to(Sources.bom_node.APPLIES_TO),
)
model.define(
    BomNode.filter_by(bom_id=Sources.bom_node.BOM_ID).part(
        Part.filter_by(part_id=Sources.bom_node.PART_ID)
    )
)

model.define(
    sc := ServiceCentre.new(centre_id=Sources.centre.CENTRE_ID),
    sc.name(Sources.centre.NAME),
    sc.country(Sources.centre.COUNTRY),
    sc.hv_certified(Sources.centre.HV_CERTIFIED),
    sc.ibs_certified(Sources.centre.IBS_CERTIFIED),
    sc.body_shop(Sources.centre.BODY_SHOP),
    sc.weekly_tech_hours(Sources.centre.WEEKLY_TECH_HOURS),
    sc.has_egr_tooling(Sources.centre.HAS_EGR_TOOLING),
)
model.define(
    ServiceCentre.filter_by(centre_id=Sources.centre.CENTRE_ID).region(
        Region.filter_by(region_code=Sources.centre.REGION_CODE)
    )
)

model.define(
    cmp := RecallCampaign.new(campaign_id=Sources.campaign.CAMPAIGN_ID),
    cmp.name(Sources.campaign.NAME),
    cmp.severity_code(Sources.campaign.SEVERITY_CODE),
    cmp.completion_days(Sources.campaign.COMPLETION_DAYS),
    cmp.announced_on(Sources.campaign.ANNOUNCED_ON),
    cmp.requires_hv_cert(Sources.campaign.REQUIRES_HV_CERT),
    cmp.requires_ibs_cert(Sources.campaign.REQUIRES_IBS_CERT),
    cmp.requires_body_shop(Sources.campaign.REQUIRES_BODY_SHOP),
    cmp.typical_labour_hours(Sources.campaign.TYPICAL_LABOUR_HOURS),
    cmp.description(Sources.campaign.DESCRIPTION),
)
model.define(
    RecallCampaign.filter_by(campaign_id=Sources.campaign.CAMPAIGN_ID).supplier(
        Supplier.filter_by(supplier_id=Sources.campaign.SUPPLIER_ID)
    )
)
model.define(
    RecallCampaign.filter_by(campaign_id=Sources.campaign.CAMPAIGN_ID).primary_part(
        Part.filter_by(part_id=Sources.campaign.PRIMARY_PART_ID)
    )
)

# =============================================================================
# LOAD: Owner, Vehicle, ServiceEvent
# =============================================================================
model.define(
    ow := Owner.new(owner_id=Sources.owner.OWNER_ID),
    ow.masked_name(Sources.owner.MASKED_NAME),
    ow.country(Sources.owner.COUNTRY),
    ow.distance_km(Sources.owner.DISTANCE_KM),
    ow.prior_accident_history(Sources.owner.PRIOR_ACCIDENT_HISTORY),
)
model.define(
    Owner.filter_by(owner_id=Sources.owner.OWNER_ID).region(
        Region.filter_by(region_code=Sources.owner.REGION_CODE)
    )
)
model.define(
    Owner.filter_by(owner_id=Sources.owner.OWNER_ID).nearest_centre(
        ServiceCentre.filter_by(centre_id=Sources.owner.NEAREST_CENTRE_ID)
    )
)

# Vehicle: core columns
model.define(
    v := Vehicle.new(vin=Sources.vehicle.VIN),
    v.serial_number(Sources.vehicle.SERIAL_NUMBER),
    v.model(Sources.vehicle.MODEL),
    v.factory(Sources.vehicle.FACTORY),
    v.engine_type(Sources.vehicle.ENGINE_TYPE),
    v.fuel_type(Sources.vehicle.FUEL_TYPE),
    v.transmission(Sources.vehicle.TRANSMISSION),
    v.chassis_number(Sources.vehicle.CHASSIS_NUMBER),
    v.emission_standard(Sources.vehicle.EMISSION_STANDARD),
    v.mileage(Sources.vehicle.MILEAGE),
    v.recall_status_raw(Sources.vehicle.RECALL_STATUS_RAW),
    v.previous_owners(Sources.vehicle.PREVIOUS_OWNERS),
    v.power_output_kw(Sources.vehicle.POWER_OUTPUT_KW),
    v.power_output_ps(Sources.vehicle.POWER_OUTPUT_PS),
    v.distance_to_nearest_centre_km(Sources.vehicle.DISTANCE_TO_NEAREST_CENTRE_KM),
    v.owner_country(Sources.vehicle.OWNER_COUNTRY),
)
# Date / nullable / FK columns bound separately to tolerate NULLs.
for _col in (
    "production_date",
    "delivery_date",
    "first_registration_date",
    "accident_date",
    "accident_type",
    "fuel_consumption",
    "repair_cost",
    "service_records",
):
    model.define(
        getattr(
            Vehicle.filter_by(vin=Sources.vehicle.VIN), _col
        )(getattr(Sources.vehicle, _col.upper()))
    )
del _col
model.define(
    Vehicle.filter_by(vin=Sources.vehicle.VIN).owner(
        Owner.filter_by(owner_id=Sources.vehicle.OWNER_ID)
    )
)
model.define(
    Vehicle.filter_by(vin=Sources.vehicle.VIN).region(
        Region.filter_by(region_code=Sources.vehicle.REGION_CODE)
    )
)
model.define(
    Vehicle.filter_by(vin=Sources.vehicle.VIN).nearest_centre(
        ServiceCentre.filter_by(centre_id=Sources.vehicle.NEAREST_CENTRE_ID)
    )
)

# ServiceEvent
model.define(
    se := ServiceEvent.new(service_event_id=Sources.service.SERVICE_EVENT_ID),
    se.service_date(Sources.service.SERVICE_DATE),
    se.service_type(Sources.service.SERVICE_TYPE),
    se.service_centre(Sources.service.SERVICE_CENTRE),
    se.service_cost(Sources.service.SERVICE_COST),
    se.warranty(Sources.service.WARRANTY),
    se.notes(Sources.service.NOTES),
)
model.define(
    ServiceEvent.filter_by(service_event_id=Sources.service.SERVICE_EVENT_ID).vehicle(
        Vehicle.filter_by(vin=Sources.service.VIN)
    )
)

# =============================================================================
# LOAD: BOM membership edges
# =============================================================================
# Bind the in_bom relationship from the bom_membership junction.
_v_bom = Vehicle.ref()
_b_bom = BomNode.ref()
model.where(
    _v_bom.vin == Sources.bom_member.VIN,
    _b_bom.bom_id == Sources.bom_member.BOM_ID,
).define(in_bom(_v_bom, _b_bom))


# =============================================================================
# LOAD: RecallAssignment
# =============================================================================
model.define(
    ra := RecallAssignment.new(recall_id=Sources.recall.RECALL_ID),
    ra.status(Sources.recall.STATUS),
    ra.announced_on(Sources.recall.ANNOUNCED_ON),
    ra.notified_on(Sources.recall.NOTIFIED_ON),
    ra.age_days_at_demo(Sources.recall.AGE_DAYS_AT_DEMO),
    ra.mileage_at_assign(Sources.recall.MILEAGE_AT_ASSIGN),
    ra.sla_breached(Sources.recall.SLA_BREACHED),
)
model.define(
    RecallAssignment.filter_by(recall_id=Sources.recall.RECALL_ID).closed_on(
        Sources.recall.CLOSED_ON
    )
)
model.define(
    RecallAssignment.filter_by(recall_id=Sources.recall.RECALL_ID).vehicle(
        Vehicle.filter_by(vin=Sources.recall.VIN)
    )
)
model.define(
    RecallAssignment.filter_by(recall_id=Sources.recall.RECALL_ID).campaign(
        RecallCampaign.filter_by(campaign_id=Sources.recall.CAMPAIGN_ID)
    )
)


# =============================================================================
# LOAD: Week (1..4 planning horizon)
# =============================================================================
# Create 4 Week rows. They are referenced by CentreCapacity, PartsStock,
# JobAssignment. Loaded via plain Python (no source table needed).
for _w in (1, 2, 3, 4):
    model.define(
        Week.new(week_index=_w),
        Week.filter_by(week_index=_w).week_label(f"week_{_w}"),
    )
del _w


# =============================================================================
# LOAD: CentreCapacity
# =============================================================================
_cc_centre = ServiceCentre.ref()
_cc_week = Week.ref()
model.where(
    _cc_centre.centre_id == Sources.capacity.CENTRE_ID,
    _cc_week.week_index == Sources.capacity.WEEK_INDEX,
).define(
    cc := CentreCapacity.new(centre=_cc_centre, week=_cc_week),
    cc.tech_hours_available(Sources.capacity.TECH_HOURS_AVAILABLE),
)


# =============================================================================
# LOAD: PartsStock
# =============================================================================
_ps_centre = ServiceCentre.ref()
_ps_camp = RecallCampaign.ref()
_ps_week = Week.ref()
model.where(
    _ps_centre.centre_id == Sources.stock.CENTRE_ID,
    _ps_camp.campaign_id == Sources.stock.CAMPAIGN_ID,
    _ps_week.week_index == Sources.stock.WEEK_INDEX,
).define(
    ps := PartsStock.new(centre=_ps_centre, campaign=_ps_camp, week=_ps_week),
    ps.on_hand_units(Sources.stock.ON_HAND_UNITS),
)


# =============================================================================
# LOAD: CentreHandoff (3-way ternary)
# =============================================================================
_h_from = ServiceCentre.ref()
_h_to = ServiceCentre.ref()
_h_camp = RecallCampaign.ref()
model.where(
    _h_from.centre_id == Sources.handoff.FROM_CENTRE_ID,
    _h_to.centre_id == Sources.handoff.TO_CENTRE_ID,
    _h_camp.campaign_id == Sources.handoff.CAMPAIGN_ID,
).define(
    ho := CentreHandoff.new(from_centre=_h_from, to_centre=_h_to, campaign=_h_camp),
    ho.monthly_handoffs(Sources.handoff.MONTHLY_HANDOFFS),
)

# Adapter: N-arity edge for Pathfinder. Per the rai-pathfinder skill
# (Adapter Pattern A), declaring an explicit ternary relationship
# `ServiceCentre.refers_for(from, CentreHandoff, to)` lets path() walk
# centre-to-centre while preserving the campaign as auxiliary middle
# field accessible via PathTraversal.relationship_fields.
ServiceCentre.refers_for = model.Relationship(
    f"{ServiceCentre:from_centre} refers (via {CentreHandoff:via}) to {ServiceCentre:to_centre}",
    short_name="refers_for",
)
_rf_from = ServiceCentre.ref()
_rf_via = CentreHandoff.ref()
_rf_to = ServiceCentre.ref()
model.where(
    _rf_via.from_centre == _rf_from,
    _rf_via.to_centre == _rf_to,
).define(ServiceCentre.refers_for(_rf_from, _rf_via, _rf_to))


# =============================================================================
# DERIVED RULES
# =============================================================================

# OpenRecall: status == 'Open'.
model.where(RecallAssignment.status == "Open").define(OpenRecall(RecallAssignment))

# SLABreached: also re-derived by PyRel (matches the pre-computed
# sla_breached column from the data layer). Open + age > completion_days +
# severity <= 2. The pre-computed column gives SQL audits the same result;
# the derived rule lives in the ontology so it propagates to other
# reasoners and to the persistent-rule act.
model.where(
    OpenRecall(RecallAssignment),
    RecallAssignment.campaign == RecallCampaign,
    RecallAssignment.age_days_at_demo > RecallCampaign.completion_days,
    RecallCampaign.severity_code <= 2,
).define(SLABreachedRecall(RecallAssignment))

# PriorAccident: a vehicle with any non-empty accident_type. The seed
# stores accident_type as nullable; presence of the property is enough.
model.where(Vehicle.accident_type).define(PriorAccident(Vehicle))

# accident_severity score: Minor / Vandalism = 1, Rear-end / Collision = 2,
# otherwise 0 (no accident on file -> no row for this property).
model.where(Vehicle.accident_type == "Minor").define(Vehicle.accident_severity(1))
model.where(Vehicle.accident_type == "Vandalism").define(Vehicle.accident_severity(1))
model.where(Vehicle.accident_type == "Rear-end").define(Vehicle.accident_severity(2))
model.where(Vehicle.accident_type == "Collision").define(Vehicle.accident_severity(2))

# PriorityVehicle: a vehicle with at least one Open recall AND a prior
# accident. This is the concept that the Act 5 persistent rule
# decorates: when the operator adds the rule "prioritise prior-accident
# VINs", the LP attaches a constraint to JobAssignment rows whose
# recall.vehicle is a PriorityVehicle.
_pv_v = Vehicle.ref()
_pv_r = RecallAssignment.ref()
model.where(
    OpenRecall(_pv_r),
    _pv_r.vehicle == _pv_v,
    PriorAccident(_pv_v),
).define(PriorityVehicle(_pv_v))

# RecallAssignment.priority_flag: an Integer (0/1) flag on each
# RecallAssignment indicating whether the underlying vehicle is a
# priority case (open recall + prior accident). Lives as a Property
# on RecallAssignment so the prescriptive constraint can filter on a
# single Property predicate without tripping the multi-ref rewriter
# bug.
RecallAssignment.priority_flag = model.Property(
    f"{RecallAssignment} priority_flag {Integer:priority_flag}"
)

_pf_r = RecallAssignment.ref()
_pf_v = Vehicle.ref()
model.where(
    _pf_r.status == "Open",
    _pf_r.vehicle == _pf_v,
    _pf_v.accident_type,
).define(_pf_r.priority_flag(1))
# Open recalls without a prior-accident vehicle - explicit 0 so the
# Property is total over OpenRecalls (the LP filter is `== 1`).
_pf_r2 = RecallAssignment.ref()
_pf_v2 = Vehicle.ref()
model.where(
    _pf_r2.status == "Open",
    _pf_r2.vehicle == _pf_v2,
    model.not_(_pf_v2.accident_type),
).define(_pf_r2.priority_flag(0))

# urgency_score: deterministic Act 3 heuristic. Weights:
#   0.30 * mileage / 250000      (utilisation proxy, ~250k km cap)
#   0.25 * notification_age_days / 730 (calendar-time proxy, ~2y cap)
#   0.30 * accident_severity / 2 (0..1 normalised, when present)
#   0.15 * distance_km / 250     (logistics, ~250 km cap)
# Bound as a derived Property on RecallAssignment.
RecallAssignment.urgency = model.Property(
    f"{RecallAssignment} urgency {Float:urgency}"
)

# Score with accident component (when accident_severity exists)
_uv = Vehicle.ref()
_ur = RecallAssignment.ref()
model.where(
    OpenRecall(_ur),
    _ur.vehicle == _uv,
    _uv.accident_severity,
).define(
    _ur.urgency(
        0.30 * (_uv.mileage * 1.0 / 250000.0)
        + 0.25 * (_ur.age_days_at_demo * 1.0 / 730.0)
        + 0.30 * (_uv.accident_severity * 1.0 / 2.0)
        + 0.15 * (_uv.distance_to_nearest_centre_km * 1.0 / 250.0)
    )
)

# Score for vehicles without an accident_severity row (no accident).
_uv2 = Vehicle.ref()
_ur2 = RecallAssignment.ref()
model.where(
    OpenRecall(_ur2),
    _ur2.vehicle == _uv2,
    model.not_(_uv2.accident_severity),
).define(
    _ur2.urgency(
        0.30 * (_uv2.mileage * 1.0 / 250000.0)
        + 0.25 * (_ur2.age_days_at_demo * 1.0 / 730.0)
        + 0.15 * (_uv2.distance_to_nearest_centre_km * 1.0 / 250.0)
    )
)


# =============================================================================
# LOAD: JobAssignment scaffolding
# =============================================================================
# Build one JobAssignment row per (OpenRecall, ServiceCentre, Week)
# triple where the centre has the required tooling certification.
# This makes the assignment grid feasibility-pre-filtered: the LP
# decides which to set to 1, not which to enumerate.
#
# Filter rules (PyRel-expressed eligibility - tooling certification):
#   - campaign.requires_hv_cert -> centre.hv_certified
#   - campaign.requires_ibs_cert -> centre.ibs_certified
#   - campaign.requires_body_shop -> centre.body_shop
_ja_r = RecallAssignment.ref()
_ja_c = ServiceCentre.ref()
_ja_w = Week.ref()
_ja_cmp = RecallCampaign.ref()

# Generic eligibility: any OpenRecall x (Centre that satisfies cert) x Week.
# We define one rule per cert-combination to keep the constraint logic
# readable. PyRel's `model.union()` collects all branches as a set OR.
# Generic case: no cert required.
model.where(
    OpenRecall(_ja_r),
    _ja_r.campaign == _ja_cmp,
    _ja_cmp.requires_hv_cert == False,
    _ja_cmp.requires_ibs_cert == False,
    _ja_cmp.requires_body_shop == False,
    _ja_c, _ja_w,
).define(JobAssignment.new(recall=_ja_r, centre=_ja_c, week=_ja_w))

# HV-only requirement
model.where(
    OpenRecall(_ja_r),
    _ja_r.campaign == _ja_cmp,
    _ja_cmp.requires_hv_cert == True,
    _ja_c.hv_certified == True,
    _ja_w,
).define(JobAssignment.new(recall=_ja_r, centre=_ja_c, week=_ja_w))

# IBS-only requirement
model.where(
    OpenRecall(_ja_r),
    _ja_r.campaign == _ja_cmp,
    _ja_cmp.requires_ibs_cert == True,
    _ja_c.ibs_certified == True,
    _ja_w,
).define(JobAssignment.new(recall=_ja_r, centre=_ja_c, week=_ja_w))

# Body-shop requirement
model.where(
    OpenRecall(_ja_r),
    _ja_r.campaign == _ja_cmp,
    _ja_cmp.requires_body_shop == True,
    _ja_c.body_shop == True,
    _ja_w,
).define(JobAssignment.new(recall=_ja_r, centre=_ja_c, week=_ja_w))


# Materialise coefficients on JobAssignment so the LP can do
# single-Concept arithmetic without the multi-Concept rewriter bug
# (the prescriptive rewriter chokes on
# `assign * OtherConcept.property` when OtherConcept is bound only
# via the aggregate's inner where).
_mj = JobAssignment.ref()
_mr = RecallAssignment.ref()
_mc = RecallCampaign.ref()
_mw = Week.ref()
model.where(
    _mj.recall == _mr,
    _mr.campaign == _mc,
).define(_mj.labour_hours(_mc.typical_labour_hours))
model.where(
    _mj.recall == _mr,
    _mr.urgency,
).define(_mj.urgency(_mr.urgency))
model.where(
    _mj.week == _mw,
).define(_mj.week_index(_mw.week_index))


# =============================================================================
# DRIVER (validates loads, prints counts)
# =============================================================================
def main():
    print("=== concept counts ===")
    concepts = [
        ("Supplier", Supplier),
        ("Region", Region),
        ("Plant", Plant),
        ("Part", Part),
        ("BomNode", BomNode),
        ("ServiceCentre", ServiceCentre),
        ("RecallCampaign", RecallCampaign),
        ("Owner", Owner),
        ("Vehicle", Vehicle),
        ("ServiceEvent", ServiceEvent),
        ("RecallAssignment", RecallAssignment),
        ("Week", Week),
        ("CentreCapacity", CentreCapacity),
        ("PartsStock", PartsStock),
        ("JobAssignment", JobAssignment),
    ]
    for name, c in concepts:
        df = model.where(c).select(aggs.count(c).alias(name)).to_df()
        n = int(df[name].iloc[0]) if not df.empty else 0
        print(f"  {name:18s} {n}")

    print("\n=== derived flags ===")
    for label, rel in (
        ("open_recalls", OpenRecall),
        ("sla_breached_recalls", SLABreachedRecall),
        ("prior_accident_vehicles", PriorAccident),
        ("priority_vehicles", PriorityVehicle),
    ):
        df = (
            model.where(rel)
            .select(aggs.count(rel).alias(label))
            .to_df()
        )
        n = int(df[label].iloc[0]) if not df.empty else 0
        print(f"  {label:24s} {n}")

    print("\n=== BOM membership (in_bom) edges ===")
    _v_e = Vehicle.ref()
    _b_e = BomNode.ref()
    df = (
        model.where(in_bom(_v_e, _b_e))
        .select(aggs.count(_v_e).alias("edges"))
        .to_df()
    )
    print(f"  total: {int(df['edges'].iloc[0]) if not df.empty else 0}")


if __name__ == "__main__":
    main()
