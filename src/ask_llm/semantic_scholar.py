#!/usr/bin/env python3

import requests
import requests_cache
import json
import time
from typing import Dict, Any, List


class SemanticScholarClient:
    def __init__(self, verbose=False):
        self.verbose = verbose
        self.base_url = "https://api.semanticscholar.org/graph/v1"
        # Use requests_cache instead of requests
        self.session = requests_cache.CachedSession(
            cache_name="semantic_scholar_cache",
            expire_after=1800,  # Cache for 30 minutes
            backend="sqlite",
            match_headers=True,
        )
        self.session.headers.update({"Content-Type": "application/json"})

        if self.verbose:
            print(
                f"[DEBUG] Initialized Semantic Scholar client with base URL: {self.base_url}"
            )
            print("[DEBUG] Using requests_cache with SQLite backend")

    def search_papers(
        self,
        query: str,
        search_params: Dict[str, Any] = None,
        relevance_search: bool = False,
    ) -> List[Dict[str, Any]]:
        """Search for papers using Semantic Scholar bulk search API"""
        if self.verbose:
            print(f"[DEBUG] Searching Semantic Scholar for: {query}")
            print(f"[DEBUG] Relevance search mode: {relevance_search}")

        # Default parameters - explicitly include paperId
        params = {
            "fields": "paperId,title,abstract,authors,year,openAccessPdf,url,citationCount,influentialCitationCount,venue,externalIds"
        }
        if relevance_search:
            params["query"] = query
            params["offset"] = 0
            params["limit"] = 100
        else:
            params["q"] = query  # Use 'q' for bulk search (bug in the API?)
            params["sort"] = "citationCount:desc"

        # Apply user-specified parameters
        if search_params:
            params.update(search_params)

        if self.verbose:
            print(f"[DEBUG] Search parameters: {params}")

        try:
            if relevance_search:
                url = f"{self.base_url}/paper/search"
            else:
                url = f"{self.base_url}/paper/search/bulk"
            if self.verbose:
                print(f"[DEBUG] Making request to: {url} with params: {params}")

            # Implement retry logic for 429 errors with exponential backoff
            max_retries = 5
            wait_times = [30, 60, 120, 180, 300]  # 30s, 1m, 2m, 3m, 5m

            for attempt in range(max_retries + 1):
                try:
                    response = self.session.get(url, params=params, timeout=30)

                    if response.status_code == 429:
                        if attempt < max_retries:
                            wait_time = wait_times[attempt]
                            if self.verbose:
                                print(
                                    f"[DEBUG] Rate limited (429), waiting {wait_time} seconds before retry {attempt + 1}/{max_retries}"
                                )
                            time.sleep(wait_time)
                            continue
                        else:
                            raise requests.exceptions.HTTPError(
                                f"Rate limited after {max_retries} retries"
                            )

                    # If we get here, the request succeeded or failed with a non-429 error
                    break

                except requests.exceptions.RequestException as e:
                    if attempt < max_retries and "429" in str(e):
                        wait_time = wait_times[attempt]
                        if self.verbose:
                            print(
                                f"[DEBUG] Request failed with rate limit, waiting {wait_time} seconds before retry {attempt + 1}/{max_retries}"
                            )
                        time.sleep(wait_time)
                        continue
                    else:
                        raise

            if self.verbose:
                print(f"[DEBUG] Response status: {response.status_code}")
                if hasattr(response, "from_cache"):
                    cache_status = (
                        "from cache" if response.from_cache else "fresh request"
                    )
                    print(f"[DEBUG] API request: {cache_status}")

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

        # Extract fields with None checks
        title = paper.get("title") or ""
        title = title.strip() if title else ""

        abstract = paper.get("abstract") or ""
        abstract = abstract.strip() if abstract else ""

        year = paper.get("year", "")

        venue = paper.get("venue") or ""
        venue = venue.strip() if venue else ""

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
            bibtex_lines.append(f"  year = {{{str(year)}}},")
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

        # Add citation counts if available
        citation_count = paper.get("citationCount")
        influential_citation_count = paper.get("influentialCitationCount")

        if citation_count is not None:
            bibtex_lines.append(f"  citationcount = {{{citation_count}}},")

        if influential_citation_count is not None:
            bibtex_lines.append(
                f"  influentialcitationcount = {{{influential_citation_count}}},"
            )

        # Add Semantic Scholar source note
        bibtex_lines.append("  keywords = {Semantic Scholar},")

        bibtex_lines.append("}")

        return "\n".join(bibtex_lines)
