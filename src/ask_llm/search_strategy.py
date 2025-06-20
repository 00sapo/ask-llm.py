#!/usr/bin/env python3

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional

from .pdf_finder import PDFFinder
from .search_engines import GoogleGroundingEngine, QwantEngine


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
    """Strategy that tries Google grounding first, then falls back to Qwant search"""

    def __init__(self, api_client, url_resolver, pdf_downloader, verbose=False):
        super().__init__(verbose)

        # Initialize both strategies
        self.google_strategy = GoogleGroundingStrategy(
            api_client, url_resolver, pdf_downloader, verbose=verbose
        )
        self.qwant_strategy = QwantSearchStrategy(pdf_downloader, verbose=verbose)

    def discover_urls_with_source(
        self, metadata: Dict[str, Any], query_text: str, response_data: Dict[str, Any]
    ) -> Optional[tuple]:
        """Try Google grounding first, then fall back to Qwant search"""
        if self.verbose:
            print("[DEBUG] Trying Google grounding strategy first")

        # Try Google grounding first
        result = self.google_strategy.discover_urls_with_source(
            metadata, query_text, response_data
        )

        if result:
            if self.verbose:
                print("[DEBUG] Google grounding found PDF")
            return result

        # Fall back to Qwant search
        if self.verbose:
            print("[DEBUG] Google grounding found no results, falling back to Qwant")

        result = self.qwant_strategy.discover_urls_with_source(
            metadata, query_text, response_data
        )

        if self.verbose and result:
            print("[DEBUG] Qwant search found PDF")

        return result


class GoogleGroundingStrategy(SearchStrategy):
    """Strategy that uses Google grounding to discover PDFs"""

    def __init__(self, api_client, url_resolver, pdf_downloader, verbose=False):
        super().__init__(verbose)
        self.search_engine = GoogleGroundingEngine(api_client, verbose=verbose)
        self.pdf_finder = PDFFinder(
            self.search_engine, url_resolver, pdf_downloader, verbose=verbose
        )

    def discover_urls_with_source(
        self, metadata: Dict[str, Any], query_text: str, response_data: Dict[str, Any]
    ) -> Optional[tuple]:
        """Make an LLM query to search for PDF URLs using Google grounding, returning path and source URL"""
        return self.pdf_finder.find_pdf_with_source(metadata)


class QwantSearchStrategy(SearchStrategy):
    """Strategy that uses Qwant search to discover PDFs"""

    def __init__(self, pdf_downloader, verbose=False):
        super().__init__(verbose)
        self.search_engine = QwantEngine(verbose=verbose)
        # Create a simple URL resolver that just returns the input URLs
        self.url_resolver = SimpleURLResolver()
        self.pdf_finder = PDFFinder(
            self.search_engine, self.url_resolver, pdf_downloader, verbose=verbose
        )

    def discover_urls_with_source(
        self, metadata: Dict[str, Any], query_text: str, response_data: Dict[str, Any]
    ) -> Optional[tuple]:
        """Use Qwant search to discover and download PDFs, returning path and source URL"""
        return self.pdf_finder.find_pdf_with_source(metadata)
