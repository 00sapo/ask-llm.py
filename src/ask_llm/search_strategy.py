#!/usr/bin/env python3

from abc import ABC, abstractmethod
from typing import Dict, List, Any

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


class GoogleGroundingStrategy(SearchStrategy):
    """Strategy that uses Google grounding to discover PDFs"""

    def __init__(self, api_client, url_resolver, verbose=False):
        super().__init__(verbose)
        self.api_client = api_client
        self.url_resolver = url_resolver

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
            search_query += (
                f'\n\nSuggested query: `intitle:"{title}" {first_author}  filetype:pdf`'
            )

            if self.verbose:
                print(f"[DEBUG] Making LLM query for PDF search: {search_query}")

            # Create payload with Google search enabled
            payload = self.api_client.create_text_payload(search_query)
            payload["tools"] = [{"googleSearch": {}}]

            temp_query_config = QueryConfig(
                text=search_query,
                params={"google_search": True, "model": "gemini-2.0-flash"},
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
                urls.extend(pdf_urls[0])

        except Exception as e:
            if self.verbose:
                print(f"[DEBUG] Error in Google grounding search: {e}")

        return urls


class QwantSearchStrategy(SearchStrategy):
    """Strategy that uses Qwant search to discover PDFs"""

    def __init__(self, pdf_searcher, verbose=False):
        super().__init__(verbose)
        self.pdf_searcher = pdf_searcher

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
