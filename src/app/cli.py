import asyncio
import json
from pathlib import Path
import typer
from rich.console import Console
from rich.table import Table

from .config import default_settings, Settings
from .io import read_json, write_json
from .core import run_discovery, build_prd, plan_oag, execute_plan

app = typer.Typer(help="Plugah Orchestrator CLI")
console = Console()

def _load_answers(path: Path) -> list[str]:
    if not path.exists():
        return []
    data = json.loads(path.read_text())
    if isinstance(data, list):
        return [str(x) for x in data]
    raise typer.BadParameter("answers.json must contain a JSON array of strings")

@app.command()
def init(
    problem: str = typer.Option(None, help="Project prompt/problem statement"),
    budget: float = typer.Option(None, help="Hard budget cap in USD"),
):
    """
    Start discovery and write questions.json.
    """
    cfg: Settings = default_settings()
    if problem: cfg.problem = problem
    if budget is not None: cfg.budget_hard_cap_usd = budget

    console.rule("[bold]Discovery: Startup Phase[/bold]")
    questions = asyncio.run(run_discovery(cfg.problem, cfg.budget_hard_cap_usd))
    console.print(f"[green]Wrote[/green] questions.json with {len(questions)} questions.")

@app.command()
def plan(
    answers_file: Path = typer.Option(Path("answers.json"), help="Path to discovery answers JSON array"),
    problem: str = typer.Option(None, help="Override problem statement"),
    budget: float = typer.Option(None, help="Override budget hard cap"),
):
    """
    Build PRD from answers, then plan OAG. Writes prd.json and oag.json.
    """
    cfg: Settings = default_settings()
    if problem: cfg.problem = problem
    if budget is not None: cfg.budget_hard_cap_usd = budget

    answers = _load_answers(answers_file)
    if not answers:
        console.print("[yellow]No answers found; provide answers.json with an array of strings.[/yellow]")

    console.rule("[bold]PRD Generation[/bold]")
    prd = asyncio.run(build_prd(answers, cfg.problem, cfg.budget_hard_cap_usd))
    console.print("[green]Wrote[/green] prd.json")

    console.rule("[bold]Organization Planning (OAG)[/bold]")
    oag = asyncio.run(plan_oag(prd, cfg.budget_hard_cap_usd))
    console.print("[green]Wrote[/green] oag.json (Organizational Agent Graph)")

@app.command()
def run():
    """
    Execute the planned work and print a cost summary. Writes results.json.
    """
    console.rule("[bold]Execution[/bold]")
    results = asyncio.run(execute_plan())
    total_cost = results.get("total_cost", 0.0)

    table = Table(title="Execution Summary")
    table.add_column("Metric")
    table.add_column("Value")
    table.add_row("total_cost", f"${total_cost:,.2f}")
    console.print(table)
    console.print("[green]Wrote[/green] results.json")

@app.command()
def quickstart(
    problem: str = typer.Option("Build a Slack summarizer bot", help="Problem statement"),
    budget: float = typer.Option(100.0, help="Budget hard cap (USD)"),
    auto_answers: bool = typer.Option(True, help="Generate simple canned answers for demo"),
):
    """
    One-shot demo: discovery → PRD → OAG → execution (non-interactive).
    """
    console.rule("[bold]Quickstart[/bold]")

    # Discovery
    questions = asyncio.run(run_discovery(problem, budget))
    if auto_answers:
        answers = [f"Auto-answer {i+1}: {q[:60]}" for i, q in enumerate(questions)]
        write_json("answers.json", answers)
    else:
        answers = _load_answers(Path("answers.json"))

    # PRD
    prd = asyncio.run(build_prd(answers, problem, budget))
    # OAG
    _ = asyncio.run(plan_oag(prd, budget))
    # Execute
    results = asyncio.run(execute_plan())

    total_cost = results.get("total_cost", 0.0)
    console.print(f"[bold green]Project complete![/bold green] Total cost: ${total_cost:,.2f}")

if __name__ == "__main__":
    app()
