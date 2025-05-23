#!/usr/bin/env python3

import time
import json
import base64
import urllib.request
import subprocess
import sys
import os
import re
from datetime import datetime
from pathlib import Path


class DocumentAnalyzer:
    def __init__(self):
        self.api_key = self._get_api_key()
        self.base_url = "https://generativelanguage.googleapis.com/v1beta"
        self.model = "gemini-2.5-flash-preview-05-20"
        self.processed_list = "processed_files.txt"
        self.logfile = "log.txt"
        self.report_file = "analysis_report.md"

        # Load configuration
        self.query = self._load_file("query.txt")
        self.structure = self._load_json("structure.json")

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

    def _load_file(self, filename):
        """Load text file content"""
        try:
            with open(filename, "r", encoding="utf-8") as f:
                return f.read().strip()
        except FileNotFoundError:
            print(f"Error: {filename} not found")
            sys.exit(1)

    def _load_json(self, filename):
        """Load JSON file"""
        try:
            with open(filename, "r", encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"Error: {filename} not found")
            sys.exit(1)
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
        """Process a single PDF file"""
        # Find the actual file
        actual_path = self._find_pdf_file(pdf_path)
        if not actual_path:
            print(f"File not found: {pdf_path}", file=sys.stderr)
            return False

        query_pdf = f"I'm attaching the file {actual_path}\n\n{self.query}"

        # Encode PDF to base64
        try:
            with open(actual_path, "rb") as f:
                encoded_pdf = base64.b64encode(f.read()).decode("utf-8")
        except Exception as e:
            print(f"Error reading PDF {actual_path}: {e}", file=sys.stderr)
            return False

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
                        {"text": query_pdf},
                    ]
                }
            ],
            "generationConfig": {
                "responseMimeType": "application/json",
                "responseSchema": self.structure,
            },
        }

        # Make API request
        url = f"{self.base_url}/models/{self.model}:generateContent?key={self.api_key}"

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
                f.write(f"=== Response for {actual_path} ===\n")
                json.dump(response_data, f, indent=2)
                f.write("\n\n")

            # Extract structured response
            try:
                response_content = response_data["candidates"][0]["content"]["parts"][
                    0
                ]["text"]

                # Record processed file
                with open(self.processed_list, "a", encoding="utf-8") as f:
                    f.write(f"{actual_path}|{bibtex_key}\n")

                # Add to report
                self._add_to_report(actual_path, bibtex_key, response_content)

                print(f"Successfully processed: {actual_path}")
                return True

            except (KeyError, IndexError):
                print(f"Error: No valid response for {actual_path}", file=sys.stderr)
                print(f"Response: {response_data}", file=sys.stderr)
                return False

        except urllib.error.HTTPError as e:
            print(f"HTTP Error {e.code} for {actual_path}: {e.reason}", file=sys.stderr)

            # Try to read and parse the error response body
            try:
                error_response = json.loads(e.read().decode("utf-8"))
                if "error" in error_response:
                    error_msg = error_response["error"].get("message", "Unknown error")
                    print(f"API Error Details: {error_msg}", file=sys.stderr)
                else:
                    print(f"Error response: {error_response}", file=sys.stderr)
            except (json.JSONDecodeError, UnicodeDecodeError):
                print(f"Could not parse error response body", file=sys.stderr)

            return False

        except Exception as e:
            print(f"Error: Failed to call API for {actual_path}: {e}", file=sys.stderr)
            return False

    def _add_to_report(self, pdf_path, bibtex_key, response_content):
        """Add entry to the report"""
        with open(self.report_file, "a", encoding="utf-8") as f:
            f.write(f"\n## {os.path.basename(pdf_path)}\n\n")
            f.write(f"**File:** `{pdf_path}`\n")
            if bibtex_key:
                f.write(f"**BibTeX Key:** `{bibtex_key}`\n")
            f.write("\n### Analysis Results\n\n")
            f.write("```json\n")
            f.write(response_content)
            f.write("\n```\n\n---\n\n")

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
**Model Used:** {self.model}

## Query Used

```
{self.query}
```

## Structure Schema

```json
{json.dumps(self.structure, indent=2)}
```

## Individual Results

"""

        # Read existing report content
        try:
            with open(self.report_file, "r", encoding="utf-8") as f:
                existing_content = f.read()
        except FileNotFoundError:
            existing_content = ""

        # Write combined content
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
    if len(sys.argv) < 2:
        print("""Usage: python3 ask-llm.py [file1.pdf file2.pdf ...] [bibliography.bib]

This script processes PDF files using the Gemini API with structured output.

Options:
  - Provide PDF files directly as arguments
  - Provide a BibTeX file (.bib) to extract PDF paths automatically
  - Mix both approaches

Examples:
  python3 ask-llm.py paper1.pdf paper2.pdf
  python3 ask-llm.py bibliography.bib
  python3 ask-llm.py paper1.pdf bibliography.bib paper2.pdf

Files needed:
  - query.txt: Contains the analysis prompt
  - structure.json: Contains the JSON schema for structured output

Output:
  - analysis_report.md: Comprehensive markdown report
  - log.txt: Raw API responses
  - processed_files.txt: List of processed files""")
        sys.exit(1)

    analyzer = DocumentAnalyzer()
    analyzer.process_files(sys.argv[1:])


if __name__ == "__main__":
    main()
