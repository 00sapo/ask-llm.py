#!/usr/bin/env python3

import os
from pathlib import Path
from datetime import datetime

from .config import ConfigManager
from .bibtex import BibtexProcessor
from .api import GeminiAPIClient
from .reports import ReportManager
from .semantic_scholar import SemanticScholarClient
from .pdf_search import PDFDownloader
from .document_processor import DocumentProcessor
from .semantic_scholar_processor import SemanticScholarProcessor


class DocumentAnalyzer:
    def __init__(
        self,
        verbose=False,
        **config_overrides,
    ):
        self.verbose = verbose

        # Initialize core components with config overrides
        self.config = ConfigManager(verbose=verbose, **config_overrides)
        self.bibtex_processor = BibtexProcessor(verbose=verbose)
        self.api_client = GeminiAPIClient(verbose=verbose)
        self.report_manager = ReportManager(verbose=verbose)

        # Initialize specialized components
        self.semantic_scholar_client = SemanticScholarClient(verbose=verbose)
        self.pdf_downloader = PDFDownloader(verbose=verbose)

        # Initialize processors with fallback strategy
        self.document_processor = DocumentProcessor(
            self.api_client,
            self.bibtex_processor,
            self.pdf_downloader,
            verbose=verbose,
        )
        self.semantic_scholar_processor = SemanticScholarProcessor(
            self.semantic_scholar_client, verbose=verbose
        )

        # Initialize with default configuration
        self.processed_list = "processed_files.txt"
        self.logfile = "log.txt"
        self.json_report_file = "analysis_report.json"
        self.csv_report_file = "analysis_report.csv"
        self.filtered_out_documents = []  # Track filtered out documents

        if self.verbose:
            print("[DEBUG] Initializing DocumentAnalyzer")
            print("[DEBUG] PDF download mode enabled")
            print("[DEBUG] Using fallback search strategy (Google grounding with Qwant fallback)")

        # Load configuration - now uses correct query file path
        self.queries = self.config.load_queries()

        if self.verbose:
            print(f"[DEBUG] Loaded {len(self.queries)} queries")

        # Clear output files
        self._clear_files()

    def _clear_files(self):
        """Clear or create output files and initialize JSON structure"""
        if self.verbose:
            print("[DEBUG] Clearing output files")
        for filename in [self.processed_list, self.logfile]:
            Path(filename).write_text("")
            if self.verbose:
                print(f"[DEBUG] Cleared {filename}")

        # Initialize JSON structure
        self.report_manager.initialize_json_structure(
            self.queries, self.api_client.default_model
        )

    def save_state(self, state_file: str = "ask_llm_state.json"):
        """Save complete process state"""
        state_data = {
            "version": "1.0.0",
            "timestamp": datetime.now().isoformat(),
            "config": {
                "query_file": self.config.settings.query_file,
                "processed_list": self.processed_list,
                "logfile": self.logfile,
                "json_report_file": self.json_report_file,
                "csv_report_file": self.csv_report_file,
            },
            "queries": [
                {
                    "text": q.text,
                    "params": q.params,
                    "structure": q.structure,
                    "filter_on": q.filter_on,
                }
                for q in self.queries
            ],
            "report_data": self.report_manager.results,
            "filtered_out_documents": self.filtered_out_documents,
        }

        self.config.save_state(state_data, state_file)
        if self.verbose:
            print(
                f"[DEBUG] Saved complete state with {len(self.report_manager.results['documents'])} documents"
            )

    def load_state(self, state_file: str = "ask_llm_state.json") -> bool:
        """Load and restore complete process state"""
        state_data = self.config.load_state(state_file)
        if not state_data:
            return False

        try:
            # Restore configuration
            config = state_data.get("config", {})
            self.processed_list = config.get("processed_list", self.processed_list)
            self.logfile = config.get("logfile", self.logfile)
            self.json_report_file = config.get(
                "json_report_file", self.json_report_file
            )
            self.csv_report_file = config.get("csv_report_file", self.csv_report_file)

            # Remove qwant strategy handling (now using fallback strategy)

            # Restore report data
            if "report_data" in state_data:
                self.report_manager.results = state_data["report_data"]

            # Restore filtered documents
            if "filtered_out_documents" in state_data:
                self.filtered_out_documents = state_data["filtered_out_documents"]

            if self.verbose:
                doc_count = len(self.report_manager.results.get("documents", []))
                filtered_count = len(self.filtered_out_documents)
                print(
                    f"[DEBUG] Restored state with {doc_count} documents and {filtered_count} filtered documents"
                )

            return True

        except Exception as e:
            print(f"Error restoring state: {e}")
            return False

    def _should_skip_processed_file(self, pdf_path: str, bibtex_key: str) -> bool:
        """Check if file was already processed based on current report state"""
        # Check if document already exists in current results
        for doc in self.report_manager.results.get("documents", []):
            # Match by bibtex_key if available
            if bibtex_key and doc.get("bibtex_key") == bibtex_key:
                if self.verbose:
                    print(
                        f"[DEBUG] Skipping already processed document with bibtex_key: {bibtex_key}"
                    )
                return True

            # Match by file path
            if pdf_path and doc.get("file_path") == pdf_path:
                if self.verbose:
                    print(
                        f"[DEBUG] Skipping already processed document with path: {pdf_path}"
                    )
                return True

        # Also check filtered out documents
        for doc in self.filtered_out_documents:
            if bibtex_key and doc.get("bibtex_key") == bibtex_key:
                if self.verbose:
                    print(
                        f"[DEBUG] Skipping already filtered document with bibtex_key: {bibtex_key}"
                    )
                return True

            if pdf_path and doc.get("file_path") == pdf_path:
                if self.verbose:
                    print(
                        f"[DEBUG] Skipping already filtered document with path: {pdf_path}"
                    )
                return True

        return False

    def _track_discovered_info(self, bibtex_key: str, discovered_info: dict):
        """Track discovered URLs and file paths for later BibTeX update"""
        # Check if we discovered a URL or file path for this document
        for doc in self.report_manager.results["documents"]:
            if doc["bibtex_key"] == bibtex_key:
                pdf_url = doc.get("pdf_url")
                file_path = doc.get("file_path")

                # Track both URL and file path if available
                info = {}
                if pdf_url:
                    info["url"] = pdf_url
                if (
                    file_path and file_path != pdf_url
                ):  # Only add file path if different from URL
                    info["file_path"] = file_path

                if info:  # Only track if we have either URL or file path
                    discovered_info[bibtex_key] = info
                    if self.verbose:
                        tracked_items = []
                        if pdf_url:
                            tracked_items.append(f"URL: {pdf_url}")
                        if file_path and file_path != pdf_url:
                            tracked_items.append(f"file path: {file_path}")
                        print(
                            f"[DEBUG] Tracked for {bibtex_key}: {', '.join(tracked_items)}"
                        )
                break

    def _save_filtered_out_list(self):
        """Save list of filtered out documents"""
        if not self.filtered_out_documents:
            if self.verbose:
                print("[DEBUG] No documents were filtered out")
            return

        filtered_out_file = "filtered_out_documents.txt"
        if self.verbose:
            print(
                f"[DEBUG] Saving {len(self.filtered_out_documents)} filtered out documents to {filtered_out_file}"
            )

        with open(filtered_out_file, "w", encoding="utf-8") as f:
            f.write("# Documents filtered out by query filters\n")
            f.write(f"# Total filtered out: {len(self.filtered_out_documents)}\n\n")

            for doc in self.filtered_out_documents:
                f.write(f"Document ID: {doc['id']}\n")
                f.write(f"File Path: {doc['file_path']}\n")
                f.write(f"BibTeX Key: {doc['bibtex_key']}\n")
                f.write(
                    f"Metadata Only: {'Yes' if doc['is_metadata_only'] else 'No'}\n"
                )
                f.write(f"PDF Source: {doc.get('pdf_source', 'unknown')}\n")
                f.write(f"PDF URL: {doc.get('pdf_url', 'N/A')}\n")
                f.write(f"Filtered at Query: {doc.get('filtered_at_query', 'N/A')}\n")
                f.write(f"Filter Reason: {doc.get('filter_reason', 'N/A')}\n")
                f.write("-" * 40 + "\n")

        print(
            f"📋 Filtered out documents saved: {filtered_out_file} ({len(self.filtered_out_documents)} documents)"
        )

    def process_pdf(self, pdf_path, bibtex_key="", entry_text="", bibtex_file_path=""):
        """Process a single PDF file, URL, or BibTeX metadata with multiple queries"""

        # Check if already processed when resuming
        if self._should_skip_processed_file(pdf_path, bibtex_key):
            if self.verbose:
                print(f"[DEBUG] Skipping already processed: {pdf_path or bibtex_key}")
            return True

        document_id = (
            len(self.report_manager.results["documents"])
            + len(self.filtered_out_documents)
            + 1
        )

        document_data, success = self.document_processor.process_document(
            pdf_path,
            bibtex_key,
            entry_text,
            bibtex_file_path,
            self.queries,
            document_id,
            self.logfile,
        )

        if not success:
            return False

        # Handle the processed document
        if document_data["is_filtered_out"]:
            # Document was filtered out during processing
            self.filtered_out_documents.append(document_data)
            display_path = document_data["file_path"] or f"metadata for {bibtex_key}"
            print(
                f"🚫 Filtered out: {display_path} (at query {document_data['filtered_at_query']})"
            )
            # Report filtered out count
            filtered_count = len(self.filtered_out_documents)
            print(f"📊 Documents filtered out: {filtered_count}")
        else:
            # Document passed all filters
            self.report_manager.add_document(document_data)

            if self.verbose:
                print(
                    f"[DEBUG] Successfully processed document for {pdf_path or bibtex_key}"
                )

            # Flush JSON and CSV output after each document
            self.report_manager.save_json_report(self.json_report_file)
            self.report_manager.save_csv_report(self.csv_report_file)

            if self.verbose:
                print(
                    f"[DEBUG] Flushed results to {self.json_report_file} and {self.csv_report_file}"
                )

            display_path = document_data["file_path"] or f"metadata for {bibtex_key}"
            print(f"✅ Successfully processed: {display_path}")

        return True

    def process_files(self, files):
        """Main processing logic"""
        if self.verbose:
            print(f"[DEBUG] Starting file processing for {len(files)} files")

        # Track discovered URLs and file paths for updating BibTeX files
        discovered_info = {}  # bibtex_key -> {'url': url, 'file_path': path} mapping
        bibtex_files_to_update = []  # Files that should be updated

        try:
            # Check if any queries use Semantic Scholar
            has_semantic_scholar = any(
                q.params.get("semantic_scholar", False) for q in self.queries
            )

            # Check if we already have Semantic Scholar results when resuming
            has_existing_semantic_scholar_results = False
            if has_semantic_scholar:
                # Check if any existing documents came from Semantic Scholar
                for doc in self.report_manager.results.get("documents", []):
                    if doc.get("bibtex_key", "").startswith("semanticscholar"):
                        has_existing_semantic_scholar_results = True
                        break

                # Also check filtered documents
                if not has_existing_semantic_scholar_results:
                    for doc in self.filtered_out_documents:
                        if doc.get("bibtex_key", "").startswith("semanticscholar"):
                            has_existing_semantic_scholar_results = True
                            break

            # Process Semantic Scholar queries first if any exist and not already processed
            semantic_scholar_bibtex = ""
            if has_semantic_scholar and not has_existing_semantic_scholar_results:
                if self.verbose:
                    print("[DEBUG] Processing Semantic Scholar queries")
                semantic_scholar_bibtex = (
                    self.semantic_scholar_processor.process_semantic_scholar_queries(
                        self.queries
                    )
                )
            elif has_semantic_scholar and has_existing_semantic_scholar_results:
                if self.verbose:
                    print(
                        "[DEBUG] Skipping Semantic Scholar queries - already processed in previous run"
                    )
                print("⏭️  Skipping Semantic Scholar queries (already processed)")

            # Separate file types
            bibtex_files = [f for f in files if f.endswith(".bib")]
            pdf_files = [f for f in files if f.endswith(".pdf")]

            if self.verbose:
                print(
                    f"[DEBUG] Found {len(bibtex_files)} BibTeX files and {len(pdf_files)} PDF files"
                )

            # Determine how to handle the processing based on file types and Semantic Scholar results
            if semantic_scholar_bibtex:
                if bibtex_files:
                    # Case 1: We have both Semantic Scholar results and BibTeX files
                    # Merge with each BibTeX file
                    for bibtex_file in bibtex_files:
                        print(
                            f"Processing BibTeX file with Semantic Scholar results: {bibtex_file}"
                        )
                        merged_content = (
                            self.semantic_scholar_processor.merge_bibtex_files(
                                bibtex_file, semantic_scholar_bibtex
                            )
                        )

                        # Create a temporary merged file
                        temp_merged_file = f"merged_{Path(bibtex_file).name}"
                        with open(temp_merged_file, "w", encoding="utf-8") as f:
                            f.write(merged_content)

                        # Process the merged file
                        pdf_mappings = self.bibtex_processor.extract_pdfs_from_bibtex(
                            temp_merged_file
                        )
                        for mapping in pdf_mappings:
                            success = self.process_pdf(
                                mapping["pdf_path"],
                                mapping["bibtex_key"],
                                mapping["entry_text"],
                                temp_merged_file,
                            )

                            # Track discovered URLs only for original BibTeX entries, not Semantic Scholar ones
                            if (
                                success
                                and mapping["bibtex_key"]
                                and not mapping["bibtex_key"].startswith(
                                    "semanticscholar"
                                )
                            ):
                                self._track_discovered_info(
                                    mapping["bibtex_key"], discovered_info
                                )

                        # Mark original bibtex file for updating (not the temporary merged file)
                        bibtex_files_to_update.append(bibtex_file)

                        if self.verbose:
                            print(
                                f"[DEBUG] Created and processed merged file: {temp_merged_file}"
                            )
                else:
                    # Case 2: Only Semantic Scholar results (no BibTeX files)
                    print("Processing Semantic Scholar results")

                    # Create the permanent Semantic Scholar BibTeX file
                    semantic_scholar_file = "semantic_scholar.bib"
                    with open(semantic_scholar_file, "w", encoding="utf-8") as f:
                        f.write(semantic_scholar_bibtex)

                    # Process the Semantic Scholar results
                    pdf_mappings = self.bibtex_processor.extract_pdfs_from_bibtex(
                        semantic_scholar_file
                    )
                    for mapping in pdf_mappings:
                        success = self.process_pdf(
                            mapping["pdf_path"],
                            mapping["bibtex_key"],
                            mapping["entry_text"],
                            semantic_scholar_file,
                        )

                        # Track discovered URLs for Semantic Scholar entries too
                        if success and mapping["bibtex_key"]:
                            self._track_discovered_info(
                                mapping["bibtex_key"], discovered_info
                            )

                    # Mark semantic scholar file for updating
                    bibtex_files_to_update.append(semantic_scholar_file)

                    if self.verbose:
                        print(
                            f"[DEBUG] Created and processed Semantic Scholar file: {semantic_scholar_file}"
                        )
            else:
                # Case 3: No Semantic Scholar results, process normally
                for bibtex_file in bibtex_files:
                    print(f"Processing BibTeX file: {bibtex_file}")
                    pdf_mappings = self.bibtex_processor.extract_pdfs_from_bibtex(
                        bibtex_file
                    )

                    for mapping in pdf_mappings:
                        success = self.process_pdf(
                            mapping["pdf_path"],
                            mapping["bibtex_key"],
                            mapping["entry_text"],
                            bibtex_file,
                        )

                        # Track discovered URLs
                        if success and mapping["bibtex_key"]:
                            self._track_discovered_info(
                                mapping["bibtex_key"], discovered_info
                            )

                    # Mark bibtex file for updating
                    bibtex_files_to_update.append(bibtex_file)

            # Process individual PDF files (these are independent of BibTeX/Semantic Scholar)
            for pdf_file in pdf_files:
                if self.verbose:
                    print(f"[DEBUG] Processing individual PDF: {pdf_file}")
                self.process_pdf(pdf_file)

            # Update BibTeX files with discovered URLs and file paths
            if discovered_info and bibtex_files_to_update:
                print(
                    f"\nUpdating BibTeX files with URLs and file paths for {len(discovered_info)} entries..."
                )

                total_updated = 0
                for bibtex_file in set(bibtex_files_to_update):  # Remove duplicates
                    if os.path.exists(bibtex_file):
                        updated_count = (
                            self.bibtex_processor.update_bibtex_with_discovered_info(
                                bibtex_file, discovered_info
                            )
                        )
                        total_updated += updated_count

                if total_updated > 0:
                    print(
                        f"✅ Updated {total_updated} BibTeX entries with discovered URLs and file paths"
                    )

            # Update filtered out count in metadata
            self.report_manager.results["metadata"]["filtered_out_count"] = len(
                self.filtered_out_documents
            )

            # Generate filtered out list
            self._save_filtered_out_list()

            # Save final report
            self.report_manager.save_json_report(self.json_report_file)
            self.report_manager.save_csv_report(self.csv_report_file)

            # Print final summary
            print("\n" + "=" * 50)
            print("🎉 Processing complete!")
            print("📊 Final summary:")
            total_docs = len(self.report_manager.results["documents"])
            filtered_docs = len(self.filtered_out_documents)
            print(f"   • Documents processed: {total_docs}")
            print(f"   • Documents filtered out: {filtered_docs}")
            print(f"   • Total documents examined: {total_docs + filtered_docs}")
            print("📁 Output files:")
            print(f"   • JSON report: {self.json_report_file}")
            print(f"   • CSV report: {self.csv_report_file}")
            print(f"   • Log file: {self.logfile}")
            print(f"   • Processed files list: {self.processed_list}")

            if self.filtered_out_documents:
                print("   • Filtered out documents: filtered_out_documents.txt")

            if has_semantic_scholar:
                print("   • Semantic Scholar BibTeX: semantic_scholar.bib")
            print("=" * 50)

            # Keep temporary files permanently for future reference
            temp_files = [f"merged_{Path(f).name}" for f in bibtex_files]
            if temp_files:
                if self.verbose:
                    print("[DEBUG] Keeping temporary merged files permanently")
                print(f"📁 Preserved {len(temp_files)} temporary BibTeX files")

        finally:
            # Always clean up downloaded PDFs
            self.document_processor.cleanup_downloaded_pdfs()
