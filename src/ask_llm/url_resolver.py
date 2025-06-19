#!/usr/bin/env python3

import requests_cache
from typing import Dict, List


class URLResolver:
    def __init__(self, verbose=False):
        self.verbose = verbose
        # Use requests_cache for consistency with other modules
        self.session = requests_cache.CachedSession(
            cache_name="url_resolver_cache",
            expire_after=3600,  # Cache for 1 hour
            backend="sqlite",
        )
        self.session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            }
        )

        if self.verbose:
            print("[DEBUG] Initialized URL resolver with requests_cache")

    def resolve_redirects(self, urls: List[str]) -> Dict[str, str]:
        """Resolve redirect URLs and return mapping of original -> resolved"""
        resolved_mapping = {}

        for url in urls:
            try:
                if self.verbose:
                    print(f"[DEBUG] Resolving redirects for: {url}")

                # Follow redirects but don't download content
                response = self.session.head(url, allow_redirects=True, timeout=10)
                resolved_url = response.url

                if resolved_url != url:
                    resolved_mapping[url] = resolved_url
                    if self.verbose:
                        print(f"[DEBUG] Resolved {url} -> {resolved_url}")
                else:
                    resolved_mapping[url] = url
                    if self.verbose:
                        print(f"[DEBUG] No redirect for {url}")

            except Exception as e:
                if self.verbose:
                    print(f"[DEBUG] Failed to resolve {url}: {e}")
                resolved_mapping[url] = url  # Keep original if resolution fails

        return resolved_mapping

    def extract_pdf_urls(self, urls: List[str]) -> List[str]:
        """Filter URLs to find likely PDF URLs"""
        pdf_urls = []

        for url in urls:
            # Check if URL ends with .pdf
            if url.lower().endswith(".pdf"):
                pdf_urls.append(url)
                if self.verbose:
                    print(f"[DEBUG] Found direct PDF URL: {url}")
                continue

            # Check if URL contains PDF indicators
            if any(
                indicator in url.lower() for indicator in ["pdf", "document", "paper"]
            ):
                # Try to check if it's actually a PDF by looking at headers
                try:
                    response = self.session.head(url, timeout=5)
                    content_type = response.headers.get("content-type", "").lower()

                    if "pdf" in content_type:
                        pdf_urls.append(url)
                        if self.verbose:
                            print(f"[DEBUG] Found PDF URL by content-type: {url}")
                    elif self.verbose:
                        print(f"[DEBUG] URL {url} has content-type: {content_type}")

                except Exception as e:
                    if self.verbose:
                        print(f"[DEBUG] Could not check content-type for {url}: {e}")

        return pdf_urls

    def resolve_and_extract_pdfs(self, urls: List[str]) -> List[str]:
        """Resolve redirects and extract PDF URLs in one step"""
        if not urls:
            return []

        # First resolve all redirects
        resolved_mapping = self.resolve_redirects(urls)
        resolved_urls = list(resolved_mapping.values())

        # Then extract PDF URLs from resolved URLs
        pdf_urls = self.extract_pdf_urls(resolved_urls)

        if self.verbose:
            print(
                f"[DEBUG] From {len(urls)} original URLs, found {len(pdf_urls)} PDF URLs"
            )

        return pdf_urls
