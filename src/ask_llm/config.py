#!/usr/bin/env python3

import json
import os
import re
import sys
import subprocess


class ConfigManager:
    def __init__(self, verbose=False):
        self.verbose = verbose

    def get_api_key(self):
        """Get API key using rbw"""
        if self.verbose:
            print("[DEBUG] Retrieving API key using rbw")
        try:
            result = subprocess.run(
                ["rbw", "get", "gemini_key"], capture_output=True, text=True, check=True
            )
            if self.verbose:
                print("[DEBUG] API key retrieved successfully")
            return result.stdout.strip()
        except subprocess.CalledProcessError:
            print("Error: Could not retrieve API key using 'rbw get gemini_key'")
            sys.exit(1)

    def load_queries(self, filename):
        """Load and parse queries from text file"""
        if self.verbose:
            print(f"[DEBUG] Loading queries from {filename}")
        try:
            with open(filename, "r", encoding="utf-8") as f:
                content = f.read().strip()
        except FileNotFoundError:
            print(f"Error: {filename} not found")
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
                    for param in ["model-name:", "temperature:", "google-search:"]
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
                queries.append(
                    {"text": query_text, "params": params, "structure": structure}
                )
                if self.verbose:
                    print(
                        f"[DEBUG] Added query {len(queries)} with {len(params)} parameters and {'structure' if structure else 'no structure'}"
                    )

        if self.verbose:
            print(f"[DEBUG] Total queries loaded: {len(queries)}")
        return queries

    def load_json(self, filename):
        """Load JSON file"""
        if self.verbose:
            print(f"[DEBUG] Attempting to load JSON from {filename}")
        if not os.path.exists(filename):
            if self.verbose:
                print(f"[DEBUG] File {filename} does not exist")
            return None
        try:
            with open(filename, "r", encoding="utf-8") as f:
                data = json.load(f)
                if self.verbose:
                    print(
                        f"[DEBUG] Successfully loaded JSON with {len(data) if isinstance(data, dict) else 'unknown'} top-level keys"
                    )
                return data
        except json.JSONDecodeError as e:
            print(f"Error: Invalid JSON in {filename}: {e}")
            sys.exit(1)
