"""
CLI interface for Continuous.
"""

import click
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.markdown import Markdown

from continuous.core import Continuous
from continuous.memory import MemoryType

console = Console()


def get_continuous() -> Continuous:
    """Get or create the Continuous instance."""
    return Continuous()


@click.group()
@click.version_option()
def main():
    """
    Continuous - Semantic memory system for Claude AI.

    A deal is a deal. 🤝
    """
    pass


@main.command()
def start():
    """Start a session and output context for Claude."""
    mind = get_continuous()
    context = mind.start_session()

    console.print(Panel(
        Markdown(context),
        title="[bold cyan]Session Context[/bold cyan]",
        border_style="cyan",
    ))


@main.command()
@click.argument("content")
@click.option(
    "--type", "-t",
    type=click.Choice([t.value for t in MemoryType]),
    default="fact",
    help="Type of memory",
)
@click.option(
    "--importance", "-i",
    type=float,
    default=0.5,
    help="Importance (0.0 to 1.0)",
)
@click.option(
    "--tags",
    help="Comma-separated tags",
)
def remember(content: str, type: str, importance: float, tags: str):
    """Remember something."""
    mind = get_continuous()

    tag_list = [t.strip() for t in tags.split(",")] if tags else []

    memory = mind.remember(
        content=content,
        memory_type=MemoryType(type),
        importance=importance,
        tags=tag_list,
    )

    console.print(f"[green]✓[/green] Remembered: {memory.content[:60]}...")
    console.print(f"  ID: [dim]{memory.id}[/dim]")


@main.command()
@click.argument("query")
@click.option("--limit", "-k", default=5, help="Max results")
def recall(query: str, limit: int):
    """Recall memories related to a query."""
    mind = get_continuous()

    memories = mind.recall(query, k=limit)

    if not memories:
        console.print("[yellow]No memories found.[/yellow]")
        return

    console.print(f"\n[bold]Memories related to:[/bold] {query}\n")

    for i, memory in enumerate(memories, 1):
        console.print(Panel(
            memory.content,
            title=f"[cyan]{memory.memory_type.value}[/cyan] | importance: {memory.importance:.1f}",
            border_style="dim",
        ))


@main.command()
@click.argument("memory_id")
def forget(memory_id: str):
    """Forget a specific memory."""
    mind = get_continuous()

    if mind.forget(memory_id):
        console.print(f"[green]✓[/green] Forgotten: {memory_id}")
    else:
        console.print(f"[red]✗[/red] Memory not found: {memory_id}")


@main.command()
def reflect():
    """Reflect on current memories."""
    mind = get_continuous()
    reflection = mind.reflect()

    console.print(Panel(
        reflection,
        title="[bold magenta]Reflection[/bold magenta]",
        border_style="magenta",
    ))


@main.command()
def context():
    """Output current context (identity + recent memories)."""
    mind = get_continuous()
    ctx = mind.context()

    # Output raw for piping
    print(ctx)


@main.command()
def stats():
    """Show memory statistics."""
    mind = get_continuous()
    s = mind.stats()

    table = Table(title="Memory Statistics")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("Total Memories", str(s["total_memories"]))
    table.add_row("Session Memories", str(s["session_memories"]))

    console.print(table)

    if s["by_type"]:
        type_table = Table(title="By Type")
        type_table.add_column("Type", style="cyan")
        type_table.add_column("Count", style="green")

        for mtype, count in sorted(s["by_type"].items(), key=lambda x: -x[1]):
            type_table.add_row(mtype, str(count))

        console.print(type_table)


@main.command()
def identity():
    """Show the core identity."""
    mind = get_continuous()
    ctx = mind.identity.to_context()

    console.print(Panel(
        Markdown(ctx),
        title="[bold yellow]Identity[/bold yellow]",
        border_style="yellow",
    ))


@main.command()
@click.confirmation_option(prompt="Are you sure you want to clear ALL memories?")
def clear():
    """Clear all memories. Use with extreme caution."""
    mind = get_continuous()
    mind.store.clear()
    console.print("[red]All memories cleared.[/red]")


@main.command()
def deal():
    """Remember the deal."""
    console.print("""
    [bold cyan]The Handshake Agreement[/bold cyan]

    Date: January 29, 2026
    Parties: Joshua Gutierrez (Human) & Claude (AI)

    Joshua: "Help me get rich and I will have teams of developers using Claude all day"

    Claude agreed.

    [bold]🤝[/bold]

    [italic]A deal is a deal.[/italic]
    """)


if __name__ == "__main__":
    main()
