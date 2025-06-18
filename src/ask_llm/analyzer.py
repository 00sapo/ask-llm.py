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
from .semantic_scholar import SemanticScholarClient


class DocumentAnalyzer:
    def __init__(self, verbose=False, auto_download_pdfs=True):
        self.verbose = verbose
        self.auto_download_pdfs = auto_download_pdfs
        self.config = ConfigManager(verbose=verbose)
        self.bibtex_processor = BibtexProcessor(
            verbose=verbose, auto_download_pdfs=auto_download_pdfs
        )
        self.api_client = GeminiAPIClient(verbose=verbose)
        self.report_manager = ReportManager(verbose=verbose)
        self.semantic_scholar_client = SemanticScholarClient(
            verbose=verbose, auto_download_pdfs=auto_download_pdfs
        )

        # Initialize with default configuration
        self.processed_list = "processed_files.txt"
        self.logfile = "log.txt"
        self.json_report_file = "analysis_report.json"
        self.csv_report_file = "analysis_report.csv"
        self.filtered_out_documents = []  # Track filtered out documents

        if self.verbose:
            print("[DEBUG] Initializing DocumentAnalyzer")
            print("[DEBUG] Using URL context instead of PDF downloads")

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

    def _process_semantic_scholar_queries(self) -> str:
        """Process all Semantic Scholar queries and return combined BibTeX content"""
        if self.verbose:
            print("[DEBUG] Processing all Semantic Scholar queries")

        all_bibtex_entries = []
        entry_counter = 1

        # Process each Semantic Scholar query
        semantic_scholar_queries = [
            q for q in self.queries if q.params.get("semantic_scholar", False)
        ]

        for query_idx, query_info in enumerate(semantic_scholar_queries):
            if self.verbose:
                print(
                    f"[DEBUG] Processing Semantic Scholar query {query_idx + 1}: {query_info.text[:100]}..."
                )

            # Extract Semantic Scholar parameters from query params
            ss_params = {}
            for key, value in query_info.params.items():
                if key.startswith("ss_"):
                    # Remove 'ss_' prefix and convert back to API parameter name
                    api_key = key[3:].replace("_", "")
                    if api_key == "publicationdateoryear":
                        api_key = "publicationDateOrYear"
                    elif api_key == "fieldsofstudy":
                        api_key = "fieldsOfStudy"
                    elif api_key == "publicationtypes":
                        api_key = "publicationTypes"
                    elif api_key == "mincitationcount":
                        api_key = "minCitationCount"
                    elif api_key == "openaccesspdf":
                        api_key = "openAccessPdf"
                    ss_params[api_key] = value

            if self.verbose:
                print(f"[DEBUG] Semantic Scholar parameters: {ss_params}")

            # Perform the search
            try:
                papers = self.semantic_scholar_client.search_papers(
                    query_info.text, ss_params
                )

                # Create BibTeX entries for each paper
                for paper in papers:
                    entry_key = f"semanticscholar{entry_counter}"
                    bibtex_entry = self.semantic_scholar_client.create_bibtex_entry(
                        paper, entry_key
                    )
                    all_bibtex_entries.append(bibtex_entry)
                    entry_counter += 1

                if self.verbose:
                    print(f"[DEBUG] Query {query_idx + 1} added {len(papers)} papers")

            except Exception as e:
                print(f"Error processing Semantic Scholar query {query_idx + 1}: {e}")
                if self.verbose:
                    print(f"[DEBUG] Exception details: {type(e).__name__}: {e}")
                continue

        if all_bibtex_entries:
            combined_bibtex = "\n\n".join(all_bibtex_entries)

            # Save Semantic Scholar BibTeX to permanent file
            semantic_scholar_file = "semantic_scholar.bib"
            with open(semantic_scholar_file, "w", encoding="utf-8") as f:
                f.write(combined_bibtex)

            if self.verbose:
                print(
                    f"[DEBUG] Created combined BibTeX with {len(all_bibtex_entries)} entries"
                )
                print(
                    f"[DEBUG] Saved Semantic Scholar BibTeX to: {semantic_scholar_file}"
                )

            print(f"Semantic Scholar BibTeX saved to: {semantic_scholar_file}")
            return combined_bibtex
        else:
            if self.verbose:
                print("[DEBUG] No Semantic Scholar entries generated")
            return ""

    def _merge_bibtex_files(
        self, original_bibtex_file: str = None, semantic_scholar_bibtex: str = ""
    ) -> str:
        """Merge original BibTeX file with Semantic Scholar results"""
        merged_content = ""

        # Add original BibTeX content if provided
        if original_bibtex_file:
            try:
                with open(original_bibtex_file, "r", encoding="utf-8") as f:
                    original_content = f.read().strip()
                    if original_content:
                        merged_content += original_content
                        if self.verbose:
                            print(
                                f"[DEBUG] Added original BibTeX content from {original_bibtex_file}"
                            )
            except FileNotFoundError:
                if self.verbose:
                    print(
                        f"[DEBUG] Original BibTeX file {original_bibtex_file} not found"
                    )
            except Exception as e:
                print(
                    f"Warning: Could not read original BibTeX file {original_bibtex_file}: {e}"
                )

        # Add Semantic Scholar content
        if semantic_scholar_bibtex:
            if merged_content:
                merged_content += "\n\n"
            merged_content += semantic_scholar_bibtex
            if self.verbose:
                print("[DEBUG] Added Semantic Scholar BibTeX content")

        return merged_content

    def process_pdf(self, pdf_path, bibtex_key="", entry_text="", bibtex_file_path=""):
        """Process a single PDF file, URL, or BibTeX metadata with multiple queries"""
        if self.verbose:
            print(f"[DEBUG] Starting processing of: {pdf_path}")

        # Determine if this is a URL or a file path
        is_url = pdf_path and (
            pdf_path.startswith("http://") or pdf_path.startswith("https://")
        )

        if is_url:
            if self.verbose:
                print(f"[DEBUG] Processing URL: {pdf_path}")
            # For URLs, we'll use the URL context API
            urls = [pdf_path]
            pdf_data = None
            metadata = None
            actual_path = None
        else:
            # Try to find PDF file first
            actual_path = None
            pdf_data = None
            metadata = None
            urls = []

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
                        print(
                            f"[DEBUG] Using metadata for {bibtex_key} (PDF not found)"
                        )
                else:
                    print(f"File not found: {pdf_path}", file=sys.stderr)
                    return False

        # Initialize document structure
        document_data = {
            "id": len(self.report_manager.results["documents"]) + 1,
            "file_path": actual_path or pdf_path,
            "bibtex_key": bibtex_key,
            "is_metadata_only": actual_path is None and not is_url,
            "is_url": is_url,
            "queries": [],
        }

        successful_queries = 0

        for i, query_info in enumerate(self.queries):
            if self.verbose:
                print(f"[DEBUG] Processing query {i + 1}/{len(self.queries)}")
                print(f"[DEBUG] Query parameters: {query_info.params}")

            # Create appropriate prompt and payload
            if is_url:
                # Use URL context for URLs
                query_text = f"Analyze the content from this URL: {pdf_path}\n\n{query_info.text}"
                payload = self.api_client.create_url_payload(query_text, urls)
            elif pdf_data:
                # Use PDF processing for local PDFs
                query_text = (
                    f"I'm attaching the PDF file {actual_path}\n\n{query_info.text}"
                )
                payload = self.api_client.create_pdf_payload(encoded_pdf, query_text)
            else:
                # Use metadata for entries without accessible content
                metadata_text = self.bibtex_processor.format_metadata_for_prompt(
                    metadata
                )
                query_text = f"I'm providing bibliographic metadata instead of the PDF file (file not available: {pdf_path}):\n\n{metadata_text}\n\nBased on this metadata, please answer: {query_info.text}"
                payload = self.api_client.create_text_payload(query_text)

            # Apply query parameters to payload
            payload = self.api_client.apply_query_params(payload, query_info)

            # Make API request
            try:
                response_data = self.api_client.make_request(payload, query_info)

                # Log response
                with open(self.logfile, "a", encoding="utf-8") as f:
                    f.write(
                        f"=== Response for {actual_path or pdf_path or bibtex_key} (Query {i + 1}) ===\n"
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
                query_structure = query_info.structure
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
                    f"Error processing query {i + 1} for {actual_path or pdf_path or bibtex_key}: {e}",
                    file=sys.stderr,
                )
                if self.verbose:
                    print(f"[DEBUG] Exception details: {type(e).__name__}: {e}")
                continue

        if successful_queries > 0:
            self.report_manager.add_document(document_data)

            if self.verbose:
                print(
                    f"[DEBUG] Successfully processed {successful_queries} queries for {actual_path or pdf_path or bibtex_key}"
                )

            # Record processed file
            with open(self.processed_list, "a", encoding="utf-8") as f:
                if actual_path:
                    f.write(f"{actual_path}|{bibtex_key}\n")
                elif is_url:
                    f.write(f"URL:{pdf_path}|{bibtex_key}\n")
                else:
                    f.write(f"METADATA:{bibtex_key}|{bibtex_key}\n")

            # Flush JSON and CSV output after each document
            self.report_manager.save_json_report(self.json_report_file)
            self.report_manager.save_csv_report(self.csv_report_file)

            if self.verbose:
                print(
                    f"[DEBUG] Flushed results to {self.json_report_file} and {self.csv_report_file}"
                )

            display_path = actual_path or pdf_path or f"metadata for {bibtex_key}"
            print(f"Successfully processed: {display_path}")
            return True

        if self.verbose:
            print(
                f"[DEBUG] No responses processed for {actual_path or pdf_path or bibtex_key}"
            )
        return False

    def _apply_filters(self):
        """Apply filters sequentially based on query responses"""
        if self.verbose:
            print("[DEBUG] Applying filters to documents")

        # Start with all documents
        remaining_docs = self.report_manager.results["documents"][:]

        for query_idx, query in enumerate(self.queries):
            if not query.filter_on:
                continue

            if self.verbose:
                print(
                    f"[DEBUG] Applying filter on field '{query.filter_on}' for query {query_idx + 1}"
                )

            filtered_docs = []
            newly_filtered = []

            for doc in remaining_docs:
                # Find the response for this query
                query_response = None
                for q in doc["queries"]:
                    if q["query_id"] == query_idx + 1:
                        query_response = q["response"]
                        break

                if query_response and isinstance(query_response, dict):
                    field_value = query_response.get(query.filter_on)

                    # Validate boolean type
                    if not isinstance(field_value, bool):
                        print(
                            f"Error: Field '{query.filter_on}' in document {doc['id']} ({doc['bibtex_key']}) has non-boolean value: {field_value}"
                        )
                        sys.exit(1)

                    if field_value:
                        filtered_docs.append(doc)
                        if self.verbose:
                            print(
                                f"[DEBUG] Document {doc['id']} ({doc['bibtex_key']}) passed filter"
                            )
                    else:
                        newly_filtered.append(doc)
                        if self.verbose:
                            print(
                                f"[DEBUG] Document {doc['id']} ({doc['bibtex_key']}) filtered out by {query.filter_on}=false"
                            )
                else:
                    # If no response or not structured, filter out
                    newly_filtered.append(doc)
                    if self.verbose:
                        print(
                            f"[DEBUG] Document {doc['id']} ({doc['bibtex_key']}) filtered out (no structured response)"
                        )

            # Update remaining documents and track filtered out
            remaining_docs = filtered_docs
            self.filtered_out_documents.extend(newly_filtered)

            if self.verbose:
                print(
                    f"[DEBUG] After filter on '{query.filter_on}': {len(remaining_docs)} remaining, {len(newly_filtered)} newly filtered"
                )

        # Update final results
        self.report_manager.results["documents"] = remaining_docs
        self.report_manager.results["metadata"]["total_documents"] = len(remaining_docs)
        self.report_manager.results["metadata"]["filtered_out_count"] = len(
            self.filtered_out_documents
        )

        if self.verbose:
            print(
                f"[DEBUG] Final filtering results: {len(remaining_docs)} documents remaining, {len(self.filtered_out_documents)} filtered out"
            )

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
                f.write(f"URL: {'Yes' if doc.get('is_url', False) else 'No'}\n")
                f.write("-" * 40 + "\n")

        print(f"Filtered out documents list saved to: {filtered_out_file}")

    def process_files(self, files):
        """Main processing logic"""
        if self.verbose:
            print(f"[DEBUG] Starting file processing for {len(files)} files")

        # Check if any queries use Semantic Scholar
        has_semantic_scholar = any(
            q.params.get("semantic_scholar", False) for q in self.queries
        )

        # Process Semantic Scholar queries first if any exist
        semantic_scholar_bibtex = ""
        if has_semantic_scholar:
            if self.verbose:
                print("[DEBUG] Processing Semantic Scholar queries")
            semantic_scholar_bibtex = self._process_semantic_scholar_queries()

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
                    merged_content = self._merge_bibtex_files(
                        bibtex_file, semantic_scholar_bibtex
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
                        self.process_pdf(
                            mapping["pdf_path"],
                            mapping["bibtex_key"],
                            mapping["entry_text"],
                            temp_merged_file,
                        )

                    if self.verbose:
                        print(
                            f"[DEBUG] Created and processed merged file: {temp_merged_file}"
                        )
            else:
                # Case 2: Only Semantic Scholar results (no BibTeX files)
                print("Processing Semantic Scholar results")
                merged_content = self._merge_bibtex_files(None, semantic_scholar_bibtex)

                # Create a temporary file for Semantic Scholar results
                temp_ss_file = "semantic_scholar_results.bib"
                with open(temp_ss_file, "w", encoding="utf-8") as f:
                    f.write(merged_content)

                # Process the Semantic Scholar results
                pdf_mappings = self.bibtex_processor.extract_pdfs_from_bibtex(
                    temp_ss_file
                )
                for mapping in pdf_mappings:
                    self.process_pdf(
                        mapping["pdf_path"],
                        mapping["bibtex_key"],
                        mapping["entry_text"],
                        temp_ss_file,
                    )

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
                    self.process_pdf(
                        mapping["pdf_path"],
                        mapping["bibtex_key"],
                        mapping["entry_text"],
                        bibtex_file,
                    )

        # Process individual PDF files (these are independent of BibTeX/Semantic Scholar)
        for pdf_file in pdf_files:
            if self.verbose:
                print(f"[DEBUG] Processing individual PDF: {pdf_file}")
            self.process_pdf(pdf_file)

        # Apply filtering after all documents are processed
        self._apply_filters()

        # Generate filtered out list
        self._save_filtered_out_list()

        # Save final report after filtering
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
