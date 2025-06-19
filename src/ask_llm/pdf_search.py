#!/usr/bin/env python3

import os
import re
import tempfile
import time
import random
from typing import Optional
from urllib.parse import urlencode

import requests_cache


class PDFSearcher:
    def __init__(self, verbose=False, enabled=True, download_pdfs=True):
        self.verbose = verbose
        self.enabled = enabled
        self.download_pdfs = (
            download_pdfs  # New parameter to control download vs URL mode
        )
        # Use requests_cache instead of requests
        self.session = requests_cache.CachedSession(
            cache_name="pdf_search_cache",
            expire_after=3600,  # Cache for 1 hour
            backend="sqlite",
        )
        self.session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            }
        )
        self.last_search_time = 0  # Track when we last made a search

        if self.verbose:
            print(f"[DEBUG] Initialized PDF searcher (enabled: {self.enabled})")
            print("[DEBUG] Using requests_cache with SQLite backend")
            if self.enabled:
                mode = "download" if self.download_pdfs else "URL-only"
                print(f"[DEBUG] PDF searcher mode: {mode}")

    def search_pdf(self, title: str, authors: str = "") -> Optional[str]:
        """Search for PDF using Qwant and return either URL or downloaded file path"""
        if not self.enabled:
            if self.verbose:
                print("[DEBUG] PDF search disabled, skipping")
            return None

        if not title.strip():
            if self.verbose:
                print("[DEBUG] No title provided for PDF search")
            return None

        # Rate limiting: wait between 3-7 seconds since last search
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

        # Create search query
        if clean_authors:
            # Use first author only to avoid overly long queries
            first_author = clean_authors.split(" and ")[0].split(",")[0].strip()
            search_query = f'"{clean_title}" {first_author} filetype:pdf'
        else:
            search_query = f'"{clean_title}" filetype:pdf'

        if self.verbose:
            print(f"[DEBUG] Searching for PDF: {search_query}")

        try:
            pdf_url = self._search_qwant(search_query)
            if pdf_url:
                if self.verbose:
                    print(f"[DEBUG] Found PDF URL: {pdf_url}")

                if self.download_pdfs:
                    # Download mode: download PDF and return local path
                    return self._download_pdf(pdf_url, title)
                else:
                    # URL mode: return URL directly
                    if self.verbose:
                        print(f"[DEBUG] Returning PDF URL (no download): {pdf_url}")
                    return pdf_url
            else:
                if self.verbose:
                    print("[DEBUG] No PDF found in search results")
                return None

        except Exception as e:
            if self.verbose:
                print(f"[DEBUG] PDF search failed: {e}")
            return None

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

    def _search_qwant(self, query: str) -> Optional[str]:
        """Search Qwant for PDF files using the API"""
        if self.verbose:
            print(f"[DEBUG] Searching Qwant with query: {query}")

        try:
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

    def _download_pdf(self, url: str, title: str) -> Optional[str]:
        """Download PDF file to temporary location"""
        try:
            if self.verbose:
                print(f"[DEBUG] Downloading PDF from: {url}")

            # Create safe filename from title
            safe_title = re.sub(r"[^\w\s\-]", "", title)[:50]  # Limit length
            safe_title = re.sub(r"\s+", "_", safe_title).strip("_")
            if not safe_title:
                safe_title = "downloaded_paper"

            # Create temporary file
            temp_dir = tempfile.gettempdir()
            pdf_filename = f"ask_llm_{safe_title}_{hash(url) % 10000}.pdf"
            pdf_path = os.path.join(temp_dir, pdf_filename)

            # Download with timeout and size limit
            response = self.session.get(url, timeout=30, stream=True)

            if self.verbose and hasattr(response, "from_cache"):
                cache_status = "from cache" if response.from_cache else "fresh download"
                print(f"[DEBUG] PDF download: {cache_status}")

            response.raise_for_status()

            # Check content type
            content_type = response.headers.get("content-type", "").lower()
            if "pdf" not in content_type and not url.lower().endswith(".pdf"):
                if self.verbose:
                    print(f"[DEBUG] URL doesn't appear to be a PDF: {content_type}")
                return None

            # Download with size limit (50MB)
            max_size = 50 * 1024 * 1024
            downloaded_size = 0

            with open(pdf_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        downloaded_size += len(chunk)
                        if downloaded_size > max_size:
                            if self.verbose:
                                print("[DEBUG] PDF too large, skipping")
                            os.remove(pdf_path)
                            return None
                        f.write(chunk)

            # Verify it's a valid PDF by checking header
            with open(pdf_path, "rb") as f:
                header = f.read(5)
                if header != b"%PDF-":
                    if self.verbose:
                        print("[DEBUG] Downloaded file is not a valid PDF")
                    os.remove(pdf_path)
                    return None

            if self.verbose:
                print(
                    f"[DEBUG] Successfully downloaded PDF: {pdf_path} ({downloaded_size} bytes)"
                )

            return pdf_path

        except Exception as e:
            if self.verbose:
                print(f"[DEBUG] PDF download failed: {e}")
            return None

    def cleanup_temp_files(self, pdf_paths: list):
        """Clean up temporary PDF files"""
        if not self.download_pdfs:
            return  # No files to clean up in URL mode

        for pdf_path in pdf_paths:
            if (
                pdf_path
                and os.path.exists(pdf_path)
                and tempfile.gettempdir() in pdf_path
            ):
                # Only clean up files with our prefix
                if "ask_llm_" in os.path.basename(pdf_path):
                    try:
                        os.remove(pdf_path)
                        if self.verbose:
                            print(f"[DEBUG] Cleaned up temporary PDF: {pdf_path}")
                    except Exception as e:
                        if self.verbose:
                            print(
                                f"[DEBUG] Could not remove temporary PDF {pdf_path}: {e}"
                            )
