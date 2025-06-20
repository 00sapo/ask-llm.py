#!/usr/bin/env python3

import json
from typing import Dict, Any, Tuple, Optional

import requests
import requests_cache

from .config import ConfigManager, QueryConfig


class GeminiAPIClient:
    def __init__(self, verbose=False):
        self.verbose = verbose
        self.config = ConfigManager(verbose=verbose)
        self.api_key = self.config.get_api_key()
        self.base_url = self.config.settings.base_url
        self.default_model = "gemini-2.5-flash"

        # Configure requests_cache session
        self.session = requests_cache.CachedSession(
            cache_name="gemini_api_cache",
            expire_after=3600,  # Cache for 1 hour
            backend="sqlite",
        )
        self.session.headers.update({"Content-Type": "application/json"})

        if self.verbose:
            print(f"[DEBUG] Initialized API client with base URL: {self.base_url}")
            print(f"[DEBUG] Default model: {self.default_model}")
            print("[DEBUG] Using requests_cache with SQLite backend")

    def create_pdf_payload(self, encoded_pdf: str, query_text: str) -> Dict[str, Any]:
        """Create payload for PDF processing"""
        return {
            "contents": [
                {
                    "parts": [
                        {
                            "inline_data": {
                                "mime_type": "application/pdf",
                                "data": encoded_pdf,
                            }
                        },
                        {"text": query_text},
                    ]
                }
            ],
            "generationConfig": {},
        }

    def create_text_payload(self, query_text: str) -> Dict[str, Any]:
        """Create payload for text processing"""
        return {
            "contents": [{"parts": [{"text": query_text}]}],
            "generationConfig": {},
        }

    def create_url_payload(self, query_text: str, urls: list) -> Dict[str, Any]:
        """Create payload for URL processing with URL context tool"""
        # Add URLs to the query text
        if urls:
            url_text = "\n".join([f"URL: {url}" for url in urls])
            full_query = f"{query_text}\n\n{url_text}"
        else:
            full_query = query_text

        return {
            "contents": [{"parts": [{"text": full_query}]}],
            "generationConfig": {},
            "tools": [{"url_context": {}}],
        }

    def apply_query_params(
        self, payload: Dict[str, Any], query_info: QueryConfig
    ) -> Dict[str, Any]:
        """Apply query-specific parameters to payload"""
        # Use query-specific model or default
        model = query_info.params.get("model", self.default_model)
        if self.verbose:
            print(f"[DEBUG] Using model: {model}")

        # Initialize tools list if not present
        if "tools" not in payload:
            payload["tools"] = []

        # Add Google Search tool if enabled
        if query_info.params.get("google_search", False):
            payload["tools"].append({"googleSearch": {}})
            if self.verbose:
                print("[DEBUG] Google Search tool enabled for this query")

        # Add temperature if specified
        if "temperature" in query_info.params:
            payload["generationConfig"]["temperature"] = query_info.params[
                "temperature"
            ]
            if self.verbose:
                print(f"[DEBUG] Set temperature to: {query_info.params['temperature']}")

        # Add structured output only if structure is available for this query
        if query_info.structure:
            payload["generationConfig"]["responseMimeType"] = "application/json"
            payload["generationConfig"]["responseSchema"] = query_info.structure
            if self.verbose:
                print("[DEBUG] Structured output enabled for this query")

        return payload

    def make_request(
        self, payload: Dict[str, Any], query_info: QueryConfig
    ) -> Dict[str, Any]:
        """Make API request to Gemini"""
        # Use query-specific model or default
        model = query_info.params.get("model", self.default_model)
        url = f"{self.base_url}/models/{model}:generateContent"
        params = {"key": self.api_key}

        if self.verbose:
            print(f"[DEBUG] Making API request to: {url}")
            print(f"[DEBUG] Payload size: {len(json.dumps(payload))} characters")

        try:
            if self.verbose:
                print("[DEBUG] Sending request to Gemini API...")

            response = self.session.post(url, params=params, json=payload, timeout=300)

            if self.verbose:
                print(f"[DEBUG] Response status: {response.status_code}")
                print(f"[DEBUG] Response size: {len(response.text)} characters")
                if hasattr(response, "from_cache"):
                    cache_status = (
                        "from cache" if response.from_cache else "fresh request"
                    )
                    print(f"[DEBUG] API request: {cache_status}")

            response.raise_for_status()
            response_data = response.json()

            if self.verbose:
                print("[DEBUG] Successfully parsed JSON response")

            return response_data

        except requests.exceptions.HTTPError as e:
            if self.verbose:
                print(
                    f"[DEBUG] HTTP Error details: {e.response.status_code} - {e.response.reason}"
                )

            try:
                error_response = e.response.json()
                if "error" in error_response:
                    error_msg = error_response["error"].get("message", "Unknown error")
                    if self.verbose:
                        print(f"[DEBUG] Full error response: {error_response}")
                    raise Exception(f"API Error: {error_msg}")
            except (json.JSONDecodeError, AttributeError):
                pass

            raise Exception(f"HTTP Error {e.response.status_code}: {e.response.reason}")

        except requests.exceptions.RequestException as e:
            if self.verbose:
                print(f"[DEBUG] Request exception: {type(e).__name__}: {e}")
            raise Exception(f"Request failed: {e}")

        except Exception as e:
            if self.verbose:
                print(f"[DEBUG] Exception details: {type(e).__name__}: {e}")
            raise

    def verify_pdf_match(
        self, pdf_content: str, expected_title: str, expected_authors: str = ""
    ) -> Dict[str, Any]:
        """Verify if a PDF matches expected metadata using LLM"""
        verification_query = f"""Please analyze this PDF and determine if it matches the expected publication.

Expected metadata:
- Title: "{expected_title}"
- Authors: "{expected_authors if expected_authors else "Not specified"}"

Please respond with JSON indicating whether this PDF matches the expected publication.
Consider title similarity, author matching, and overall content relevance.
Be strict about matching - minor variations in title are acceptable, but completely different papers should be rejected."""

        payload = {
            "contents": [
                {
                    "parts": [
                        {
                            "inline_data": {
                                "mime_type": "application/pdf",
                                "data": pdf_content,
                            }
                        },
                        {"text": verification_query},
                    ]
                }
            ],
            "generationConfig": {
                "responseMimeType": "application/json",
                "responseSchema": {
                    "type": "object",
                    "properties": {
                        "matches": {
                            "type": "boolean",
                            "description": "Whether the PDF matches the expected metadata",
                        },
                        "confidence": {
                            "type": "number",
                            "description": "Confidence level from 0.0 to 1.0",
                        },
                        "reason": {
                            "type": "string",
                            "description": "Brief explanation of the matching decision",
                        },
                        "found_title": {
                            "type": "string",
                            "description": "Actual title found in the PDF",
                        },
                        "found_authors": {
                            "type": "string",
                            "description": "Actual authors found in the PDF",
                        },
                    },
                    "required": ["matches", "confidence", "reason"],
                },
            },
        }

        # Create a temporary query config for verification
        temp_query_config = QueryConfig(
            text=verification_query, params={"model": self.default_model}
        )

        return self.make_request(payload, temp_query_config)

    def extract_response(
        self, response_data: Dict[str, Any]
    ) -> Tuple[str, Optional[Dict[str, Any]]]:
        """Extract response content and grounding metadata"""
        try:
            response_content = response_data["candidates"][0]["content"]["parts"][0][
                "text"
            ]

            # Extract grounding metadata if available
            grounding_metadata = response_data["candidates"][0].get("groundingMetadata")

            # Extract URL context metadata if available
            url_context_metadata = response_data["candidates"][0].get(
                "urlContextMetadata"
            )

            if self.verbose and grounding_metadata:
                print("[DEBUG] Found grounding metadata")
                if "webSearchQueries" in grounding_metadata:
                    print(
                        f"[DEBUG] Search queries: {grounding_metadata['webSearchQueries']}"
                    )
                if "groundingChunks" in grounding_metadata:
                    print(
                        f"[DEBUG] Found {len(grounding_metadata['groundingChunks'])} grounding chunks"
                    )

            if self.verbose and url_context_metadata:
                print("[DEBUG] Found URL context metadata")
                if "urlMetadata" in url_context_metadata:
                    print(
                        f"[DEBUG] Found {len(url_context_metadata['urlMetadata'])} URL metadata entries"
                    )

            # Combine grounding metadata and URL context metadata
            combined_metadata = {}
            if grounding_metadata:
                combined_metadata["grounding"] = grounding_metadata
            if url_context_metadata:
                combined_metadata["url_context"] = url_context_metadata

            return response_content, combined_metadata if combined_metadata else None

        except (KeyError, IndexError):
            if self.verbose:
                print(f"[DEBUG] Response structure: {list(response_data.keys())}")
            raise Exception(f"No valid response found. Response: {response_data}")
