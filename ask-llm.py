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
    def __init__(self):
        self.api_key = self._get_api_key()
        self.base_url = "https://generativelanguage.googleapis.com/v1beta"
        self.model = "gemini-2.5-flash-preview-05-20"
        self.processed_list = "processed_files.txt"
        self.logfile = "log.txt"
        self.report_file = "analysis_report.md"

        # Load configuration
        self.queries = self._load_queries("query.txt")
        self.structure = (
            self._load_json("structure.json")
            if os.path.exists("structure.json")
            else None
        )

        # Clear output files
        self._clear_files()

    def _get_api_key(self):
        """Get API key using rbw"""
        try:
            result = subprocess.run(
                ["rbw", "get", "gemini_key"], capture_output=True, text=True, check=True
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError:
            print("Error: Could not retrieve API key using 'rbw get gemini_key'")
            sys.exit(1)

    def _load_queries(self, filename):
        """Load and parse queries from text file"""
        try:
            with open(filename, "r", encoding="utf-8") as f:
                content = f.read().strip()
        except FileNotFoundError:
            print(f"Error: {filename} not found")
            sys.exit(1)

        # Split by 3 or more equals signs
        query_sections = re.split(r"={3,}", content)

        queries = []
        for section in query_sections:
            section = section.strip()
            if not section:
                continue

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
            if query_text:
                queries.append({"text": query_text, "params": params})

        return queries

    def _load_json(self, filename):
        """Load JSON file"""
        if not os.path.exists(filename):
            return None
        try:
            with open(filename, "r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            print(f"Error: Invalid JSON in {filename}: {e}")
            sys.exit(1)

    def _clear_files(self):
        """Clear or create output files"""
        for filename in [self.processed_list, self.logfile, self.report_file]:
            Path(filename).write_text("")

    def extract_pdfs_from_bibtex(self, bibtex_file):
        """Extract PDF paths and keys from BibTeX file"""
        try:
            with open(bibtex_file, "r", encoding="utf-8") as f:
                content = f.read()
        except FileNotFoundError:
            print(f"BibTeX file not found: {bibtex_file}")
            return []

        pdf_mappings = []
        # Split by @ to get entries
        entries = re.split(r"@", content)[1:]  # Skip first empty part

        for entry in entries:
            lines = entry.split("\n")
            if not lines:
                continue

            # Extract entry key from first line
            key_match = re.search(r"^[^{]*\{([^,]+)", lines[0])
            if not key_match:
                continue

            bibtex_key = key_match.group(1).strip()

            # Look for file field
            for line in lines:
                file_match = re.search(r'file\s*=\s*["{]([^"}]+)', line)
                if file_match:
                    file_path = file_match.group(1)
                    # Extract PDF path (first part before semicolon)
                    pdf_match = re.search(r"^([^;:]+\.pdf)", file_path)
                    if pdf_match:
                        pdf_path = pdf_match.group(1)
                        pdf_mappings.append((pdf_path, bibtex_key))
                        break

        return pdf_mappings

    def _find_pdf_file(self, pdf_path):
        """Find PDF file in common locations if not found at given path"""
        if os.path.isfile(pdf_path):
            return pdf_path

        # Try common directories
        common_dirs = [".", "papers", "pdfs", "documents"]
        basename = os.path.basename(pdf_path)

        for directory in common_dirs:
            full_path = os.path.join(directory, basename)
            if os.path.isfile(full_path):
                return full_path

        return None

    def process_pdf(self, pdf_path, bibtex_key=""):
        """Process a single PDF file with multiple queries"""
        # Find the actual file
        actual_path = self._find_pdf_file(pdf_path)
        if not actual_path:
            print(f"File not found: {pdf_path}", file=sys.stderr)
            return False

        # Encode PDF to base64
        try:
            with open(actual_path, "rb") as f:
                encoded_pdf = base64.b64encode(f.read()).decode("utf-8")
        except Exception as e:
            print(f"Error reading PDF {actual_path}: {e}", file=sys.stderr)
            return False

        all_responses = []

        for i, query_info in enumerate(self.queries):
            query_text = f"I'm attaching the file {actual_path}\n\n{query_info['text']}"

            # Use query-specific model or default
            model = query_info["params"].get("model", self.model)

            # Create request payload
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

            # Add tools if Google Search is enabled
            tools = []
            if query_info["params"].get("google_search", False):
                tools.append({"googleSearch": {}})

            if tools:
                payload["tools"] = tools

            # Add temperature if specified
            if "temperature" in query_info["params"]:
                payload["generationConfig"]["temperature"] = query_info["params"][
                    "temperature"
                ]

            # Add structured output only if structure is available
            if self.structure:
                payload["generationConfig"]["responseMimeType"] = "application/json"
                payload["generationConfig"]["responseSchema"] = self.structure

            # Make API request
            url = f"{self.base_url}/models/{model}:generateContent?key={self.api_key}"

            try:
                req = urllib.request.Request(
                    url,
                    data=json.dumps(payload).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                )

                with urllib.request.urlopen(req) as response:
                    response_data = json.loads(response.read().decode("utf-8"))

                # Log response
                with open(self.logfile, "a", encoding="utf-8") as f:
                    f.write(f"=== Response for {actual_path} (Query {i + 1}) ===\n")
                    json.dump(response_data, f, indent=2)
                    f.write("\n\n")

                # Extract response
                try:
                    response_content = response_data["candidates"][0]["content"][
                        "parts"
                    ][0]["text"]

                    # Extract grounding metadata if available
                    grounding_metadata = response_data["candidates"][0].get(
                        "groundingMetadata"
                    )

                    all_responses.append(
                        {
                            "query_index": i + 1,
                            "query_text": query_info["text"],
                            "params": query_info["params"],
                            "response": response_content,
                            "grounding_metadata": grounding_metadata,
                        }
                    )

                except (KeyError, IndexError):
                    print(
                        f"Error: No valid response for {actual_path} (Query {i + 1})",
                        file=sys.stderr,
                    )
                    print(f"Response: {response_data}", file=sys.stderr)
                    continue

            except urllib.error.HTTPError as e:
                print(
                    f"HTTP Error {e.code} for {actual_path} (Query {i + 1}): {e.reason}",
                    file=sys.stderr,
                )
                try:
                    error_response = json.loads(e.read().decode("utf-8"))
                    if "error" in error_response:
                        error_msg = error_response["error"].get(
                            "message", "Unknown error"
                        )
                        print(f"API Error Details: {error_msg}", file=sys.stderr)
                except (json.JSONDecodeError, UnicodeDecodeError):
                    pass
                continue

            except Exception as e:
                print(
                    f"Error: Failed to call API for {actual_path} (Query {i + 1}): {e}",
                    file=sys.stderr,
                )
                continue

        if all_responses:
            # Record processed file
            with open(self.processed_list, "a", encoding="utf-8") as f:
                f.write(f"{actual_path}|{bibtex_key}\n")

            # Add to report
            self._add_to_report(actual_path, bibtex_key, all_responses)
            print(f"Successfully processed: {actual_path}")
            return True

        return False

    def _add_to_report(self, pdf_path, bibtex_key, all_responses):
        """Add entry to the report with multiple query responses"""
        with open(self.report_file, "a", encoding="utf-8") as f:
            f.write(f"\n## {os.path.basename(pdf_path)}\n\n")
            f.write(f"**File:** `{pdf_path}`\n")
            if bibtex_key:
                f.write(f"**BibTeX Key:** `{bibtex_key}`\n")

            for response_info in all_responses:
                f.write(f"\n### Query {response_info['query_index']}\n\n")
                f.write("**Query:**\n```\n")
                f.write(response_info["query_text"])
                f.write("\n```\n\n")

                if response_info["params"]:
                    f.write("**Parameters:**\n")
                    for key, value in response_info["params"].items():
                        f.write(f"- {key}: {value}\n")
                    f.write("\n")

                f.write("**Response:**\n")
                if self.structure:
                    f.write("```json\n")
                    f.write(response_info["response"])
                    f.write("\n```\n\n")
                else:
                    f.write(response_info["response"])
                    f.write("\n\n")

                # Add grounding information if available
                if response_info.get("grounding_metadata"):
                    grounding = response_info["grounding_metadata"]
                    f.write("**Grounding Information:**\n")

                    # Show search queries used
                    if "webSearchQueries" in grounding:
                        f.write("*Search Queries:* ")
                        f.write(
                            ", ".join(f"`{q}`" for q in grounding["webSearchQueries"])
                        )
                        f.write("\n\n")

                    # Show grounding sources
                    if "groundingChunks" in grounding:
                        f.write("*Sources:*\n")
                        for chunk in grounding["groundingChunks"]:
                            if "web" in chunk:
                                web_info = chunk["web"]
                                title = web_info.get("title", "Unknown")
                                uri = web_info.get("uri", "#")
                                f.write(f"- [{title}]({uri})\n")
                        f.write("\n")

                    # Show search entry point (Google Search suggestions)
                    if (
                        "searchEntryPoint" in grounding
                        and "renderedContent" in grounding["searchEntryPoint"]
                    ):
                        f.write(
                            "*Google Search Suggestions available in response metadata*\n\n"
                        )

            f.write("---\n\n")

    def _generate_summary(self):
        """Generate summary report header and aggregated analysis"""
        try:
            with open(self.processed_list, "r") as f:
                total_processed = len(f.readlines())
        except FileNotFoundError:
            total_processed = 0

        # Create header
        header = f"""# Document Analysis Report

**Generated:** {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
**Total Documents Processed:** {total_processed}
**Total Queries:** {len(self.queries)}
**Model Used:** {self.model}

## Queries Used

"""

        for i, query_info in enumerate(self.queries):
            header += f"### Query {i + 1}\n\n"
            header += "```\n"
            header += query_info["text"]
            header += "\n```\n\n"
            if query_info["params"]:
                header += "**Parameters:**\n"
                for key, value in query_info["params"].items():
                    header += f"- {key}: {value}\n"
                header += "\n"

        if self.structure:
            header += f"""## Structure Schema

```json
{json.dumps(self.structure, indent=2)}
```

"""

        header += "## Individual Results\n\n"

        # Read existing report content and write combined content
        try:
            with open(self.report_file, "r", encoding="utf-8") as f:
                existing_content = f.read()
        except FileNotFoundError:
            existing_content = ""

        with open(self.report_file, "w", encoding="utf-8") as f:
            f.write(header)
            f.write(existing_content)

        # Generate aggregated analysis if we have results
        if total_processed > 0:
            self._generate_aggregated_analysis()

    def _generate_aggregated_analysis(self):
        """Generate aggregated analysis section"""
        with open(self.report_file, "a", encoding="utf-8") as f:
            f.write("## Aggregated Analysis\n\n")

        # Extract JSON responses for analysis
        try:
            with open(self.report_file, "r", encoding="utf-8") as f:
                content = f.read()

            # Find all JSON blocks
            json_blocks = re.findall(r"```json\n(.*?)\n```", content, re.DOTALL)

            if json_blocks:
                # Parse JSON responses
                responses = []
                for block in json_blocks:
                    try:
                        responses.append(json.loads(block))
                    except json.JSONDecodeError:
                        continue

                if responses:
                    with open(self.report_file, "a", encoding="utf-8") as f:
                        f.write("### Summary Statistics\n\n")

                        # Count keywords (if present in structure)
                        all_keywords = []
                        for response in responses:
                            if "keywords" in response and isinstance(
                                response["keywords"], list
                            ):
                                all_keywords.extend(response["keywords"])

                        if all_keywords:
                            keyword_counts = {}
                            for keyword in all_keywords:
                                keyword_counts[keyword] = (
                                    keyword_counts.get(keyword, 0) + 1
                                )

                            f.write("**Keyword Distribution:**\n\n")
                            for keyword, count in sorted(
                                keyword_counts.items(), key=lambda x: x[1], reverse=True
                            ):
                                f.write(f"- {keyword}: {count}\n")
                            f.write("\n")

        except Exception as e:
            print(f"Warning: Could not generate aggregated analysis: {e}")

    def process_files(self, files):
        """Main processing logic"""
        bibtex_files = [f for f in files if f.endswith(".bib")]
        pdf_files = [f for f in files if f.endswith(".pdf")]

        # Process BibTeX files
        for bibtex_file in bibtex_files:
            print(f"Processing BibTeX file: {bibtex_file}")
            pdf_mappings = self.extract_pdfs_from_bibtex(bibtex_file)

            for pdf_path, bibtex_key in pdf_mappings:
                self.process_pdf(pdf_path, bibtex_key)

        # Process individual PDF files
        for pdf_file in pdf_files:
            self.process_pdf(pdf_file)

        # Generate final report
        self._generate_summary()

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
        "--structure",
        type=str,
        default=None,
        help="Override structure schema file (default: structure.json)",
    )
    parser.add_argument(
        "--report",
        type=str,
        default=None,
        help="Override report output file (default: analysis_report.md)",
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
        )
        sys.exit(1)

    # Patch DocumentAnalyzer with CLI overrides
    class CLIAnalyzer(DocumentAnalyzer):
        def __init__(self):
            super().__init__()
            if args.model:
                self.model = args.model
            if args.query:
                query_params = {}
                if args.google_search:
                    query_params["google_search"] = True
                self.queries = [{"text": args.query, "params": query_params}]
            elif args.google_search:
                # Enable Google Search for all queries if --google-search flag is used
                for query in self.queries:
                    if "google_search" not in query["params"]:
                        query["params"]["google_search"] = True
            if args.structure:
                self.structure = self._load_json(args.structure)
            if args.report:
                self.report_file = args.report
            if args.log:
                self.logfile = args.log
            if args.processed_list:
                self.processed_list = args.processed_list
            if args.no_clear:
                # Override _clear_files to do nothing
                self._clear_files = lambda: None

    analyzer = CLIAnalyzer()
    analyzer.process_files(args.files)


if __name__ == "__main__":
    main()
