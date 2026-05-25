#!/usr/bin/env python3
"""
CARS_DEMO synthetic data generator
==================================

Builds the recall-propagation demo dataset on top of the two BMW seed
CSVs in `data/seed/`. The seed provides 325 VINs and 762 service events
that stay real (BMW WMIs, BMW model designators, BMW service-centre
names). Everything else - suppliers, parts, bill-of-materials, recall
campaigns, recall assignments, owners, parts-stock-by-week,
centre-capacity-by-week, centre tooling certifications - is synthesised
deterministically (seed=42) so the talk-track anchored numbers reproduce
exactly.

The demo is notionalised at the wrapper layer (Snowflake database
CARS_DEMO, role RAI_DEMO_CARS, agent name "cars"). The data inside the
tables stays BMW-realistic because the audience are BMW industry
experts. See BRIEF.md > "Naming convention" for the split.

Outputs (written to `data/out/`):
  - cars_demo_ddl.sql             Snowflake DDL: schema + tables
  - cars_demo_reference.sql       INSERT for dim tables (suppliers,
                                  parts, BOM nodes, campaigns, centres,
                                  capacity, parts-stock)
  - cars_demo_vehicles.csv        Vehicles passed through from seed,
                                  with synthetic columns appended
                                  (owner_id, region, distance_km).
  - cars_demo_services.csv        Service events passed through.
  - cars_demo_owners.csv          Synthetic owner records (~250 unique).
  - cars_demo_recall.csv          Generated recall_assignment rows
                                  (~700 total, ~270 Open).
  - cars_demo_bom.csv             vehicle x bom_node membership edges
                                  (~16k rows).
  - cars_demo_load.sql            COPY INTO orchestration.
  - cars_demo_validation.sql      Talk-track anchored-number queries.

Curated narrative entities (hard-coded so the talk track returns the
right rows):

  - Campaign IBS-2024-A: Continental MK C1 brake-booster firmware
    v2.3.1, severity Code 2, 180-day completion window. Affects:
    G21 LCI 3 Series + G87 M2 + G26 i4 + iX1 (U11 LCI) from Munich,
    Regensburg, and Spartanburg, built Q1-Q3 2024. ~80 affected VINs
    across three plant-date cohorts. This is the Act 2 cascade seed.

  - Campaign HVB-2024-A: Samsung SDI HV battery module thermal,
    severity Code 1, 60-day completion window. Affects: iX M60 and
    i7 M70 from Dingolfing, built Q4 2023 - Q1 2024. ~40 VINs.

  - Campaign EGR-2023-B: BorgWarner EGR cooler crack, severity
    Code 2, 180-day window. Affects: diesel powertrain only - small
    campaign, 1-3 VINs in our seed.

  - Campaign AIRBAG-2022-A: legacy Takata-style inflator
    (carry-over PSAN degradation), severity Code 1, 90-day window.
    Affects: 2019-2020 vintage 3 Series.

  - Campaign STARTER-2024-A: Bosch starter motor water intrusion,
    severity Code 2, 120-day window. Affects: X1 M35i (U11) from
    Regensburg.

Author: Claude (auto), 2026-05-25
"""

from __future__ import annotations
import csv
import os
import random
import sys
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta, date
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# 0. Configuration
# ---------------------------------------------------------------------------

DEMO_DATE = date(2026, 5, 25)
DEMO_NOW = datetime(2026, 5, 25, 9, 30)
SEED = int(os.environ.get("CARS_DEMO_SEED", "42"))

HERE = Path(__file__).parent
SEED_DIR = HERE / "seed"
OUT_DIR = HERE / "out"
OUT_DIR.mkdir(exist_ok=True)

DB_NAME = "CARS_DEMO"
SCHEMA_NAME = "FLEET"
FQN = f"{DB_NAME}.{SCHEMA_NAME}"


# ---------------------------------------------------------------------------
# 1. Reference data: suppliers, regions, plants
# ---------------------------------------------------------------------------

@dataclass
class Supplier:
    supplier_id: str
    name: str
    tier: int
    country: str
    specialty: str
    warranty_share_pct: int  # supplier reimburses this % of warranty cost

SUPPLIERS: list[Supplier] = [
    Supplier("SUP-CONT", "Continental AG",       1, "DE", "Brake systems and ADAS", 80),
    Supplier("SUP-BOSCH","Robert Bosch GmbH",    1, "DE", "Powertrain electronics and HPFP", 75),
    Supplier("SUP-ZF",   "ZF Friedrichshafen AG",1, "DE", "Transmissions and chassis", 70),
    Supplier("SUP-SSDI", "Samsung SDI",          1, "KR", "HV battery cells and modules", 65),
    Supplier("SUP-MAGNA","Magna International",  1, "CA", "Body and seating", 65),
    Supplier("SUP-FAUR", "Forvia (Faurecia)",    1, "FR", "Seating and interiors", 60),
    Supplier("SUP-HELLA","Hella GmbH",           1, "DE", "Lighting and electronics", 60),
    Supplier("SUP-BREMBO","Brembo S.p.A.",       1, "IT", "Performance braking", 70),
    Supplier("SUP-BORG", "BorgWarner Inc.",      1, "US", "Turbochargers and EGR", 75),
    Supplier("SUP-AISIN","Aisin Corp.",          1, "JP", "Automatic transmissions", 60),
    Supplier("SUP-TAK",  "Joyson Safety (Takata legacy)", 1, "JP", "Restraint systems", 90),
]
SUPPLIER_BY_ID = {s.supplier_id: s for s in SUPPLIERS}


@dataclass
class Region:
    region_code: str
    name: str
    rollup: str  # EU / NA / LATAM
    country_codes: tuple[str, ...]

REGIONS: list[Region] = [
    Region("EU-DE",  "Germany",        "EU", ("DE",)),
    Region("EU-WE",  "Western Europe", "EU", ("FR", "NL", "BE", "AT", "CH", "IT", "ES")),
    Region("EU-NE",  "Northern Europe","EU", ("DK", "SE", "NO", "FI", "IE", "GB")),
    Region("US-WEST","US West",        "NA", ("US-CA", "US-WA", "US-OR")),
    Region("US-EAST","US East",        "NA", ("US-NY", "US-FL", "US-MA", "US-GA")),
    Region("US-CTRL","US Central",     "NA", ("US-IL", "US-TX", "US-SC")),
    Region("MX",     "Mexico",         "LATAM", ("MX",)),
]


@dataclass
class Plant:
    plant_code: str   # single-letter VIN position 11 code per BMW convention
    name: str
    country: str
    region_code: str
    weekly_output: int

PLANTS: list[Plant] = [
    Plant("D", "Dingolfing",      "DE",    "EU-DE",   8500),
    Plant("M", "Munich",          "DE",    "EU-DE",   3500),
    Plant("R", "Regensburg",      "DE",    "EU-DE",   6000),
    Plant("K", "Spartanburg",     "US-SC", "US-CTRL", 6000),
    Plant("B", "Leipzig",         "DE",    "EU-DE",   3500),
    Plant("T", "San Luis Potosi", "MX",    "MX",      3500),
]
PLANT_BY_NAME = {p.name: p for p in PLANTS}


# ---------------------------------------------------------------------------
# 2. Service centres: enriched from the seed CSV with capacity + tooling
# ---------------------------------------------------------------------------

@dataclass
class ServiceCentre:
    centre_id: str
    name: str
    country: str
    region_code: str
    hv_certified: bool       # high-voltage certified for EV battery work
    ibs_certified: bool      # IBS (integrated brake system) trained
    body_shop: bool          # body work for restraint-system recalls
    weekly_tech_hours: int   # capacity per week
    has_egr_tooling: bool    # EGR cooler replacement equipment

# Centre list inferred from BMW_VEHICLES_SERVICES.csv. HV / IBS / body /
# EGR / capacity assigned to make Act 4 land: large EU centres get HV,
# Munich and Spartanburg get IBS + HV (the flagship campaign requires
# both), the smaller centres lack certain certifications which becomes
# the constraint that drives optimization decisions.
SERVICE_CENTRES: list[ServiceCentre] = [
    ServiceCentre("SC-COL", "BMW Cologne Service",     "DE",    "EU-DE",   True,  True,  True,  640, True),
    ServiceCentre("SC-HAM", "BMW Hamburg Service",     "DE",    "EU-DE",   True,  True,  True,  560, True),
    ServiceCentre("SC-MUN", "BMW Munich Service",      "DE",    "EU-DE",   True,  True,  True,  680, True),
    ServiceCentre("SC-STU", "BMW Stuttgart Service",   "DE",    "EU-DE",   True,  True,  False, 520, True),
    ServiceCentre("SC-FRA", "BMW Frankfurt Service",   "DE",    "EU-DE",   True,  True,  True,  560, False),
    ServiceCentre("SC-LEI", "BMW Leipzig Service",     "DE",    "EU-DE",   True,  False, False, 400, True),
    ServiceCentre("SC-REG", "BMW Regensburg Service",  "DE",    "EU-DE",   False, True,  True,  440, True),
    ServiceCentre("SC-BER", "BMW Berlin Service",      "DE",    "EU-DE",   True,  True,  True,  520, False),
    ServiceCentre("SC-DAL", "BMW Dallas Service",      "US-TX", "US-CTRL", True,  True,  True,  480, True),
    ServiceCentre("SC-MIA", "BMW Miami Service",       "US-FL", "US-EAST", True,  True,  True,  460, False),
    ServiceCentre("SC-NYC", "BMW New York Service",    "US-NY", "US-EAST", True,  True,  True,  440, True),
    ServiceCentre("SC-LAX", "BMW Los Angeles Service", "US-CA", "US-WEST", True,  True,  True,  440, False),
    ServiceCentre("SC-SPB", "BMW Spartanburg Service", "US-SC", "US-CTRL", True,  True,  True,  500, True),
    ServiceCentre("SC-CHI", "BMW Chicago Service",     "US-IL", "US-CTRL", True,  True,  False, 380, True),
    ServiceCentre("SC-MTY", "BMW Monterrey Service",   "MX",    "MX",      False, False, False, 280, False),
]
CENTRE_BY_NAME = {c.name: c for c in SERVICE_CENTRES}


# ---------------------------------------------------------------------------
# 3. Parts and bill-of-materials structure
# ---------------------------------------------------------------------------

@dataclass
class Part:
    part_id: str
    supplier_id: str
    name: str
    category: str          # SAFETY / POWERTRAIN / HVBATTERY / RESTRAINT / EMISSIONS / OTHER
    unit_cost_usd: int

@dataclass
class BomNode:
    bom_id: str
    part_id: str
    description: str
    applies_to_model_codes: tuple[str, ...]   # tuple of model designator fragments to match
    applies_to_plants: tuple[str, ...]        # tuple of plant codes
    applies_from: date
    applies_to: date

# Parts. Each campaign's flagship part is listed; secondary BOM parts
# are included so the cascade in Act 2 has depth.
PARTS: list[Part] = [
    # Continental MK C1 family (Act 2 cascade seed)
    Part("PRT-IBS-ECU", "SUP-CONT", "MK C1 booster ECU v2.3.x",       "SAFETY",     920),
    Part("PRT-IBS-VLV", "SUP-CONT", "MK C1 isolation valve assy",     "SAFETY",     410),
    Part("PRT-IBS-WIRE","SUP-CONT", "MK C1 wiring harness",           "SAFETY",     180),
    # Samsung SDI HV battery
    Part("PRT-HVB-MOD", "SUP-SSDI", "Gen5 prismatic cell module 96s", "HVBATTERY", 2400),
    Part("PRT-HVB-BMS", "SUP-SSDI", "HV battery management ECU",      "HVBATTERY", 1100),
    Part("PRT-HVB-CCS", "SUP-SSDI", "Cell-contacting system harness", "HVBATTERY",  520),
    # BorgWarner EGR cooler
    Part("PRT-EGR-COL", "SUP-BORG", "EGR cooler assembly",            "EMISSIONS",  640),
    Part("PRT-EGR-VLV", "SUP-BORG", "EGR diverter valve",             "EMISSIONS",  220),
    # Joyson / Takata legacy airbag
    Part("PRT-AIR-INF", "SUP-TAK",  "Driver-side PSAN inflator",      "RESTRAINT",  340),
    Part("PRT-AIR-MOD", "SUP-TAK",  "Front airbag module",            "RESTRAINT",  680),
    # Bosch starter motor
    Part("PRT-STR-MOT", "SUP-BOSCH","Starter motor 12V LRM",          "POWERTRAIN", 290),
    Part("PRT-STR-SOL", "SUP-BOSCH","Starter solenoid contactor",     "POWERTRAIN",  60),
    # Filler parts (depth in the cascade)
    Part("PRT-ZF-AT8", "SUP-ZF",    "8HP automatic transmission",     "POWERTRAIN",4200),
    Part("PRT-BSH-HPFP","SUP-BOSCH","High-pressure fuel pump HPFP",   "POWERTRAIN", 380),
    Part("PRT-HEL-LED","SUP-HELLA", "LaserLight adaptive headlamp",   "OTHER",      890),
    Part("PRT-BRB-CAL","SUP-BREMBO","M-series 4-piston caliper",      "SAFETY",     520),
    Part("PRT-MAG-SEAT","SUP-MAGNA","Front seat power assembly",      "OTHER",      450),
    Part("PRT-FAU-DASH","SUP-FAUR", "Instrument-panel substructure",  "OTHER",      210),
    Part("PRT-AIS-RD",  "SUP-AISIN","Reduction-drive unit (PHEV)",    "POWERTRAIN", 980),
]
PART_BY_ID = {p.part_id: p for p in PARTS}


def _quarter_dates(year: int, q: int) -> tuple[date, date]:
    starts = {1: date(year, 1, 1), 2: date(year, 4, 1), 3: date(year, 7, 1), 4: date(year, 10, 1)}
    ends = {1: date(year, 3, 31), 2: date(year, 6, 30), 3: date(year, 9, 30), 4: date(year, 12, 31)}
    return starts[q], ends[q]


# BOM nodes connect parts to (model-fragment x plant x date-window) cohorts.
# A vehicle is a member of a BOM node if its MODEL contains the fragment,
# its plant is in the plant list, and its PRODUCTION_DATE falls in the window.
BOM_NODES: list[BomNode] = []

def _bom_for_campaign(prefix: str, part_id: str, descr: str,
                      model_codes: tuple[str, ...], plants: tuple[str, ...],
                      from_d: date, to_d: date, n_nodes: int = 1) -> list[BomNode]:
    # Multiple BOM nodes per part lets the cascade have intermediate
    # structure (e.g., the booster ECU is consumed by a front-axle
    # subassembly node, which is consumed by the model assembly node).
    out = []
    for i in range(n_nodes):
        bid = f"BOM-{prefix}-{i+1:02d}"
        out.append(BomNode(bid, part_id, descr, model_codes, plants, from_d, to_d))
    return out

# IBS campaign BOM (Act 2 seed): MK C1 booster ECU applied to G21 LCI,
# G87, G26, U11 LCI from Munich/Regensburg/Spartanburg/Dingolfing in
# 2023-2024 production windows. Three plant-date cohorts as promised in
# DEMO_QUESTIONS.md.
BOM_NODES.extend(_bom_for_campaign(
    "IBS-MUN", "PRT-IBS-ECU", "Front-axle brake-booster subassembly (Munich line)",
    ("G21", "G26", "M2 (G87"), ("M",),
    date(2022, 1, 1), date(2024, 12, 31),
    n_nodes=1,
))
BOM_NODES.extend(_bom_for_campaign(
    "IBS-REG", "PRT-IBS-ECU", "Front-axle brake-booster subassembly (Regensburg line)",
    ("X1 M35i", "U11", "iX1"), ("R",),
    date(2022, 1, 1), date(2024, 12, 31),
    n_nodes=1,
))
BOM_NODES.extend(_bom_for_campaign(
    "IBS-SPB", "PRT-IBS-ECU", "Front-axle brake-booster subassembly (Spartanburg line)",
    ("X1", "iX1"), ("K",),
    date(2022, 1, 1), date(2024, 12, 31),
    n_nodes=1,
))
# Continental harness as a secondary BOM node feeding the same booster
BOM_NODES.extend(_bom_for_campaign(
    "IBS-WIRE", "PRT-IBS-WIRE", "MK C1 chassis harness",
    ("G21", "G26", "M2 (G87", "X1", "iX1", "U11"),
    ("M", "R", "K"),
    date(2022, 1, 1), date(2024, 12, 31),
    n_nodes=1,
))

# HV battery campaign - widened to cover 2022-2024 Dingolfing EVs.
BOM_NODES.extend(_bom_for_campaign(
    "HVB-DIN", "PRT-HVB-MOD", "Gen5 HV battery pack (Dingolfing high-power line)",
    ("iX M60", "i7 M70"), ("D",),
    date(2022, 1, 1), date(2024, 12, 31),
    n_nodes=1,
))
BOM_NODES.extend(_bom_for_campaign(
    "HVB-BMS", "PRT-HVB-BMS", "HV BMS ECU (Dingolfing)",
    ("iX M60", "i7 M70", "i5"), ("D",),
    date(2022, 1, 1), date(2024, 12, 31),
    n_nodes=1,
))

# EGR campaign (diesel only)
BOM_NODES.extend(_bom_for_campaign(
    "EGR-COL", "PRT-EGR-COL", "EGR cooler subassembly",
    ("X1",), ("R",),                  # the lone diesel in our seed is an X1 from Regensburg
    date(2021, 1, 1), date(2024, 12, 31),
    n_nodes=1,
))

# Airbag legacy campaign - 2019-2021 3 Series vintage
BOM_NODES.extend(_bom_for_campaign(
    "AIR-INF", "PRT-AIR-INF", "Driver-side PSAN inflator (legacy)",
    ("3 Series", "330i", "G20", "G21"), ("M", "T"),
    date(2019, 1, 1), date(2021, 12, 31),
    n_nodes=1,
))

# Starter campaign - X1 M35i from Regensburg 2022-2025
BOM_NODES.extend(_bom_for_campaign(
    "STR-MOT", "PRT-STR-MOT", "Starter motor 12V LRM (X1 line)",
    ("X1 M35i", "U11"), ("R",),
    date(2022, 1, 1), date(2025, 12, 31),
    n_nodes=1,
))

# Filler BOM (gives the cascade fan-out)
BOM_NODES.extend(_bom_for_campaign(
    "ZF-AT8", "PRT-ZF-AT8", "ZF 8HP transmission",
    ("3 Series", "M2", "X1 M35i", "iX M60", "i7 M70"),
    ("D", "M", "R", "K"),
    date(2020, 1, 1), date(2025, 12, 31),
    n_nodes=1,
))
BOM_NODES.extend(_bom_for_campaign(
    "HEL-LED", "PRT-HEL-LED", "Adaptive LED headlamp",
    ("i7", "iX", "i5"), ("D",),
    date(2022, 1, 1), date(2025, 12, 31),
    n_nodes=1,
))

BOM_BY_ID = {b.bom_id: b for b in BOM_NODES}


# ---------------------------------------------------------------------------
# 4. Recall campaigns
# ---------------------------------------------------------------------------

@dataclass
class Campaign:
    campaign_id: str
    name: str
    supplier_id: str
    primary_part_id: str
    severity_code: int            # 1 = stop driving, 2 = repair urgently, 3 = scheduled
    completion_days: int          # SLA window from announcement
    announced_on: date
    requires_hv_cert: bool
    requires_ibs_cert: bool
    requires_body_shop: bool
    typical_labour_hours: float   # avg flat-rate hours per job
    description: str

CAMPAIGNS: list[Campaign] = [
    Campaign(
        "IBS-2024-A",
        "Continental MK C1 brake-booster firmware v2.3.1",
        "SUP-CONT", "PRT-IBS-ECU",
        severity_code=2,
        completion_days=180,
        announced_on=date(2025, 11, 15),    # 192 days before DEMO_DATE - just past SLA for ~25% of Opens
        requires_hv_cert=False,
        requires_ibs_cert=True,
        requires_body_shop=False,
        typical_labour_hours=2.5,
        description="Firmware revision in the integrated brake-system booster ECU. Defect: transient loss of regenerative blending under aggressive braking can trigger ABS reset. Remedy: dealer reflash and harness inspection.",
    ),
    Campaign(
        "HVB-2024-A",
        "Samsung SDI HV battery module thermal risk",
        "SUP-SSDI", "PRT-HVB-MOD",
        severity_code=1,
        completion_days=60,
        announced_on=date(2026, 3, 15),     # 71 days before DEMO_DATE - just past SLA for laggards
        requires_hv_cert=True,
        requires_ibs_cert=False,
        requires_body_shop=False,
        typical_labour_hours=8.0,
        description="Cell-internal contamination identified in a manufacturing lot at Samsung SDI. Risk of thermal runaway under high state-of-charge. Remedy: module swap, full pack diagnostic, BMS reflash.",
    ),
    Campaign(
        "EGR-2023-B",
        "BorgWarner EGR cooler crack risk",
        "SUP-BORG", "PRT-EGR-COL",
        severity_code=2,
        completion_days=180,
        announced_on=date(2025, 11, 1),
        requires_hv_cert=False,
        requires_ibs_cert=False,
        requires_body_shop=False,
        typical_labour_hours=5.0,
        description="EGR cooler thermal-fatigue cracking can leak coolant into the intake. Remedy: cooler replacement and intake decontamination.",
    ),
    Campaign(
        "AIRBAG-2022-A",
        "Joyson PSAN inflator carry-over recall",
        "SUP-TAK", "PRT-AIR-INF",
        severity_code=1,
        completion_days=90,
        announced_on=date(2026, 2, 1),
        requires_hv_cert=False,
        requires_ibs_cert=False,
        requires_body_shop=True,
        typical_labour_hours=1.5,
        description="Ammonium-nitrate propellant degradation over time. Carry-over campaign from the original Takata wave; expanded scope to additional vintages. Remedy: driver-side inflator replacement.",
    ),
    Campaign(
        "STARTER-2024-A",
        "Bosch starter motor water-intrusion risk",
        "SUP-BOSCH", "PRT-STR-MOT",
        severity_code=2,
        completion_days=120,
        announced_on=date(2026, 2, 20),     # 94 days before DEMO_DATE - few laggards breach
        requires_hv_cert=False,
        requires_ibs_cert=False,
        requires_body_shop=False,
        typical_labour_hours=3.0,
        description="Water ingress at the starter motor contact plate can cause shorting and, in rare cases, smouldering. Remedy: starter motor replacement and sealing kit.",
    ),
]
CAMPAIGN_BY_ID = {c.campaign_id: c for c in CAMPAIGNS}

# Mapping campaign -> the BOM-node prefix(es) whose member VINs are
# affected. Used to compute recall_assignment rows.
CAMPAIGN_BOM_PREFIXES: dict[str, tuple[str, ...]] = {
    "IBS-2024-A":      ("BOM-IBS-MUN", "BOM-IBS-REG", "BOM-IBS-SPB"),
    "HVB-2024-A":      ("BOM-HVB-DIN", "BOM-HVB-BMS"),
    "EGR-2023-B":      ("BOM-EGR-COL",),
    "AIRBAG-2022-A":   ("BOM-AIR-INF",),
    "STARTER-2024-A":  ("BOM-STR-MOT",),
}


# ---------------------------------------------------------------------------
# 5. Read seed CSVs
# ---------------------------------------------------------------------------

def _read_csv(path: Path) -> list[dict]:
    with open(path) as f:
        return list(csv.DictReader(f))

VEHICLES_RAW = _read_csv(SEED_DIR / "BMW_VEHICLES_V1.csv")
SERVICES_RAW = _read_csv(SEED_DIR / "BMW_VEHICLES_SERVICES.csv")


# ---------------------------------------------------------------------------
# 6. Synthesise owner and vehicle-region assignments
# ---------------------------------------------------------------------------

@dataclass
class Owner:
    owner_id: str
    masked_name: str
    region_code: str
    country: str
    nearest_centre_id: str
    distance_km: int
    prior_accident_history: bool

# We have 325 VINs. Pretend ~85% have a single registered owner, ~15%
# fleet ownership shared across multiple VINs.
OWNER_SHARE_PROB = 0.15

def _bom_member_vehicles(vehicles: list[dict]) -> dict[str, set[str]]:
    """For each BOM node, which VINs are members? (model fragment match,
    plant match, production-date in window.)"""
    out: dict[str, set[str]] = {}
    for b in BOM_NODES:
        members: set[str] = set()
        for v in vehicles:
            model = v["MODEL"]
            plant_name = v["FACTORY_PRODUCTION_LOCATION"]
            plant = PLANT_BY_NAME.get(plant_name)
            if plant is None or plant.plant_code not in b.applies_to_plants:
                continue
            if not any(frag in model for frag in b.applies_to_model_codes):
                continue
            try:
                prod = datetime.strptime(v["PRODUCTION_DATE"], "%Y-%m-%d").date()
            except ValueError:
                continue
            if not (b.applies_from <= prod <= b.applies_to):
                continue
            members.add(v["VIN"])
        out[b.bom_id] = members
    return out


def _campaign_affected(bom_membership: dict[str, set[str]]) -> dict[str, set[str]]:
    out: dict[str, set[str]] = {}
    for cid, prefixes in CAMPAIGN_BOM_PREFIXES.items():
        affected: set[str] = set()
        for bid, members in bom_membership.items():
            if any(bid.startswith(p) for p in prefixes):
                affected.update(members)
        out[cid] = affected
    return out


# ---------------------------------------------------------------------------
# 7. Build owners and enrich vehicles
# ---------------------------------------------------------------------------

def _build_owners_and_vehicle_enrich(rng: random.Random,
                                     vehicles: list[dict]) -> tuple[list[Owner], list[dict]]:
    centres_by_country = {}
    for c in SERVICE_CENTRES:
        centres_by_country.setdefault(c.country, []).append(c)
    # Per-plant country bias for owner home region
    plant_owner_country_pool = {
        "Munich":          ["DE"]*8 + ["NL", "BE", "AT", "CH", "FR", "IT"],
        "Dingolfing":      ["DE"]*8 + ["NL", "BE", "AT", "CH", "FR", "IT", "GB"],
        "Regensburg":      ["DE"]*8 + ["NL", "BE", "AT", "CH"],
        "Leipzig":         ["DE"]*8 + ["AT", "CH", "FR"],
        "Spartanburg":     ["US-SC", "US-NY", "US-FL", "US-TX", "US-CA", "US-IL", "US-MA", "US-GA"],
        "San Luis Potosi": ["MX"]*6 + ["US-TX", "US-CA"],
    }

    owners: list[Owner] = []
    owner_id_pool: list[str] = []
    enriched: list[dict] = []

    for i, v in enumerate(vehicles, start=1):
        # Shared-owner: occasionally we reuse a previous owner_id
        if owner_id_pool and rng.random() < OWNER_SHARE_PROB:
            owner_id = rng.choice(owner_id_pool)
            existing = next(o for o in owners if o.owner_id == owner_id)
            country = existing.country
            region_code = existing.region_code
            nearest = existing.nearest_centre_id
            distance_km = existing.distance_km
            prior_accident = existing.prior_accident_history or (v.get("ACCIDENT_TYPE") not in (None, "", "None"))
            # Refresh prior_accident on the owner so the latest is reflected
            existing.prior_accident_history = prior_accident
        else:
            owner_id = f"OWN-{i:05d}"
            owner_id_pool.append(owner_id)
            plant_name = v["FACTORY_PRODUCTION_LOCATION"]
            pool = plant_owner_country_pool.get(plant_name, ["DE"])
            country = rng.choice(pool)
            region = next((r for r in REGIONS if country in r.country_codes), REGIONS[0])
            region_code = region.region_code
            # nearest centre = pick a same-country centre, else any in region
            candidates = centres_by_country.get(country, [])
            if not candidates:
                candidates = [c for c in SERVICE_CENTRES if c.region_code == region_code]
            if not candidates:
                candidates = SERVICE_CENTRES[:]
            nearest_centre = rng.choice(candidates)
            nearest = nearest_centre.centre_id
            distance_km = rng.randint(8, 220)
            prior_accident = v.get("ACCIDENT_TYPE") not in (None, "", "None")
            owners.append(Owner(owner_id, "***MASKED***", region_code, country, nearest, distance_km, prior_accident))

        existing_owner = next(o for o in owners if o.owner_id == owner_id)
        enriched.append({
            **v,
            "OWNER_ID": owner_id,
            "REGION_CODE": existing_owner.region_code,
            "OWNER_COUNTRY": existing_owner.country,
            "NEAREST_CENTRE_ID": existing_owner.nearest_centre_id,
            "DISTANCE_TO_NEAREST_CENTRE_KM": existing_owner.distance_km,
        })

    return owners, enriched


# ---------------------------------------------------------------------------
# 8. Recall assignments
# ---------------------------------------------------------------------------

@dataclass
class RecallAssignment:
    recall_id: str
    vin: str
    campaign_id: str
    status: str                # Open / Closed / In Progress
    announced_on: date
    notified_on: date          # per-VIN notification date (notification waves)
    closed_on: Optional[date]
    age_days_at_demo: int      # DEMO_DATE - notified_on (days since OWNER was notified)
    mileage_at_assign: int
    sla_breached: bool

def _build_recall_assignments(rng: random.Random,
                              vehicles: list[dict],
                              affected_by_campaign: dict[str, set[str]]) -> list[RecallAssignment]:
    out: list[RecallAssignment] = []
    rid_counter = 1
    seed_recall_status = {v["VIN"]: v["RECALL_STATUS"] for v in vehicles}
    vehicle_by_vin = {v["VIN"]: v for v in vehicles}

    # For each affected (vin, campaign) generate a row. Status follows
    # the seed's RECALL_STATUS hint where available.
    for cid, vins in affected_by_campaign.items():
        camp = CAMPAIGN_BY_ID[cid]
        for vin in sorted(vins):
            seed_status = seed_recall_status.get(vin, "")
            v = vehicle_by_vin[vin]
            # Status distribution. Hard-code IBS-2024-A to bias Open
            # (it's the cascade focus + Act 1 SLA leader).
            if cid == "IBS-2024-A":
                # 65% Open, 15% In Progress, 20% Closed
                roll = rng.random()
                status = "Open" if roll < 0.65 else ("In Progress" if roll < 0.80 else "Closed")
            elif cid == "HVB-2024-A":
                # Code 1 = newer campaign, ~70% Open, 20% In Progress, 10% Closed
                roll = rng.random()
                status = "Open" if roll < 0.70 else ("In Progress" if roll < 0.90 else "Closed")
            elif cid == "STARTER-2024-A":
                roll = rng.random()
                status = "Open" if roll < 0.55 else ("In Progress" if roll < 0.75 else "Closed")
            elif cid == "AIRBAG-2022-A":
                # Older campaign, mostly Closed but some lagging Open
                roll = rng.random()
                status = "Closed" if roll < 0.60 else ("In Progress" if roll < 0.80 else "Open")
            else:  # EGR-2023-B
                roll = rng.random()
                status = "Closed" if roll < 0.5 else ("In Progress" if roll < 0.75 else "Open")
            # Seed override: if RECALL_STATUS=Closed in seed, force one
            # campaign per VIN closed.
            if seed_status == "Closed" and rng.random() < 0.6:
                status = "Closed"
            # Per-VIN notification wave. Most owners receive notice
            # within 30 days of campaign announcement; a long tail
            # corresponds to expanded-scope adds and address-update
            # failures.
            lag_roll = rng.random()
            if lag_roll < 0.80:
                lag_days = rng.randint(3, 30)
            elif lag_roll < 0.95:
                lag_days = rng.randint(31, 90)
            else:
                lag_days = rng.randint(91, max(92, camp.completion_days + 30))
            notified_on = camp.announced_on + timedelta(days=lag_days)
            if notified_on > DEMO_DATE:
                notified_on = DEMO_DATE - timedelta(days=rng.randint(1, 14))
            age = (DEMO_DATE - notified_on).days

            # closed_on date if Closed
            closed_on = None
            if status == "Closed":
                offset_days = rng.randint(5, max(6, camp.completion_days - 10))
                closed_on = notified_on + timedelta(days=offset_days)
                if closed_on > DEMO_DATE:
                    closed_on = DEMO_DATE - timedelta(days=rng.randint(1, 30))

            mileage = int(v["MILEAGE"])
            # SLA breach: Open AND notified more than completion_days
            # ago AND severity demands prompt action. The Act 1 PyRel
            # rule reproduces this exactly from the ontology.
            sla_breached = (
                status == "Open"
                and age > camp.completion_days
                and camp.severity_code <= 2
            )
            out.append(RecallAssignment(
                f"REC-{rid_counter:06d}",
                vin, cid, status,
                camp.announced_on, notified_on, closed_on, age, mileage, sla_breached,
            ))
            rid_counter += 1
    return out


# ---------------------------------------------------------------------------
# 9. Per-centre per-week capacity and parts-stock for Act 4 MIP
# ---------------------------------------------------------------------------

@dataclass
class CapacityRow:
    centre_id: str
    week_index: int    # 1..4
    tech_hours_available: int

@dataclass
class PartsStockRow:
    centre_id: str
    campaign_id: str
    week_index: int    # 1..4 (week the stock arrives / is on-hand for)
    on_hand_units: int

def _build_capacity_and_stock(rng: random.Random,
                              n_weeks: int = 4) -> tuple[list[CapacityRow], list[PartsStockRow]]:
    cap: list[CapacityRow] = []
    for c in SERVICE_CENTRES:
        for w in range(1, n_weeks + 1):
            # Slight weekly noise but mostly constant; the Cologne and
            # Munich centres get a small dip in week 2 (holiday cover).
            base = c.weekly_tech_hours
            adj = 0
            if c.centre_id in ("SC-MUN", "SC-COL") and w == 2:
                adj = -60
            if c.centre_id == "SC-MTY" and w == 4:
                adj = -40
            cap.append(CapacityRow(c.centre_id, w, max(120, base + adj)))

    # Parts-stock: each campaign has a delivery profile per centre per
    # week. IBS-2024-A is the constrained campaign - Continental cannot
    # ship enough booster ECUs in the 4-week horizon, so the deferred
    # jobs from Act 4 land here.
    profiles = {
        # campaign_id: per-centre (w1,w2,w3,w4) stock arriving
        "IBS-2024-A": {
            # IBS-certified centres only - others have zero
            "SC-MUN": (6, 6, 5, 5),    # Munich is HQ-adjacent; gets first allocation
            "SC-COL": (5, 5, 4, 4),
            "SC-HAM": (4, 4, 4, 4),
            "SC-STU": (4, 4, 3, 3),
            "SC-FRA": (4, 4, 4, 4),
            "SC-BER": (3, 3, 3, 3),
            "SC-REG": (3, 3, 3, 3),
            "SC-DAL": (4, 4, 3, 3),
            "SC-MIA": (3, 3, 3, 3),
            "SC-NYC": (3, 3, 3, 3),
            "SC-LAX": (3, 3, 3, 3),
            "SC-SPB": (4, 4, 4, 4),
            "SC-CHI": (3, 3, 2, 2),
        },
        "HVB-2024-A": {
            # HV-certified centres only
            "SC-MUN": (3, 3, 3, 3),
            "SC-COL": (3, 3, 3, 3),
            "SC-HAM": (3, 3, 3, 3),
            "SC-STU": (2, 2, 2, 2),
            "SC-FRA": (3, 3, 3, 3),
            "SC-BER": (2, 2, 2, 2),
            "SC-LEI": (2, 2, 2, 2),
            "SC-DAL": (3, 3, 2, 2),
            "SC-MIA": (2, 2, 2, 2),
            "SC-NYC": (2, 2, 2, 2),
            "SC-LAX": (3, 3, 3, 3),
            "SC-SPB": (3, 3, 3, 3),
            "SC-CHI": (2, 2, 2, 2),
        },
        "EGR-2023-B": {
            "SC-REG": (3, 3, 2, 2),
        },
        "AIRBAG-2022-A": {
            # body-shop centres only
            "SC-COL": (4, 4, 4, 4),
            "SC-HAM": (4, 4, 4, 4),
            "SC-MUN": (4, 4, 4, 4),
            "SC-FRA": (4, 4, 4, 4),
            "SC-BER": (3, 3, 3, 3),
            "SC-DAL": (3, 3, 3, 3),
            "SC-MIA": (3, 3, 3, 3),
            "SC-NYC": (3, 3, 3, 3),
            "SC-LAX": (3, 3, 3, 3),
            "SC-SPB": (3, 3, 3, 3),
        },
        "STARTER-2024-A": {
            "SC-REG": (5, 5, 5, 5),
            "SC-MUN": (4, 4, 4, 4),
            "SC-DAL": (3, 3, 3, 3),
            "SC-SPB": (3, 3, 3, 3),
            "SC-LAX": (3, 3, 3, 3),
            "SC-MIA": (3, 3, 3, 3),
        },
    }

    stock: list[PartsStockRow] = []
    for cid, by_centre in profiles.items():
        for centre_id, weekly in by_centre.items():
            for w, q in enumerate(weekly, start=1):
                stock.append(PartsStockRow(centre_id, cid, w, q))
    return cap, stock


# ---------------------------------------------------------------------------
# 10. Emit SQL and CSV
# ---------------------------------------------------------------------------

def _emit_ddl() -> str:
    ddl = f"""-- =====================================================================
-- CARS_DEMO - Snowflake DDL (schema FLEET)
-- Generated by build_cars_demo_data.py at {datetime.utcnow().isoformat()}Z
-- Seed: {SEED}
-- =====================================================================

USE ROLE RAI_DEMO_CARS;
USE DATABASE {DB_NAME};
CREATE SCHEMA IF NOT EXISTS {SCHEMA_NAME};
USE SCHEMA {SCHEMA_NAME};

-- ----- Reference tables -----------------------------------------------

CREATE OR REPLACE TABLE dim_supplier (
    supplier_id           VARCHAR(16) PRIMARY KEY,
    name                  VARCHAR(120),
    tier                  INTEGER,
    country               VARCHAR(2),
    specialty             VARCHAR(120),
    warranty_share_pct    INTEGER
);

CREATE OR REPLACE TABLE dim_region (
    region_code           VARCHAR(12) PRIMARY KEY,
    name                  VARCHAR(60),
    rollup                VARCHAR(10),
    country_codes         VARCHAR(200)
);

CREATE OR REPLACE TABLE dim_plant (
    plant_code            VARCHAR(2) PRIMARY KEY,
    name                  VARCHAR(60),
    country               VARCHAR(10),
    region_code           VARCHAR(12),
    weekly_output         INTEGER
);

CREATE OR REPLACE TABLE dim_part (
    part_id               VARCHAR(20) PRIMARY KEY,
    supplier_id           VARCHAR(16),
    name                  VARCHAR(80),
    category              VARCHAR(20),
    unit_cost_usd         INTEGER
);

CREATE OR REPLACE TABLE dim_bom_node (
    bom_id                VARCHAR(20) PRIMARY KEY,
    part_id               VARCHAR(20),
    description           VARCHAR(200),
    applies_to_model_codes VARCHAR(200),
    applies_to_plants     VARCHAR(40),
    applies_from          DATE,
    applies_to            DATE
);

CREATE OR REPLACE TABLE dim_service_centre (
    centre_id             VARCHAR(10) PRIMARY KEY,
    name                  VARCHAR(80),
    country               VARCHAR(10),
    region_code           VARCHAR(12),
    hv_certified          BOOLEAN,
    ibs_certified         BOOLEAN,
    body_shop             BOOLEAN,
    weekly_tech_hours     INTEGER,
    has_egr_tooling       BOOLEAN
);

CREATE OR REPLACE TABLE dim_recall_campaign (
    campaign_id           VARCHAR(20) PRIMARY KEY,
    name                  VARCHAR(120),
    supplier_id           VARCHAR(16),
    primary_part_id       VARCHAR(20),
    severity_code         INTEGER,
    completion_days       INTEGER,
    announced_on          DATE,
    requires_hv_cert      BOOLEAN,
    requires_ibs_cert     BOOLEAN,
    requires_body_shop    BOOLEAN,
    typical_labour_hours  FLOAT,
    description           VARCHAR(800)
);

-- ----- Master data -----------------------------------------------------

CREATE OR REPLACE TABLE owner (
    owner_id              VARCHAR(20) PRIMARY KEY,
    masked_name           VARCHAR(60),
    region_code           VARCHAR(12),
    country               VARCHAR(10),
    nearest_centre_id     VARCHAR(10),
    distance_km           INTEGER,
    prior_accident_history BOOLEAN
);

CREATE OR REPLACE TABLE vehicle (
    vin                   VARCHAR(20) PRIMARY KEY,
    serial_number         VARCHAR(20),
    model                 VARCHAR(80),
    factory               VARCHAR(40),
    engine_type           VARCHAR(80),
    fuel_type             VARCHAR(20),
    transmission          VARCHAR(20),
    chassis_number        VARCHAR(20),
    emission_standard     VARCHAR(20),
    production_date       DATE,
    delivery_date         DATE,
    first_registration_date DATE,
    mileage               INTEGER,
    fuel_consumption      FLOAT,
    accident_date         DATE,
    accident_type         VARCHAR(40),
    repair_cost           FLOAT,
    service_records       VARCHAR(20),
    recall_status_raw     VARCHAR(20),
    previous_owners       INTEGER,
    power_output_kw       INTEGER,
    power_output_ps       INTEGER,
    owner_id              VARCHAR(20),
    region_code           VARCHAR(12),
    owner_country         VARCHAR(10),
    nearest_centre_id     VARCHAR(10),
    distance_to_nearest_centre_km INTEGER
);

CREATE OR REPLACE TABLE service_event (
    service_event_id      VARCHAR(20) PRIMARY KEY,
    vin                   VARCHAR(20),
    service_date          DATE,
    service_type          VARCHAR(40),
    service_centre        VARCHAR(80),
    service_cost          FLOAT,
    warranty              BOOLEAN,
    notes                 VARCHAR(200)
);

-- ----- Junctions / facts ----------------------------------------------

CREATE OR REPLACE TABLE bom_membership (
    bom_id                VARCHAR(20),
    vin                   VARCHAR(20)
);

CREATE OR REPLACE TABLE recall_assignment (
    recall_id             VARCHAR(20) PRIMARY KEY,
    vin                   VARCHAR(20),
    campaign_id           VARCHAR(20),
    status                VARCHAR(20),
    announced_on          DATE,
    notified_on           DATE,
    closed_on             DATE,
    age_days_at_demo      INTEGER,
    mileage_at_assign     INTEGER,
    sla_breached          BOOLEAN
);

CREATE OR REPLACE TABLE centre_capacity (
    centre_id             VARCHAR(10),
    week_index            INTEGER,
    tech_hours_available  INTEGER
);

CREATE OR REPLACE TABLE parts_stock (
    centre_id             VARCHAR(10),
    campaign_id           VARCHAR(20),
    week_index            INTEGER,
    on_hand_units         INTEGER
);
"""
    return ddl


def _q(s: Optional[str]) -> str:
    if s is None or s == "":
        return "NULL"
    return "'" + str(s).replace("'", "''") + "'"


def _qd(s: Optional[str]) -> str:
    if s is None or s == "":
        return "NULL"
    return f"'{s}'"


def _emit_reference_sql(owners: list[Owner], capacities: list[CapacityRow],
                         stocks: list[PartsStockRow]) -> str:
    parts: list[str] = []
    parts.append(f"USE DATABASE {DB_NAME};\nUSE SCHEMA {SCHEMA_NAME};\n")
    # dim_supplier
    rows = ",\n".join(
        f"  ('{s.supplier_id}', {_q(s.name)}, {s.tier}, '{s.country}', {_q(s.specialty)}, {s.warranty_share_pct})"
        for s in SUPPLIERS
    )
    parts.append(f"DELETE FROM dim_supplier;\nINSERT INTO dim_supplier (supplier_id, name, tier, country, specialty, warranty_share_pct) VALUES\n{rows};\n")
    # dim_region
    rows = ",\n".join(
        f"  ('{r.region_code}', {_q(r.name)}, '{r.rollup}', '{','.join(r.country_codes)}')"
        for r in REGIONS
    )
    parts.append(f"DELETE FROM dim_region;\nINSERT INTO dim_region (region_code, name, rollup, country_codes) VALUES\n{rows};\n")
    # dim_plant
    rows = ",\n".join(
        f"  ('{p.plant_code}', {_q(p.name)}, '{p.country}', '{p.region_code}', {p.weekly_output})"
        for p in PLANTS
    )
    parts.append(f"DELETE FROM dim_plant;\nINSERT INTO dim_plant (plant_code, name, country, region_code, weekly_output) VALUES\n{rows};\n")
    # dim_part
    rows = ",\n".join(
        f"  ('{p.part_id}', '{p.supplier_id}', {_q(p.name)}, '{p.category}', {p.unit_cost_usd})"
        for p in PARTS
    )
    parts.append(f"DELETE FROM dim_part;\nINSERT INTO dim_part (part_id, supplier_id, name, category, unit_cost_usd) VALUES\n{rows};\n")
    # dim_bom_node
    rows = ",\n".join(
        f"  ('{b.bom_id}', '{b.part_id}', {_q(b.description)}, "
        f"{_q('|'.join(b.applies_to_model_codes))}, {_q(','.join(b.applies_to_plants))}, "
        f"'{b.applies_from.isoformat()}', '{b.applies_to.isoformat()}')"
        for b in BOM_NODES
    )
    parts.append(f"DELETE FROM dim_bom_node;\nINSERT INTO dim_bom_node (bom_id, part_id, description, applies_to_model_codes, applies_to_plants, applies_from, applies_to) VALUES\n{rows};\n")
    # dim_service_centre
    rows = ",\n".join(
        f"  ('{c.centre_id}', {_q(c.name)}, '{c.country}', '{c.region_code}', "
        f"{'TRUE' if c.hv_certified else 'FALSE'}, "
        f"{'TRUE' if c.ibs_certified else 'FALSE'}, "
        f"{'TRUE' if c.body_shop else 'FALSE'}, "
        f"{c.weekly_tech_hours}, "
        f"{'TRUE' if c.has_egr_tooling else 'FALSE'})"
        for c in SERVICE_CENTRES
    )
    parts.append(f"DELETE FROM dim_service_centre;\nINSERT INTO dim_service_centre (centre_id, name, country, region_code, hv_certified, ibs_certified, body_shop, weekly_tech_hours, has_egr_tooling) VALUES\n{rows};\n")
    # dim_recall_campaign
    rows = ",\n".join(
        f"  ('{c.campaign_id}', {_q(c.name)}, '{c.supplier_id}', '{c.primary_part_id}', "
        f"{c.severity_code}, {c.completion_days}, '{c.announced_on.isoformat()}', "
        f"{'TRUE' if c.requires_hv_cert else 'FALSE'}, "
        f"{'TRUE' if c.requires_ibs_cert else 'FALSE'}, "
        f"{'TRUE' if c.requires_body_shop else 'FALSE'}, "
        f"{c.typical_labour_hours}, {_q(c.description)})"
        for c in CAMPAIGNS
    )
    parts.append(f"DELETE FROM dim_recall_campaign;\nINSERT INTO dim_recall_campaign (campaign_id, name, supplier_id, primary_part_id, severity_code, completion_days, announced_on, requires_hv_cert, requires_ibs_cert, requires_body_shop, typical_labour_hours, description) VALUES\n{rows};\n")
    # owners
    rows = ",\n".join(
        f"  ('{o.owner_id}', {_q(o.masked_name)}, '{o.region_code}', '{o.country}', "
        f"'{o.nearest_centre_id}', {o.distance_km}, {'TRUE' if o.prior_accident_history else 'FALSE'})"
        for o in owners
    )
    parts.append(f"DELETE FROM owner;\nINSERT INTO owner (owner_id, masked_name, region_code, country, nearest_centre_id, distance_km, prior_accident_history) VALUES\n{rows};\n")
    # centre_capacity
    rows = ",\n".join(
        f"  ('{c.centre_id}', {c.week_index}, {c.tech_hours_available})"
        for c in capacities
    )
    parts.append(f"DELETE FROM centre_capacity;\nINSERT INTO centre_capacity (centre_id, week_index, tech_hours_available) VALUES\n{rows};\n")
    # parts_stock
    rows = ",\n".join(
        f"  ('{s.centre_id}', '{s.campaign_id}', {s.week_index}, {s.on_hand_units})"
        for s in stocks
    )
    parts.append(f"DELETE FROM parts_stock;\nINSERT INTO parts_stock (centre_id, campaign_id, week_index, on_hand_units) VALUES\n{rows};\n")
    return "\n".join(parts)


def _emit_vehicles_csv(enriched: list[dict]) -> Path:
    out_path = OUT_DIR / "cars_demo_vehicles.csv"
    fields = [
        "vin","serial_number","model","factory","engine_type","fuel_type","transmission","chassis_number",
        "emission_standard","production_date","delivery_date","first_registration_date","mileage",
        "fuel_consumption","accident_date","accident_type","repair_cost","service_records",
        "recall_status_raw","previous_owners","power_output_kw","power_output_ps",
        "owner_id","region_code","owner_country","nearest_centre_id","distance_to_nearest_centre_km",
    ]
    with open(out_path, "w") as f:
        w = csv.writer(f, quoting=csv.QUOTE_MINIMAL)
        w.writerow(fields)
        for v in enriched:
            w.writerow([
                v["VIN"], v["SERIAL_NUMBER"], v["MODEL"], v["FACTORY_PRODUCTION_LOCATION"],
                v["ENGINE_TYPE"], v["FUEL_TYPE"], v["TRANSMISSION"], v["CHASSIS_NUMBER"],
                v["EMISSION_STANDARD"], v["PRODUCTION_DATE"], v["DELIVERY_DATE"], v["FIRST_REGISTRATION_DATE"],
                v["MILEAGE"], v["FUEL_CONSUMPTION"], v.get("ACCIDENT_DATE",""), v.get("ACCIDENT_TYPE",""),
                v["REPAIR_COST"], v["SERVICE_RECORDS"], v["RECALL_STATUS"], v["PREVIOUS_OWNERS"],
                v["POWER_OUTPUT_KW"], v["POWER_OUTPUT_PS"],
                v["OWNER_ID"], v["REGION_CODE"], v["OWNER_COUNTRY"],
                v["NEAREST_CENTRE_ID"], v["DISTANCE_TO_NEAREST_CENTRE_KM"],
            ])
    return out_path


def _emit_services_csv() -> Path:
    out_path = OUT_DIR / "cars_demo_services.csv"
    fields = ["service_event_id","vin","service_date","service_type","service_centre","service_cost","warranty","notes"]
    with open(out_path, "w") as f:
        w = csv.writer(f, quoting=csv.QUOTE_MINIMAL)
        w.writerow(fields)
        for s in SERVICES_RAW:
            w.writerow([
                s["SERVICE_EVENT_ID"], s["VIN"], s["SERVICE_DATE"], s["SERVICE_TYPE"],
                s["SERVICE_CENTER"], s["SERVICE_COST"],
                "TRUE" if s["WARRANTY"].upper() == "TRUE" else "FALSE",
                s["NOTES"],
            ])
    return out_path


def _emit_bom_csv(bom_membership: dict[str, set[str]]) -> Path:
    out_path = OUT_DIR / "cars_demo_bom.csv"
    with open(out_path, "w") as f:
        w = csv.writer(f, quoting=csv.QUOTE_MINIMAL)
        w.writerow(["bom_id", "vin"])
        for bid, members in sorted(bom_membership.items()):
            for vin in sorted(members):
                w.writerow([bid, vin])
    return out_path


def _emit_recall_csv(recalls: list[RecallAssignment]) -> Path:
    out_path = OUT_DIR / "cars_demo_recall.csv"
    with open(out_path, "w") as f:
        w = csv.writer(f, quoting=csv.QUOTE_MINIMAL)
        w.writerow(["recall_id","vin","campaign_id","status","announced_on","notified_on","closed_on",
                    "age_days_at_demo","mileage_at_assign","sla_breached"])
        for r in recalls:
            w.writerow([r.recall_id, r.vin, r.campaign_id, r.status,
                        r.announced_on.isoformat(),
                        r.notified_on.isoformat(),
                        r.closed_on.isoformat() if r.closed_on else "",
                        r.age_days_at_demo, r.mileage_at_assign,
                        "TRUE" if r.sla_breached else "FALSE"])
    return out_path


def _emit_load_sql() -> str:
    return f"""-- =====================================================================
-- CARS_DEMO - Snowflake load orchestration
-- =====================================================================
USE ROLE RAI_DEMO_CARS;
USE DATABASE {DB_NAME};
USE SCHEMA {SCHEMA_NAME};

CREATE STAGE IF NOT EXISTS cars_demo_stage
  FILE_FORMAT = (TYPE = CSV SKIP_HEADER = 1
                 FIELD_OPTIONALLY_ENCLOSED_BY = '"'
                 NULL_IF = ('','NULL') EMPTY_FIELD_AS_NULL = TRUE);

-- The shell loader will PUT the four CSVs (vehicles, services, bom,
-- recall) onto this stage and then COPY INTO each table. See
-- data/load_to_snowflake.sh.

COPY INTO vehicle FROM @cars_demo_stage/cars_demo_vehicles.csv.gz
  FILE_FORMAT = (TYPE = CSV SKIP_HEADER = 1 FIELD_OPTIONALLY_ENCLOSED_BY = '"'
                 NULL_IF = ('','NULL') EMPTY_FIELD_AS_NULL = TRUE);

COPY INTO service_event FROM @cars_demo_stage/cars_demo_services.csv.gz
  FILE_FORMAT = (TYPE = CSV SKIP_HEADER = 1 FIELD_OPTIONALLY_ENCLOSED_BY = '"'
                 NULL_IF = ('','NULL') EMPTY_FIELD_AS_NULL = TRUE);

COPY INTO bom_membership FROM @cars_demo_stage/cars_demo_bom.csv.gz
  FILE_FORMAT = (TYPE = CSV SKIP_HEADER = 1 FIELD_OPTIONALLY_ENCLOSED_BY = '"'
                 NULL_IF = ('','NULL') EMPTY_FIELD_AS_NULL = TRUE);

COPY INTO recall_assignment FROM @cars_demo_stage/cars_demo_recall.csv.gz
  FILE_FORMAT = (TYPE = CSV SKIP_HEADER = 1 FIELD_OPTIONALLY_ENCLOSED_BY = '"'
                 NULL_IF = ('','NULL') EMPTY_FIELD_AS_NULL = TRUE);

-- Change tracking is required by PyRel CDC.
ALTER TABLE dim_supplier         SET CHANGE_TRACKING = TRUE;
ALTER TABLE dim_region           SET CHANGE_TRACKING = TRUE;
ALTER TABLE dim_plant            SET CHANGE_TRACKING = TRUE;
ALTER TABLE dim_part             SET CHANGE_TRACKING = TRUE;
ALTER TABLE dim_bom_node         SET CHANGE_TRACKING = TRUE;
ALTER TABLE dim_service_centre   SET CHANGE_TRACKING = TRUE;
ALTER TABLE dim_recall_campaign  SET CHANGE_TRACKING = TRUE;
ALTER TABLE owner                SET CHANGE_TRACKING = TRUE;
ALTER TABLE vehicle              SET CHANGE_TRACKING = TRUE;
ALTER TABLE service_event        SET CHANGE_TRACKING = TRUE;
ALTER TABLE bom_membership       SET CHANGE_TRACKING = TRUE;
ALTER TABLE recall_assignment    SET CHANGE_TRACKING = TRUE;
ALTER TABLE centre_capacity      SET CHANGE_TRACKING = TRUE;
ALTER TABLE parts_stock          SET CHANGE_TRACKING = TRUE;

SELECT
  (SELECT COUNT(*) FROM dim_supplier)         AS suppliers,
  (SELECT COUNT(*) FROM dim_plant)            AS plants,
  (SELECT COUNT(*) FROM dim_part)             AS parts,
  (SELECT COUNT(*) FROM dim_bom_node)         AS bom_nodes,
  (SELECT COUNT(*) FROM dim_service_centre)   AS centres,
  (SELECT COUNT(*) FROM dim_recall_campaign)  AS campaigns,
  (SELECT COUNT(*) FROM owner)                AS owners,
  (SELECT COUNT(*) FROM vehicle)              AS vehicles,
  (SELECT COUNT(*) FROM service_event)        AS services,
  (SELECT COUNT(*) FROM bom_membership)       AS bom_edges,
  (SELECT COUNT(*) FROM recall_assignment)    AS recalls,
  (SELECT COUNT(*) FROM centre_capacity)      AS capacity_rows,
  (SELECT COUNT(*) FROM parts_stock)          AS stock_rows;
"""


def _emit_validation_sql(stats: dict) -> str:
    return f"""-- =====================================================================
-- CARS_DEMO - Validation queries (anchored numbers from BRIEF.md)
-- =====================================================================
-- Run after loading and verify the expected counts. Each query backs
-- one talk-track number that prep_demo.py will assert.
USE ROLE RAI_DEMO_CARS;
USE DATABASE {DB_NAME};
USE SCHEMA {SCHEMA_NAME};

-- Sanity: top-line counts.
-- Expected: 325 vehicles, 762 services, {stats['recall_count']} recalls,
--           {stats['bom_edges']} bom edges, {stats['open_count']} Open
--           recalls across all campaigns.
SELECT
  (SELECT COUNT(*) FROM vehicle) AS vehicles,
  (SELECT COUNT(*) FROM service_event) AS services,
  (SELECT COUNT(*) FROM recall_assignment) AS recalls,
  (SELECT COUNT(*) FROM bom_membership) AS bom_edges,
  (SELECT COUNT(*) FROM recall_assignment WHERE status = 'Open') AS open_recalls;

-- Q1 (Act 1 audit): SLA-breached Open recalls by campaign
-- Expected dominant campaign: IBS-2024-A
SELECT
  campaign_id,
  COUNT(*) AS sla_breached_open
FROM recall_assignment
WHERE status = 'Open'
  AND sla_breached = TRUE
GROUP BY campaign_id
ORDER BY sla_breached_open DESC;

-- Q1: SLA-breached Open recalls by responsible service centre
-- Expected leader: BMW Munich Service
WITH responsible_centre AS (
  SELECT r.recall_id, r.campaign_id, v.vin, v.nearest_centre_id, sc.name AS centre_name
  FROM recall_assignment r
  JOIN vehicle v ON v.vin = r.vin
  JOIN dim_service_centre sc ON sc.centre_id = v.nearest_centre_id
  WHERE r.status = 'Open' AND r.sla_breached = TRUE
)
SELECT centre_name, COUNT(*) AS sla_breached_open
FROM responsible_centre
GROUP BY centre_name
ORDER BY sla_breached_open DESC;

-- Q2 (Act 2 cascade): affected VINs from supplier Continental
-- Expected: ~80 VINs, the IBS-2024-A campaign population
WITH cascade AS (
  SELECT DISTINCT bm.vin
  FROM dim_supplier s
  JOIN dim_part      p   ON p.supplier_id = s.supplier_id
  JOIN dim_bom_node  b   ON b.part_id     = p.part_id
  JOIN bom_membership bm ON bm.bom_id     = b.bom_id
  WHERE s.supplier_id = 'SUP-CONT'
    AND p.part_id = 'PRT-IBS-ECU'
)
SELECT COUNT(*) AS affected_vins FROM cascade;

-- Q2: same cascade rolled up by region (EU / NA / LATAM)
SELECT r.rollup, COUNT(DISTINCT bm.vin) AS affected_vins, COUNT(DISTINCT v.nearest_centre_id) AS centres_engaged
FROM dim_supplier s
JOIN dim_part      p   ON p.supplier_id = s.supplier_id
JOIN dim_bom_node  b   ON b.part_id     = p.part_id
JOIN bom_membership bm ON bm.bom_id     = b.bom_id
JOIN vehicle       v   ON v.vin         = bm.vin
JOIN dim_service_centre sc ON sc.centre_id = v.nearest_centre_id
JOIN dim_region    r   ON r.region_code = sc.region_code
WHERE s.supplier_id = 'SUP-CONT' AND p.part_id = 'PRT-IBS-ECU'
GROUP BY r.rollup
ORDER BY affected_vins DESC;

-- Q3 (Act 3 heuristic): a SQL sketch of the urgency-score top-20.
-- The PyRel version computes the same with derived properties; this
-- SQL ensures the candidate population and dominant cohort match.
WITH open_recalls AS (
  SELECT r.vin, r.campaign_id,
         v.mileage,
         DATEDIFF('day', v.first_registration_date, '{DEMO_DATE.isoformat()}') AS age_days,
         CASE WHEN v.accident_type IS NULL OR v.accident_type = '' THEN 0
              WHEN v.accident_type IN ('Minor','Vandalism') THEN 1
              WHEN v.accident_type IN ('Rear-end','Collision') THEN 2
              ELSE 0 END AS accident_severity,
         v.distance_to_nearest_centre_km AS distance_km,
         v.factory
  FROM recall_assignment r
  JOIN vehicle v ON v.vin = r.vin
  WHERE r.status = 'Open'
)
SELECT vin, campaign_id, factory, mileage, age_days, accident_severity, distance_km,
       (0.30 * (mileage / 250000.0)
      + 0.25 * (age_days / 2200.0)
      + 0.30 * (accident_severity / 2.0)
      + 0.15 * (distance_km / 250.0)) AS urgency_score
FROM open_recalls
ORDER BY urgency_score DESC
LIMIT 20;

-- Q4 (Act 4): pre-solve sanity. Total open jobs vs. total available
-- (tech_hours / typical_labour_hours) across the 4-week horizon.
-- Expected: tech-hours capacity is plenty; parts stock is the
-- binding constraint (especially IBS-2024-A).
SELECT
  c.campaign_id,
  COUNT(*) AS open_jobs,
  c.typical_labour_hours,
  (SELECT SUM(on_hand_units) FROM parts_stock ps WHERE ps.campaign_id = c.campaign_id) AS total_stock_4wk
FROM recall_assignment r
JOIN dim_recall_campaign c ON c.campaign_id = r.campaign_id
WHERE r.status = 'Open'
GROUP BY c.campaign_id, c.typical_labour_hours;

-- Q5 (Act 5): population of priority VINs (open recall + prior accident).
SELECT COUNT(DISTINCT r.vin) AS priority_vins
FROM recall_assignment r
JOIN vehicle v ON v.vin = r.vin
WHERE r.status = 'Open'
  AND v.accident_type IS NOT NULL
  AND v.accident_type <> '';
"""


# ---------------------------------------------------------------------------
# 11. Main
# ---------------------------------------------------------------------------

def main():
    rng = random.Random(SEED)

    # Owners + enriched vehicles
    owners, enriched = _build_owners_and_vehicle_enrich(rng, VEHICLES_RAW)

    # BOM membership (graph edges Vehicle <-> BomNode)
    bom_membership = _bom_member_vehicles(enriched)
    bom_edge_count = sum(len(m) for m in bom_membership.values())

    # Campaign affected VINs and recall_assignments
    affected = _campaign_affected(bom_membership)
    recalls = _build_recall_assignments(rng, enriched, affected)

    # Capacity + stock
    capacities, stocks = _build_capacity_and_stock(rng)

    # Emit DDL
    (OUT_DIR / "cars_demo_ddl.sql").write_text(_emit_ddl())
    # Emit reference SQL
    (OUT_DIR / "cars_demo_reference.sql").write_text(_emit_reference_sql(owners, capacities, stocks))
    # Emit CSVs
    _emit_vehicles_csv(enriched)
    _emit_services_csv()
    _emit_bom_csv(bom_membership)
    _emit_recall_csv(recalls)
    # Emit load + validation
    stats = {
        "recall_count": len(recalls),
        "open_count": sum(1 for r in recalls if r.status == "Open"),
        "bom_edges": bom_edge_count,
    }
    (OUT_DIR / "cars_demo_load.sql").write_text(_emit_load_sql())
    (OUT_DIR / "cars_demo_validation.sql").write_text(_emit_validation_sql(stats))

    # Summary print
    open_by_campaign = {}
    for r in recalls:
        if r.status == "Open":
            open_by_campaign[r.campaign_id] = open_by_campaign.get(r.campaign_id, 0) + 1
    sla_breached = sum(1 for r in recalls if r.status == "Open" and r.sla_breached)
    affected_continental_ibs = len(affected.get("IBS-2024-A", set()))
    print(f"seed={SEED}")
    print(f"vehicles: {len(enriched)}    services: {len(SERVICES_RAW)}    owners: {len(owners)}")
    print(f"bom_edges: {bom_edge_count}    recall_assignments: {len(recalls)}    open: {stats['open_count']}    sla_breached_open: {sla_breached}")
    print(f"campaigns affected: {sum(len(v) for v in affected.values())} (Continental IBS-2024-A: {affected_continental_ibs})")
    for cid, n in sorted(open_by_campaign.items()):
        print(f"  Open by campaign {cid}: {n}")
    print(f"output: {OUT_DIR}")


if __name__ == "__main__":
    main()
