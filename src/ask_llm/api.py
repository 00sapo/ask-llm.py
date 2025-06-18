#!/usr/bin/env python3

import json
import urllib.request
import urllib.error

from .config import ConfigManager


class GeminiAPIClient:
    def __init__(self, verbose=False):
        self.verbose = verbose
        self.config = ConfigManager(verbose=verbose)
        self.api_key = self.config.get_api_key()
        self.base_url = "https://generativelanguage.googleapis.com/v1beta"
        self.model = "gemini-2.5-flash-preview-05-20"

        if self.verbose:
            print(f"[DEBUG] Initialized API client with base URL: {self.base_url}")
            print(f"[DEBUG] Default model: {self.model}")

    def create_pdf_payload(self, encoded_pdf, query_text):
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

    def create_text_payload(self, query_text):
        """Create payload for text processing"""
        return {
            "contents": [{"parts": [{"text": query_text}]}],
            "generationConfig": {},
        }

    def apply_query_params(self, payload, query_info):
        """Apply query-specific parameters to payload"""
        # Use query-specific model or default
        model = query_info["params"].get("model", self.model)
        if self.verbose:
            print(f"[DEBUG] Using model: {model}")

        # Add tools if Google Search is enabled
        tools = []
        if query_info["params"].get("google_search", False):
            tools.append({"googleSearch": {}})
            if self.verbose:
                print("[DEBUG] Google Search tool enabled for this query")

        if tools:
            payload["tools"] = tools

        # Add temperature if specified
        if "temperature" in query_info["params"]:
            payload["generationConfig"]["temperature"] = query_info["params"][
                "temperature"
            ]
            if self.verbose:
                print(
                    f"[DEBUG] Set temperature to: {query_info['params']['temperature']}"
                )

        # Add structured output only if structure is available for this query
        query_structure = query_info.get("structure")
        if query_structure:
            payload["generationConfig"]["responseMimeType"] = "application/json"
            payload["generationConfig"]["responseSchema"] = query_structure
            if self.verbose:
                print("[DEBUG] Structured output enabled for this query")

        return payload

    def make_request(self, payload, query_info):
        """Make API request to Gemini"""
        # Use query-specific model or default
        model = query_info["params"].get("model", self.model)
        url = f"{self.base_url}/models/{model}:generateContent?key={self.api_key}"

        if self.verbose:
            print(f"[DEBUG] Making API request to: {url}")
            print(f"[DEBUG] Payload size: {len(json.dumps(payload))} characters")

        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
            )

            if self.verbose:
                print("[DEBUG] Sending request to Gemini API...")

            with urllib.request.urlopen(req) as response:
                response_data = json.loads(response.read().decode("utf-8"))

            if self.verbose:
                print(
                    f"[DEBUG] Received response with {len(str(response_data))} characters"
                )

            return response_data

        except urllib.error.HTTPError as e:
            if self.verbose:
                print(f"[DEBUG] HTTP Error details: {e.code} - {e.reason}")
            try:
                error_response = json.loads(e.read().decode("utf-8"))
                if "error" in error_response:
                    error_msg = error_response["error"].get("message", "Unknown error")
                    if self.verbose:
                        print(f"[DEBUG] Full error response: {error_response}")
                    raise Exception(f"API Error: {error_msg}")
            except (json.JSONDecodeError, UnicodeDecodeError):
                pass
            raise Exception(f"HTTP Error {e.code}: {e.reason}")

        except Exception as e:
            if self.verbose:
                print(f"[DEBUG] Exception details: {type(e).__name__}: {e}")
            raise

    def extract_response(self, response_data):
        """Extract response content and grounding metadata"""
        try:
            response_content = response_data["candidates"][0]["content"]["parts"][0][
                "text"
            ]

            # Extract grounding metadata if available
            grounding_metadata = response_data["candidates"][0].get("groundingMetadata")

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

            return response_content, grounding_metadata

        except (KeyError, IndexError):
            if self.verbose:
                print(f"[DEBUG] Response structure: {list(response_data.keys())}")
            raise Exception(f"No valid response found. Response: {response_data}")
