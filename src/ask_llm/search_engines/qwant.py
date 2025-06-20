#!/usr/bin/env python3

import re
import time
import random
from typing import List, Optional
from urllib.parse import urlencode, urljoin
import requests_cache
from .base import SearchEngine


class QwantEngine(SearchEngine):
    """Search engine that uses Qwant API"""

    def __init__(self, verbose=False):
        super().__init__(verbose)
        # Use requests_cache for Qwant API calls
        self.session = requests_cache.CachedSession(
            cache_name="qwant_search_cache",
            expire_after=3600,  # Cache for 1 hour
            backend="sqlite",
        )
        self.last_search_time = 0  # Track when we last made a search

        if self.verbose:
            print("[DEBUG] Initialized Qwant search engine with requests_cache")

    def search_pdfs(self, title: str, authors: str = "") -> List[str]:
        """Search for PDFs using Qwant"""
        if not title.strip():
            if self.verbose:
                print("[DEBUG] No title provided for PDF search")
            return []

        # Try strict search first
        pdf_urls = self._search_pdfs_with_query(title, authors, strict=True)

        # If no results, try relaxed search
        if not pdf_urls:
            if self.verbose:
                print("[DEBUG] No PDF found with strict search, trying relaxed query")
            pdf_urls = self._search_pdfs_with_query(title, authors, strict=False)

        return pdf_urls

    def _search_pdfs_with_query(
        self, title: str, authors: str, strict: bool = True
    ) -> List[str]:
        """Search for PDFs with either strict or relaxed query"""
        self._rate_limit()

        if authors:
            first_author = authors.split(" and ")[0].split(",")[0].strip()
        else:
            first_author = ""

        if strict:
            search_query = (
                f'"{title}" {first_author} filetype:pdf -researchgate.net -jstor.org'
            )
        else:
            search_query = f"{title} {first_author} filetype:pdf -researchgate.net -jstor.org".strip()

        if self.verbose:
            query_type = "strict" if strict else "relaxed"
            print(f"[DEBUG] Searching for PDF with {query_type} query: {search_query}")

        return self._search_qwant_urls(search_query)

    def _rate_limit(self):
        """Apply rate limiting between searches"""
        current_time = time.time()
        time_since_last = current_time - self.last_search_time
        min_wait = 3.0  # Minimum 3 seconds between searches
        max_wait = 7.0  # Maximum 7 seconds for randomization

        if time_since_last < min_wait:
            wait_time = (
                min_wait - time_since_last + random.uniform(0, max_wait - min_wait)
            )
            if self.verbose:
                print(
                    f"[DEBUG] Rate limiting: waiting {wait_time:.1f} seconds before search"
                )
            time.sleep(wait_time)

        self.last_search_time = time.time()

    def _search_qwant_urls(self, query: str) -> List[str]:
        """Search Qwant and return list of URLs"""
        if self.verbose:
            print(f"[DEBUG] Searching Qwant with query: {query}")

        try:
            # Random device selection
            devices = ["desktop", "smartphone", "tablet"]
            device = random.choice(devices)

            if self.verbose:
                print(f"[DEBUG] Using device: {device}")

            # Qwant API parameters
            params = {
                "q": query,
                "count": 10,
                "locale": "en_gb",
                "offset": 0,
                "device": device,
                "tgp": 2,
                "safesearch": 1,
                "displayed": False,
                "llm": False,
            }

            url = "https://api.qwant.com/v3/search/web"
            headers = self._get_headers()

            if self.verbose:
                curl_command = f"curl '{url}?{urlencode(params)}' "
                for key, value in headers.items():
                    curl_command += f"-H '{key}: {value}' "
                curl_command += "--compressed"
                print(
                    f"Making request to Qwant API, corresponding curl: {curl_command}"
                )

            response = self.session.get(url, params=params, headers=headers, timeout=30)
            response.raise_for_status()

            data = response.json()

            if self.verbose:
                print(f"[DEBUG] Response status: {data.get('status', 'unknown')}")

            return self._extract_urls_from_response(data, query)

        except Exception as e:
            if self.verbose:
                print(f"[DEBUG] Qwant search error: {e}")
            return []

    def _get_headers(self) -> dict:
        """Get headers for Qwant API requests"""
        return {
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:139.0) Gecko/20100101 Firefox/139.0",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US;q=0.7,en;q=0.3",
            "Accept-Encoding": "gzip, deflate, br, zstd",
            "Referer": "https://www.qwant.com/",
            "Origin": "https://www.qwant.com",
            "DNT": "1",
            "Sec-GPC": "1",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-site",
            "Priority": "u=4",
            "TE": "trailers",
        }

    def _extract_urls_from_response(self, data: dict, query: str) -> List[str]:
        """Extract URLs from Qwant API response"""
        # Check if request was successful
        if data.get("status") != "success":
            if self.verbose:
                print(
                    f"[DEBUG] Qwant API returned non-success status: {data.get('status')}"
                )
            return []

        # Extract results from the response structure
        result_data = data.get("data", {}).get("result", {})
        items_data = result_data.get("items", {})
        mainline = items_data.get("mainline", [])

        if not mainline:
            if self.verbose:
                print("[DEBUG] No mainline results found")
            return []

        # Get the web results
        web_results = None
        for item in mainline:
            if item.get("type") == "web":
                web_results = item.get("items", [])
                break

        if not web_results:
            if self.verbose:
                print("[DEBUG] No web results found in mainline")
            return []

        if self.verbose:
            print(f"[DEBUG] Found {len(web_results)} search results")

        urls = []

        # Look for direct PDF URLs
        for result in web_results:
            url_result = result.get("url", "")
            if url_result:
                if self.verbose:
                    print(f"[DEBUG] Found link: {url_result}")
                urls.append(url_result)

        return urls

    def _clean_search_term(self, text: str) -> str:
        """Clean text for search query"""
        if not text:
            return ""

        # Remove LaTeX commands and special characters
        text = re.sub(r"\\[a-zA-Z]+\{([^}]*)\}", r"\1", text)  # \emph{text} -> text
        text = re.sub(r"[{}\\]", "", text)  # Remove braces and backslashes
        text = text.replace("&", "and")
        text = re.sub(
            r"[^\w\s\-\.]", " ", text
        )  # Keep only word chars, spaces, hyphens, dots
        text = re.sub(r"\s+", " ", text).strip()  # Normalize whitespace

        return text
