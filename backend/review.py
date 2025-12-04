"""Review and export transcripts."""

import argparse
from rich.console import Console
from rich.table import Table
from storage import get_all_transcripts, export_corpus, get_uncleaned_transcripts

console = Console()


def show_transcripts(cleaned_only: bool = False, limit: int = 50):
    """Display transcripts in a table."""
    transcripts = get_all_transcripts(cleaned_only=cleaned_only)

    if not transcripts:
        console.print("[yellow]No transcripts found.[/yellow]")
        return

    # Limit display
    if len(transcripts) > limit:
        transcripts = transcripts[-limit:]
        console.print(f"[dim]Showing last {limit} of {len(transcripts)} transcripts[/dim]\n")

    table = Table(title="Transcripts")
    table.add_column("ID", style="dim", width=6)
    table.add_column("Time", style="cyan", width=20)
    table.add_column("Raw Text", width=40)
    table.add_column("Cleaned", width=40)

    for id_, timestamp, raw_text, cleaned_text in transcripts:
        # Truncate long text
        raw_display = (raw_text[:37] + "...") if len(raw_text) > 40 else raw_text
        cleaned_display = ""
        if cleaned_text:
            cleaned_display = (cleaned_text[:37] + "...") if len(cleaned_text) > 40 else cleaned_text

        # Format timestamp
        time_short = timestamp[11:19] if len(timestamp) > 19 else timestamp

        table.add_row(str(id_), time_short, raw_display, cleaned_display)

    console.print(table)


def show_stats():
    """Show corpus statistics."""
    all_transcripts = get_all_transcripts()
    uncleaned = get_uncleaned_transcripts(limit=10000)

    total = len(all_transcripts)
    uncleaned_count = len(uncleaned)
    cleaned_count = total - uncleaned_count

    # Word counts
    raw_words = sum(len(t[2].split()) for t in all_transcripts if t[2])
    cleaned_words = sum(len(t[3].split()) for t in all_transcripts if t[3])

    console.print("\n[bold]Corpus Statistics[/bold]")
    console.print(f"  Total segments: {total}")
    console.print(f"  Cleaned: {cleaned_count}")
    console.print(f"  Uncleaned: {uncleaned_count}")
    console.print(f"  Raw word count: {raw_words}")
    console.print(f"  Cleaned word count: {cleaned_words}")
    console.print()


def do_export(output: str = "corpus.txt", use_cleaned: bool = True):
    """Export corpus to file."""
    path = export_corpus(output, use_cleaned)
    console.print(f"[green]✓ Exported to {path}[/green]")


def main():
    parser = argparse.ArgumentParser(description="Review and export transcripts")
    parser.add_argument("--cleaned", "-c", action="store_true", help="Show only cleaned transcripts")
    parser.add_argument("--limit", "-l", type=int, default=50, help="Max transcripts to display")
    parser.add_argument("--export", "-e", type=str, help="Export to file")
    parser.add_argument("--stats", "-s", action="store_true", help="Show statistics")
    parser.add_argument("--raw", "-r", action="store_true", help="Export raw (uncleaned) text")

    args = parser.parse_args()

    if args.stats:
        show_stats()
    elif args.export:
        do_export(args.export, use_cleaned=not args.raw)
    else:
        show_transcripts(cleaned_only=args.cleaned, limit=args.limit)
        show_stats()


if __name__ == "__main__":
    main()
