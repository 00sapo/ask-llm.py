#!/usr/bin/env python3

from typing import Dict, List, Any, Optional, Tuple
from .search_engines import SearchEngine


class PDFFinder:
    """Handles PDF discovery and downloading using search engines"""

    def __init__(
        self, search_engine: SearchEngine, url_resolver, pdf_downloader, verbose=False
    ):
        self.search_engine = search_engine
        self.url_resolver = url_resolver
        self.pdf_downloader = pdf_downloader
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
        """Find and download PDF, returning tuple of (local_path, original_url) or None"""
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

        # Download first successful PDF
        for pdf_url in resolved_urls:
            downloaded_path = self.pdf_downloader.download_pdf(pdf_url, title)
            if downloaded_path:
                if self.verbose:
                    print(
                        f"[DEBUG] Downloaded PDF: {downloaded_path} from URL: {pdf_url}"
                    )
                return downloaded_path, pdf_url

        return None
