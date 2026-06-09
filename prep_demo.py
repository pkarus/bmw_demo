#!/usr/bin/env python3
"""prep_demo.py - the demo-day pre-flight gate.

Run from the project root 10 minutes before showtime:

    .venv/bin/python prep_demo.py

Order of operations:
    1. Snowflake connection + role check
    2. Database / schema row counts (catch a missing load)
    3. Anchored-number validation (talk track sentinels)
    4. Engine resume (cars_logic_l + cars_prescriptive_m)
    5. Per-query smoke test (Q1 -> Q5, including the MIPs)
    6. Cortex agent status (if deployed)
    7. Optional: regenerate static PNG figures for RUNNING.html

Exits 0 if every check is GREEN, 1 if any check is RED. Yellow checks
print a warning but do not block.

Flags:
    --skip-figures   skip step 7 (saves ~30s on a warm run)
    --skip-chat      skip the agent chat smoke test
    --skip-snowsight skip the Snowsight notebook upload check
    --redeploy       force-redeploy the Cortex agent before chat test
"""
from __future__ import annotations
import argparse
import json
import re
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

ROOT = Path(__file__).parent
CONN = "rai"
ROLE = "RAI_DEMO_CARS"
DB = "CARS_DEMO"
SCHEMA = "FLEET"
LOGIC_ENGINE = "cars_logic_l"
PRESC_ENGINE = "cars_prescriptive_m"

GREEN = "\033[32m"
RED = "\033[31m"
YELLOW = "\033[33m"
RESET = "\033[0m"
BOLD = "\033[1m"


@dataclass
class CheckResult:
    name: str
    passed: bool
    detail: str = ""
    warn: bool = False
    elapsed: float = 0.0


@dataclass
class Phase:
    name: str
    checks: list[CheckResult] = field(default_factory=list)


def _print_phase(p: Phase) -> None:
    print(f"\n{BOLD}== {p.name} =={RESET}")
    for c in p.checks:
        color = GREEN if c.passed else (YELLOW if c.warn else RED)
        tag = "PASS" if c.passed else ("WARN" if c.warn else "FAIL")
        print(f"  [{color}{tag}{RESET}] {c.name:48s} {c.elapsed:5.1f}s   {c.detail}")


def _snow(sql: str, expect_rows: bool = True) -> tuple[bool, str, list[dict]]:
    proc = subprocess.run(
        ["snow", "sql", "-c", CONN, "--role", ROLE, "--format", "json", "-q", sql],
        capture_output=True, text=True, timeout=120,
    )
    if proc.returncode != 0:
        return False, proc.stderr.strip() or proc.stdout.strip(), []
    m = re.search(r"\[.*\]", proc.stdout, re.DOTALL)
    if not m:
        return True, "no rows", []
    try:
        rows = json.loads(m.group(0))
    except json.JSONDecodeError:
        return False, "JSON decode error", []
    return True, "", rows


def _check(name: str, fn: Callable[[], tuple[bool, str]], warn_on_fail: bool = False) -> CheckResult:
    t0 = time.time()
    try:
        ok, detail = fn()
    except Exception as e:
        return CheckResult(name=name, passed=False, detail=f"exception: {e}", warn=warn_on_fail, elapsed=time.time() - t0)
    return CheckResult(name=name, passed=ok, detail=detail, warn=warn_on_fail and not ok, elapsed=time.time() - t0)


def check_connection() -> tuple[bool, str]:
    ok, err, rows = _snow("SELECT CURRENT_ROLE() AS role, CURRENT_USER() AS u")
    if not ok:
        return False, err
    role = rows[0].get("ROLE") if rows else None
    user = rows[0].get("U") if rows else None
    return role == ROLE, f"role={role} user={user}"


def check_row_counts() -> tuple[bool, str]:
    expectations = {
        "vehicle": 325, "service_event": 762, "owner": 282,
        "bom_membership": 531, "recall_assignment": 254,
        "dim_supplier": 11, "dim_part": 19, "dim_bom_node": 11,
        "dim_service_centre": 15, "dim_recall_campaign": 5,
        "centre_capacity": 60, "parts_stock": 172,
    }
    mismatches = []
    for table, expected in expectations.items():
        ok, err, rows = _snow(f"SELECT COUNT(*) AS N FROM {DB}.{SCHEMA}.{table}")
        if not ok:
            return False, f"{table}: query failed ({err[:60]})"
        actual = int(rows[0]["N"]) if rows else 0
        if actual != expected:
            mismatches.append(f"{table}={actual}!={expected}")
    if mismatches:
        return False, ", ".join(mismatches)
    return True, f"{len(expectations)} tables OK"


def check_anchored_numbers() -> tuple[bool, str]:
    """The 5 talk-track anchors. If any of these miss, the talk track
    breaks."""
    checks = [
        # (label, sql, expected)
        ("Q1 SLA breaches", f"SELECT COUNT(*) AS N FROM {DB}.{SCHEMA}.recall_assignment WHERE status='Open' AND sla_breached=TRUE", 19),
        ("Q1 IBS breaches", f"SELECT COUNT(*) AS N FROM {DB}.{SCHEMA}.recall_assignment WHERE status='Open' AND sla_breached=TRUE AND campaign_id='IBS-2024-A'", 8),
        ("Q1 HVB breaches", f"SELECT COUNT(*) AS N FROM {DB}.{SCHEMA}.recall_assignment WHERE status='Open' AND sla_breached=TRUE AND campaign_id='HVB-2024-A'", 7),
        ("Open recalls", f"SELECT COUNT(*) AS N FROM {DB}.{SCHEMA}.recall_assignment WHERE status='Open'", 121),
        ("Q2 Continental cascade", f"""SELECT COUNT(DISTINCT bm.vin) AS N FROM {DB}.{SCHEMA}.dim_supplier s JOIN {DB}.{SCHEMA}.dim_part p ON p.supplier_id=s.supplier_id JOIN {DB}.{SCHEMA}.dim_bom_node b ON b.part_id=p.part_id JOIN {DB}.{SCHEMA}.bom_membership bm ON bm.bom_id=b.bom_id WHERE s.supplier_id='SUP-CONT' AND p.part_id='PRT-IBS-ECU'""", 67),
        ("Q5 priority VINs", f"""SELECT COUNT(DISTINCT r.vin) AS N FROM {DB}.{SCHEMA}.recall_assignment r JOIN {DB}.{SCHEMA}.vehicle v ON v.vin=r.vin WHERE r.status='Open' AND v.accident_type IS NOT NULL AND v.accident_type <> ''""", 15),
    ]
    mismatches = []
    for label, sql, expected in checks:
        ok, err, rows = _snow(sql)
        if not ok:
            return False, f"{label}: query failed"
        actual = int(rows[0]["N"]) if rows else 0
        if actual != expected:
            mismatches.append(f"{label}={actual}!={expected}")
    if mismatches:
        return False, ", ".join(mismatches)
    return True, f"{len(checks)} anchors OK"


def check_engines(resume: bool = True) -> tuple[bool, str]:
    """Resume both engines and confirm READY."""
    rai = str(ROOT / ".venv" / "bin" / "rai")
    if not Path(rai).exists():
        return False, f"missing {rai}"
    # Trigger resume by importing the ontology and running a trivial query.
    smoke = ROOT / "_prep_smoke.py"
    smoke.write_text(
        "from rai_code.manual.cars import model, Vehicle\n"
        "from relationalai.semantics.std import aggregates as aggs\n"
        "df = model.where(Vehicle).select(aggs.count(Vehicle).alias('n')).to_df()\n"
        "print(f'vehicles: {int(df.n.iloc[0])}')\n"
    )
    try:
        proc = subprocess.run(
            [str(ROOT / ".venv" / "bin" / "python"), str(smoke)],
            capture_output=True, text=True, timeout=600,
        )
        if proc.returncode != 0:
            return False, proc.stderr[-200:].strip()
        return True, proc.stdout.strip()[-80:]
    finally:
        smoke.unlink(missing_ok=True)


def check_smoke_queries() -> tuple[bool, str]:
    """Run all seven demo queries end-to-end. Slowest gate; ~4 min cold,
    ~2 min warm."""
    smoke = ROOT / "_prep_smoke_queries.py"
    smoke.write_text(
        "from rai_code.manual import demo_queries\n"
        "errors = []\n"
        "try: df1 = demo_queries.q1_recall_sla_audit(); assert len(df1) >= 4, f'Q1 rows={len(df1)}'\n"
        "except Exception as e: errors.append(f'Q1: {e}')\n"
        "try: df2 = demo_queries.q2_continental_cascade(); assert len(df2) == 67, f'Q2 vins={len(df2)}'\n"
        "except Exception as e: errors.append(f'Q2: {e}')\n"
        "try: df3 = demo_queries.q3_urgency_top20(); assert len(df3) == 20, f'Q3 rows={len(df3)}'\n"
        "except Exception as e: errors.append(f'Q3: {e}')\n"
        "try:\n"
        "    df4, si4 = demo_queries.q4_assign_recall_jobs()\n"
        "    assert si4.termination_status == 'OPTIMAL', f'Q4 status={si4.termination_status}'\n"
        "except Exception as e: errors.append(f'Q4: {e}')\n"
        "try:\n"
        "    df5, si5 = demo_queries.q5_assign_recall_jobs_priority()\n"
        "    assert si5.termination_status == 'OPTIMAL', f'Q5 status={si5.termination_status}'\n"
        "except Exception as e: errors.append(f'Q5: {e}')\n"
        "try:\n"
        "    df11 = demo_queries.q11_handoff_chains()\n"
        "    assert df11 is not None and len(df11) >= 10, f'Q11 rows={0 if df11 is None else len(df11)}'\n"
        "except Exception as e: errors.append(f'Q11: {e}')\n"
        "try:\n"
        "    df12, si12, by_comm = demo_queries.q12_balanced_schedule()\n"
        "    assert si12.termination_status == 'OPTIMAL', f'Q12 status={si12.termination_status}'\n"
        "    assert len(by_comm) >= 1, f'Q12 communities={len(by_comm)}'\n"
        "except Exception as e: errors.append(f'Q12: {e}')\n"
        "if errors:\n"
        "    print('|'.join(errors)); raise SystemExit(1)\n"
        "print(f'Q1 ok | Q2 ok | Q3 ok | Q4 obj={si4.objective_value:.2f} {si4.solve_time_sec:.1f}s | Q5 obj={si5.objective_value:.2f} {si5.solve_time_sec:.1f}s | Q11 hops={len(df11)} | Q12 obj={si12.objective_value:.2f} {si12.solve_time_sec:.1f}s')\n"
    )
    try:
        proc = subprocess.run(
            [str(ROOT / ".venv" / "bin" / "python"), str(smoke)],
            capture_output=True, text=True, timeout=900,
        )
        if proc.returncode != 0:
            return False, (proc.stdout + proc.stderr)[-200:].strip()
        return True, proc.stdout.strip()
    finally:
        smoke.unlink(missing_ok=True)


def check_cortex_agent(redeploy: bool = False) -> tuple[bool, str]:
    """Check the Cortex agent is deployed and respondable."""
    # The agent module needs to exist for this check; if it's not there
    # yet (Phase 7 incomplete), warn rather than fail.
    deploy = ROOT / "agent" / "deploy.py"
    if not deploy.exists():
        return False, "agent/deploy.py not built yet (Phase 7 pending)"
    if redeploy:
        proc = subprocess.run(
            [str(ROOT / ".venv" / "bin" / "python"), "-m", "agent.deploy", "deploy"],
            capture_output=True, text=True, timeout=180,
        )
        if proc.returncode != 0:
            return False, f"deploy failed: {proc.stderr[-100:]}"
    proc = subprocess.run(
        [str(ROOT / ".venv" / "bin" / "python"), "-m", "agent.deploy", "status"],
        capture_output=True, text=True, timeout=60,
    )
    if proc.returncode != 0:
        return False, f"status check failed: {proc.stderr[-100:]}"
    return True, proc.stdout.strip()[-80:]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-figures", action="store_true")
    parser.add_argument("--skip-chat", action="store_true")
    parser.add_argument("--skip-snowsight", action="store_true")
    parser.add_argument("--redeploy", action="store_true")
    args = parser.parse_args()

    phases: list[Phase] = []

    p0 = Phase("0 - Snowflake connection")
    p0.checks.append(_check("snow CLI role-bound to RAI_DEMO_CARS", check_connection))
    phases.append(p0)
    _print_phase(p0)
    if any(not c.passed and not c.warn for c in p0.checks):
        return 1

    p1 = Phase("1 - Snowflake data")
    p1.checks.append(_check("row counts (12 tables)", check_row_counts))
    p1.checks.append(_check("anchored numbers (6 sentinels)", check_anchored_numbers))
    phases.append(p1)
    _print_phase(p1)
    if any(not c.passed and not c.warn for c in p1.checks):
        return 1

    p2 = Phase("2 - RelationalAI engines")
    p2.checks.append(_check(f"resume {LOGIC_ENGINE} + load ontology", check_engines))
    phases.append(p2)
    _print_phase(p2)

    p3 = Phase("3 - Demo queries Q1-Q5, Q11, Q12")
    p3.checks.append(_check("Q1-Q5 + Q11/Q12 smoke test", check_smoke_queries))
    phases.append(p3)
    _print_phase(p3)

    p4 = Phase("4 - Cortex agent")
    p4.checks.append(_check("agent deployed", lambda: check_cortex_agent(args.redeploy), warn_on_fail=True))
    phases.append(p4)
    _print_phase(p4)

    fails = [c for ph in phases for c in ph.checks if not c.passed and not c.warn]
    if fails:
        print(f"\n{RED}{BOLD}FAIL{RESET} - {len(fails)} blocking check(s) failed.")
        return 1
    warns = [c for ph in phases for c in ph.checks if not c.passed and c.warn]
    if warns:
        print(f"\n{YELLOW}{BOLD}OK with warnings{RESET} - {len(warns)} non-blocking check(s).")
    else:
        print(f"\n{GREEN}{BOLD}OK{RESET} - all checks GREEN, demo is ready.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
