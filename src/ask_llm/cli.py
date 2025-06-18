#!/usr/bin/env python3

import os
import json
from typing import List, Optional
from pathlib import Path

import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from .analyzer import DocumentAnalyzer

app = typer.Typer(
    name="ask-llm",
    help="Process PDF files and BibTeX bibliographies using the Gemini API with structured output.",
    add_completion=False,
)
console = Console()


@app.command()
def main(
    files: List[Path] = typer.Argument(
        ...,
        help="PDF files and/or BibTeX files to process",
        exists=True,
    ),
    no_clear: bool = typer.Option(
        False,
        "--no-clear",
        help="Do not clear output files before processing (append mode)",
    ),
    model: Optional[str] = typer.Option(
        None,
        "--model",
        help="Override Gemini model (default: gemini-2.5-flash-preview-05-20)",
    ),
    query: Optional[str] = typer.Option(
        None,
        "--query",
        help="Override query prompt (default: contents of query.txt)",
    ),
    report: Optional[Path] = typer.Option(
        None,
        "--report",
        help="Override report output file (default: analysis_report.json, use .csv extension for CSV format)",
    ),
    log: Optional[Path] = typer.Option(
        None,
        "--log",
        help="Override log output file (default: log.txt)",
    ),
    processed_list: Optional[Path] = typer.Option(
        None,
        "--processed-list",
        help="Override processed files list output (default: processed_files.txt)",
    ),
    google_search: bool = typer.Option(
        False,
        "--google-search",
        help="Enable Google Search grounding for all queries",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Enable verbose debug output",
    ),
) -> None:
    """Process PDF files and BibTeX bibliographies using the Gemini API."""

    if verbose:
        console.print("[DEBUG] Starting ask-llm with verbose output", style="dim")
        console.print(f"[DEBUG] Processing {len(files)} files", style="dim")

    # Convert Path objects to strings for compatibility
    file_paths = [str(f) for f in files]

    # Patch DocumentAnalyzer with CLI overrides
    class CLIAnalyzer(DocumentAnalyzer):
        def __init__(self):
            super().__init__(verbose=verbose)

            if model:
                self.model = model
                if verbose:
                    console.print(f"[DEBUG] Model overridden to: {model}", style="dim")

            if query:
                query_params = {}
                if google_search:
                    query_params["google_search"] = True
                self.queries = [
                    {"text": query, "params": query_params, "structure": None}
                ]
                if verbose:
                    console.print(
                        f"[DEBUG] Query overridden with {len(query_params)} parameters",
                        style="dim",
                    )
            elif google_search:
                # Enable Google Search for all queries if --google-search flag is used
                for query_obj in self.queries:
                    if "google_search" not in query_obj.params:
                        query_obj.params["google_search"] = True
                if verbose:
                    console.print(
                        "[DEBUG] Google Search enabled for all queries via CLI flag",
                        style="dim",
                    )

            if report:
                self.report_file = str(report)
                if verbose:
                    console.print(
                        f"[DEBUG] Report file overridden to: {report}", style="dim"
                    )

            if log:
                self.logfile = str(log)
                if verbose:
                    console.print(f"[DEBUG] Log file overridden to: {log}", style="dim")

            if processed_list:
                self.processed_list = str(processed_list)
                if verbose:
                    console.print(
                        f"[DEBUG] Processed list file overridden to: {processed_list}",
                        style="dim",
                    )

            if no_clear:
                # Load existing JSON if it exists
                if os.path.exists(self.report_file):
                    try:
                        with open(self.report_file, "r", encoding="utf-8") as f:
                            self.results = json.load(f)
                        if verbose:
                            console.print(
                                f"[DEBUG] Loaded existing JSON with {len(self.results['documents'])} documents",
                                style="dim",
                            )
                    except (json.JSONDecodeError, FileNotFoundError):
                        if verbose:
                            console.print(
                                "[DEBUG] Could not load existing JSON, starting fresh",
                                style="dim",
                            )
                        self._initialize_json_structure()
                else:
                    self._initialize_json_structure()

    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Processing files...", total=None)

            analyzer = CLIAnalyzer()
            analyzer.process_files(file_paths)

            progress.update(task, description="✅ Processing complete!")

        console.print("🎉 Processing completed successfully!", style="bold green")

    except KeyboardInterrupt:
        console.print("\n❌ Processing interrupted by user", style="bold red")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"❌ Error: {e}", style="bold red")
        if verbose:
            console.print_exception()
        raise typer.Exit(1)


@app.command()
def version():
    """Show version information."""
    console.print("ask-llm version 1.0.0", style="bold blue")


if __name__ == "__main__":
    app()
