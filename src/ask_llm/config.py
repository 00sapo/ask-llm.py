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

    api_key: Optional[str] = Field(None, env="GEMINI_API_KEY")
    api_key_command: str = Field("rbw get gemini_key", env="GEMINI_API_KEY_COMMAND")
    base_url: str = Field(
        "https://generativelanguage.googleapis.com/v1beta", env="GEMINI_BASE_URL"
    )
    query_file: str = Field("query.md", env="QUERY_FILE")
    report_file: str = Field("analysis_report.json", env="REPORT_FILE")
    log_file: str = Field("log.txt", env="LOG_FILE")
    processed_list: str = Field("processed_files.txt", env="PROCESSED_LIST")
    verbose: bool = Field(False, env="VERBOSE")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


class ConfigManager:
    def __init__(self, verbose=False):
        self.verbose = verbose
        self.settings = Settings(verbose=verbose)

    def get_api_key(self) -> str:
        """Get API key from environment or custom command"""
        if self.settings.api_key:
            if self.verbose:
                print("[DEBUG] Using API key from environment variable")
            return self.settings.api_key

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
                "Tip: Set GEMINI_API_KEY environment variable or configure GEMINI_API_KEY_COMMAND"
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
                "Tip: Set GEMINI_API_KEY environment variable or configure a different GEMINI_API_KEY_COMMAND"
            )
            sys.exit(1)

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
            params = {}
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
                    ]
                ):
                    key, value = line.split(":", 1)
                    key = key.strip().lower().replace("-", "_")
                    value = value.strip()

                    if self.verbose:
                        print(f"[DEBUG] Found parameter: {key} = {value}")

                    if key == "temperature":
                        try:
                            params[key] = float(value)
                        except ValueError:
                            print(
                                f"Warning: Invalid temperature value '{value}', ignoring"
                            )
                    elif key == "model_name":
                        params["model"] = value
                    elif key == "google_search":
                        # Parse boolean values
                        if value.lower() in ["true", "yes", "1", "on"]:
                            params["google_search"] = True
                        elif value.lower() in ["false", "no", "0", "off"]:
                            params["google_search"] = False
                        else:
                            print(
                                f"Warning: Invalid google-search value '{value}', should be true/false"
                            )
                    elif key == "filter_on":
                        params["filter_on"] = value
                else:
                    query_lines.append(line)

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
                    params=params,
                    structure=structure,
                    filter_on=params.get("filter_on"),
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
                        f"[DEBUG] Added query {len(queries)} with {len(params)} parameters, {'structure' if structure else 'no structure'}, and {'filter_on=' + query_config.filter_on if query_config.filter_on else 'no filter'}"
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
