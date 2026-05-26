"""Deploy the cars manual ontology as a Snowflake Intelligence agent.

Run from project root:

    .venv/bin/python -m agent.deploy preflight                   # probe grants
    .venv/bin/python -m agent.deploy setup-sql                   # emit GRANTs
    .venv/bin/python -m agent.deploy deploy                      # create
    .venv/bin/python -m agent.deploy update                      # refresh sprocs
    .venv/bin/python -m agent.deploy status
    .venv/bin/python -m agent.deploy chat "How many SLA-breached recalls do we have?"
    .venv/bin/python -m agent.deploy teardown

The agent is registered at SNOWFLAKE_INTELLIGENCE.AGENTS.cars so it
appears in Snowsight's Snowflake Intelligence picker. Stored procedures
and the dependency stage live in CARS_DEMO.RAI_AGENT.

If `preflight` reports missing grants, run `setup-sql` as ACCOUNTADMIN
(rai profile default), apply the GRANT block it prints, then re-run
`preflight` until it passes, then `deploy`.
"""
import argparse

from snowflake import snowpark

from relationalai.agent.cortex import (
    CortexAgentManager,
    DeploymentConfig,
    QueryCatalog,
    ToolRegistry,
    discover_imports,
)
from relationalai.config import SnowflakeConnection, create_config


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
AGENT_NAME = "cars"
DATABASE = "CARS_DEMO"
SCHEMA = "RAI_AGENT"
# Place the agent directly in the Snowflake Intelligence schema so it
# appears in the SI picker. The stored procedures still live in
# CARS_DEMO.RAI_AGENT (per `database`+`schema`).
AGENT_SCHEMA = "SNOWFLAKE_INTELLIGENCE.AGENTS"
WAREHOUSE = "RAI_XS"


def _agent_location() -> str:
    return AGENT_SCHEMA or f"{DATABASE}.{SCHEMA}"


def _build_manager() -> CortexAgentManager:
    session: snowpark.Session = create_config().get_session(SnowflakeConnection)
    session.sql(f"CREATE SCHEMA IF NOT EXISTS {DATABASE}.{SCHEMA}").collect()
    return CortexAgentManager(
        session=session,
        config=DeploymentConfig(
            agent_name=AGENT_NAME,
            database=DATABASE,
            schema=SCHEMA,
            agent_schema=AGENT_SCHEMA,
            warehouse=WAREHOUSE,
            allow_preview=True,  # required for QueryCatalog (PREVIEW)
        ),
    )


# ---------------------------------------------------------------------------
# init_tools - executed inside each sproc invocation.
# ---------------------------------------------------------------------------
def init_tools():
    from rai_code.manual import cars, demo_queries

    from . import queries

    return ToolRegistry().add(
        model=cars.model,
        description=(
            "OEM recall propagation: vehicles, owners, service centres, "
            "suppliers, parts, BOM, 5 recall campaigns (IBS, HVB, EGR, "
            "AIRBAG, STARTER), and a 4-week scheduling MIP. Answers SLA "
            "audit, supplier cascade, urgency ranking, and recall-job "
            "assignment with an operator-added priority rule. "
            "CHART HINTS: '*_chart' queries return chart_hint dicts - "
            "tell the user to click Snowsight's chart icon to render as "
            "{chart_hint.type} of {chart_hint.y} by {chart_hint.x}."
        ),
        queries=QueryCatalog(
            queries.recall_sla_audit_by_campaign,
            queries.recall_sla_audit_by_campaign_chart,
            queries.recall_sla_audit_by_centre,
            queries.recall_sla_audit_by_centre_chart,
            queries.continental_cascade_full,
            queries.continental_cascade_regional_chart,
            queries.continental_cascade_centres_chart,
            queries.urgency_top20,
            queries.urgency_top20_chart,
            queries.schedule_recall_jobs,
            queries.schedule_recall_jobs_chart,
            queries.schedule_recall_jobs_priority,
            queries.schedule_recall_jobs_priority_chart,
            queries.vehicle_cohort_communities,
            queries.vehicle_cohort_communities_chart,
        ),
    )


# ---------------------------------------------------------------------------
# CLI commands
# ---------------------------------------------------------------------------
def cmd_deploy(manager: CortexAgentManager) -> None:
    print(
        f"Deploying sprocs to {DATABASE}.{SCHEMA} "
        f"and agent {AGENT_NAME} to {_agent_location()} ..."
    )
    manager.deploy(
        init_tools=init_tools,
        imports=discover_imports(),
        extra_packages=["httpx"],
    )
    print(manager.status())


def cmd_update(manager: CortexAgentManager) -> None:
    print(f"Updating stored procedures for {AGENT_NAME} ...")
    manager.update(
        init_tools=init_tools,
        imports=discover_imports(),
        extra_packages=["httpx"],
    )
    print(manager.status())


def cmd_status(manager: CortexAgentManager) -> None:
    print(manager.status())


def cmd_chat(manager: CortexAgentManager, message: str) -> None:
    chat = manager.chat()
    response = chat.send(message)
    print(response.full_text())


def cmd_teardown(manager: CortexAgentManager) -> None:
    print(
        f"Tearing down agent {AGENT_NAME} from {_agent_location()} "
        f"and sprocs from {DATABASE}.{SCHEMA} ..."
    )
    print("WARNING: this permanently deletes SI conversation history.")
    manager.cleanup()
    print(manager.status())


def cmd_preflight(manager: CortexAgentManager) -> None:
    """Probe deploy-time grants without creating resources. Surfaces
    missing privileges with a paste-ready fix block."""
    report = manager.preflight(init_tools=init_tools)
    print(report.format(config=manager.config))


def cmd_setup_sql(manager: CortexAgentManager, deployer_role: str, si_role: str) -> None:
    """Emit a paste-ready GRANT block for the deployer and SI-user
    roles. Run as ACCOUNTADMIN."""
    manager.print_setup_sql(deployer_role=deployer_role, si_role=si_role)


def main() -> None:
    parser = argparse.ArgumentParser(description="Manage the cars Cortex agent lifecycle.")
    sub = parser.add_subparsers(dest="command")
    sub.required = True

    sub.add_parser("deploy", help="Create schema, stage, sprocs, and agent")
    sub.add_parser("update", help="Update sprocs without re-registering the agent")
    sub.add_parser("status", help="Print deployment status")
    sub.add_parser("preflight", help="Probe grants without deploying")

    setup_p = sub.add_parser("setup-sql", help="Emit a paste-ready GRANT block")
    setup_p.add_argument("--deployer-role", default="RAI_DEMO_CARS")
    setup_p.add_argument("--si-role", default="RAI_DEMO_CARS")

    chat_p = sub.add_parser("chat", help="Send a message to the deployed agent")
    chat_p.add_argument("message", help="Message to send")

    sub.add_parser("teardown", help="Remove all agent resources")

    args = parser.parse_args()
    manager = _build_manager()

    commands = {
        "deploy": lambda: cmd_deploy(manager),
        "update": lambda: cmd_update(manager),
        "status": lambda: cmd_status(manager),
        "chat": lambda: cmd_chat(manager, args.message),
        "teardown": lambda: cmd_teardown(manager),
        "preflight": lambda: cmd_preflight(manager),
        "setup-sql": lambda: cmd_setup_sql(manager, args.deployer_role, args.si_role),
    }
    commands[args.command]()


if __name__ == "__main__":
    main()
