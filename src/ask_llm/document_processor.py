#!/usr/bin/env python3

import json
import base64
import sys
import os

from .api import GeminiAPIClient
from .bibtex import BibtexProcessor
from .pdf_search import PDFSearcher


class DocumentProcessor:
    def __init__(
        self,
        api_client: GeminiAPIClient,
        bibtex_processor: BibtexProcessor,
        pdf_searcher: PDFSearcher,
        verbose=False,
    ):
        self.api_client = api_client
        self.bibtex_processor = bibtex_processor
        self.pdf_searcher = pdf_searcher
        self.verbose = verbose
        self.downloaded_pdfs = []  # Track downloaded PDF files for cleanup

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

    def _search_for_pdf(self, metadata):
        """Search for PDF using title and authors from metadata"""
        if not metadata:
            return None

        title = metadata.get("title", "")
        authors = metadata.get("author", "")

        if not title:
            if self.verbose:
                print("[DEBUG] No title available for PDF search")
            return None

        if self.verbose:
            print(f"[DEBUG] Searching for PDF using title: {title[:50]}...")

        try:
            result = self.pdf_searcher.search_pdf(title, authors)
            if result:
                if self.verbose:
                    if self.pdf_searcher.download_pdfs:
                        print(f"[DEBUG] Downloaded PDF to: {result}")
                        # Track downloaded file for cleanup
                        self.downloaded_pdfs.append(result)
                    else:
                        print(f"[DEBUG] Found PDF URL: {result}")
                return result
            else:
                if self.verbose:
                    print("[DEBUG] PDF search did not find any results")
                return None
        except Exception as e:
            if self.verbose:
                print(f"[DEBUG] PDF search failed with error: {e}")
            return None

    def _evaluate_filter(self, response, filter_field, document_data, query_id):
        """Evaluate filter immediately after query processing.
        Returns True if processing should continue, False if document should be filtered out."""

        if not isinstance(response, dict):
            # No structured response - filter out
            document_data["is_filtered_out"] = True
            document_data["filtered_at_query"] = query_id
            document_data["filter_reason"] = (
                f"No structured response for filter field '{filter_field}'"
            )
            if self.verbose:
                print(
                    f"[DEBUG] Document {document_data['id']} filtered out at query {query_id}: No structured response"
                )
            return False

        field_value = response.get(filter_field)

        if not isinstance(field_value, bool):
            print(f"Error: Field '{filter_field}' has non-boolean value: {field_value}")
            sys.exit(1)

        if not field_value:  # False means filter out
            document_data["is_filtered_out"] = True
            document_data["filtered_at_query"] = query_id
            document_data["filter_reason"] = (
                f"Filter field '{filter_field}' evaluated to False"
            )
            if self.verbose:
                print(
                    f"[DEBUG] Document {document_data['id']} ({document_data['bibtex_key']}) filtered out at query {query_id}: {filter_field}=false"
                )
            return False

        if self.verbose:
            print(
                f"[DEBUG] Document {document_data['id']} ({document_data['bibtex_key']}) passed filter at query {query_id}: {filter_field}=true"
            )
        return True  # Continue processing

    def process_document(
        self,
        pdf_path,
        bibtex_key="",
        entry_text="",
        bibtex_file_path="",
        queries=None,
        document_id=1,
        logfile="log.txt",
    ):
        """Process a single PDF file, URL, or BibTeX metadata with multiple queries"""
        if self.verbose:
            print(f"[DEBUG] Starting processing of: {pdf_path}")

        # Determine if this is a URL or a file path
        is_url = pdf_path and (
            pdf_path.startswith("http://") or pdf_path.startswith("https://")
        )

        # Initialize variables
        actual_path = None
        pdf_data = None
        metadata = None
        urls = []
        pdf_source = "unknown"

        if is_url:
            if self.verbose:
                print(f"[DEBUG] Processing URL: {pdf_path}")
            # For URLs, we'll use the URL context API
            urls = [pdf_path]
            pdf_source = "provided_url"
        else:
            # Try to find PDF file first
            if pdf_path:
                actual_path = self._find_pdf_file(
                    pdf_path,
                    os.path.dirname(bibtex_file_path) if bibtex_file_path else None,
                )

            if actual_path:
                # Process local PDF
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
                            pdf_source = "local_file"
                except Exception as e:
                    print(f"Error reading PDF {actual_path}: {e}", file=sys.stderr)
                    return None, False
            else:
                # PDF not found locally - try to search for it or use metadata
                if entry_text and bibtex_key:
                    metadata = self.bibtex_processor.extract_metadata(
                        entry_text, bibtex_key
                    )

                    # Try to search for PDF using metadata
                    search_result = self._search_for_pdf(metadata)

                    if search_result:
                        # Check if search result is URL or downloaded file
                        if search_result.startswith(
                            "http://"
                        ) or search_result.startswith("https://"):
                            # URL mode - use URL context
                            urls = [search_result]
                            is_url = True
                            pdf_source = "searched_url"
                            if self.verbose:
                                print(
                                    f"[DEBUG] Using searched PDF URL: {search_result}"
                                )
                        else:
                            # Download mode - process as local file
                            actual_path = search_result
                            try:
                                with open(actual_path, "rb") as f:
                                    pdf_data = f.read()
                                    if pdf_data:
                                        encoded_pdf = base64.b64encode(pdf_data).decode(
                                            "utf-8"
                                        )
                                        pdf_source = "searched_download"
                                        if self.verbose:
                                            print(
                                                f"[DEBUG] Using downloaded PDF: {actual_path}"
                                            )
                            except Exception as e:
                                print(
                                    f"Error reading downloaded PDF {actual_path}: {e}",
                                    file=sys.stderr,
                                )
                                # Fallback to metadata
                                pdf_source = "metadata_only"
                                if self.verbose:
                                    print(
                                        f"[DEBUG] Falling back to metadata for {bibtex_key}"
                                    )
                    else:
                        # No PDF found, use metadata only
                        pdf_source = "metadata_only"
                        if self.verbose:
                            print(
                                f"[DEBUG] Using metadata for {bibtex_key} (PDF not found)"
                            )
                else:
                    print(f"File not found: {pdf_path}", file=sys.stderr)
                    return None, False

        # Initialize document structure with new filtering fields
        document_data = {
            "id": document_id,
            "file_path": actual_path or pdf_path,
            "bibtex_key": bibtex_key,
            "bibtex_metadata": metadata or {},
            "is_metadata_only": pdf_source == "metadata_only",
            "is_url": is_url,
            "pdf_source": pdf_source,  # Track how the PDF was obtained
            "is_filtered_out": False,  # Track if document was filtered during processing
            "filtered_at_query": None,  # Which query caused the filtering
            "filter_reason": None,  # Reason for filtering
            "queries": [],
        }

        successful_queries = 0

        for i, query_info in enumerate(queries or []):
            # Skip Semantic Scholar queries when processing documents
            if query_info.params.get("semantic_scholar", False):
                if self.verbose:
                    print(
                        f"[DEBUG] Skipping Semantic Scholar query {i + 1} for document processing"
                    )
                continue

            if self.verbose:
                print(f"[DEBUG] Processing query {i + 1}/{len(queries)}")
                print(f"[DEBUG] Query parameters: {query_info.params}")

            # Create appropriate prompt and payload
            if is_url:
                # Use URL context for URLs
                query_text = (
                    f"Analyze the content from this URL: {urls[0]}\n\n{query_info.text}"
                )
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
                with open(logfile, "a", encoding="utf-8") as f:
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

                # Check for early termination based on filter
                if query_info.filter_on:
                    should_continue = self._evaluate_filter(
                        parsed_response, query_info.filter_on, document_data, i + 1
                    )
                    if not should_continue:
                        # Document filtered out - stop processing remaining queries
                        if self.verbose:
                            print(
                                f"[DEBUG] Early termination: document filtered out at query {i + 1}"
                            )
                        break  # Stop processing remaining queries

            except Exception as e:
                print(
                    f"Error processing query {i + 1} for {actual_path or pdf_path or bibtex_key}: {e}",
                    file=sys.stderr,
                )
                if self.verbose:
                    print(f"[DEBUG] Exception details: {type(e).__name__}: {e}")
                continue

        return document_data, successful_queries > 0

    def cleanup_downloaded_pdfs(self):
        """Clean up downloaded temporary PDF files"""
        if self.downloaded_pdfs:
            if self.verbose:
                print(
                    f"[DEBUG] Cleaning up {len(self.downloaded_pdfs)} downloaded PDF files"
                )
            self.pdf_searcher.cleanup_temp_files(self.downloaded_pdfs)
            self.downloaded_pdfs.clear()
