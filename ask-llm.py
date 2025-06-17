#!/usr/bin/env python3

import json
import base64
import urllib.request
import subprocess
import sys
import os
import re
from datetime import datetime
from pathlib import Path
import argparse


class DocumentAnalyzer:
    def __init__(self, verbose=False):
        self.verbose = verbose
        self.api_key = self._get_api_key()
        self.base_url = "https://generativelanguage.googleapis.com/v1beta"
        self.model = "gemini-2.5-flash-preview-05-20"
        self.processed_list = "processed_files.txt"
        self.logfile = "log.txt"
        self.report_file = "analysis_report.json"

        if self.verbose:
            print("[DEBUG] Initializing DocumentAnalyzer")
            print(f"[DEBUG] Base URL: {self.base_url}")
            print(f"[DEBUG] Default model: {self.model}")

        # Load configuration
        self.queries = self._load_queries("query.md")

        if self.verbose:
            print(f"[DEBUG] Loaded {len(self.queries)} queries")

        # Clear output files
        self._clear_files()

    def _get_api_key(self):
        """Get API key using rbw"""
        if self.verbose:
            print("[DEBUG] Retrieving API key using rbw")
        try:
            result = subprocess.run(
                ["rbw", "get", "gemini_key"], capture_output=True, text=True, check=True
            )
            if self.verbose:
                print("[DEBUG] API key retrieved successfully")
            return result.stdout.strip()
        except subprocess.CalledProcessError:
            print("Error: Could not retrieve API key using 'rbw get gemini_key'")
            sys.exit(1)

    def _load_queries(self, filename):
        """Load and parse queries from text file"""
        if self.verbose:
            print(f"[DEBUG] Loading queries from {filename}")
        try:
            with open(filename, "r", encoding="utf-8") as f:
                content = f.read().strip()
        except FileNotFoundError:
            print(f"Error: {filename} not found")
            sys.exit(1)

        # Split by 3 or more equals signs
        query_sections = re.split(r"={3,}", content)
        if self.verbose:
            print(f"[DEBUG] Found {len(query_sections)} query sections")

        queries = []
        for section_idx, section in enumerate(query_sections):
            section = section.strip()
            if not section:
                if self.verbose:
                    print(f"[DEBUG] Section {section_idx} is empty, skipping")
                continue

            if self.verbose:
                print(f"[DEBUG] Processing query section {section_idx + 1}")

            # Parse parameters and query text
            lines = section.split("\n")
            params = {}
            query_lines = []

            for line in lines:
                line = line.strip()
                if ":" in line and any(
                    param in line.lower()
                    for param in ["model-name:", "temperature:", "google-search:"]
                ):
                    key, value = line.split(":", 1)
                    key = key.strip().lower().replace("-", "_")
                    value = value.strip()

                    if self.verbose:
                        print(f"[DEBUG] Found parameter: {key} = {value}")

                    if key == "temperature":
                        try:
                            params[key] = float(value)
                        except ValueError:
                            print(
                                f"Warning: Invalid temperature value '{value}', ignoring"
                            )
                    elif key == "model_name":
                        params["model"] = value
                    elif key == "google_search":
                        # Parse boolean values
                        if value.lower() in ["true", "yes", "1", "on"]:
                            params["google_search"] = True
                        elif value.lower() in ["false", "no", "0", "off"]:
                            params["google_search"] = False
                        else:
                            print(
                                f"Warning: Invalid google-search value '{value}', should be true/false"
                            )
                else:
                    query_lines.append(line)

            query_text = "\n".join(query_lines).strip()

            # Look for JSON code blocks in the query
            json_blocks = re.findall(r"```json\s*\n(.*?)\n```", section, re.DOTALL)
            structure = None
            if json_blocks:
                try:
                    structure = json.loads(json_blocks[0])  # Use first JSON block
                    if self.verbose:
                        print(
                            f"[DEBUG] Found JSON structure in query {len(queries) + 1}"
                        )
                except json.JSONDecodeError as e:
                    print(
                        f"Warning: Invalid JSON structure in query {len(queries) + 1}: {e}"
                    )

            if query_text:
                queries.append(
                    {"text": query_text, "params": params, "structure": structure}
                )
                if self.verbose:
                    print(
                        f"[DEBUG] Added query {len(queries)} with {len(params)} parameters and {'structure' if structure else 'no structure'}"
                    )

        if self.verbose:
            print(f"[DEBUG] Total queries loaded: {len(queries)}")
        return queries

    def _load_json(self, filename):
        """Load JSON file"""
        if self.verbose:
            print(f"[DEBUG] Attempting to load JSON from {filename}")
        if not os.path.exists(filename):
            if self.verbose:
                print(f"[DEBUG] File {filename} does not exist")
            return None
        try:
            with open(filename, "r", encoding="utf-8") as f:
                data = json.load(f)
                if self.verbose:
                    print(
                        f"[DEBUG] Successfully loaded JSON with {len(data) if isinstance(data, dict) else 'unknown'} top-level keys"
                    )
                return data
        except json.JSONDecodeError as e:
            print(f"Error: Invalid JSON in {filename}: {e}")
            sys.exit(1)

    def _initialize_json_structure(self):
        """Initialize the JSON output structure"""
        self.results = {
            "metadata": {
                "generated": datetime.now().isoformat(),
                "total_documents": 0,
                "model_used": self.model,
                "queries": [],
            },
            "documents": [],
        }

        # Store query information
        for i, query_info in enumerate(self.queries):
            query_data = {
                "id": i + 1,
                "text": query_info["text"],
                "parameters": query_info["params"],
                "structure": query_info.get("structure"),
            }
            self.results["metadata"]["queries"].append(query_data)

    def _clear_files(self):
        """Clear or create output files and initialize JSON structure"""
        if self.verbose:
            print("[DEBUG] Clearing output files")
        for filename in [self.processed_list, self.logfile]:
            Path(filename).write_text("")
            if self.verbose:
                print(f"[DEBUG] Cleared {filename}")

        # Initialize JSON structure
        self._initialize_json_structure()

    def _extract_bibtex_metadata(self, entry_text, bibtex_key):
        """Extract metadata from a BibTeX entry"""
        metadata = {"bibtex_key": bibtex_key}

        # Fields to extract
        fields = ["title", "author", "year", "abstract", "journal", "booktitle"]

        for field in fields:
            # Match field = {content} or field = "content"
            pattern = rf'{field}\s*=\s*[{{"]([^{{}}"]*)[\}}"]\s*[,\s]'
            match = re.search(pattern, entry_text, re.IGNORECASE | re.DOTALL)
            if match:
                value = match.group(1).strip()
                # Clean up common LaTeX formatting
                value = re.sub(
                    r"\\[a-zA-Z]+\{([^}]*)\}", r"\1", value
                )  # \emph{text} -> text
                value = re.sub(r"[{}]", "", value)  # Remove remaining braces
                value = value.replace("\\&", "&").replace("\\_", "_")  # Common escapes
                metadata[field] = value

        return metadata

    def _format_metadata_for_prompt(self, metadata):
        """Format metadata for inclusion in prompt"""
        parts = []
        if metadata.get("title"):
            parts.append(f"Title: {metadata['title']}")
        if metadata.get("author"):
            parts.append(f"Authors: {metadata['author']}")
        if metadata.get("year"):
            parts.append(f"Year: {metadata['year']}")
        if metadata.get("journal"):
            parts.append(f"Journal: {metadata['journal']}")
        if metadata.get("booktitle"):
            parts.append(f"Book/Conference: {metadata['booktitle']}")
        if metadata.get("abstract"):
            parts.append(f"Abstract: {metadata['abstract']}")

        return "\n".join(parts)

    def extract_pdfs_from_bibtex(self, bibtex_file):
        """Extract PDF paths and keys from BibTeX file, including full entry text"""
        if self.verbose:
            print(f"[DEBUG] Extracting PDFs from BibTeX file: {bibtex_file}")
        try:
            with open(bibtex_file, "r", encoding="utf-8") as f:
                content = f.read()
        except FileNotFoundError:
            print(f"BibTeX file not found: {bibtex_file}")
            return []

        pdf_mappings = []
        # Split by @ to get entries
        entries = re.split(r"@", content)[1:]  # Skip first empty part

        if self.verbose:
            print(f"[DEBUG] Found {len(entries)} BibTeX entries")

        for entry_idx, entry in enumerate(entries):
            lines = entry.split("\n")
            if not lines:
                continue

            # Extract entry key from first line
            key_match = re.search(r"^[^{]*\{([^,]+)", lines[0])
            if not key_match:
                if self.verbose:
                    print(f"[DEBUG] Entry {entry_idx} has no valid key, skipping")
                continue

            bibtex_key = key_match.group(1).strip()
            full_entry = "@" + entry  # Store full entry for metadata extraction

            if self.verbose:
                print(f"[DEBUG] Processing BibTeX entry: {bibtex_key}")

            # Look for file field
            pdf_path = None
            for line in lines:
                file_match = re.search(r'file\s*=\s*["{]([^"}]+)', line)
                if file_match:
                    file_path = file_match.group(1)
                    # Extract PDF path (first part before semicolon)
                    pdf_match = re.search(r"^([^;:]+\.pdf)", file_path)
                    if pdf_match:
                        pdf_path = pdf_match.group(1)
                        if self.verbose:
                            print(f"[DEBUG] Found PDF: {pdf_path} for key {bibtex_key}")
                        break

            # Store mapping with full entry text
            pdf_mappings.append(
                {
                    "pdf_path": pdf_path,
                    "bibtex_key": bibtex_key,
                    "entry_text": full_entry,
                }
            )

        if self.verbose:
            print(f"[DEBUG] Extracted {len(pdf_mappings)} PDF mappings from BibTeX")
        return pdf_mappings

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

    def _save_json_report(self):
        """Save results to JSON file"""
        if self.verbose:
            print(f"[DEBUG] Saving JSON report to {self.report_file}")

        with open(self.report_file, "w", encoding="utf-8") as f:
            json.dump(self.results, f, indent=2, ensure_ascii=False)

        if self.verbose:
            print(
                f"[DEBUG] JSON report saved with {len(self.results['documents'])} documents"
            )

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
                metadata = self._extract_bibtex_metadata(entry_text, bibtex_key)
                if self.verbose:
                    print(f"[DEBUG] Using metadata for {bibtex_key} (PDF not found)")
            else:
                print(f"File not found: {pdf_path}", file=sys.stderr)
                return False

        # Initialize document structure
        document_data = {
            "id": len(self.results["documents"]) + 1,
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

            # Use query-specific model or default
            model = query_info["params"].get("model", self.model)
            if self.verbose:
                print(f"[DEBUG] Using model: {model}")

            # Create appropriate prompt and payload
            if pdf_data:
                # PDF processing
                query_text = (
                    f"I'm attaching the PDF file {actual_path}\n\n{query_info['text']}"
                )
                payload = {
                    "contents": [
                        {
                            "parts": [
                                {
                                    "inline_data": {
                                        "mime_type": "application/pdf",
                                        "data": encoded_pdf,
                                    }
                                },
                                {"text": query_text},
                            ]
                        }
                    ],
                    "generationConfig": {},
                }
            else:
                # Metadata processing
                metadata_text = self._format_metadata_for_prompt(metadata)
                query_text = f"I'm providing bibliographic metadata instead of the PDF file (file not available: {pdf_path}):\n\n{metadata_text}\n\nBased on this metadata, please answer: {query_info['text']}"
                payload = {
                    "contents": [{"parts": [{"text": query_text}]}],
                    "generationConfig": {},
                }

            # Add tools if Google Search is enabled
            tools = []
            if query_info["params"].get("google_search", False):
                tools.append({"googleSearch": {}})
                if self.verbose:
                    print("[DEBUG] Google Search tool enabled for this query")

            if tools:
                payload["tools"] = tools

            # Add temperature if specified
            if "temperature" in query_info["params"]:
                payload["generationConfig"]["temperature"] = query_info["params"][
                    "temperature"
                ]
                if self.verbose:
                    print(
                        f"[DEBUG] Set temperature to: {query_info['params']['temperature']}"
                    )

            # Add structured output only if structure is available for this query
            query_structure = query_info.get("structure")
            if query_structure:
                payload["generationConfig"]["responseMimeType"] = "application/json"
                payload["generationConfig"]["responseSchema"] = query_structure
                if self.verbose:
                    print("[DEBUG] Structured output enabled for this query")

            # Make API request
            url = f"{self.base_url}/models/{model}:generateContent?key={self.api_key}"

            if self.verbose:
                print(f"[DEBUG] Making API request to: {url}")
                print(f"[DEBUG] Payload size: {len(json.dumps(payload))} characters")

            try:
                req = urllib.request.Request(
                    url,
                    data=json.dumps(payload).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                )

                if self.verbose:
                    print("[DEBUG] Sending request to Gemini API...")

                with urllib.request.urlopen(req) as response:
                    response_data = json.loads(response.read().decode("utf-8"))

                if self.verbose:
                    print(
                        f"[DEBUG] Received response with {len(str(response_data))} characters"
                    )

                # Log response
                with open(self.logfile, "a", encoding="utf-8") as f:
                    f.write(
                        f"=== Response for {actual_path or bibtex_key} (Query {i + 1}) ===\n"
                    )
                    json.dump(response_data, f, indent=2)
                    f.write("\n\n")

                # Extract response
                try:
                    response_content = response_data["candidates"][0]["content"][
                        "parts"
                    ][0]["text"]

                    if self.verbose:
                        print(
                            f"[DEBUG] Extracted response content: {len(response_content)} characters"
                        )

                    # Extract grounding metadata if available
                    grounding_metadata = response_data["candidates"][0].get(
                        "groundingMetadata"
                    )

                    if self.verbose and grounding_metadata:
                        print("[DEBUG] Found grounding metadata")
                        if "webSearchQueries" in grounding_metadata:
                            print(
                                f"[DEBUG] Search queries: {grounding_metadata['webSearchQueries']}"
                            )
                        if "groundingChunks" in grounding_metadata:
                            print(
                                f"[DEBUG] Found {len(grounding_metadata['groundingChunks'])} grounding chunks"
                            )

                    # Parse JSON response if structure was requested
                    parsed_response = response_content
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

                except (KeyError, IndexError):
                    print(
                        f"Error: No valid response for {actual_path or bibtex_key} (Query {i + 1})",
                        file=sys.stderr,
                    )
                    if self.verbose:
                        print(
                            f"[DEBUG] Response structure: {list(response_data.keys())}"
                        )
                    print(f"Response: {response_data}", file=sys.stderr)
                    continue

            except urllib.error.HTTPError as e:
                print(
                    f"HTTP Error {e.code} for {actual_path or bibtex_key} (Query {i + 1}): {e.reason}",
                    file=sys.stderr,
                )
                if self.verbose:
                    print(f"[DEBUG] HTTP Error details: {e.code} - {e.reason}")
                try:
                    error_response = json.loads(e.read().decode("utf-8"))
                    if "error" in error_response:
                        error_msg = error_response["error"].get(
                            "message", "Unknown error"
                        )
                        print(f"API Error Details: {error_msg}", file=sys.stderr)
                        if self.verbose:
                            print(f"[DEBUG] Full error response: {error_response}")
                except (json.JSONDecodeError, UnicodeDecodeError):
                    pass
                continue

            except Exception as e:
                print(
                    f"Error: Failed to call API for {actual_path or bibtex_key} (Query {i + 1}): {e}",
                    file=sys.stderr,
                )
                if self.verbose:
                    print(f"[DEBUG] Exception details: {type(e).__name__}: {e}")
                continue

        if successful_queries > 0:
            self.results["documents"].append(document_data)
            self.results["metadata"]["total_documents"] += 1

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
            pdf_mappings = self.extract_pdfs_from_bibtex(bibtex_file)

            for mapping in pdf_mappings:
                self.process_pdf(
                    mapping["pdf_path"],
                    mapping["bibtex_key"],
                    mapping["entry_text"],
                    bibtex_file,  # Pass the BibTeX file path
                )

        # Process individual PDF files
        for pdf_file in pdf_files:
            if self.verbose:
                print(f"[DEBUG] Processing individual PDF: {pdf_file}")
            self.process_pdf(pdf_file)  # No bibtex_file_path needed for direct PDFs

        # Generate final report
        self._save_json_report()

        print("\nProcessing complete!")
        print(f"Report saved to: {self.report_file}")
        print(f"Log saved to: {self.logfile}")
        print(f"Processed files list: {self.processed_list}")


def main():
    parser = argparse.ArgumentParser(
        description="Process PDF files and BibTeX bibliographies using the Gemini API with structured output."
    )
    parser.add_argument(
        "files",
        nargs="*",
        help="PDF files and/or BibTeX files to process",
    )
    parser.add_argument(
        "--no-clear",
        action="store_true",
        help="Do not clear output files before processing (append mode)",
    )
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="Override Gemini model (default: gemini-2.5-flash-preview-05-20)",
    )
    parser.add_argument(
        "--query",
        type=str,
        default=None,
        help="Override query prompt (default: contents of query.txt)",
    )
    parser.add_argument(
        "--report",
        type=str,
        default=None,
        help="Override report output file (default: analysis_report.json)",
    )
    parser.add_argument(
        "--log",
        type=str,
        default=None,
        help="Override log output file (default: log.txt)",
    )
    parser.add_argument(
        "--processed-list",
        type=str,
        default=None,
        help="Override processed files list output (default: processed_files.txt)",
    )
    parser.add_argument(
        "--google-search",
        action="store_true",
        help="Enable Google Search grounding for all queries",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose debug output",
    )
    parser.add_argument(
        "--version",
        action="version",
        version="ask-llm.py 1.0",
    )

    args = parser.parse_args()

    if not args.files:
        parser.print_help()
        print(
            "\nExamples:\n"
            "  python3 ask-llm.py paper1.pdf paper2.pdf\n"
            "  python3 ask-llm.py bibliography.bib\n"
            "  python3 ask-llm.py paper1.pdf bibliography.bib paper2.pdf\n"
            "  python3 ask-llm.py --google-search paper1.pdf\n"
            "  python3 ask-llm.py --verbose paper1.pdf\n"
        )
        sys.exit(1)

    # Patch DocumentAnalyzer with CLI overrides
    class CLIAnalyzer(DocumentAnalyzer):
        def __init__(self):
            super().__init__(verbose=args.verbose)
            if args.model:
                self.model = args.model
                if self.verbose:
                    print(f"[DEBUG] Model overridden to: {args.model}")
            if args.query:
                query_params = {}
                if args.google_search:
                    query_params["google_search"] = True
                self.queries = [
                    {"text": args.query, "params": query_params, "structure": None}
                ]
                if self.verbose:
                    print(
                        f"[DEBUG] Query overridden with {len(query_params)} parameters"
                    )
            elif args.google_search:
                # Enable Google Search for all queries if --google-search flag is used
                for query in self.queries:
                    if "google_search" not in query["params"]:
                        query["params"]["google_search"] = True
                if self.verbose:
                    print("[DEBUG] Google Search enabled for all queries via CLI flag")
            if args.report:
                self.report_file = args.report
                if self.verbose:
                    print(f"[DEBUG] Report file overridden to: {args.report}")
            if args.log:
                self.logfile = args.log
                if self.verbose:
                    print(f"[DEBUG] Log file overridden to: {args.log}")
            if args.processed_list:
                self.processed_list = args.processed_list
                if self.verbose:
                    print(
                        f"[DEBUG] Processed list file overridden to: {args.processed_list}"
                    )
            if args.no_clear:
                # Load existing JSON if it exists
                if os.path.exists(self.report_file):
                    try:
                        with open(self.report_file, "r", encoding="utf-8") as f:
                            self.results = json.load(f)
                        if self.verbose:
                            print(
                                f"[DEBUG] Loaded existing JSON with {len(self.results['documents'])} documents"
                            )
                    except (json.JSONDecodeError, FileNotFoundError):
                        if self.verbose:
                            print(
                                "[DEBUG] Could not load existing JSON, starting fresh"
                            )
                        self._initialize_json_structure()
                else:
                    self._initialize_json_structure()

    analyzer = CLIAnalyzer()
    analyzer.process_files(args.files)


if __name__ == "__main__":
    main()
