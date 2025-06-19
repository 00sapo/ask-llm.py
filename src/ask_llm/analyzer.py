#!/usr/bin/env python3

import os
from pathlib import Path
from datetime import datetime
from typing import List

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
        use_qwant_strategy=False,
        **config_overrides,
    ):
        self.verbose = verbose
        self.use_qwant_strategy = use_qwant_strategy

        # Initialize core components with config overrides
        self.config = ConfigManager(verbose=verbose, **config_overrides)
        self.bibtex_processor = BibtexProcessor(verbose=verbose)
        self.api_client = GeminiAPIClient(verbose=verbose)
        self.report_manager = ReportManager(verbose=verbose)

        # Initialize specialized components
        self.semantic_scholar_client = SemanticScholarClient(verbose=verbose)
        self.pdf_downloader = PDFDownloader(verbose=verbose)

        # Initialize processors with strategy choice
        self.document_processor = DocumentProcessor(
            self.api_client,
            self.bibtex_processor,
            self.pdf_downloader,
            verbose=verbose,
            use_qwant_strategy=use_qwant_strategy,
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

            strategy_name = "Qwant" if use_qwant_strategy else "Google grounding"
            print(f"[DEBUG] Using {strategy_name} search strategy")

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
                "use_qwant_strategy": self.use_qwant_strategy,
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
            "processed_files": self._get_processed_files(),
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

            # Restore strategy setting if available
            if "use_qwant_strategy" in config:
                self.use_qwant_strategy = config["use_qwant_strategy"]
                if self.verbose:
                    strategy_name = (
                        "Qwant" if self.use_qwant_strategy else "Google grounding"
                    )
                    print(f"[DEBUG] Restored search strategy: {strategy_name}")

            # Restore report data
            if "report_data" in state_data:
                self.report_manager.results = state_data["report_data"]

            # Restore filtered documents
            if "filtered_out_documents" in state_data:
                self.filtered_out_documents = state_data["filtered_out_documents"]

            # Restore processed files list
            if "processed_files" in state_data:
                self._restore_processed_files(state_data["processed_files"])

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

    def _get_processed_files(self) -> List[str]:
        """Get list of processed files"""
        try:
            if os.path.exists(self.processed_list):
                with open(self.processed_list, "r", encoding="utf-8") as f:
                    return f.read().splitlines()
        except Exception:
            pass
        return []

    def _restore_processed_files(self, processed_files: List[str]):
        """Restore processed files list"""
        try:
            with open(self.processed_list, "w", encoding="utf-8") as f:
                f.write("\n".join(processed_files))
        except Exception as e:
            if self.verbose:
                print(f"[DEBUG] Could not restore processed files list: {e}")

    def _should_skip_processed_file(self, pdf_path: str, bibtex_key: str) -> bool:
        """Check if file was already processed based on state"""
        processed_files = self._get_processed_files()

        # Check various formats that might be in processed list
        search_patterns = [
            f"{pdf_path}|{bibtex_key}",
            f"URL:{pdf_path}|{bibtex_key}",
            f"METADATA:{bibtex_key}|{bibtex_key}",
            pdf_path,  # Just the path
        ]

        for pattern in search_patterns:
            if pattern in processed_files:
                if self.verbose:
                    print(f"[DEBUG] Skipping already processed: {pattern}")
                return True

        return False

    def _track_discovered_url(self, bibtex_key: str, discovered_urls: dict):
        """Track discovered URLs for later BibTeX update"""
        # Check if we discovered a URL for this document
        for doc in self.report_manager.results["documents"]:
            if doc["bibtex_key"] == bibtex_key and doc.get("pdf_source") in [
                "searched_download",
            ]:
                # Find the URL from the document processing
                if doc.get("file_path"):
                    discovered_urls[bibtex_key] = doc["file_path"]
                    if self.verbose:
                        print(
                            f"[DEBUG] Tracked discovered URL for {bibtex_key}: {doc['file_path']}"
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
                f.write(f"Filtered at Query: {doc.get('filtered_at_query', 'N/A')}\n")
                f.write(f"Filter Reason: {doc.get('filter_reason', 'N/A')}\n")
                f.write("-" * 40 + "\n")

        print(f"Filtered out documents list saved to: {filtered_out_file}")

    def process_pdf(self, pdf_path, bibtex_key="", entry_text="", bibtex_file_path=""):
        """Process a single PDF file, URL, or BibTeX metadata with multiple queries"""

        # Check if already processed when resuming
        if self._should_skip_processed_file(pdf_path, bibtex_key):
            if self.verbose:
                print(f"[DEBUG] Skipping already processed: {pdf_path or bibtex_key}")
            return True

        document_id = len(self.report_manager.results["documents"]) + 1

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
                f"Filtered out during processing: {display_path} (at query {document_data['filtered_at_query']})"
            )
        else:
            # Document passed all filters
            self.report_manager.add_document(document_data)

            if self.verbose:
                print(
                    f"[DEBUG] Successfully processed document for {pdf_path or bibtex_key}"
                )

            # Record processed file
            with open(self.processed_list, "a", encoding="utf-8") as f:
                if document_data["is_metadata_only"]:
                    f.write(f"METADATA:{bibtex_key}|{bibtex_key}\n")
                else:
                    f.write(f"{document_data['file_path']}|{bibtex_key}\n")

            # Flush JSON and CSV output after each document
            self.report_manager.save_json_report(self.json_report_file)
            self.report_manager.save_csv_report(self.csv_report_file)

            if self.verbose:
                print(
                    f"[DEBUG] Flushed results to {self.json_report_file} and {self.csv_report_file}"
                )

            display_path = document_data["file_path"] or f"metadata for {bibtex_key}"
            print(f"Successfully processed: {display_path}")

        return True

    def process_files(self, files):
        """Main processing logic"""
        if self.verbose:
            print(f"[DEBUG] Starting file processing for {len(files)} files")

        # Track discovered URLs for updating BibTeX files
        discovered_urls = {}  # bibtex_key -> url mapping
        bibtex_files_to_update = []  # Files that should be updated

        try:
            # Check if any queries use Semantic Scholar
            has_semantic_scholar = any(
                q.params.get("semantic_scholar", False) for q in self.queries
            )

            # Process Semantic Scholar queries first if any exist
            semantic_scholar_bibtex = ""
            if has_semantic_scholar:
                if self.verbose:
                    print("[DEBUG] Processing Semantic Scholar queries")
                semantic_scholar_bibtex = (
                    self.semantic_scholar_processor.process_semantic_scholar_queries(
                        self.queries
                    )
                )

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

                            # Track discovered URLs
                            if success and mapping["bibtex_key"]:
                                self._track_discovered_url(
                                    mapping["bibtex_key"], discovered_urls
                                )

                        # Mark original bibtex file for updating
                        bibtex_files_to_update.append(bibtex_file)

                        if self.verbose:
                            print(
                                f"[DEBUG] Created and processed merged file: {temp_merged_file}"
                            )
                else:
                    # Case 2: Only Semantic Scholar results (no BibTeX files)
                    print("Processing Semantic Scholar results")
                    merged_content = self.semantic_scholar_processor.merge_bibtex_files(
                        None, semantic_scholar_bibtex
                    )

                    # Create a temporary file for Semantic Scholar results
                    temp_ss_file = "semantic_scholar_results.bib"
                    with open(temp_ss_file, "w", encoding="utf-8") as f:
                        f.write(merged_content)

                    # Process the Semantic Scholar results
                    pdf_mappings = self.bibtex_processor.extract_pdfs_from_bibtex(
                        temp_ss_file
                    )
                    for mapping in pdf_mappings:
                        success = self.process_pdf(
                            mapping["pdf_path"],
                            mapping["bibtex_key"],
                            mapping["entry_text"],
                            temp_ss_file,
                        )

                        # Track discovered URLs
                        if success and mapping["bibtex_key"]:
                            self._track_discovered_url(
                                mapping["bibtex_key"], discovered_urls
                            )

                    # Mark semantic scholar file for updating
                    bibtex_files_to_update.append("semantic_scholar.bib")

                    if self.verbose:
                        print(
                            f"[DEBUG] Created and processed Semantic Scholar file: {temp_ss_file}"
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
                            self._track_discovered_url(
                                mapping["bibtex_key"], discovered_urls
                            )

                    # Mark bibtex file for updating
                    bibtex_files_to_update.append(bibtex_file)

            # Process individual PDF files (these are independent of BibTeX/Semantic Scholar)
            for pdf_file in pdf_files:
                if self.verbose:
                    print(f"[DEBUG] Processing individual PDF: {pdf_file}")
                self.process_pdf(pdf_file)

            # Update BibTeX files with discovered URLs
            if discovered_urls and bibtex_files_to_update:
                print(
                    f"\nUpdating BibTeX files with {len(discovered_urls)} discovered URLs..."
                )

                total_updated = 0
                for bibtex_file in set(bibtex_files_to_update):  # Remove duplicates
                    if os.path.exists(bibtex_file):
                        updated_count = self.bibtex_processor.update_bibtex_with_urls(
                            bibtex_file, discovered_urls
                        )
                        total_updated += updated_count

                if total_updated > 0:
                    print(
                        f"Updated {total_updated} BibTeX entries with discovered URLs"
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

            print("\nProcessing complete!")
            print(f"Final JSON report saved to: {self.json_report_file}")
            print(f"Final CSV report saved to: {self.csv_report_file}")
            print(f"Log saved to: {self.logfile}")
            print(f"Processed files list: {self.processed_list}")

            if self.filtered_out_documents:
                print("Filtered out documents: filtered_out_documents.txt")

            if has_semantic_scholar:
                print("Semantic Scholar BibTeX saved to: semantic_scholar.bib")

            # Clean up temporary files if they exist
            temp_files = ["semantic_scholar_results.bib"] + [
                f"merged_{Path(f).name}" for f in bibtex_files
            ]
            for temp_file in temp_files:
                if os.path.exists(temp_file):
                    try:
                        os.remove(temp_file)
                        if self.verbose:
                            print(f"[DEBUG] Cleaned up temporary file: {temp_file}")
                    except Exception as e:
                        if self.verbose:
                            print(
                                f"[DEBUG] Could not remove temporary file {temp_file}: {e}"
                            )

        finally:
            # Always clean up downloaded PDFs
            self.document_processor.cleanup_downloaded_pdfs()
