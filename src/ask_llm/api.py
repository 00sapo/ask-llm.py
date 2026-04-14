#!/usr/bin/env python3

import json
from typing import Dict, Any, Tuple, Optional, List

from litellm import completion

from .config import ConfigManager, QueryConfig


class LLMAPIClient:
    def __init__(self, verbose=False, **config_overrides):
        self.verbose = verbose
        self.config = ConfigManager(verbose=verbose, **config_overrides)
        self.api_key = self.config.get_api_key()
        self.base_url = self.config.settings.base_url
        self.default_model = self._normalize_model_name(
            self.config.settings.default_model
        )

        if self.verbose:
            print("[DEBUG] Initialized LiteLLM client")
            print(f"[DEBUG] Base URL override: {self.base_url or 'not set'}")
            print(f"[DEBUG] Default model: {self.default_model}")

    def _normalize_model_name(self, model_name: str) -> str:
        if not model_name:
            return "gemini/gemini-2.5-flash"
        if "/" in model_name:
            return model_name

        lowered = model_name.lower()
        if lowered.startswith("models/"):
            model_name = model_name.split("/", 1)[1]
            lowered = model_name.lower()

        if lowered.startswith("gemini") or lowered.startswith("gemma"):
            return f"gemini/{model_name}"
        if lowered.startswith("gpt"):
            return f"openai/{model_name}"
        if lowered.startswith("claude"):
            return f"anthropic/{model_name}"
        if lowered.startswith("deepseek"):
            return f"deepseek/{model_name}"

        return model_name

    def create_pdf_payload(self, encoded_pdf: str, query_text: str) -> Dict[str, Any]:
        """Create payload for PDF processing"""
        return {
            "query_text": query_text,
            "encoded_pdf": encoded_pdf,
            "temperature": None,
            "structure": None,
        }

    def create_text_payload(self, query_text: str) -> Dict[str, Any]:
        """Create payload for text processing"""
        return {
            "query_text": query_text,
            "encoded_pdf": None,
            "temperature": None,
            "structure": None,
        }

    def create_url_payload(self, query_text: str, urls: list) -> Dict[str, Any]:
        """Create payload for URL processing"""
        if urls:
            url_text = "\n".join([f"URL: {url}" for url in urls])
            full_query = f"{query_text}\n\n{url_text}"
        else:
            full_query = query_text
        return self.create_text_payload(full_query)

    def apply_query_params(
        self, payload: Dict[str, Any], query_info: QueryConfig
    ) -> Dict[str, Any]:
        """Apply query-specific parameters to payload"""
        model = self._normalize_model_name(
            query_info.params.get("model", self.default_model)
        )
        if self.verbose:
            print(f"[DEBUG] Using model: {model}")

        payload["model"] = model

        # Add temperature if specified
        if "temperature" in query_info.params:
            payload["temperature"] = query_info.params["temperature"]
            if self.verbose:
                print(f"[DEBUG] Set temperature to: {query_info.params['temperature']}")

        # Add structured output only if structure is available for this query
        if query_info.structure:
            payload["structure"] = query_info.structure
            if self.verbose:
                print("[DEBUG] Structured output enabled for this query")

        return payload

    def make_request(
        self, payload: Dict[str, Any], query_info: QueryConfig
    ) -> Dict[str, Any]:
        """Make request using LiteLLM"""
        model = self._normalize_model_name(
            query_info.params.get("model", payload.get("model", self.default_model))
        )

        if self.verbose:
            print(f"[DEBUG] Making LiteLLM request with model: {model}")

        query_text = payload.get("query_text", "")
        encoded_pdf = payload.get("encoded_pdf")
        temperature = payload.get("temperature")
        structure = payload.get("structure")

        messages = [{"role": "user", "content": query_text}]
        if encoded_pdf:
            messages = [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": query_text},
                        {
                            "type": "file",
                            "file": {
                                "mime_type": "application/pdf",
                                "file_data": f"data:application/pdf;base64,{encoded_pdf}",
                            },
                        },
                    ],
                }
            ]

        completion_kwargs = {
            "model": model,
            "messages": messages,
            "timeout": 300,
        }

        if temperature is not None:
            completion_kwargs["temperature"] = temperature

        if self.api_key:
            completion_kwargs["api_key"] = self.api_key

        if self.base_url:
            completion_kwargs["api_base"] = self.base_url

        if structure:
            completion_kwargs["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": "ask_llm_response",
                    "schema": structure,
                },
            }

        try:
            response = completion(**completion_kwargs)
            response_data = response.model_dump()
            if self.verbose:
                print("[DEBUG] Successfully parsed JSON response")
            return response_data

        except Exception as first_error:
            # Fallback 1: some models/providers do not support json_schema response_format.
            if structure and "response_format" in completion_kwargs:
                if self.verbose:
                    print(
                        "[DEBUG] Retrying without json_schema response_format due to provider incompatibility"
                    )

                relaxed_prompt = (
                    f"{query_text}\n\n"
                    "Return only valid JSON and ensure it matches this schema exactly:\n"
                    f"{json.dumps(structure, ensure_ascii=False)}"
                )
                relaxed_messages = [{"role": "user", "content": relaxed_prompt}]
                if encoded_pdf:
                    relaxed_messages = [
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": relaxed_prompt},
                                {
                                    "type": "file",
                                    "file": {
                                        "mime_type": "application/pdf",
                                        "file_data": f"data:application/pdf;base64,{encoded_pdf}",
                                    },
                                },
                            ],
                        }
                    ]

                relaxed_kwargs = dict(completion_kwargs)
                relaxed_kwargs.pop("response_format", None)
                relaxed_kwargs["messages"] = relaxed_messages
                try:
                    response = completion(**relaxed_kwargs)
                    return response.model_dump()
                except Exception:
                    pass

            # Fallback 2: some providers do not support PDF file parts.
            if encoded_pdf:
                if self.verbose:
                    print(
                        "[DEBUG] Retrying without PDF attachment because provider likely does not support file inputs"
                    )

                text_only_query = (
                    f"{query_text}\n\n"
                    "The PDF attachment could not be passed to the provider. "
                    "Answer using available metadata/context only."
                )
                text_only_kwargs = dict(completion_kwargs)
                text_only_kwargs["messages"] = [
                    {"role": "user", "content": text_only_query}
                ]
                try:
                    response = completion(**text_only_kwargs)
                    return response.model_dump()
                except Exception:
                    pass

            if self.verbose:
                print(
                    f"[DEBUG] Exception details: {type(first_error).__name__}: {first_error}"
                )
            raise first_error

    def generate_search_queries(
        self,
        user_query: str,
        metadata: Optional[Dict[str, Any]],
        query_info: QueryConfig,
        max_queries: int = 5,
    ) -> List[str]:
        """Ask the LLM for up to max_queries web search queries."""
        title = (metadata or {}).get("title", "")
        authors = (metadata or {}).get("author", "")
        prompt = (
            "Generate concise web search queries for Qwant to help answer the task.\n"
            f'Return JSON only in this shape: {{"queries": ["..."]}}\n'
            f"Use at most {max_queries} queries.\n"
            "Avoid duplicates and focus on high-information queries.\n\n"
            f"Task: {user_query}\n"
            f"Document title (optional): {title}\n"
            f"Document authors (optional): {authors}"
        )

        planner_query = QueryConfig(
            text=prompt,
            params={"model": query_info.params.get("model", self.default_model)},
            structure={
                "type": "object",
                "properties": {
                    "queries": {
                        "type": "array",
                        "items": {"type": "string"},
                        "maxItems": max_queries,
                    }
                },
                "required": ["queries"],
            },
        )

        payload = self.create_text_payload(prompt)
        payload = self.apply_query_params(payload, planner_query)
        response_data = self.make_request(payload, planner_query)
        response_text, _ = self.extract_response(response_data)

        try:
            data = json.loads(response_text)
            queries = data.get("queries", [])
            queries = [q.strip() for q in queries if isinstance(q, str) and q.strip()]
            return queries[:max_queries]
        except json.JSONDecodeError:
            if self.verbose:
                print("[DEBUG] Could not parse search query planner response as JSON")
            return []

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

        payload = self.create_pdf_payload(pdf_content, verification_query)
        payload["structure"] = {
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
        }

        # Create a temporary query config for verification
        temp_query_config = QueryConfig(
            text=verification_query, params={"model": self.default_model}
        )

        return self.make_request(payload, temp_query_config)

    def extract_response(
        self, response_data: Dict[str, Any]
    ) -> Tuple[str, Optional[Dict[str, Any]]]:
        """Extract response content and optional metadata"""
        try:
            choices = response_data.get("choices", [])
            if not choices:
                raise KeyError("choices")

            message = choices[0].get("message", {})
            content = message.get("content", "")

            if isinstance(content, list):
                text_parts = []
                for part in content:
                    if isinstance(part, dict) and part.get("type") == "text":
                        text_parts.append(part.get("text", ""))
                    elif isinstance(part, str):
                        text_parts.append(part)
                response_content = "\n".join([p for p in text_parts if p])
            else:
                response_content = str(content)

            return response_content, None

        except (KeyError, IndexError):
            if self.verbose:
                print(f"[DEBUG] Response structure: {list(response_data.keys())}")
            raise Exception(f"No valid response found. Response: {response_data}")


GeminiAPIClient = LLMAPIClient
