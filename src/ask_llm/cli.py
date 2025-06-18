#!/usr/bin/env python3

import argparse
import sys
import os
import json

from .analyzer import DocumentAnalyzer


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
        help="Override report output file (default: analysis_report.json, use .csv extension for CSV format)",
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
        version="ask-llm 1.0",
    )

    args = parser.parse_args()

    if not args.files:
        parser.print_help()
        print(
            "\nExamples:\n"
            "  ask-llm paper1.pdf paper2.pdf\n"
            "  ask-llm bibliography.bib\n"
            "  ask-llm paper1.pdf bibliography.bib paper2.pdf\n"
            "  ask-llm --google-search paper1.pdf\n"
            "  ask-llm --verbose paper1.pdf\n"
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
