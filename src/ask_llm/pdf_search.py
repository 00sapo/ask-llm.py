#!/usr/bin/env python3

import os
import re
import tempfile
import time
from typing import Optional

import requests
from duckduckgo_search import DDGS


class PDFSearcher:
    def __init__(self, verbose=False, enabled=True, download_pdfs=True):
        self.verbose = verbose
        self.enabled = enabled
        self.download_pdfs = (
            download_pdfs  # New parameter to control download vs URL mode
        )
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            }
        )

        if self.verbose:
            print(f"[DEBUG] Initialized PDF searcher (enabled: {self.enabled})")
            if self.enabled:
                mode = "download" if self.download_pdfs else "URL-only"
                print(f"[DEBUG] PDF searcher mode: {mode}")

    def search_pdf(self, title: str, authors: str = "") -> Optional[str]:
        """Search for PDF using DuckDuckGo and return either URL or downloaded file path"""
        if not self.enabled:
            if self.verbose:
                print("[DEBUG] PDF search disabled, skipping")
            return None

        if not title.strip():
            if self.verbose:
                print("[DEBUG] No title provided for PDF search")
            return None

        # Clean title and authors for search
        clean_title = self._clean_search_term(title)
        clean_authors = self._clean_search_term(authors) if authors else ""

        # Create search query
        if clean_authors:
            # Use first author only to avoid overly long queries
            first_author = clean_authors.split(" and ")[0].split(",")[0].strip()
            search_query = f"{clean_title} {first_author} filetype:pdf"
        else:
            search_query = f"{clean_title} filetype:pdf"

        if self.verbose:
            print(f"[DEBUG] Searching for PDF: {search_query}")

        try:
            pdf_url = self._search_duckduckgo(search_query)
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

    def _search_duckduckgo(self, query: str) -> Optional[str]:
        """Search DuckDuckGo for PDF files using the duckduckgo_search library"""
        if self.verbose:
            print(f"[DEBUG] Searching DuckDuckGo with query: {query}")

        try:
            # Add delay to be respectful
            time.sleep(1)

            # Use DDGS to search for text results
            with DDGS() as ddgs:
                results = ddgs.text(
                    keywords=query, region="wt-wt", safesearch="off", max_results=10
                )

                if self.verbose:
                    print(f"[DEBUG] Found {len(results)} search results")

                # Look for PDF URLs in the results
                for result in results:
                    href = result.get("href", "")
                    if href.lower().endswith(".pdf"):
                        if self.verbose:
                            print(f"[DEBUG] Found direct PDF link: {href}")
                        return href

                    # Also check the title and body for PDF mentions
                    title = result.get("title", "").lower()
                    body = result.get("body", "").lower()
                    if "pdf" in title or "pdf" in body:
                        # Try to extract PDF URL from the page
                        pdf_url = self._extract_pdf_from_page(href)
                        if pdf_url:
                            return pdf_url

                if self.verbose:
                    print("[DEBUG] No PDF URLs found in search results")
                return None

        except Exception as e:
            if self.verbose:
                print(f"[DEBUG] DuckDuckGo search error: {e}")
            return None

    def _extract_pdf_from_page(self, page_url: str) -> Optional[str]:
        """Try to extract PDF URL from a webpage"""
        try:
            if self.verbose:
                print(f"[DEBUG] Checking page for PDF links: {page_url}")

            response = self.session.get(page_url, timeout=10)
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
