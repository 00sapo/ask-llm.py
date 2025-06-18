#!/usr/bin/env python3

import json
import csv
from datetime import datetime


class ReportManager:
    def __init__(self, verbose=False):
        self.verbose = verbose
        self.results = {}

    def initialize_json_structure(self, queries, model):
        """Initialize the JSON output structure"""
        self.results = {
            "metadata": {
                "generated": datetime.now().isoformat(),
                "total_documents": 0,
                "model_used": model,
                "queries": [],
            },
            "documents": [],
        }

        # Store query information
        for i, query_info in enumerate(queries):
            query_data = {
                "id": i + 1,
                "text": query_info["text"],
                "parameters": query_info["params"],
                "structure": query_info.get("structure"),
            }
            self.results["metadata"]["queries"].append(query_data)

    def add_document(self, document_data):
        """Add a document to the results"""
        self.results["documents"].append(document_data)
        self.results["metadata"]["total_documents"] += 1

    def save_json_report(self, filename):
        """Save results to JSON file"""
        if self.verbose:
            print(f"[DEBUG] Saving JSON report to {filename}")

        with open(filename, "w", encoding="utf-8") as f:
            json.dump(self.results, f, indent=2, ensure_ascii=False)

        if self.verbose:
            print(
                f"[DEBUG] JSON report saved with {len(self.results['documents'])} documents"
            )

    def save_csv_report(self, filename):
        """Save results to CSV file"""
        if self.verbose:
            print(f"[DEBUG] Saving CSV report to {filename}")

        if not self.results["documents"]:
            print("Warning: No documents processed, creating empty CSV")
            with open(filename, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(
                    ["Document", "BibTeX Key", "File Path", "Metadata Only"]
                )
            return

        # Prepare CSV structure
        # Columns: Document info + one column per query
        headers = ["Document ID", "BibTeX Key", "File Path", "Metadata Only"]

        # Add query columns
        for query in self.results["metadata"]["queries"]:
            # Truncate long query text for column header
            query_text = (
                query["text"][:50] + "..." if len(query["text"]) > 50 else query["text"]
            )
            headers.append(f"Query {query['id']}: {query_text}")

        with open(filename, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(headers)

            for doc in self.results["documents"]:
                row = [
                    doc["id"],
                    doc["bibtex_key"],
                    doc["file_path"],
                    "Yes" if doc["is_metadata_only"] else "No",
                ]

                # Create a mapping of query_id to response for this document
                query_responses = {q["query_id"]: q["response"] for q in doc["queries"]}

                # Add response for each query (in order)
                for query in self.results["metadata"]["queries"]:
                    query_id = query["id"]
                    response = query_responses.get(query_id, "")

                    # Convert response to string format suitable for CSV
                    if isinstance(response, dict):
                        # For structured JSON responses, convert to compact JSON string
                        response_str = json.dumps(response, ensure_ascii=False)
                    elif isinstance(response, list):
                        # For list responses, convert to compact JSON string
                        response_str = json.dumps(response, ensure_ascii=False)
                    else:
                        # For string responses, use as-is but clean up newlines
                        response_str = (
                            str(response).replace("\n", " ").replace("\r", " ")
                        )

                    row.append(response_str)

                writer.writerow(row)

        if self.verbose:
            print(
                f"[DEBUG] CSV report saved with {len(self.results['documents'])} documents"
            )

    def save_report(self, filename):
        """Save results to appropriate format based on file extension"""
        if filename.lower().endswith(".csv"):
            self.save_csv_report(filename)
        else:
            self.save_json_report(filename)
