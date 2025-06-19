#!/usr/bin/env python3

import json
import csv
from datetime import datetime
from urllib.parse import quote_plus


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
                "filtered_out_count": 0,
                "queries": [],
            },
            "documents": [],
        }

        # Store query information
        for i, query_info in enumerate(queries):
            query_data = {
                "id": i + 1,
                "text": query_info.text,
                "parameters": query_info.params,
                "structure": query_info.structure,
                "filter_on": query_info.filter_on,
            }
            self.results["metadata"]["queries"].append(query_data)

    def add_document(self, document_data):
        """Add a document to the results"""

        # Extract title and authors from BibTeX metadata if available
        title = ""
        authors = ""

        # Get BibTeX metadata from document_data if it was stored during processing
        bibtex_metadata = document_data.get("bibtex_metadata", {})
        if bibtex_metadata:
            title = bibtex_metadata.get("title", "")
            authors = bibtex_metadata.get("author", "")

        # Add title, authors, and Google Scholar link to document data
        document_data["title"] = title
        document_data["authors"] = authors
        document_data["google_scholar_link"] = self.generate_google_scholar_link(
            title, authors
        )

        # Generate and display Google Scholar link
        if document_data["google_scholar_link"]:
            search_query = title
            if authors:
                # Extract first author's last name
                author_parts = authors.strip().split()
                if author_parts and len(author_parts) >= 2:
                    first_author_last = author_parts[-1]
                    search_query += f" {first_author_last}"
            print(f"🔗 Google Scholar link: {document_data['google_scholar_link']}")
            print(f"🔍 Search query: {search_query}")

        self.results["documents"].append(document_data)
        self.results["metadata"]["total_documents"] += 1

        # Report current document count
        doc_count = len(self.results["documents"])
        print(f"📊 Documents processed: {doc_count}")

    def generate_google_scholar_link(self, title, authors=None):
        """Generate a Google Scholar search link for a paper"""
        if not title:
            return ""

        # Clean title for search
        search_query = title.strip()

        # Add author information if available
        if authors:
            # Extract first author's last name for better search results
            author_parts = authors.strip().split()
            if author_parts:
                # Try to get the last name (assuming "First Last" format)
                if len(author_parts) >= 2:
                    first_author_last = author_parts[-1]
                    search_query += f" {first_author_last}"
                else:
                    # Single name, use as is
                    search_query += f" {author_parts[0]}"

        # URL encode the search query
        encoded_query = quote_plus(search_query)

        # Construct Google Scholar search URL
        scholar_url = f"https://scholar.google.com/scholar?q={encoded_query}"

        if self.verbose:
            print(f"[DEBUG] Generated Google Scholar link for '{title}': {scholar_url}")

        return scholar_url

    def save_json_report(self, filename):
        """Save results to JSON file"""
        if self.verbose:
            print(f"[DEBUG] Saving JSON report to {filename}")

        with open(filename, "w", encoding="utf-8") as f:
            json.dump(self.results, f, indent=2, ensure_ascii=False)

        doc_count = len(self.results["documents"])
        print(f"💾 JSON report saved: {filename} ({doc_count} documents)")

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
                    [
                        "Document ID",
                        "BibTeX Key",
                        "Title",
                        "Authors",
                        "Google Scholar Link",
                        "File Path",
                        "Metadata Only",
                    ]
                )
            return

        # Analyze queries to determine column structure - skip semantic-scholar queries
        headers = [
            "Document ID",
            "BibTeX Key",
            "Title",
            "Authors",
            "Google Scholar Link",
            "File Path",
            "Metadata Only",
        ]
        query_columns = []  # Track column info for data extraction

        for query in self.results["metadata"]["queries"]:
            query_id = query["id"]

            # Skip semantic-scholar queries
            if query.get("parameters", {}).get("semantic_scholar", False):
                if self.verbose:
                    print(f"[DEBUG] Skipping semantic-scholar query {query_id} in CSV")
                continue

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
                    doc.get("title", ""),
                    doc.get("authors", ""),
                    doc.get("google_scholar_link", ""),
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

        doc_count = len(self.results["documents"])
        print(f"💾 CSV report saved: {filename} ({doc_count} documents)")

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
