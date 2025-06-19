#!/usr/bin/env python3

from abc import ABC, abstractmethod
from typing import Dict, List, Any


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
    def modify_query(
        self, query_text: str, metadata: Dict[str, Any]
    ) -> tuple[str, bool]:
        """Modify query text if needed. Returns (modified_query, google_search_enabled)."""
        pass


class GoogleGroundingStrategy(SearchStrategy):
    """Strategy that uses Google grounding to discover PDFs"""

    def __init__(self, url_resolver, verbose=False):
        super().__init__(verbose)
        self.url_resolver = url_resolver

    def modify_query(
        self, query_text: str, metadata: Dict[str, Any]
    ) -> tuple[str, bool]:
        """Add search suggestion to query and enable Google search"""
        title = metadata.get("title", "")
        authors = metadata.get("author", "")

        if not title:
            return query_text, True  # Just enable Google search

        # Create search suggestion
        search_suggestion = f'title:"{title}"'
        if authors:
            # Use first author
            first_author = authors.split(" and ")[0].split(",")[0].strip()
            search_suggestion += f' author:"{first_author}"'
        search_suggestion += " filetype:pdf"

        # Add suggestion to query
        modified_query = (
            query_text
            + f"\n\nTo help answer this question, you might want to search for: {search_suggestion}"
        )

        if self.verbose:
            print(f"[DEBUG] Modified query with search suggestion: {search_suggestion}")

        return modified_query, True  # Enable Google search

    def discover_urls(
        self, metadata: Dict[str, Any], query_text: str, response_data: Dict[str, Any]
    ) -> List[str]:
        """Extract URLs from Google grounding metadata"""
        urls = []

        try:
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
                urls.extend(pdf_urls)

        except Exception as e:
            if self.verbose:
                print(f"[DEBUG] Error extracting URLs from grounding metadata: {e}")

        return urls


class QwantSearchStrategy(SearchStrategy):
    """Strategy that uses Qwant search to discover PDFs"""

    def __init__(self, pdf_searcher, verbose=False):
        super().__init__(verbose)
        self.pdf_searcher = pdf_searcher

    def modify_query(
        self, query_text: str, metadata: Dict[str, Any]
    ) -> tuple[str, bool]:
        """Don't modify query for Qwant strategy"""
        return query_text, False  # Don't enable Google search

    def discover_urls(
        self, metadata: Dict[str, Any], query_text: str, response_data: Dict[str, Any]
    ) -> List[str]:
        """Use existing Qwant search to discover PDFs"""
        urls = []

        if not self.pdf_searcher.enabled:
            return urls

        title = metadata.get("title", "")
        authors = metadata.get("author", "")

        if not title:
            if self.verbose:
                print("[DEBUG] No title available for Qwant search")
            return urls

        try:
            result = self.pdf_searcher.search_pdf(title, authors)
            if result:
                urls.append(result)
                if self.verbose:
                    print(f"[DEBUG] Qwant search found: {result}")
        except Exception as e:
            if self.verbose:
                print(f"[DEBUG] Qwant search failed: {e}")

        return urls
