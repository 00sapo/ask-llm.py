#!/usr/bin/env python3

from typing import Dict, List, Any, Optional, Tuple
from .search_engines import SearchEngine


class PDFFinder:
    """Handles PDF discovery and downloading using search engines"""

    def __init__(
        self,
        search_engine: SearchEngine,
        url_resolver,
        pdf_downloader,
        api_client=None,
        verbose=False,
    ):
        self.search_engine = search_engine
        self.url_resolver = url_resolver
        self.pdf_downloader = pdf_downloader
        self.api_client = api_client
        self.verbose = verbose

    def find_pdfs(self, metadata: Dict[str, Any]) -> List[str]:
        """Find and download PDFs for a document, returning list of local paths"""
        title = metadata.get("title", "")
        authors = metadata.get("author", "")

        if not title:
            if self.verbose:
                print("[DEBUG] No title available for PDF search")
            return []

        # Search for PDF URLs
        pdf_urls = self.search_engine.search_pdfs(title, authors)

        if not pdf_urls:
            if self.verbose:
                print("[DEBUG] No PDF URLs found")
            return []

        # Resolve redirects and extract additional PDFs if needed
        resolved_urls = self.url_resolver.resolve_and_extract_pdfs(pdf_urls)

        # Download PDFs
        downloaded_paths = []
        for pdf_url in resolved_urls:
            downloaded_path = self.pdf_downloader.download_pdf(pdf_url, title)
            if downloaded_path:
                downloaded_paths.append(downloaded_path)
                if self.verbose:
                    print(f"[DEBUG] Downloaded PDF: {downloaded_path}")

        return downloaded_paths

    def find_pdf_with_source(
        self, metadata: Dict[str, Any]
    ) -> Optional[Tuple[str, str]]:
        """Find and download PDF, verifying it matches expected metadata"""
        title = metadata.get("title", "")
        authors = metadata.get("author", "")

        if not title:
            if self.verbose:
                print("[DEBUG] No title available for PDF search")
            return None

        # Search for PDF URLs
        pdf_urls = self.search_engine.search_pdfs(title, authors)

        if not pdf_urls:
            if self.verbose:
                print("[DEBUG] No PDF URLs found")
            return None

        # Resolve redirects and extract additional PDFs if needed
        resolved_urls = self.url_resolver.resolve_and_extract_pdfs(pdf_urls)

        # Try each URL and verify it matches
        for i, pdf_url in enumerate(resolved_urls):
            if self.verbose:
                print(f"[DEBUG] Trying PDF {i + 1}/{len(resolved_urls)}: {pdf_url}")

            downloaded_path = self.pdf_downloader.download_pdf(pdf_url, title)
            if not downloaded_path:
                if self.verbose:
                    print(f"[DEBUG] Failed to download PDF from: {pdf_url}")
                continue

            # Verify the PDF matches expected metadata
            if self._verify_pdf_match(downloaded_path, title, authors):
                if self.verbose:
                    print(
                        f"[DEBUG] PDF verified and matches: {downloaded_path} from URL: {pdf_url}"
                    )
                return downloaded_path, pdf_url
            else:
                if self.verbose:
                    print(
                        "[DEBUG] PDF does not match expected metadata, trying next URL"
                    )
                # Clean up the downloaded file since it doesn't match
                import os

                try:
                    os.remove(downloaded_path)
                    if self.verbose:
                        print(f"[DEBUG] Removed non-matching PDF: {downloaded_path}")
                except Exception as e:
                    if self.verbose:
                        print(f"[DEBUG] Could not remove non-matching PDF: {e}")

        if self.verbose:
            print("[DEBUG] No matching PDFs found after verification")
        return None

    def _verify_pdf_match(
        self, pdf_path: str, expected_title: str, expected_authors: str = ""
    ) -> bool:
        """Verify if downloaded PDF matches expected metadata using LLM"""
        try:
            import base64
            import json

            # Skip verification if no API client available
            if not self.api_client:
                if self.verbose:
                    print(
                        "[DEBUG] No API client available for PDF verification, skipping verification"
                    )
                return True  # Default to accepting if we can't verify

            # Read and encode PDF
            with open(pdf_path, "rb") as f:
                pdf_data = f.read()
            encoded_pdf = base64.b64encode(pdf_data).decode("utf-8")

            if self.verbose:
                print(f"[DEBUG] Verifying PDF match for: {expected_title}")

            response_data = self.api_client.verify_pdf_match(
                encoded_pdf, expected_title, expected_authors
            )
            response_content, _ = self.api_client.extract_response(response_data)

            # Parse JSON response
            verification_result = json.loads(response_content)

            matches = verification_result.get("matches", False)
            confidence = verification_result.get("confidence", 0.0)
            reason = verification_result.get("reason", "No reason provided")

            if self.verbose:
                print(
                    f"[DEBUG] Verification result: matches={matches}, confidence={confidence:.2f}"
                )
                print(f"[DEBUG] Verification reason: {reason}")
                if "found_title" in verification_result:
                    print(
                        f"[DEBUG] Found title in PDF: {verification_result['found_title']}"
                    )

            # Require high confidence for acceptance
            is_match = matches and confidence >= 0.7
            if self.verbose:
                print(
                    f"[DEBUG] PDF verification {'passed' if is_match else 'failed'} (confidence threshold: 0.7)"
                )

            return is_match

        except Exception as e:
            if self.verbose:
                print(f"[DEBUG] Error during PDF verification: {e}")
            return True  # Default to accepting if verification fails
