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
        help="PDF files and/or BibTeX files to process (optional when using Semantic Scholar)",
    ),
    no_clear: bool = typer.Option(
        False,
        "--no-clear",
        help="Do not clear output files before processing (append mode)",
    ),
    no_pdf_download: bool = typer.Option(
        False,
        "--no-pdf-download",
        help="Disable automatic PDF downloading for missing files and use context url instead",
    ),
    save_state: Optional[Path] = typer.Option(
        None,
        "--save-state",
        help="Save process state to specified file",
    ),
    load_state: Optional[Path] = typer.Option(
        None,
        "--load-state",
        help="Load and resume from saved state file",
    ),
    resume: bool = typer.Option(
        False,
        "--resume",
        help="Resume from default state file (ask_llm_state.json)",
    ),
    query_file: Optional[Path] = typer.Option(
        None,
        "--query-file",
        help="Override query file (default: query.md)",
    ),
    report: Optional[Path] = typer.Option(
        None,
        "--report",
        help="Override report output file (default: analysis_report.json and analysis_report.csv)",
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
    """Process PDF files and BibTeX bibliographies using the Gemini API.

    Files are optional when using Semantic Scholar queries. You can run with just
    a query file that contains semantic-scholar: true parameters.
    """

    # If no subcommand was invoked, process files or run semantic scholar queries
    if ctx.invoked_subcommand is None:
        # Check if we have a query file to determine if Semantic Scholar queries might be present
        query_file_path = query_file or Path("query.md")

        # If no files provided, check if we have Semantic Scholar queries
        if not files:
            if not query_file_path.exists():
                console.print(
                    "Error: No files provided and no query file found.\n"
                    "Either provide input files or create a query.md file with semantic-scholar queries.",
                    style="bold red",
                )
                console.print(
                    "\nExample query.md for Semantic Scholar:\n"
                    "semantic-scholar: true\n"
                    "limit: 10\n\n"
                    "Find papers about machine learning",
                    style="dim",
                )
                raise typer.Exit(1)
            else:
                # Check if the query file contains Semantic Scholar queries
                try:
                    with open(query_file_path, "r", encoding="utf-8") as f:
                        query_content = f.read()

                    if "semantic-scholar:" not in query_content.lower():
                        console.print(
                            "Error: No files provided and no Semantic Scholar queries found in query file.\n"
                            "Either provide input files or add 'semantic-scholar: true' to your queries.",
                            style="bold red",
                        )
                        console.print(
                            "\nExample query for Semantic Scholar:\n"
                            "semantic-scholar: true\n"
                            "limit: 10\n\n"
                            "Find papers about machine learning",
                            style="dim",
                        )
                        raise typer.Exit(1)
                    else:
                        if verbose:
                            console.print(
                                "[DEBUG] No input files provided, but Semantic Scholar queries found. Proceeding with Semantic Scholar only.",
                                style="dim",
                            )
                        files = []  # Set files to empty list for processing

                except Exception as e:
                    console.print(
                        f"Error reading query file {query_file_path}: {e}",
                        style="bold red",
                    )
                    raise typer.Exit(1)
        else:
            # Validate that provided files exist
            for file in files:
                if not file.exists():
                    console.print(
                        f"Error: File does not exist: {file}", style="bold red"
                    )
                    raise typer.Exit(1)

        if verbose:
            console.print("[DEBUG] Starting ask-llm with verbose output", style="dim")
            if files:
                console.print(f"[DEBUG] Processing {len(files)} files", style="dim")
            else:
                console.print(
                    "[DEBUG] Running with Semantic Scholar queries only", style="dim"
                )
            if no_pdf_download:
                console.print("[DEBUG] PDF download disabled", style="dim")

        # Convert Path objects to strings for compatibility (files might be empty)
        file_paths = [str(f) for f in files] if files else []

        # Create simplified CLIAnalyzer
        class CLIAnalyzer(DocumentAnalyzer):
            def __init__(self):
                # Prepare config overrides
                config_overrides = {}
                if query_file:
                    config_overrides["query_file"] = str(query_file)
                if api_key:
                    config_overrides["api_key"] = api_key
                if api_key_command:
                    config_overrides["api_key_command"] = api_key_command
                if base_url:
                    config_overrides["base_url"] = base_url

                # Pass no_pdf_download option to parent constructor
                auto_download_pdfs = not no_pdf_download
                super().__init__(
                    verbose=verbose,
                    auto_download_pdfs=auto_download_pdfs,
                    **config_overrides,
                )

                # Handle state loading
                state_loaded = False
                if load_state:
                    state_loaded = self.load_state(str(load_state))
                    if state_loaded:
                        if verbose:
                            console.print(
                                f"[DEBUG] Loaded state from: {load_state}", style="dim"
                            )
                    else:
                        console.print(
                            f"Warning: Could not load state from {load_state}",
                            style="yellow",
                        )
                elif resume:
                    state_loaded = self.load_state()
                    if state_loaded:
                        if verbose:
                            console.print(
                                "[DEBUG] Resumed from default state file", style="dim"
                            )
                    else:
                        console.print(
                            "Warning: Could not resume from default state file",
                            style="yellow",
                        )

                # Apply remaining CLI overrides that aren't handled by ConfigManager
                if base_url:
                    self.api_client.base_url = base_url
                    if verbose:
                        console.print(
                            f"[DEBUG] Base URL overridden to: {base_url}", style="dim"
                        )

                if report:
                    report_str = str(report)
                    if report_str.endswith(".csv"):
                        self.csv_report_file = report_str
                        self.json_report_file = report_str.replace(".csv", ".json")
                    elif report_str.endswith(".json"):
                        self.json_report_file = report_str
                        self.csv_report_file = report_str.replace(".json", ".csv")
                    else:
                        self.json_report_file = report_str + ".json"
                        self.csv_report_file = report_str + ".csv"

                    if verbose:
                        console.print(
                            f"[DEBUG] Report files overridden to: {self.json_report_file} and {self.csv_report_file}",
                            style="dim",
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

                # Handle no_clear option - only if no state was loaded
                if not state_loaded and no_clear:
                    # Load existing JSON if it exists
                    if os.path.exists(self.json_report_file):
                        try:
                            with open(
                                self.json_report_file, "r", encoding="utf-8"
                            ) as f:
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

            def process_files_with_state_saving(self, file_paths, save_state_file=None):
                """Process files with automatic state saving"""
                try:
                    # Process files normally
                    self.process_files(file_paths)

                    # Save final state if requested
                    if save_state_file:
                        self.save_state(str(save_state_file))
                        console.print(
                            f"💾 Final state saved to: {save_state_file}",
                            style="bold blue",
                        )

                except Exception:
                    # Save state even on error for recovery
                    if save_state_file:
                        error_state_file = str(save_state_file).replace(
                            ".json", "_error.json"
                        )
                        self.save_state(error_state_file)
                        console.print(
                            f"💾 Error state saved to: {error_state_file}",
                            style="bold yellow",
                        )
                    raise

        try:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                if files:
                    task = progress.add_task("Processing files...", total=None)
                else:
                    task = progress.add_task(
                        "Processing Semantic Scholar queries...", total=None
                    )

                analyzer = CLIAnalyzer()
                if save_state:
                    analyzer.process_files_with_state_saving(file_paths, save_state)
                else:
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
