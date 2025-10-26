#!/usr/bin/env python3

import json
import re
import sys
import subprocess
from typing import List, Dict, Any, Optional
from pathlib import Path

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings


class QueryConfig(BaseModel):
    """Configuration for a single query"""

    text: str
    params: Dict[str, Any] = Field(default_factory=dict)
    structure: Optional[Dict[str, Any]] = None
    filter_on: Optional[str] = None


class Settings(BaseSettings):
    """Application settings with environment variable support"""

    api_key: Optional[str] = Field(None, alias="gemini_api_key")
    api_key_command: Optional[str] = Field(None, alias="gemini_api_key_command")
    base_url: str = Field(
        "https://generativelanguage.googleapis.com/v1beta", alias="gemini_base_url"
    )
    query_file: str = Field("query.md", alias="query_file")
    report_file: str = Field("analysis_report.json", alias="report_file")
    log_file: str = Field("log.txt", alias="log_file")
    processed_list: str = Field("processed_files.txt", alias="processed_list")
    verbose: bool = Field(False, alias="verbose")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        populate_by_name = True


class ConfigManager:
    def __init__(
        self,
        verbose=False,
        query_file=None,
        api_key=None,
        base_url=None,
        api_key_command=None,
    ):
        self.verbose = verbose
        self.settings = Settings()

        # Apply overrides before loading queries
        if query_file:
            self.settings.query_file = query_file
        if api_key:
            self.settings.api_key = api_key
        if base_url:
            self.settings.base_url = base_url
        if api_key_command:
            self.settings.api_key_command = api_key_command

    def get_api_key(self) -> str:
        """Get API key from environment or custom command"""
        if self.settings.api_key:
            if self.verbose:
                print("[DEBUG] Using API key from environment variable")
            return self.settings.api_key

        # Check if api_key_command was explicitly provided
        if not self.settings.api_key_command:
            print("Error: No API key available")
            print("Please either:")
            print("  1. Set GEMINI_API_KEY environment variable, or")
            print("  2. Use --api-key-command to specify a command to retrieve the API key")
            print("")
            print("Example:")
            print("  export GEMINI_API_KEY=your_api_key_here")
            print("  # or")
            print("  ask-llm --api-key-command 'your_command_here' ...")
            sys.exit(1)

        if self.verbose:
            print(
                f"[DEBUG] Retrieving API key using command: {self.settings.api_key_command}"
            )
        try:
            # Split command string into list for subprocess
            command_parts = self.settings.api_key_command.split()
            result = subprocess.run(
                command_parts, capture_output=True, text=True, check=True
            )
            if self.verbose:
                print("[DEBUG] API key retrieved successfully")
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            print(
                f"Error: Could not retrieve API key using '{self.settings.api_key_command}'"
            )
            print(f"Command failed with exit code {e.returncode}")
            if e.stderr:
                print(f"Error output: {e.stderr}")
            print(
                "Tip: Set GEMINI_API_KEY environment variable or configure a working command to retrieve the api key"
            )
            sys.exit(1)
        except FileNotFoundError:
            command_name = (
                self.settings.api_key_command.split()[0]
                if self.settings.api_key_command
                else "command"
            )
            print(f"Error: Command not found: {command_name}")
            print(
                "Tip: Set GEMINI_API_KEY environment variable or configure a different command to retrieve the api key"
            )
            sys.exit(1)
        except FileNotFoundError:
            command_name = (
                self.settings.api_key_command.split()[0]
                if self.settings.api_key_command
                else "command"
            )
            print(f"Error: Command not found: {command_name}")
            print(
                f"Make sure the command '{command_name}' is installed and in your PATH"
            )
            print(
                "Tip: Set GEMINI_API_KEY environment variable or configure a different command to retrieve the api key"
            )
            sys.exit(1)

    def save_state(
        self, state_data: Dict[str, Any], filename: str = "ask_llm_state.json"
    ):
        """Save complete process state"""
        if self.verbose:
            print(f"[DEBUG] Saving state to {filename}")

        with open(filename, "w", encoding="utf-8") as f:
            json.dump(state_data, f, indent=2, ensure_ascii=False)

    def load_state(
        self, filename: str = "ask_llm_state.json"
    ) -> Optional[Dict[str, Any]]:
        """Load complete process state"""
        if self.verbose:
            print(f"[DEBUG] Loading state from {filename}")

        file_path = Path(filename)
        if not file_path.exists():
            if self.verbose:
                print(f"[DEBUG] State file {filename} does not exist")
            return None

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            print(f"Error: Invalid state file {filename}: {e}")
            return None

    def load_queries(self, filename: Optional[str] = None) -> List[QueryConfig]:
        """Load and parse queries from text file"""
        query_file = filename or self.settings.query_file

        if self.verbose:
            print(f"[DEBUG] Loading queries from {query_file}")

        try:
            with open(query_file, "r", encoding="utf-8") as f:
                content = f.read().strip()
        except FileNotFoundError:
            print(f"Error: {query_file} not found")
            sys.exit(1)

        # Split by 3 or more equals signs
        query_sections = re.split(r"={3,}", content)
        if self.verbose:
            print(f"[DEBUG] Found {len(query_sections)} query sections")

        queries = []
        accumulated_params = {}  # Track parameters across queries

        for section_idx, section in enumerate(query_sections):
            section = section.strip()
            if not section:
                if self.verbose:
                    print(f"[DEBUG] Section {section_idx} is empty, skipping")
                continue

            if self.verbose:
                print(f"[DEBUG] Processing query section {section_idx + 1}")

            # Parse parameters and query text
            lines = section.split("\n")
            current_params = {}  # Parameters for this specific query
            query_lines = []

            for line in lines:
                line = line.strip()
                if ":" in line and any(
                    param in line.lower()
                    for param in [
                        "model-name:",
                        "temperature:",
                        "google-search:",
                        "filter-on:",
                        "semantic-scholar:",
                        "relevance-search:",
                        "limit:",
                        "offset:",
                        "sort:",
                        "fields:",
                        "publication-types:",
                        "open-access-pdf:",
                        "min-citation-count:",
                        "publication-date-or-year:",
                        "year:",
                        "venue:",
                        "fields-of-study:",
                    ]
                ):
                    key, value = line.split(":", 1)
                    key = key.strip().lower().replace("-", "_")
                    value = value.strip()

                    if self.verbose:
                        print(f"[DEBUG] Found parameter: {key} = {value}")

                    if key == "temperature":
                        try:
                            current_params[key] = float(value)
                        except ValueError:
                            print(
                                f"Warning: Invalid temperature value '{value}', ignoring"
                            )
                    elif key == "model_name":
                        current_params["model"] = value
                    elif key == "google_search":
                        # Parse boolean values
                        if value.lower() in ["true", "yes", "1", "on"]:
                            current_params["google_search"] = True
                        elif value.lower() in ["false", "no", "0", "off"]:
                            current_params["google_search"] = False
                        else:
                            print(
                                f"Warning: Invalid google-search value '{value}', should be true/false"
                            )
                    elif key == "semantic_scholar":
                        # Parse boolean values
                        if value.lower() in ["true", "yes", "1", "on"]:
                            current_params["semantic_scholar"] = True
                        elif value.lower() in ["false", "no", "0", "off"]:
                            current_params["semantic_scholar"] = False
                        else:
                            print(
                                f"Warning: Invalid semantic-scholar value '{value}', should be true/false"
                            )
                    elif key == "limit":
                        try:
                            current_params["limit"] = int(value)
                        except ValueError:
                            print(f"Warning: Invalid limit value '{value}', ignoring")
                    elif key == "relevance_search":
                        if value.lower() in ["true", "yes", "1", "on"]:
                            current_params["relevance_search"] = True
                        else:
                            current_params["relevance_search"] = False
                    elif key == "filter_on":
                        current_params["filter_on"] = value
                    # Add semantic scholar search parameters
                    elif key in [
                        "limit",
                        "offset",
                        "sort",
                        "fields",
                        "publication_types",
                        "open_access_pdf",
                        "min_citation_count",
                        "publication_date_or_year",
                        "venue",
                        "year",
                        "fields_of_study",
                    ]:
                        current_params[f"ss_{key}"] = (
                            value  # Prefix with 'ss_' for semantic scholar params
                        )
                else:
                    query_lines.append(line)

            # Define one-shot parameters that should not persist across queries
            one_shot_params = {"semantic_scholar", "filter_on", "relevance_search"}

            # Separate current parameters into persistent and one-shot
            persistent_params = {
                k: v for k, v in current_params.items() if k not in one_shot_params
            }
            oneshot_params = {
                k: v for k, v in current_params.items() if k in one_shot_params
            }

            # Merge accumulated parameters with current persistent parameters
            # Current parameters override accumulated ones
            merged_params = accumulated_params.copy()
            merged_params.update(persistent_params)
            merged_params.update(
                oneshot_params
            )  # Add one-shot params for this query only

            # Update accumulated parameters for next query (only persistent params)
            accumulated_params.update(persistent_params)

            if self.verbose and current_params:
                print(
                    f"[DEBUG] Query {section_idx + 1} new parameters: {current_params}"
                )
                print(
                    f"[DEBUG] Query {section_idx + 1} persistent params: {persistent_params}"
                )
                print(
                    f"[DEBUG] Query {section_idx + 1} one-shot params: {oneshot_params}"
                )
                print(
                    f"[DEBUG] Query {section_idx + 1} effective parameters: {merged_params}"
                )

            query_text = "\n".join(query_lines).strip()

            # Look for JSON code blocks in the query
            json_blocks = re.findall(r"```json\s*\n(.*?)\n```", section, re.DOTALL)
            structure = None
            if json_blocks:
                try:
                    structure = json.loads(json_blocks[0])  # Use first JSON block
                    if self.verbose:
                        print(
                            f"[DEBUG] Found JSON structure in query {len(queries) + 1}"
                        )
                except json.JSONDecodeError as e:
                    print(
                        f"Warning: Invalid JSON structure in query {len(queries) + 1}: {e}"
                    )

            if query_text:
                query_config = QueryConfig(
                    text=query_text,
                    params=merged_params,  # Use merged parameters instead of current_params
                    structure=structure,
                    filter_on=merged_params.get("filter_on"),  # Use merged parameters
                )

                # Validate filter_on usage
                if query_config.filter_on and not query_config.structure:
                    print(
                        f"Error: Query {len(queries) + 1} has filter-on but no structure defined"
                    )
                    sys.exit(1)

                queries.append(query_config)
                if self.verbose:
                    print(
                        f"[DEBUG] Added query {len(queries)} with {len(merged_params)} parameters, {'structure' if structure else 'no structure'}, and {'filter_on=' + query_config.filter_on if query_config.filter_on else 'no filter'}"
                    )

        if self.verbose:
            print(f"[DEBUG] Total queries loaded: {len(queries)}")
        return queries

    def load_json(self, filename: str) -> Optional[Dict[str, Any]]:
        """Load JSON file"""
        if self.verbose:
            print(f"[DEBUG] Attempting to load JSON from {filename}")

        file_path = Path(filename)
        if not file_path.exists():
            if self.verbose:
                print(f"[DEBUG] File {filename} does not exist")
            return None

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if self.verbose:
                    print(
                        f"[DEBUG] Successfully loaded JSON with {len(data) if isinstance(data, dict) else 'unknown'} top-level keys"
                    )
                return data
        except json.JSONDecodeError as e:
            print(f"Error: Invalid JSON in {filename}: {e}")
            sys.exit(1)
