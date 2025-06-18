#!/usr/bin/env python3

import json
import base64
import sys
import os
from pathlib import Path

from .config import ConfigManager
from .bibtex import BibtexProcessor
from .api import GeminiAPIClient
from .reports import ReportManager


class DocumentAnalyzer:
    def __init__(self, verbose=False):
        self.verbose = verbose
        self.config = ConfigManager(verbose=verbose)
        self.bibtex_processor = BibtexProcessor(verbose=verbose)
        self.api_client = GeminiAPIClient(verbose=verbose)
        self.report_manager = ReportManager(verbose=verbose)

        # Initialize with default configuration
        self.processed_list = "processed_files.txt"
        self.logfile = "log.txt"
        self.report_file = "analysis_report.json"

        if self.verbose:
            print("[DEBUG] Initializing DocumentAnalyzer")

        # Load configuration
        self.queries = self.config.load_queries("query.md")

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

    def _find_pdf_file(self, pdf_path, bibtex_dir=None):
        """Find PDF file in common locations if not found at given path"""
        if self.verbose:
            print(f"[DEBUG] Looking for PDF file: {pdf_path}")

        if os.path.isfile(pdf_path):
            if self.verbose:
                print(f"[DEBUG] Found PDF at original path: {pdf_path}")
            return pdf_path

        # If we have a BibTeX directory, try relative to that first
        if bibtex_dir:
            bibtex_relative_path = os.path.join(bibtex_dir, pdf_path)
            if os.path.isfile(bibtex_relative_path):
                if self.verbose:
                    print(
                        f"[DEBUG] Found PDF relative to BibTeX directory: {bibtex_relative_path}"
                    )
                return bibtex_relative_path

        if self.verbose:
            print("[DEBUG] PDF file not found in any location")
        return None

    def process_pdf(self, pdf_path, bibtex_key="", entry_text="", bibtex_file_path=""):
        """Process a single PDF file or BibTeX metadata with multiple queries"""
        if self.verbose:
            print(f"[DEBUG] Starting processing of: {pdf_path}")

        # Try to find PDF file first
        actual_path = None
        pdf_data = None
        metadata = None

        if pdf_path:
            actual_path = self._find_pdf_file(
                pdf_path,
                os.path.dirname(bibtex_file_path) if bibtex_file_path else None,
            )

        if actual_path:
            # Process PDF
            try:
                with open(actual_path, "rb") as f:
                    pdf_data = f.read()
                    if self.verbose:
                        print(f"[DEBUG] Read PDF file: {len(pdf_data)} bytes")
                    if pdf_data:
                        encoded_pdf = base64.b64encode(pdf_data).decode("utf-8")
                        if self.verbose:
                            print(
                                f"[DEBUG] Encoded PDF to base64: {len(encoded_pdf)} characters"
                            )
            except Exception as e:
                print(f"Error reading PDF {actual_path}: {e}", file=sys.stderr)
                return False
        else:
            # Fallback to metadata if PDF not found and we have BibTeX entry
            if entry_text and bibtex_key:
                metadata = self.bibtex_processor.extract_metadata(
                    entry_text, bibtex_key
                )
                if self.verbose:
                    print(f"[DEBUG] Using metadata for {bibtex_key} (PDF not found)")
            else:
                print(f"File not found: {pdf_path}", file=sys.stderr)
                return False

        # Initialize document structure
        document_data = {
            "id": len(self.report_manager.results["documents"]) + 1,
            "file_path": actual_path or pdf_path,
            "bibtex_key": bibtex_key,
            "is_metadata_only": actual_path is None,
            "queries": [],
        }

        successful_queries = 0

        for i, query_info in enumerate(self.queries):
            if self.verbose:
                print(f"[DEBUG] Processing query {i + 1}/{len(self.queries)}")
                print(f"[DEBUG] Query parameters: {query_info['params']}")

            # Create appropriate prompt and payload
            if pdf_data:
                query_text = (
                    f"I'm attaching the PDF file {actual_path}\n\n{query_info['text']}"
                )
                payload = self.api_client.create_pdf_payload(encoded_pdf, query_text)
            else:
                metadata_text = self.bibtex_processor.format_metadata_for_prompt(
                    metadata
                )
                query_text = f"I'm providing bibliographic metadata instead of the PDF file (file not available: {pdf_path}):\n\n{metadata_text}\n\nBased on this metadata, please answer: {query_info['text']}"
                payload = self.api_client.create_text_payload(query_text)

            # Apply query parameters to payload
            payload = self.api_client.apply_query_params(payload, query_info)

            # Make API request
            try:
                response_data = self.api_client.make_request(payload, query_info)

                # Log response
                with open(self.logfile, "a", encoding="utf-8") as f:
                    f.write(
                        f"=== Response for {actual_path or bibtex_key} (Query {i + 1}) ===\n"
                    )
                    json.dump(response_data, f, indent=2)
                    f.write("\n\n")

                # Extract and process response
                response_content, grounding_metadata = self.api_client.extract_response(
                    response_data
                )

                if self.verbose:
                    print(
                        f"[DEBUG] Extracted response content: {len(response_content)} characters"
                    )

                # Parse JSON response if structure was requested
                parsed_response = response_content
                query_structure = query_info.get("structure")
                if query_structure:
                    try:
                        parsed_response = json.loads(response_content)
                    except json.JSONDecodeError:
                        if self.verbose:
                            print(
                                f"[DEBUG] Failed to parse JSON response for query {i + 1}"
                            )

                query_result = {
                    "query_id": i + 1,
                    "response": parsed_response,
                    "grounding_metadata": grounding_metadata,
                }

                document_data["queries"].append(query_result)
                successful_queries += 1

                if self.verbose:
                    print(f"[DEBUG] Successfully processed query {i + 1}")

            except Exception as e:
                print(
                    f"Error processing query {i + 1} for {actual_path or bibtex_key}: {e}",
                    file=sys.stderr,
                )
                if self.verbose:
                    print(f"[DEBUG] Exception details: {type(e).__name__}: {e}")
                continue

        if successful_queries > 0:
            self.report_manager.add_document(document_data)

            if self.verbose:
                print(
                    f"[DEBUG] Successfully processed {successful_queries} queries for {actual_path or bibtex_key}"
                )

            # Record processed file
            with open(self.processed_list, "a", encoding="utf-8") as f:
                if actual_path:
                    f.write(f"{actual_path}|{bibtex_key}\n")
                else:
                    f.write(f"METADATA:{bibtex_key}|{bibtex_key}\n")

            # Flush JSON output after each document
            self.report_manager.save_report(self.report_file)

            if self.verbose:
                print(f"[DEBUG] Flushed results to {self.report_file}")

            print(
                f"Successfully processed: {actual_path or f'metadata for {bibtex_key}'}"
            )
            return True

        if self.verbose:
            print(f"[DEBUG] No responses processed for {actual_path or bibtex_key}")
        return False

    def process_files(self, files):
        """Main processing logic"""
        if self.verbose:
            print(f"[DEBUG] Starting file processing for {len(files)} files")

        bibtex_files = [f for f in files if f.endswith(".bib")]
        pdf_files = [f for f in files if f.endswith(".pdf")]

        if self.verbose:
            print(
                f"[DEBUG] Found {len(bibtex_files)} BibTeX files and {len(pdf_files)} PDF files"
            )

        # Process BibTeX files
        for bibtex_file in bibtex_files:
            print(f"Processing BibTeX file: {bibtex_file}")
            pdf_mappings = self.bibtex_processor.extract_pdfs_from_bibtex(bibtex_file)

            for mapping in pdf_mappings:
                self.process_pdf(
                    mapping["pdf_path"],
                    mapping["bibtex_key"],
                    mapping["entry_text"],
                    bibtex_file,
                )

        # Process individual PDF files
        for pdf_file in pdf_files:
            if self.verbose:
                print(f"[DEBUG] Processing individual PDF: {pdf_file}")
            self.process_pdf(pdf_file)

        print("\nProcessing complete!")
        print(f"Final report saved to: {self.report_file}")
        print(f"Log saved to: {self.logfile}")
        print(f"Processed files list: {self.processed_list}")
