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


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    files: List[Path] = typer.Argument(
        None,
        help="PDF files and/or BibTeX files to process",
    ),
    no_clear: bool = typer.Option(
        False,
        "--no-clear",
        help="Do not clear output files before processing (append mode)",
    ),
    query_file: Optional[Path] = typer.Option(
        None,
        "--query-file",
        help="Override query file (default: query.md)",
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
    api_key: Optional[str] = typer.Option(
        None,
        "--api-key",
        help="Override Gemini API key (default: from GEMINI_API_KEY env var)",
    ),
    api_key_command: Optional[str] = typer.Option(
        None,
        "--api-key-command",
        help="Override command to retrieve API key (default: rbw get gemini_key)",
    ),
    base_url: Optional[str] = typer.Option(
        None,
        "--base-url",
        help="Override Gemini API base URL (default: https://generativelanguage.googleapis.com/v1beta)",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Enable verbose debug output",
    ),
) -> None:
    """Process PDF files and BibTeX bibliographies using the Gemini API."""

    # If no subcommand was invoked and no files provided, show help
    if ctx.invoked_subcommand is None:
        if not files:
            console.print("Error: No files provided", style="bold red")
            raise typer.Exit(1)

        # Validate that files exist
        for file in files:
            if not file.exists():
                console.print(f"Error: File does not exist: {file}", style="bold red")
                raise typer.Exit(1)

        if verbose:
            console.print("[DEBUG] Starting ask-llm with verbose output", style="dim")
            console.print(f"[DEBUG] Processing {len(files)} files", style="dim")

        # Convert Path objects to strings for compatibility
        file_paths = [str(f) for f in files]

        # Patch DocumentAnalyzer with CLI overrides
        class CLIAnalyzer(DocumentAnalyzer):
            def __init__(self):
                super().__init__(verbose=verbose)

                # Override config settings with CLI options
                if api_key:
                    self.config.settings.api_key = api_key
                    if verbose:
                        console.print("[DEBUG] API key overridden via CLI", style="dim")

                if api_key_command:
                    self.config.settings.api_key_command = api_key_command
                    if verbose:
                        console.print(
                            f"[DEBUG] API key command overridden to: {api_key_command}",
                            style="dim",
                        )

                if base_url:
                    self.config.settings.base_url = base_url
                    self.api_client.base_url = base_url
                    if verbose:
                        console.print(
                            f"[DEBUG] Base URL overridden to: {base_url}", style="dim"
                        )

                if query_file:
                    self.config.settings.query_file = str(query_file)
                    # Reload queries with new file
                    self.queries = self.config.load_queries(str(query_file))
                    if verbose:
                        console.print(
                            f"[DEBUG] Query file overridden to: {query_file}",
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
                        console.print(
                            f"[DEBUG] Log file overridden to: {log}", style="dim"
                        )

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
                                self.report_manager.results = json.load(f)
                            if verbose:
                                console.print(
                                    f"[DEBUG] Loaded existing JSON with {len(self.report_manager.results['documents'])} documents",
                                    style="dim",
                                )
                        except (json.JSONDecodeError, FileNotFoundError):
                            if verbose:
                                console.print(
                                    "[DEBUG] Could not load existing JSON, starting fresh",
                                    style="dim",
                                )
                            self.report_manager.initialize_json_structure(
                                self.queries, "gemini-2.5-flash"
                            )
                    else:
                        self.report_manager.initialize_json_structure(
                            self.queries, "gemini-2.5-flash"
                        )

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
