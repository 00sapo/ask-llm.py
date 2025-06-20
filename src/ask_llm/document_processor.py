#!/usr/bin/env python3

import json
import base64
import sys
import os

from .api import GeminiAPIClient
from .bibtex import BibtexProcessor
from .pdf_search import PDFDownloader
from .search_strategy import GoogleGroundingStrategy, QwantSearchStrategy
from .url_resolver import URLResolver


class DocumentProcessor:
    def __init__(
        self,
        api_client: GeminiAPIClient,
        bibtex_processor: BibtexProcessor,
        pdf_downloader: PDFDownloader,
        verbose=False,
        use_qwant_strategy=False,
    ):
        self.api_client = api_client
        self.bibtex_processor = bibtex_processor
        self.pdf_downloader = pdf_downloader
        self.verbose = verbose
        self.use_qwant_strategy = use_qwant_strategy
        self.downloaded_pdfs = []  # Track downloaded PDF files for cleanup

        # Initialize search strategy
        if use_qwant_strategy:
            self.search_strategy = QwantSearchStrategy(
                self.pdf_downloader, verbose=verbose
            )
            if self.verbose:
                print("[DEBUG] Using Qwant search strategy")
        else:
            url_resolver = URLResolver(verbose=verbose)
            self.search_strategy = GoogleGroundingStrategy(
                self.api_client, url_resolver, self.pdf_downloader, verbose=verbose
            )
            if self.verbose:
                print("[DEBUG] Using Google grounding search strategy")

    def _is_url(self, path: str) -> bool:
        """Check if the given path is a URL"""
        return path and (path.startswith("http://") or path.startswith("https://"))

    def _download_pdf_from_url(self, url: str, title: str = "downloaded_pdf") -> str:
        """Download PDF from URL and return local path"""
        if self.verbose:
            print(f"[DEBUG] Downloading PDF from URL: {url}")

        downloaded_path = self.pdf_downloader.download_pdf(url, title)
        if downloaded_path:
            self.downloaded_pdfs.append(downloaded_path)
            if self.verbose:
                print(f"[DEBUG] Successfully downloaded PDF to: {downloaded_path}")
            print(f"📥 Downloaded PDF from URL: {url}")
            return downloaded_path
        else:
            if self.verbose:
                print(f"[DEBUG] Failed to download PDF from URL: {url}")
            print(f"❌ Failed to download PDF from URL: {url}")
            return None

    def _find_pdf_file(self, pdf_path, bibtex_dir=None):
        """Find PDF file in common locations if not found at given path"""
        if self.verbose:
            print(f"[DEBUG] Looking for PDF file: {pdf_path}")

        if os.path.isfile(pdf_path):
            if self.verbose:
                print(f"[DEBUG] Found PDF at original path: {pdf_path}")
            print(f"📄 PDF found: {pdf_path}")
            return pdf_path

        # If we have a BibTeX directory, try relative to that first
        if bibtex_dir:
            bibtex_relative_path = os.path.join(bibtex_dir, pdf_path)
            if os.path.isfile(bibtex_relative_path):
                if self.verbose:
                    print(
                        f"[DEBUG] Found PDF relative to BibTeX directory: {bibtex_relative_path}"
                    )
                print(f"📄 PDF found: {bibtex_relative_path}")
                return bibtex_relative_path

        if self.verbose:
            print("[DEBUG] PDF file not found in any location")
        print(f"❌ PDF not found: {pdf_path}")
        return None

    def _search_for_pdf(self, metadata, query_text="", response_data=None):
        """Search for PDF using the configured strategy and always download
        Returns tuple of (downloaded_path, original_url)"""
        if not metadata:
            return None, None

        if self.verbose:
            strategy_name = "Qwant" if self.use_qwant_strategy else "Google grounding"
            print(f"[DEBUG] Searching for PDF using {strategy_name} strategy")

        title = metadata.get("title", "")
        if title:
            print(f"🔍 Searching for PDF: {title}")

        try:
            # Use strategy to discover URLs and get both path and original URL
            result = self.search_strategy.discover_urls_with_source(
                metadata, query_text or "", response_data or {}
            )

            if result:
                downloaded_path, original_url = result
                if self.verbose:
                    print(
                        f"[DEBUG] Downloaded PDF to: {downloaded_path} from URL: {original_url}"
                    )
                    # Track downloaded file for cleanup
                    self.downloaded_pdfs.append(downloaded_path)
                print(f"✅ PDF downloaded: {downloaded_path}")
                return downloaded_path, original_url
            else:
                if self.verbose:
                    print("[DEBUG] PDF search did not find any results")
                print("❌ PDF search failed: No results found")
                return None, None
        except Exception as e:
            if self.verbose:
                print(f"[DEBUG] PDF search failed with error: {e}")
            print(f"❌ PDF search failed: {e}")
            return None, None

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
        """Process a single PDF file or BibTeX metadata with multiple queries"""
        if self.verbose:
            print(f"[DEBUG] Starting processing of: {pdf_path}")

        # Initialize variables
        actual_path = None
        pdf_data = None
        metadata = None
        pdf_source = "unknown"
        pdf_url = None  # Track original URL for downloaded PDFs

        # Check if pdf_path is a URL and handle accordingly
        if pdf_path:
            if self._is_url(pdf_path):
                # If it's a URL, download it directly
                if self.verbose:
                    print(f"[DEBUG] Detected URL, downloading: {pdf_path}")

                title = bibtex_key or "downloaded_pdf"
                actual_path = self._download_pdf_from_url(pdf_path, title)
                if actual_path:
                    pdf_url = pdf_path  # Store original URL
                    pdf_source = "url_download"
                # else, if actual_path is still not set, let's search for it (see below)
            else:
                # It's a local file path, try to find it
                actual_path = self._find_pdf_file(
                    pdf_path,
                    os.path.dirname(bibtex_file_path) if bibtex_file_path else None,
                )

        if actual_path:
            # Process local PDF (either originally local or downloaded from URL)
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
                        if pdf_source == "unknown":
                            pdf_source = "local_file"
            except Exception as e:
                print(f"Error reading PDF {actual_path}: {e}", file=sys.stderr)
                return None, False
        else:
            # PDF not found locally and not a URL - try to search for it and download or use metadata
            if entry_text and bibtex_key:
                metadata = self.bibtex_processor.extract_metadata(
                    entry_text, bibtex_key
                )

                # Try to search for PDF using metadata
                search_result, original_url = self._search_for_pdf(metadata)

                if search_result:
                    # Search result should be downloaded file path
                    actual_path = search_result
                    pdf_url = original_url  # Store the original URL
                    try:
                        with open(actual_path, "rb") as f:
                            pdf_data = f.read()
                            if pdf_data:
                                encoded_pdf = base64.b64encode(pdf_data).decode("utf-8")
                                pdf_source = "searched_download"
                                if self.verbose:
                                    print(
                                        f"[DEBUG] Using downloaded PDF: {actual_path} from URL: {pdf_url}"
                                    )
                    except Exception as e:
                        print(
                            f"Error reading downloaded PDF {actual_path}: {e}",
                            file=sys.stderr,
                        )
                        # Fallback to metadata
                        pdf_source = "metadata_only"
                        pdf_url = None  # Clear URL if we can't use the downloaded file
                        if self.verbose:
                            print(f"[DEBUG] Falling back to metadata for {bibtex_key}")
                        print(f"📚 Using metadata only: {bibtex_key}")
                else:
                    # No PDF found, use metadata only
                    pdf_source = "metadata_only"
                    if self.verbose:
                        print(
                            f"[DEBUG] Using metadata for {bibtex_key} (PDF not found)"
                        )
                    print(f"📚 Using metadata only: {bibtex_key}")
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
            "pdf_source": pdf_source,  # Track how the PDF was obtained
            "pdf_url": pdf_url,  # Track original URL for downloaded PDFs
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
            if pdf_data:
                # Include metadata with PDF
                metadata_text = ""
                if metadata:
                    metadata_text = self.bibtex_processor.format_metadata_for_prompt(
                        metadata
                    )
                    metadata_text = f"\n\nDocument metadata:\n{metadata_text}"

                query_text = f"I'm attaching the PDF file {actual_path}{metadata_text}\n\n{query_info.text}"
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

                # If using Google grounding strategy and no PDF found yet, try to discover URLs from grounding
                if (
                    not pdf_data
                    and not self.use_qwant_strategy
                    and query_info.params.get("google_search", False)
                    and grounding_metadata
                ):
                    try:
                        discovered_result = (
                            self.search_strategy.discover_urls_with_source(
                                metadata or {}, query_text, response_data
                            )
                        )

                        if discovered_result and not actual_path:
                            # Download first discovered PDF
                            downloaded_path, original_url = discovered_result
                            if downloaded_path and os.path.exists(downloaded_path):
                                actual_path = downloaded_path
                                pdf_source = "searched_download"
                                pdf_url = original_url
                                document_data["file_path"] = downloaded_path
                                document_data["pdf_source"] = pdf_source
                                document_data["pdf_url"] = pdf_url
                                # Track for cleanup
                                self.downloaded_pdfs.append(downloaded_path)

                                # Try to read the downloaded PDF for subsequent queries
                                try:
                                    with open(actual_path, "rb") as f:
                                        pdf_data = f.read()
                                        if pdf_data:
                                            encoded_pdf = base64.b64encode(
                                                pdf_data
                                            ).decode("utf-8")
                                            document_data["is_metadata_only"] = False
                                            if self.verbose:
                                                print(
                                                    f"[DEBUG] Downloaded and loaded PDF from Google grounding: {downloaded_path} from URL: {pdf_url}"
                                                )
                                except Exception as e:
                                    if self.verbose:
                                        print(
                                            f"[DEBUG] Could not read downloaded PDF: {e}"
                                        )
                    except AttributeError:
                        # Fallback to old method if discover_urls_with_source doesn't exist
                        discovered_urls = self.search_strategy.discover_urls(
                            metadata or {}, query_text, response_data
                        )

                        if discovered_urls and not actual_path:
                            # Download first discovered PDF
                            downloaded_path = discovered_urls[0]
                            if downloaded_path and os.path.exists(downloaded_path):
                                actual_path = downloaded_path
                                pdf_source = "searched_download"
                                document_data["file_path"] = downloaded_path
                                document_data["pdf_source"] = pdf_source
                                # Track for cleanup
                                self.downloaded_pdfs.append(downloaded_path)

                                # Try to read the downloaded PDF for subsequent queries
                                try:
                                    with open(actual_path, "rb") as f:
                                        pdf_data = f.read()
                                        if pdf_data:
                                            encoded_pdf = base64.b64encode(
                                                pdf_data
                                            ).decode("utf-8")
                                            document_data["is_metadata_only"] = False
                                            if self.verbose:
                                                print(
                                                    f"[DEBUG] Downloaded and loaded PDF from Google grounding: {downloaded_path}"
                                                )
                                except Exception as e:
                                    if self.verbose:
                                        print(
                                            f"[DEBUG] Could not read downloaded PDF: {e}"
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
            self.pdf_downloader.cleanup_temp_files(self.downloaded_pdfs)
            self.downloaded_pdfs.clear()
