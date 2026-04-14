#!/usr/bin/env python3

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional

from .pdf_finder import PDFFinder
from .search_engines import QwantEngine


class SimpleURLResolver:
    """Simple URL resolver that just returns input URLs without modification"""

    def resolve_and_extract_pdfs(self, urls):
        """Return URLs as-is since QwantEngine already returns PDF URLs"""
        return urls


class SearchStrategy(ABC):
    """Abstract base class for different PDF search strategies"""

    def __init__(self, verbose=False):
        self.verbose = verbose

    @abstractmethod
    def discover_urls_with_source(
        self, metadata: Dict[str, Any], query_text: str, response_data: Dict[str, Any]
    ) -> Optional[tuple]:
        """Discover PDF URLs for a document. Returns tuple of (downloaded_path, original_url) or None."""
        pass


class FallbackSearchStrategy(SearchStrategy):
    """Qwant-based strategy for PDF discovery"""

    def __init__(self, api_client, url_resolver, pdf_downloader, verbose=False):
        super().__init__(verbose)

        self.qwant_strategy = QwantSearchStrategy(
            api_client, pdf_downloader, verbose=verbose
        )

    def discover_urls_with_source(
        self, metadata: Dict[str, Any], query_text: str, response_data: Dict[str, Any]
    ) -> Optional[tuple]:
        """Use Qwant search for PDF discovery"""
        if self.verbose:
            print("[DEBUG] Using Qwant strategy for PDF discovery")

        result = self.qwant_strategy.discover_urls_with_source(
            metadata, query_text, response_data
        )

        if self.verbose and result:
            print("[DEBUG] Qwant search found PDF")

        return result


class QwantSearchStrategy(SearchStrategy):
    """Strategy that uses Qwant search to discover PDFs"""

    def __init__(self, api_client, pdf_downloader, verbose=False):
        super().__init__(verbose)
        self.search_engine = QwantEngine(verbose=verbose)
        # Create a simple URL resolver that just returns the input URLs
        self.url_resolver = SimpleURLResolver()
        self.pdf_finder = PDFFinder(
            self.search_engine,
            self.url_resolver,
            pdf_downloader,
            api_client,
            verbose=verbose,
        )

    def discover_urls_with_source(
        self, metadata: Dict[str, Any], query_text: str, response_data: Dict[str, Any]
    ) -> Optional[tuple]:
        """Use Qwant search to discover and download PDFs, returning path and source URL"""
        return self.pdf_finder.find_pdf_with_source(metadata)
