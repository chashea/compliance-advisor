"""
CLI entrypoint for the Purview threat hunter.

Usage:
    purview-hunt ask "show me users who downgraded sensitivity labels this week"
    purview-hunt ask --template label-downgrade --days 7
    purview-hunt ask --kql "DataSecurityEvents | where ActionType == 'SensitivityLabelDowngraded' | limit 10"
    purview-hunt templates
    purview-hunt schema
"""

import json
import logging
import sys

import click
from rich.console import Console
from rich.markdown import Markdown
from rich.table import Table

from collector.hunter.config import HunterSettings
from collector.hunter.graph import HuntingQueryError
from collector.hunter.pipeline import HuntResult, hunt
from collector.hunter.schemas import ALL_TABLES, build_schema_prompt
from collector.hunter.templates import get_template, list_templates, render_template

console = Console()
log = logging.getLogger("hunter")


def _print_result(result: HuntResult, output_json: bool = False) -> None:
    """Print hunt results to the terminal."""
    if output_json:
        click.echo(
            json.dumps(
                {
                    "question": result.question,
                    "kql": result.kql,
                    "row_count": result.row_count,
                    "results": result.results,
                    "narrative": result.narrative,
                    "retries": result.retries,
                    "errors": result.errors,
                },
                indent=2,
                default=str,
            )
        )
        return

    # Question
    console.print(f"\n[bold]Question:[/bold] {result.question}")

    # KQL
    console.print("\n[bold]KQL Query:[/bold]")
    console.print(f"[dim]{result.kql}[/dim]")

    if result.retries > 0:
        console.print(f"\n[yellow]Query was retried {result.retries} time(s) due to errors.[/yellow]")

    # Results table
    console.print(f"\n[bold]Results:[/bold] {result.row_count} rows")

    if result.results:
        table = Table(show_lines=False, expand=False)
        headers = list(result.results[0].keys())
        for h in headers:
            table.add_column(h, overflow="fold")
        for row in result.results[:50]:
            table.add_row(*[str(row.get(h, "")) for h in headers])
        console.print(table)

    # Narrative
    if result.narrative:
        console.print("\n[bold]Analysis:[/bold]")
        console.print(Markdown(result.narrative))
    console.print()


@click.group()
def main():
    """AI-powered Purview threat hunting via Defender XDR Advanced Hunting."""


@main.command()
@click.argument("question", required=False)
@click.option("--template", "-t", help="Use a pre-built hunt template by name")
@click.option("--kql", help="Execute a raw KQL query directly")
@click.option("--days", type=int, default=None, help="Lookback window in days (default: 30, max: 30)")
@click.option("--limit", type=int, default=None, help="Maximum result rows (default: 50)")
@click.option("--no-narrate", is_flag=True, help="Skip AI narrative, just show KQL + results")
@click.option("--json-output", "output_json", is_flag=True, help="Output results as JSON")
@click.option("--verbose", "-v", is_flag=True, help="Enable debug logging")
def ask(
    question: str | None,
    template: str | None,
    kql: str | None,
    days: int | None,
    limit: int | None,
    no_narrate: bool,
    output_json: bool,
    verbose: bool,
):
    """Ask a natural language question, run a template, or execute raw KQL."""
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )

    if not question and not template and not kql:
        click.echo("Provide a question, --template, or --kql.", err=True)
        sys.exit(1)

    try:
        settings = HunterSettings()
    except Exception as e:
        click.echo(f"Configuration error: {e}", err=True)
        click.echo("Set AZURE_OPENAI_ENDPOINT in .env or environment.", err=True)
        sys.exit(1)

    if days is not None:
        settings.LOOKBACK_DAYS = min(days, 30)
    if limit is not None:
        settings.MAX_RESULTS = limit

    # Determine mode
    kql_override: str | None = None
    hunt_question: str

    if kql:
        kql_override = kql
        hunt_question = "Raw KQL query"
    elif template:
        tmpl = get_template(template)
        if not tmpl:
            available = ", ".join(t.name for t in list_templates())
            click.echo(f"Unknown template: {template}", err=True)
            click.echo(f"Available: {available}", err=True)
            sys.exit(1)
        kql_override = render_template(tmpl, days=settings.LOOKBACK_DAYS, limit=settings.MAX_RESULTS)
        hunt_question = tmpl.description
    else:
        hunt_question = question  # type: ignore[assignment]

    try:
        result = hunt(
            question=hunt_question,
            settings=settings,
            kql_override=kql_override,
            skip_narrate=no_narrate,
        )
        _print_result(result, output_json=output_json)
    except HuntingQueryError as e:
        click.echo(f"Hunting query error: {e}", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        if verbose:
            log.exception("Full traceback")
        sys.exit(1)


@main.command()
def templates():
    """List all available hunt templates."""
    table = Table(title="Hunt Templates", show_lines=False)
    table.add_column("Name", style="bold")
    table.add_column("Description")
    table.add_column("Table", style="dim")

    for t in list_templates():
        table.add_row(t.name, t.description, t.table)

    console.print(table)


@main.command()
@click.argument("table_name", required=False)
def schema(table_name: str | None):
    """Print table schemas used for hunting."""
    if table_name:
        matching = [t for t in ALL_TABLES if t["name"].lower() == table_name.lower()]
        if not matching:
            available = ", ".join(t["name"] for t in ALL_TABLES)
            click.echo(f"Unknown table: {table_name}. Available: {available}", err=True)
            sys.exit(1)
        for t in matching:
            console.print(f"\n[bold]{t['name']}[/bold]")
            console.print(f"[dim]{t['description']}[/dim]\n")
            tbl = Table(show_lines=False)
            tbl.add_column("Column", style="bold")
            tbl.add_column("Type")
            tbl.add_column("Description")
            for col in t["columns"]:
                tbl.add_row(col.name, col.type, col.description)
            console.print(tbl)
    else:
        console.print(Markdown(build_schema_prompt()))


if __name__ == "__main__":
    main()
