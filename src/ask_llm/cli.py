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
def process(
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

    State is automatically saved to ask_llm_state.json for recovery purposes.
    """

    # When using --resume, automatically enable --no-clear
    if resume:
        no_clear = True
        if verbose:
            console.print(
                "[DEBUG] --resume enabled, automatically setting --no-clear",
                style="dim",
            )

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
            console.print("[DEBUG] PDF download always enabled", style="dim")
            console.print(
                "[DEBUG] State saving enabled (ask_llm_state.json)", style="dim"
            )
            console.print(
                "[DEBUG] Using fallback search strategy (Google grounding with Qwant fallback)",
                style="dim",
            )

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

                # Initialize (PDF download is always enabled now)
                super().__init__(
                    verbose=verbose,
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
                                existing_data = json.load(f)
                                # Merge with current results structure
                                if "documents" in existing_data:
                                    self.report_manager.results["documents"] = (
                                        existing_data["documents"]
                                    )
                                if "metadata" in existing_data:
                                    # Preserve some metadata but update timestamp
                                    self.report_manager.results["metadata"].update(
                                        {
                                            "total_documents": existing_data[
                                                "metadata"
                                            ].get("total_documents", 0),
                                            "filtered_out_count": existing_data[
                                                "metadata"
                                            ].get("filtered_out_count", 0),
                                        }
                                    )
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

            def process_files_with_state_saving(self, file_paths):
                """Process files with automatic state saving"""
                state_file = "ask_llm_state.json"

                # Save initial state before processing
                try:
                    if verbose:
                        console.print(
                            f"[DEBUG] Saving initial state to {state_file}", style="dim"
                        )
                    self.save_state(state_file)
                    console.print(
                        f"💾 Initial state saved to: {state_file}", style="bold blue"
                    )
                except Exception as e:
                    console.print(
                        f"Warning: Could not save initial state: {e}", style="yellow"
                    )

                try:
                    # Process files normally with periodic state saving
                    self.process_files_with_periodic_state_saving(
                        file_paths, state_file
                    )

                    # Always save final state on successful completion
                    try:
                        self.save_state(state_file)
                        console.print(
                            f"💾 Final state saved to: {state_file}",
                            style="bold blue",
                        )
                    except Exception as e:
                        console.print(
                            f"Warning: Could not save final state: {e}", style="yellow"
                        )

                except KeyboardInterrupt:
                    # Save state on user interruption
                    try:
                        self.save_state(state_file)
                        console.print(
                            f"💾 Interrupted state saved to: {state_file}",
                            style="bold yellow",
                        )
                    except Exception as e:
                        console.print(
                            f"Warning: Could not save interrupted state: {e}",
                            style="yellow",
                        )
                    raise

                except Exception:
                    # Save state even on error for recovery
                    try:
                        self.save_state(state_file)
                        console.print(
                            f"💾 Error state saved to: {state_file}",
                            style="bold yellow",
                        )
                    except Exception as save_error:
                        console.print(
                            f"Warning: Could not save error state: {save_error}",
                            style="yellow",
                        )
                    raise

            def process_files_with_periodic_state_saving(self, file_paths, state_file):
                """Process files with periodic state saving after each document"""
                # Override the process_pdf method to save state after each document
                original_process_pdf = self.process_pdf

                def process_pdf_with_state_saving(*args, **kwargs):
                    result = original_process_pdf(*args, **kwargs)
                    # Save state after each document is processed
                    try:
                        if verbose:
                            console.print(
                                "[DEBUG] Saving state after document processing",
                                style="dim",
                            )
                        self.save_state(state_file)
                    except Exception as e:
                        if verbose:
                            console.print(
                                f"[DEBUG] Warning: Could not save state after document: {e}",
                                style="dim",
                            )
                    return result

                # Temporarily replace the method
                self.process_pdf = process_pdf_with_state_saving

                try:
                    # Call the original process_files method
                    self.process_files(file_paths)
                finally:
                    # Restore the original method
                    self.process_pdf = original_process_pdf

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
                analyzer.process_files_with_state_saving(file_paths)

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
def fulltext(
    bibtex_files: List[Path] = typer.Argument(
        ...,
        help="BibTeX files to process for PDF search and download",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Enable verbose debug output",
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
) -> None:
    """Search for and download PDFs from BibTeX entries, updating the BibTeX files with URLs and file paths.

    This command processes BibTeX files to:
    1. Extract bibliographic entries
    2. Search for PDFs using fallback strategy (Google grounding + Qwant)
    3. Download found PDFs to ask_llm_downloads directory
    4. Update BibTeX files with discovered URLs and local file paths
    """

    # Validate input files
    for bibtex_file in bibtex_files:
        if not bibtex_file.exists():
            console.print(
                f"Error: BibTeX file does not exist: {bibtex_file}", style="bold red"
            )
            raise typer.Exit(1)
        if not str(bibtex_file).endswith(".bib"):
            console.print(
                f"Warning: File does not have .bib extension: {bibtex_file}",
                style="yellow",
            )

    if verbose:
        console.print("[DEBUG] Starting fulltext PDF search and download", style="dim")
        console.print(
            f"[DEBUG] Processing {len(bibtex_files)} BibTeX files", style="dim"
        )

    try:
        from .bibtex import BibtexProcessor
        from .api import GeminiAPIClient
        from .pdf_search import PDFDownloader
        from .url_resolver import URLResolver
        from .search_strategy import FallbackSearchStrategy

        # Initialize components
        config_overrides = {}
        if api_key:
            config_overrides["api_key"] = api_key
        if api_key_command:
            config_overrides["api_key_command"] = api_key_command

        bibtex_processor = BibtexProcessor(verbose=verbose)
        api_client = GeminiAPIClient(verbose=verbose)
        pdf_downloader = PDFDownloader(verbose=verbose)
        url_resolver = URLResolver(verbose=verbose)

        # Override API client config if provided
        if api_key:
            api_client.api_key = api_key
        if api_key_command:
            # Would need to re-initialize, but for simplicity we'll just warn
            if verbose:
                console.print(
                    "[DEBUG] API key command override not applied to existing client",
                    style="dim",
                )

        # Initialize search strategy
        search_strategy = FallbackSearchStrategy(
            api_client, url_resolver, pdf_downloader, verbose=verbose
        )

        total_entries = 0
        total_found = 0
        total_downloaded = 0
        total_updated = 0
        discovered_info = {}  # Track URLs and file paths for BibTeX updates

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            for bibtex_file in bibtex_files:
                task = progress.add_task(
                    f"Processing {bibtex_file.name}...", total=None
                )

                console.print(f"\n📚 Processing BibTeX file: {bibtex_file}")

                # Extract PDF mappings from BibTeX
                try:
                    pdf_mappings = bibtex_processor.extract_pdfs_from_bibtex(
                        str(bibtex_file)
                    )
                    console.print(
                        f"📖 Found {len(pdf_mappings)} entries in {bibtex_file.name}"
                    )
                    total_entries += len(pdf_mappings)

                except Exception as e:
                    console.print(
                        f"❌ Error reading {bibtex_file}: {e}", style="bold red"
                    )
                    continue

                file_found = 0
                file_downloaded = 0

                # Process each entry
                for mapping in pdf_mappings:
                    bibtex_key = mapping.get("bibtex_key", "")
                    pdf_path = mapping.get("pdf_path")
                    metadata = mapping.get("metadata", {})

                    if not bibtex_key:
                        if verbose:
                            console.print(
                                "[DEBUG] Skipping entry with no BibTeX key", style="dim"
                            )
                        continue

                    title = metadata.get("title", "")
                    if verbose:
                        console.print(
                            f"[DEBUG] Processing entry: {bibtex_key}", style="dim"
                        )
                        if title:
                            console.print(
                                f"[DEBUG] Title: {title[:100]}...", style="dim"
                            )

                    # Skip if entry already has a local PDF file that exists
                    if pdf_path and not pdf_path.startswith(("http://", "https://")):
                        if os.path.exists(pdf_path):
                            if verbose:
                                console.print(
                                    f"[DEBUG] {bibtex_key} already has local PDF: {pdf_path}",
                                    style="dim",
                                )
                            continue

                    # Search for PDF using the fallback strategy
                    try:
                        result = search_strategy.discover_urls_with_source(
                            metadata, "", {}
                        )

                        if result:
                            downloaded_path, original_url = result
                            file_found += 1
                            file_downloaded += 1

                            console.print(
                                f"✅ {bibtex_key}: Downloaded PDF from {original_url}"
                            )

                            # Track for BibTeX update
                            info = {}
                            if original_url:
                                info["url"] = original_url
                            if downloaded_path:
                                info["file_path"] = downloaded_path

                            if info:
                                discovered_info[bibtex_key] = info

                            if verbose:
                                console.print(
                                    f"[DEBUG] Tracked {bibtex_key}: URL={original_url}, file={downloaded_path}",
                                    style="dim",
                                )
                        else:
                            if verbose:
                                console.print(
                                    f"[DEBUG] {bibtex_key}: No PDF found", style="dim"
                                )
                            console.print(f"❌ {bibtex_key}: No PDF found")

                    except Exception as e:
                        console.print(
                            f"❌ {bibtex_key}: Error searching for PDF: {e}",
                            style="red",
                        )
                        if verbose:
                            console.print(
                                f"[DEBUG] Exception details: {type(e).__name__}: {e}",
                                style="dim",
                            )
                        continue

                # Update BibTeX file with discovered URLs and file paths
                if discovered_info:
                    console.print(
                        f"\n📝 Updating {bibtex_file.name} with {len(discovered_info)} discovered URLs and file paths..."
                    )
                    try:
                        updated_count = (
                            bibtex_processor.update_bibtex_with_discovered_info(
                                str(bibtex_file), discovered_info
                            )
                        )
                        total_updated += updated_count
                        if updated_count > 0:
                            console.print(
                                f"✅ Updated {updated_count} entries in {bibtex_file.name}"
                            )
                        else:
                            console.print(
                                f"ℹ️  No updates needed for {bibtex_file.name}"
                            )
                    except Exception as e:
                        console.print(
                            f"❌ Error updating {bibtex_file}: {e}", style="red"
                        )

                total_found += file_found
                total_downloaded += file_downloaded

                console.print(
                    f"📊 {bibtex_file.name}: {file_found} PDFs found, {file_downloaded} downloaded"
                )
                progress.update(task, description=f"✅ {bibtex_file.name} complete")

        # Print final summary
        console.print("\n" + "=" * 60)
        console.print("🎉 Fulltext search and download complete!", style="bold green")
        console.print("📊 Final summary:")
        console.print(f"   • Total entries processed: {total_entries}")
        console.print(f"   • PDFs found and downloaded: {total_found}")
        console.print(f"   • BibTeX entries updated: {total_updated}")
        console.print("   • Downloaded files location: ask_llm_downloads/")
        console.print("=" * 60)

    except KeyboardInterrupt:
        console.print("\n❌ Fulltext search interrupted by user", style="bold red")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"❌ Error during fulltext search: {e}", style="bold red")
        if verbose:
            console.print_exception()
        raise typer.Exit(1)


@app.command()
def version():
    """Show version information."""
    console.print("ask-llm version 1.0.0", style="bold blue")


@app.command()
def clean():
    """Clean up all generated files, caches, and downloads."""
    import shutil
    import glob

    files_to_remove = []
    dirs_to_remove = []

    # Generated files
    generated_files = [
        "analysis_report.json",
        "analysis_report.csv",
        "log.txt",
        "processed_files.txt",
        "filtered_out_documents.txt",
        "ask_llm_state.json",
        "semantic_scholar.bib",
    ]

    # Find merged BibTeX files
    merged_bibtex = glob.glob("merged_*.bib")

    # Cache databases
    cache_files = [
        "gemini_api_cache.sqlite",
        "pdf_download_cache.sqlite",
        "semantic_scholar_cache.sqlite",
        "qwant_search_cache.sqlite",
        "url_resolver_cache.sqlite",
    ]

    # Downloads directory
    downloads_dir = "ask_llm_downloads"

    # Collect all files to remove
    files_to_remove.extend(generated_files)
    files_to_remove.extend(merged_bibtex)
    files_to_remove.extend(cache_files)

    if os.path.exists(downloads_dir):
        dirs_to_remove.append(downloads_dir)

    removed_files = 0
    removed_dirs = 0

    # Remove files
    for file_path in files_to_remove:
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
                console.print(f"🗑️  Removed: {file_path}", style="dim")
                removed_files += 1
            except Exception as e:
                console.print(f"❌ Failed to remove {file_path}: {e}", style="red")

    # Remove directories
    for dir_path in dirs_to_remove:
        if os.path.exists(dir_path):
            try:
                shutil.rmtree(dir_path)
                console.print(f"🗑️  Removed directory: {dir_path}", style="dim")
                removed_dirs += 1
            except Exception as e:
                console.print(
                    f"❌ Failed to remove directory {dir_path}: {e}", style="red"
                )

    # Summary
    if removed_files > 0 or removed_dirs > 0:
        console.print(
            f"✅ Cleanup complete: removed {removed_files} files and {removed_dirs} directories",
            style="bold green",
        )
    else:
        console.print("ℹ️  No files to clean up", style="bold blue")


if __name__ == "__main__":
    app()
