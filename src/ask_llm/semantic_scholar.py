#!/usr/bin/env python3

import requests
import json
from typing import Dict, Any, List


class SemanticScholarClient:
    def __init__(self, verbose=False, auto_download_pdfs=True):
        self.verbose = verbose
        self.auto_download_pdfs = (
            auto_download_pdfs  # Keep for compatibility but won't download
        )
        self.base_url = "https://api.semanticscholar.org/graph/v1"
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})

        if self.verbose:
            print(
                f"[DEBUG] Initialized Semantic Scholar client with base URL: {self.base_url}"
            )
            print("[DEBUG] Using URL context instead of PDF downloads")

    def search_papers(
        self, query: str, search_params: Dict[str, Any] = None
    ) -> List[Dict[str, Any]]:
        """Search for papers using Semantic Scholar bulk search API"""
        if self.verbose:
            print(f"[DEBUG] Searching Semantic Scholar for: {query}")

        # Default parameters
        params = {
            "query": query,
            "sort": "citationCount:desc",  # Default sort by citation count descending
            "fields": "title,abstract,authors,year,openAccessPdf,url,citationCount,venue,externalIds",
            "limit": 100,  # Default limit
        }

        # Apply user-specified parameters
        if search_params:
            params.update(search_params)

        if self.verbose:
            print(f"[DEBUG] Search parameters: {params}")

        try:
            url = f"{self.base_url}/paper/search/bulk"
            response = self.session.get(url, params=params, timeout=30)

            if self.verbose:
                print(f"[DEBUG] Response status: {response.status_code}")

            response.raise_for_status()
            data = response.json()

            papers = data.get("data", [])
            if self.verbose:
                print(f"[DEBUG] Found {len(papers)} papers")

            return papers

        except requests.exceptions.RequestException as e:
            if self.verbose:
                print(f"[DEBUG] Semantic Scholar API error: {e}")
            raise Exception(f"Semantic Scholar API request failed: {e}")
        except json.JSONDecodeError as e:
            if self.verbose:
                print(f"[DEBUG] JSON decode error: {e}")
            raise Exception(f"Failed to parse Semantic Scholar response: {e}")

    def create_bibtex_entry(self, paper: Dict[str, Any], entry_key: str = None) -> str:
        """Create a BibTeX entry from a Semantic Scholar paper"""
        if not entry_key:
            # Generate entry key from first author and year
            authors = paper.get("authors", [])
            year = paper.get("year", "Unknown")
            if authors and len(authors) > 0:
                first_author_name = authors[0].get("name", "Unknown")
                # Clean the name for use in entry key
                first_author = "".join(c for c in first_author_name if c.isalnum())
                entry_key = f"{first_author}{year}"
            else:
                entry_key = f"Unknown{year}"

        # Clean entry key to be valid BibTeX (only alphanumeric characters)
        entry_key = "".join(c for c in str(entry_key) if c.isalnum())
        if not entry_key:
            entry_key = "SemanticScholarEntry"

        # Extract fields
        title = paper.get("title", "").strip()
        abstract = paper.get("abstract", "").strip()
        year = paper.get("year", "")
        venue = paper.get("venue", "").strip()

        # Format authors
        authors_list = paper.get("authors", [])
        authors_str = " and ".join(
            [
                author.get("name", "").strip()
                for author in authors_list
                if author.get("name", "").strip()
            ]
        )

        # Get URL - prefer open access PDF, then regular URL
        url = ""

        # Check for open access PDF
        open_access_pdf = paper.get("openAccessPdf")
        if open_access_pdf and open_access_pdf.get("url"):
            url = open_access_pdf["url"]
        # avoid regular url: we only want url to pdf files

        # Get DOI if available
        doi = ""
        external_ids = paper.get("externalIds", {})
        if external_ids and external_ids.get("DOI"):
            doi = external_ids["DOI"]

        # Build BibTeX entry
        bibtex_lines = [f"@article{{{entry_key},"]

        if title:
            # Escape special characters in title
            clean_title = title.replace("{", "\\{").replace("}", "\\}")
            bibtex_lines.append(f"  title = {{{clean_title}}},")
        if authors_str:
            bibtex_lines.append(f"  author = {{{authors_str}}},")
        if year:
            bibtex_lines.append(f"  year = {{{year}}},")
        if abstract:
            # Clean abstract for BibTeX - escape braces and remove problematic characters
            clean_abstract = (
                abstract.replace("{", "\\{").replace("}", "\\}").replace("\\", "\\\\")
            )
            # Limit abstract length to avoid overly long entries
            if len(clean_abstract) > 500:
                clean_abstract = clean_abstract[:497] + "..."
            bibtex_lines.append(f"  abstract = {{{clean_abstract}}},")
        if venue:
            clean_venue = venue.replace("{", "\\{").replace("}", "\\}")
            bibtex_lines.append(f"  journal = {{{clean_venue}}},")
        if doi:
            bibtex_lines.append(f"  doi = {{{doi}}},")
        if url:
            bibtex_lines.append(f"  url = {{{url}}},")

        # Add citation count if available
        citation_count = paper.get("citationCount")
        if citation_count is not None:
            bibtex_lines.append(f"  note = {{Citations: {citation_count}}},")

        # Add Semantic Scholar source note
        bibtex_lines.append("  keywords = {Semantic Scholar},")

        bibtex_lines.append("}")

        return "\n".join(bibtex_lines)

    def search_and_create_bibtex(
        self, query: str, search_params: Dict[str, Any] = None
    ) -> str:
        """Search for papers and return them as a BibTeX bibliography"""
        papers = self.search_papers(query, search_params)

        bibtex_entries = []
        for i, paper in enumerate(papers):
            entry_key = f"semanticscholar{i + 1}"
            bibtex_entry = self.create_bibtex_entry(paper, entry_key)
            bibtex_entries.append(bibtex_entry)

        return "\n\n".join(bibtex_entries)
