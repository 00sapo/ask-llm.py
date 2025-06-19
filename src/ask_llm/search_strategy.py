#!/usr/bin/env python3

import requests_cache
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional

from .config import QueryConfig


class SearchStrategy(ABC):
    """Abstract base class for different PDF search strategies"""

    def __init__(self, verbose=False):
        self.verbose = verbose

    @abstractmethod
    def discover_urls(
        self, metadata: Dict[str, Any], query_text: str, response_data: Dict[str, Any]
    ) -> List[str]:
        """Discover PDF URLs for a document. Returns list of discovered URLs."""
        pass

    @abstractmethod
    def discover_urls_with_source(
        self, metadata: Dict[str, Any], query_text: str, response_data: Dict[str, Any]
    ) -> Optional[tuple]:
        """Discover PDF URLs for a document. Returns tuple of (downloaded_path, original_url) or None."""
        pass


class GoogleGroundingStrategy(SearchStrategy):
    """Strategy that uses Google grounding to discover PDFs"""

    def __init__(self, api_client, url_resolver, pdf_downloader, verbose=False):
        super().__init__(verbose)
        self.api_client = api_client
        self.url_resolver = url_resolver
        self.pdf_downloader = pdf_downloader

    def _create_relaxed_query(self, original_query: str) -> str:
        """Create a relaxed version of the search query by removing intitle: and quotes"""
        relaxed_query = original_query

        # Remove intitle: prefix and quotes around the title
        import re

        # Pattern to match intitle:"title" or similar
        relaxed_query = re.sub(r'intitle:"([^"]*)"', r"\1", relaxed_query)
        # Also handle cases without quotes after intitle:
        relaxed_query = re.sub(r"intitle:([^\s]+)", r"\1", relaxed_query)

        # Clean up extra spaces
        relaxed_query = re.sub(r"\s+", " ", relaxed_query).strip()

        if self.verbose:
            print(f"[DEBUG] Created relaxed query: {relaxed_query}")

        return relaxed_query

    def discover_urls(
        self, metadata: Dict[str, Any], query_text: str, response_data: Dict[str, Any]
    ) -> List[str]:
        """Make an LLM query to search for PDF URLs using Google grounding"""
        urls = []

        title = metadata.get("title", "")
        authors = metadata.get("author", "")

        if not title:
            if self.verbose:
                print("[DEBUG] No title available for Google grounding search")
            return urls

        try:
            # Create search query for the LLM
            search_query = f'Find the PDF for this paper: "{title}"'
            if authors:
                first_author = authors.split(" and ")[0].split(",")[0].strip()
                search_query += f" by {first_author}"
            else:
                first_author = ""
            search_query += f'\n\nSuggested query: `intitle:"{title}" {first_author}  filetype:pdf -site:jstor.org -site:researchgate.net`'

            if self.verbose:
                print(f"[DEBUG] Making LLM query for PDF search: {search_query}")

            # Create payload with Google search enabled
            payload = self.api_client.create_text_payload(search_query)
            payload["tools"] = [{"googleSearch": {}}]

            temp_query_config = QueryConfig(
                text=search_query,
                params={"google_search": True, "model": "gemini-2.5-flash"},
            )

            response_data = self.api_client.make_request(payload, temp_query_config)

            # Extract grounding metadata
            candidates = response_data.get("candidates", [])
            if not candidates:
                return urls

            grounding_metadata = candidates[0].get("groundingMetadata")
            if not grounding_metadata:
                if self.verbose:
                    print("[DEBUG] No grounding metadata found")
                return urls

            # Extract URLs from grounding chunks
            grounding_chunks = grounding_metadata.get("groundingChunks", [])
            source_urls = []

            for chunk in grounding_chunks:
                web_chunk = chunk.get("web", {})
                uri = web_chunk.get("uri")
                if uri:
                    source_urls.append(uri)
                    if self.verbose:
                        print(f"[DEBUG] Found grounding URL: {uri}")

            if source_urls:
                # Resolve redirects and extract PDF URLs
                pdf_urls = self.url_resolver.resolve_and_extract_pdfs(source_urls)

                # Download PDFs and return local paths
                downloaded_paths = []
                for pdf_url in pdf_urls:
                    title = metadata.get("title", "grounding_result")
                    downloaded_path = self.pdf_downloader.download_pdf(pdf_url, title)
                    if downloaded_path:
                        downloaded_paths.append(downloaded_path)
                        if self.verbose:
                            print(
                                f"[DEBUG] Downloaded PDF from grounding: {downloaded_path}"
                            )

                urls.extend(downloaded_paths)

            # If no URLs found, try with relaxed query
            if not urls:
                if self.verbose:
                    print(
                        "[DEBUG] No PDFs found with strict query, trying relaxed query"
                    )

                # Create relaxed search query
                relaxed_search_query = f"Find the PDF for this paper: {title}"
                if authors:
                    first_author = authors.split(" and ")[0].split(",")[0].strip()
                    relaxed_search_query += f" by {first_author}"

                # Create relaxed suggested query without intitle: and quotes
                relaxed_suggested = f"{title} {first_author if first_author else ''} filetype:pdf -site:jstor.org -site:researchgate.net".strip()
                relaxed_search_query += f"\n\nSuggested query: `{relaxed_suggested}`"

                if self.verbose:
                    print(
                        f"[DEBUG] Making relaxed LLM query for PDF search: {relaxed_search_query}"
                    )

                # Create payload for relaxed search
                relaxed_payload = self.api_client.create_text_payload(
                    relaxed_search_query
                )
                relaxed_payload["tools"] = [{"googleSearch": {}}]

                relaxed_temp_query_config = QueryConfig(
                    text=relaxed_search_query,
                    params={"google_search": True, "model": "gemini-2.5-flash"},
                )

                relaxed_response_data = self.api_client.make_request(
                    relaxed_payload, relaxed_temp_query_config
                )

                # Extract grounding metadata from relaxed search
                relaxed_candidates = relaxed_response_data.get("candidates", [])
                if relaxed_candidates:
                    relaxed_grounding_metadata = relaxed_candidates[0].get(
                        "groundingMetadata"
                    )
                    if relaxed_grounding_metadata:
                        # Extract URLs from relaxed grounding chunks
                        relaxed_grounding_chunks = relaxed_grounding_metadata.get(
                            "groundingChunks", []
                        )
                        relaxed_source_urls = []

                        for chunk in relaxed_grounding_chunks:
                            web_chunk = chunk.get("web", {})
                            uri = web_chunk.get("uri")
                            if uri:
                                relaxed_source_urls.append(uri)
                                if self.verbose:
                                    print(f"[DEBUG] Found relaxed grounding URL: {uri}")

                        if relaxed_source_urls:
                            # Resolve redirects and extract PDF URLs
                            relaxed_pdf_urls = (
                                self.url_resolver.resolve_and_extract_pdfs(
                                    relaxed_source_urls
                                )
                            )

                            # Download PDFs and return local paths
                            for pdf_url in relaxed_pdf_urls:
                                title = metadata.get("title", "grounding_result")
                                downloaded_path = self.pdf_downloader.download_pdf(
                                    pdf_url, title
                                )
                                if downloaded_path:
                                    urls.append(downloaded_path)
                                    if self.verbose:
                                        print(
                                            f"[DEBUG] Downloaded PDF from relaxed grounding: {downloaded_path}"
                                        )

        except Exception as e:
            if self.verbose:
                print(f"[DEBUG] Error in Google grounding search: {e}")

        return urls

    def discover_urls_with_source(
        self, metadata: Dict[str, Any], query_text: str, response_data: Dict[str, Any]
    ) -> Optional[tuple]:
        """Make an LLM query to search for PDF URLs using Google grounding, returning path and source URL"""
        urls = self.discover_urls(metadata, query_text, response_data)
        if urls:
            # Return the first downloaded path and None for original URL (since discover_urls returns local paths)
            return urls[0], None
        return None


class QwantSearchStrategy(SearchStrategy):
    """Strategy that uses Qwant search to discover PDFs"""

    def __init__(self, pdf_downloader, verbose=False):
        super().__init__(verbose)
        self.pdf_downloader = pdf_downloader
        # Use requests_cache for Qwant API calls
        self.session = requests_cache.CachedSession(
            cache_name="qwant_search_cache",
            expire_after=3600,  # Cache for 1 hour
            backend="sqlite",
        )
        self.last_search_time = 0  # Track when we last made a search

        if self.verbose:
            print("[DEBUG] Initialized Qwant search strategy with requests_cache")

    def discover_urls(
        self, metadata: Dict[str, Any], query_text: str, response_data: Dict[str, Any]
    ) -> List[str]:
        """Use Qwant search to discover and download PDFs"""
        urls = []

        title = metadata.get("title", "")
        authors = metadata.get("author", "")

        if not title:
            if self.verbose:
                print("[DEBUG] No title available for Qwant search")
            return urls

        try:
            result = self._search_and_download_pdf(title, authors)
            if result:
                urls.append(result)
                if self.verbose:
                    print(f"[DEBUG] Qwant search found and downloaded: {result}")
        except Exception as e:
            if self.verbose:
                print(f"[DEBUG] Qwant search failed: {e}")

        return urls

    def discover_urls_with_source(
        self, metadata: Dict[str, Any], query_text: str, response_data: Dict[str, Any]
    ) -> Optional[tuple]:
        """Use Qwant search to discover and download PDFs, returning path and source URL"""
        title = metadata.get("title", "")
        authors = metadata.get("author", "")

        if not title:
            if self.verbose:
                print("[DEBUG] No title available for Qwant search")
            return None

        try:
            downloaded_path, original_url = self._search_and_download_pdf_with_source(
                title, authors
            )
            if downloaded_path:
                if self.verbose:
                    print(
                        f"[DEBUG] Qwant search found and downloaded: {downloaded_path} from URL: {original_url}"
                    )
                return downloaded_path, original_url
            return None
        except Exception as e:
            if self.verbose:
                print(f"[DEBUG] Qwant search failed: {e}")
            return None

    def _search_and_download_pdf(self, title: str, authors: str = "") -> Optional[str]:
        """Search for PDF using Qwant and download it"""
        if not title.strip():
            if self.verbose:
                print("[DEBUG] No title provided for PDF search")
            return None

        # Rate limiting: wait between 3-7 seconds since last search
        import time
        import random

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

        # Clean title and authors for search
        clean_title = self._clean_search_term(title)
        clean_authors = self._clean_search_term(authors) if authors else ""

        # Create search query with quotes (strict search)
        if clean_authors:
            # Use first author only to avoid overly long queries
            first_author = clean_authors.split(" and ")[0].split(",")[0].strip()
            search_query = f'"{clean_title}" {first_author} filetype:pdf'
        else:
            search_query = f'"{clean_title}" filetype:pdf'

        if self.verbose:
            print(f"[DEBUG] Searching for PDF with strict query: {search_query}")

        try:
            pdf_url = self._search_qwant(search_query)
            if pdf_url:
                if self.verbose:
                    print(f"[DEBUG] Found PDF URL with strict search: {pdf_url}")

                # Download PDF and return local path
                return self.pdf_downloader.download_pdf(pdf_url, title)
            else:
                if self.verbose:
                    print(
                        "[DEBUG] No PDF found with strict search, trying relaxed query"
                    )

                # Try relaxed search without quotes
                relaxed_search_query = f"{clean_title} {first_author if clean_authors else ''} filetype:pdf".strip()

                if self.verbose:
                    print(
                        f"[DEBUG] Searching for PDF with relaxed query: {relaxed_search_query}"
                    )

                # Add another rate limit pause for the second search
                time.sleep(random.uniform(3, 7))
                self.last_search_time = time.time()

                relaxed_pdf_url = self._search_qwant(relaxed_search_query)
                if relaxed_pdf_url:
                    if self.verbose:
                        print(
                            f"[DEBUG] Found PDF URL with relaxed search: {relaxed_pdf_url}"
                        )

                    # Download PDF and return local path
                    return self.pdf_downloader.download_pdf(relaxed_pdf_url, title)
                else:
                    if self.verbose:
                        print("[DEBUG] No PDF found in relaxed search results")
                    return None

        except Exception as e:
            if self.verbose:
                print(f"[DEBUG] PDF search failed: {e}")
            return None

    def _search_and_download_pdf_with_source(
        self, title: str, authors: str = ""
    ) -> tuple:
        """Search for PDF using Qwant and download it, returning both path and original URL"""
        if not title.strip():
            if self.verbose:
                print("[DEBUG] No title provided for PDF search")
            return None, None

        # Use the same rate limiting and search logic as _search_and_download_pdf
        import time
        import random

        current_time = time.time()
        time_since_last = current_time - self.last_search_time
        min_wait = 3.0
        max_wait = 7.0

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

        # Clean title and authors for search
        clean_title = self._clean_search_term(title)
        clean_authors = self._clean_search_term(authors) if authors else ""

        # Create search query with quotes (strict search)
        if clean_authors:
            first_author = clean_authors.split(" and ")[0].split(",")[0].strip()
            search_query = f'"{clean_title}" {first_author} filetype:pdf'
        else:
            search_query = f'"{clean_title}" filetype:pdf'

        if self.verbose:
            print(f"[DEBUG] Searching for PDF with strict query: {search_query}")

        try:
            pdf_url = self._search_qwant(search_query)
            if pdf_url:
                if self.verbose:
                    print(f"[DEBUG] Found PDF URL with strict search: {pdf_url}")

                # Download PDF and return both local path and original URL
                downloaded_path = self.pdf_downloader.download_pdf(pdf_url, title)
                if downloaded_path:
                    return downloaded_path, pdf_url
                return None, None
            else:
                if self.verbose:
                    print(
                        "[DEBUG] No PDF found with strict search, trying relaxed query"
                    )

                # Try relaxed search without quotes
                relaxed_search_query = f"{clean_title} {first_author if clean_authors else ''} filetype:pdf".strip()

                if self.verbose:
                    print(
                        f"[DEBUG] Searching for PDF with relaxed query: {relaxed_search_query}"
                    )

                # Add another rate limit pause for the second search
                time.sleep(random.uniform(3, 7))
                self.last_search_time = time.time()

                relaxed_pdf_url = self._search_qwant(relaxed_search_query)
                if relaxed_pdf_url:
                    if self.verbose:
                        print(
                            f"[DEBUG] Found PDF URL with relaxed search: {relaxed_pdf_url}"
                        )

                    # Download PDF and return both local path and original URL
                    downloaded_path = self.pdf_downloader.download_pdf(
                        relaxed_pdf_url, title
                    )
                    if downloaded_path:
                        return downloaded_path, relaxed_pdf_url
                    return None, None
                else:
                    if self.verbose:
                        print("[DEBUG] No PDF found in relaxed search results")
                    return None, None

        except Exception as e:
            if self.verbose:
                print(f"[DEBUG] PDF search failed: {e}")
            return None, None

    def _clean_search_term(self, text: str) -> str:
        """Clean text for search query"""
        if not text:
            return ""

        # Remove LaTeX commands and special characters
        import re

        text = re.sub(r"\\[a-zA-Z]+\{([^}]*)\}", r"\1", text)  # \emph{text} -> text
        text = re.sub(r"[{}\\]", "", text)  # Remove braces and backslashes
        text = text.replace("&", "and")
        text = re.sub(
            r"[^\w\s\-\.]", " ", text
        )  # Keep only word chars, spaces, hyphens, dots
        text = re.sub(r"\s+", " ", text).strip()  # Normalize whitespace

        return text

    def _search_qwant(self, query: str) -> Optional[str]:
        """Search Qwant for PDF files using the API"""
        if self.verbose:
            print(f"[DEBUG] Searching Qwant with query: {query}")

        try:
            import random
            from urllib.parse import urlencode

            # Random device selection instead of dummy searches
            devices = ["desktop", "smartphone", "tablet"]
            device = random.choice(devices)

            if self.verbose:
                print(f"[DEBUG] Using device: {device}")

            # Qwant API parameters
            params = {
                "q": query,
                "count": 10,  # Must be 10 for Qwant
                "locale": "en_gb",
                "offset": 0,
                "device": device,
                "tgp": 2,
                "safesearch": 1,
                "displayed": False,
                "llm": False,
            }

            url = "https://api.qwant.com/v3/search/web"

            # Headers similar to the curl example
            headers = {
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

            if self.verbose:
                curl_command = "curl '" + url + "?"
                curl_command += urlencode(params) + "' "
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

            # Check if request was successful
            if data.get("status") != "success":
                if self.verbose:
                    print(
                        f"[DEBUG] Qwant API returned non-success status: {data.get('status')}"
                    )
                return None

            # Extract results from the response structure
            result_data = data.get("data", {}).get("result", {})
            items_data = result_data.get("items", {})
            mainline = items_data.get("mainline", [])

            if not mainline:
                if self.verbose:
                    print("[DEBUG] No mainline results found")
                return None

            # Get the web results (first mainline item with type 'web')
            web_results = None
            for item in mainline:
                if item.get("type") == "web":
                    web_results = item.get("items", [])
                    break

            if not web_results:
                if self.verbose:
                    print("[DEBUG] No web results found in mainline")
                return None

            if self.verbose:
                print(f"[DEBUG] Found {len(web_results)} search results")

            # Look for PDF URLs in the results
            for result in web_results:
                url_result = result.get("url", "")
                if url_result.lower().endswith(".pdf"):
                    if self.verbose:
                        print(f"[DEBUG] Found direct PDF link: {url_result}")
                    return url_result

            # If no direct PDF links, try to extract from pages
            for result in web_results:
                url_result = result.get("url", "")
                title = result.get("title", "").lower()
                desc = result.get("desc", "").lower()

                if "pdf" in title or "pdf" in desc:
                    # Try to extract PDF URL from the page
                    page_pdf_url = self._extract_pdf_from_page(url_result)
                    if page_pdf_url:
                        return page_pdf_url

            if self.verbose:
                print("[DEBUG] No PDF URLs found in search results")
            return None

        except Exception as e:
            if self.verbose:
                print(f"[DEBUG] Qwant search error: {e}")
            return None

    def _extract_pdf_from_page(self, page_url: str) -> Optional[str]:
        """Try to extract PDF URL from a webpage"""
        try:
            if self.verbose:
                print(f"[DEBUG] Checking page for PDF links: {page_url}")

            response = self.session.get(page_url, timeout=10)

            if self.verbose and hasattr(response, "from_cache"):
                cache_status = "from cache" if response.from_cache else "fresh request"
                print(f"[DEBUG] Page request: {cache_status}")

            response.raise_for_status()

            # Look for PDF links in the HTML
            import re

            pdf_links = re.findall(
                r'href=["\']([^"\']*\.pdf[^"\']*)["\']', response.text, re.IGNORECASE
            )

            for link in pdf_links:
                # Convert relative URLs to absolute
                if link.startswith("/"):
                    from urllib.parse import urljoin

                    link = urljoin(page_url, link)
                elif not link.startswith("http"):
                    continue

                if self.verbose:
                    print(f"[DEBUG] Found PDF link on page: {link}")
                return link

            return None

        except Exception as e:
            if self.verbose:
                print(f"[DEBUG] Error extracting PDF from page {page_url}: {e}")
            return None
