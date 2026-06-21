#!/usr/bin/env python3
"""
wrench-voice CLI
================
Command-line interface for the wrench-voice mechanic assistant.

Commands
--------
diagnose    Run a diagnostic query interactively or from args
parts       Look up part availability and pricing
plan        Plan parts for a pending job
kb          Search the knowledge base
serve       Start a lightweight local voice gateway (future)
"""

import sys
from pathlib import Path

# Ensure src/ is on path for local development
sys.path.insert(0, str(Path(__file__).parent.parent))

import click


@click.group()
@click.version_option(version="0.1.0")
def main() -> None:
    """Wrench Voice — combustion engine repair assistant."""
    pass


@main.command()
@click.argument("symptom")
@click.option("--make", "-m", help="Vehicle make (e.g. Toyota)")
@click.option("--model", "-M", help="Vehicle model (e.g. Camry)")
@click.option("--engine", "-e", help="Engine code or displacement (e.g. 2.2L)")
@click.option("--year", "-y", type=int, help="Model year")
def diagnose(symptom: str, make: str | None, model: str | None, engine: str | None, year: int | None) -> None:
    """Diagnose a symptom."""
    from wrench_voice.diagnostic_engine import DiagnosticEngine

    diag = DiagnosticEngine()
    results = diag.diagnose(
        symptom_slug=symptom,
        make=make,
        model=model,
        engine=engine,
        year=year,
    )
    click.echo(results.to_markdown())


@main.command()
@click.argument("part_name")
@click.option("--make", "-m", help="Vehicle make")
@click.option("--year", "-y", type=int, help="Model year")
@click.option("--engine", "-e", help="Engine code")
def parts(part_name: str, make: str | None, year: int | None, engine: str | None) -> None:
    """Look up part availability and pricing."""
    from wrench_voice.parts_finder import PartsFinder

    finder = PartsFinder()
    results = finder.lookup(part_name, make=make, year=year, engine=engine)
    for r in results:
        click.echo(f"{r.supplier}: {r.part_number} — ${r.price:.2f}  ({r.availability})")


@main.command()
@click.argument("job_file", type=click.Path(exists=True, path_type=Path))
def plan(job_file: Path) -> None:
    """Plan parts for a pending job described in a YAML or JSON file."""
    from wrench_voice.parts_planner import PartsPlanner

    planner = PartsPlanner()
    plan_result = planner.plan_from_file(job_file)
    click.echo(plan_result.to_markdown())


@main.command()
@click.argument("query")
def kb(query: str) -> None:
    """Search the knowledge base for procedures, specs, or torque values."""
    from wrench_voice.kb import KnowledgeBase

    kbase = KnowledgeBase()
    results = kbase.search(query)
    for r in results[:10]:
        click.echo(f"{r.score:.2f}  {r.title}\n    {r.snippet}\n")


@main.command()
@click.option("--port", "-p", default="/dev/ttyUSB0", help="OBD adapter serial port")
@click.option("--mock", is_flag=True, help="Simulate OBD data (no adapter needed)")
def obd(port: str, mock: bool) -> None:
    """Perform an OBD-II scan: read codes, freeze frame, readiness, live data."""
    from wrench_voice.obd_bridge import OBDBridge

    finder = OBDBridge(port=port, mock_mode=mock)
    result = finder.full_scan()
    click.echo(result.to_markdown())


if __name__ == "__main__":
    main()
