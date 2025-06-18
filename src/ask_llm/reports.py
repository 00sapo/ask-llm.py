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
        """Save results to CSV file with JSON fields expanded to separate columns"""
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

        # Analyze queries to determine column structure
        headers = ["Document ID", "BibTeX Key", "File Path", "Metadata Only"]
        query_columns = []  # Track column info for data extraction

        for query in self.results["metadata"]["queries"]:
            query_id = query["id"]

            # Check if this query has structured responses
            has_structured_response = False
            field_names = []

            # First, check if structure is defined in query metadata
            if query.get("structure") and query["structure"].get("properties"):
                field_names = list(query["structure"]["properties"].keys())
                has_structured_response = True
                if self.verbose:
                    print(
                        f"[DEBUG] Query {query_id} has predefined structure with fields: {field_names}"
                    )
            else:
                # Check first response to see if it's structured
                for doc in self.results["documents"]:
                    for q in doc["queries"]:
                        if q["query_id"] == query_id and isinstance(
                            q["response"], dict
                        ):
                            field_names = list(q["response"].keys())
                            has_structured_response = True
                            if self.verbose:
                                print(
                                    f"[DEBUG] Query {query_id} has structured response with fields: {field_names}"
                                )
                            break
                    if has_structured_response:
                        break

            if has_structured_response:
                # Create separate columns for each field
                for field_name in field_names:
                    column_name = f"Query {query_id} - {field_name}"
                    headers.append(column_name)
                    query_columns.append({"query_id": query_id, "field": field_name})
            else:
                # Single column for non-structured response
                query_text = (
                    query["text"][:50] + "..."
                    if len(query["text"]) > 50
                    else query["text"]
                )
                column_name = f"Query {query_id}: {query_text}"
                headers.append(column_name)
                query_columns.append({"query_id": query_id, "field": None})

        if self.verbose:
            print(f"[DEBUG] Created {len(headers)} CSV columns")

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

                # Add response for each query column
                for col_info in query_columns:
                    query_id = col_info["query_id"]
                    field_name = col_info["field"]
                    response = query_responses.get(query_id, "")

                    if field_name is None:
                        # Non-structured response - use entire response
                        if isinstance(response, dict):
                            # If response is unexpectedly structured, convert to JSON string
                            response_str = json.dumps(response, ensure_ascii=False)
                        elif isinstance(response, list):
                            # If response is a list, convert to JSON string
                            response_str = json.dumps(response, ensure_ascii=False)
                        else:
                            # String response - clean up newlines
                            response_str = (
                                str(response).replace("\n", " ").replace("\r", " ")
                            )
                    else:
                        # Structured response - extract specific field
                        if isinstance(response, dict):
                            field_value = response.get(field_name, "")
                            if isinstance(field_value, (dict, list)):
                                # Sub-objects and arrays are converted to JSON strings
                                response_str = json.dumps(
                                    field_value, ensure_ascii=False
                                )
                            elif field_value is None:
                                response_str = ""
                            else:
                                # Simple values (strings, numbers, booleans)
                                response_str = (
                                    str(field_value)
                                    .replace("\n", " ")
                                    .replace("\r", " ")
                                )
                        else:
                            # Response should be structured but isn't - leave empty
                            response_str = ""

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
