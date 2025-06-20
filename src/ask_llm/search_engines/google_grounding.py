#!/usr/bin/env python3

from typing import List
from .base import SearchEngine
from ..config import QueryConfig


class GoogleGroundingEngine(SearchEngine):
    """Search engine that uses Google grounding via LLM API"""

    def __init__(self, api_client, verbose=False):
        super().__init__(verbose)
        self.api_client = api_client

    def search(self, query: str) -> List[str]:
        """Basic search - not implemented for Google Grounding"""
        return []

    def search_pdfs(self, title: str, authors: str = "") -> List[str]:
        """Search for PDFs using Google grounding"""
        if not title:
            if self.verbose:
                print("[DEBUG] No title available for Google grounding search")
            return []

        # Try strict search first
        pdf_urls = self._search_with_query(title, authors, strict=True)

        # If no results, try relaxed search
        if not pdf_urls:
            if self.verbose:
                print("[DEBUG] No PDFs found with strict query, trying relaxed query")
            pdf_urls = self._search_with_query(title, authors, strict=False)

        return pdf_urls

    def _search_with_query(
        self, title: str, authors: str, strict: bool = True
    ) -> List[str]:
        """Perform a search with either strict or relaxed query"""
        try:
            search_query = self._build_search_query(title, authors, strict)

            if self.verbose:
                query_type = "strict" if strict else "relaxed"
                print(
                    f"[DEBUG] Making LLM query for PDF search ({query_type}): {search_query}"
                )

            # Create payload with Google search enabled
            payload = self.api_client.create_text_payload(search_query)
            payload["tools"] = [{"googleSearch": {}}]

            temp_query_config = QueryConfig(
                text=search_query,
                params={
                    "google_search": True,
                    "model": "gemini-2.5-flash-lite-preview-06-17",
                },
            )

            response_data = self.api_client.make_request(payload, temp_query_config)
            return self._extract_urls_from_response(response_data)

        except Exception as e:
            if self.verbose:
                print(f"[DEBUG] Error in Google grounding search: {e}")
            return []

    def _build_search_query(self, title: str, authors: str, strict: bool = True) -> str:
        """Build search query for the LLM"""
        search_query = f'Find the PDF for this paper: "{title}"'

        first_author = ""
        if authors:
            first_author = authors.split(" and ")[0].split(",")[0].strip()
            search_query += f" by {first_author}"

        if strict:
            suggested_query = f'intitle:"{title}" {first_author}  filetype:pdf -site:jstor.org -site:researchgate.net'
        else:
            suggested_query = f"{title} {first_author if first_author else ''} filetype:pdf -site:jstor.org -site:researchgate.net".strip()

        search_query += f"\n\nSuggested query: `{suggested_query}`"
        return search_query

    def _extract_urls_from_response(self, response_data: dict) -> List[str]:
        """Extract URLs from the API response"""
        candidates = response_data.get("candidates", [])
        if not candidates:
            return []

        grounding_metadata = candidates[0].get("groundingMetadata")
        if not grounding_metadata:
            if self.verbose:
                print("[DEBUG] No grounding metadata found")
            return []

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

        return source_urls
