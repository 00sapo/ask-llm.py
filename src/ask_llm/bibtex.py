#!/usr/bin/env python3

import re
from typing import List, Dict, Any
from pathlib import Path

import bibtexparser
from bibtexparser.bparser import BibTexParser
from bibtexparser.customization import convert_to_unicode, author, editor


class BibtexProcessor:
    def __init__(self, verbose=False):
        self.verbose = verbose

    def _create_parser(self):
        """Create a fresh parser instance"""
        parser = BibTexParser(common_strings=True)
        parser.customization = self._customize_entry
        return parser

    def _customize_entry(self, record):
        """Customize entry parsing"""
        record = convert_to_unicode(record)
        record = author(record)
        record = editor(record)
        return record

    def _extract_metadata_from_entry(self, entry: Dict[str, Any]) -> Dict[str, Any]:
        """Extract metadata from already-parsed BibTeX entry"""
        bibtex_key = entry.get("ID", "")
        metadata = {"bibtex_key": bibtex_key}

        # Extract common fields
        fields_to_extract = [
            "title",
            "author",
            "year",
            "abstract",
            "journal",
            "booktitle",
        ]
        for field in fields_to_extract:
            if field in entry:
                value = entry[field]
                # Handle case where bibtexparser returns a list (e.g., for authors)
                if isinstance(value, list):
                    if field == "author":
                        # Join authors with "and"
                        value = " and ".join(str(author) for author in value)
                    else:
                        # For other list fields, join with semicolons
                        value = "; ".join(str(item) for item in value)
                # Clean up LaTeX formatting
                value = self._clean_latex(value)
                metadata[field] = value

        if self.verbose:
            print(
                f"[DEBUG] Extracted {len(metadata) - 1} metadata fields for {bibtex_key}"
            )

        return metadata

    def extract_metadata(self, entry_text: str, bibtex_key: str) -> Dict[str, Any]:
        """Extract metadata from a BibTeX entry text (for single entry processing)"""
        metadata = {"bibtex_key": bibtex_key}

        # Parse using bibtexparser for better accuracy
        try:
            parser = self._create_parser()  # Create fresh parser
            bib_database = bibtexparser.loads(entry_text, parser=parser)
            if bib_database.entries:
                entry = bib_database.entries[0]
                return self._extract_metadata_from_entry(entry)

        except Exception as e:
            if self.verbose:
                print(
                    f"[DEBUG] bibtexparser failed for {bibtex_key}, falling back to regex: {e}"
                )

            # Fallback to regex parsing
            metadata = self._extract_metadata_regex(entry_text, bibtex_key)

        return metadata

    def _extract_metadata_regex(
        self, entry_text: str, bibtex_key: str
    ) -> Dict[str, Any]:
        """Fallback regex-based metadata extraction"""
        metadata = {"bibtex_key": bibtex_key}

        # Fields to extract
        fields = ["title", "author", "year", "abstract", "journal", "booktitle"]

        for field in fields:
            # Match field = {content} or field = "content"
            pattern = rf'{field}\s*=\s*[{{"]([^{{}}"]*)[\}}"]\s*[,\s]'
            match = re.search(pattern, entry_text, re.IGNORECASE | re.DOTALL)
            if match:
                value = match.group(1).strip()
                value = self._clean_latex(value)
                metadata[field] = value

        return metadata

    def _clean_latex(self, text: str) -> str:
        """Clean LaTeX formatting from text"""
        if not text:
            return text

        # Remove list artifacts (brackets and quotes from bibtexparser)
        text = text.replace("[", "").replace("]", "").replace("'", "")

        # Remove common LaTeX commands
        text = re.sub(r"\\[a-zA-Z]+\{([^}]*)\}", r"\1", text)  # \emph{text} -> text
        text = re.sub(r"[{}]", "", text)  # Remove remaining braces
        text = text.replace("\\&", "&").replace("\\_", "_")  # Common escapes
        text = text.replace("\\textquoteright", "'")
        text = text.replace("\\textquoteleft", "'")
        text = text.replace("--", "–")  # em dash
        text = text.replace("---", "—")  # en dash

        # Clean up extra whitespace
        text = re.sub(r"\s+", " ", text).strip()

        return text

    def format_metadata_for_prompt(self, metadata: Dict[str, Any]) -> str:
        """Format metadata for inclusion in prompt"""
        parts = []
        if metadata.get("title"):
            parts.append(f"Title: {metadata['title']}")
        if metadata.get("author"):
            parts.append(f"Authors: {metadata['author']}")
        if metadata.get("year"):
            parts.append(f"Year: {metadata['year']}")
        if metadata.get("journal"):
            parts.append(f"Journal: {metadata['journal']}")
        if metadata.get("booktitle"):
            parts.append(f"Book/Conference: {metadata['booktitle']}")
        if metadata.get("abstract"):
            parts.append(f"Abstract: {metadata['abstract']}")

        return "\n".join(parts)

    def update_bibtex_with_urls(
        self, bibtex_file: str, url_mappings: Dict[str, str]
    ) -> int:
        """Update BibTeX file with discovered PDF URLs"""
        if self.verbose:
            print(
                f"[DEBUG] Updating BibTeX file {bibtex_file} with {len(url_mappings)} URLs"
            )

        try:
            # Read original file
            with open(bibtex_file, "r", encoding="utf-8") as f:
                content = f.read()

            # Parse with fresh parser
            parser = self._create_parser()
            bib_database = bibtexparser.loads(content, parser=parser)

            updated_count = 0
            for entry in bib_database.entries:
                bibtex_key = entry.get("ID", "")
                if bibtex_key in url_mappings:
                    discovered_url = url_mappings[bibtex_key]

                    # Only add URL if not already present
                    if "url" not in entry or not entry["url"].strip():
                        entry["url"] = discovered_url
                        updated_count += 1
                        if self.verbose:
                            print(
                                f"[DEBUG] Added URL to {bibtex_key}: {discovered_url}"
                            )

            # Write back to file if we made updates
            if updated_count > 0:
                with open(bibtex_file, "w", encoding="utf-8") as f:
                    bibtexparser.dump(bib_database, f)

                if self.verbose:
                    print(f"[DEBUG] Updated {updated_count} entries in {bibtex_file}")

                return updated_count
            else:
                if self.verbose:
                    print(f"[DEBUG] No updates needed for {bibtex_file}")
                return 0

        except Exception as e:
            print(f"Warning: Could not update BibTeX file {bibtex_file}: {e}")
            return 0

    def extract_pdfs_from_bibtex(self, bibtex_file: str) -> List[Dict[str, Any]]:
        """Extract PDF paths and URLs from BibTeX file"""
        if self.verbose:
            print(f"[DEBUG] Extracting URLs from BibTeX file: {bibtex_file}")

        file_path = Path(bibtex_file)
        if not file_path.exists():
            print(f"BibTeX file not found: {bibtex_file}")
            return []

        pdf_mappings = []

        try:
            # Use a fresh parser for the entire file
            parser = self._create_parser()
            with open(file_path, "r", encoding="utf-8") as f:
                bib_database = bibtexparser.load(f, parser=parser)

            if self.verbose:
                print(f"[DEBUG] Found {len(bib_database.entries)} BibTeX entries")

            for entry in bib_database.entries:
                bibtex_key = entry.get("ID", "")

                if self.verbose:
                    print(f"[DEBUG] Processing BibTeX entry: {bibtex_key}")

                # Look for URL first (either in url field or file field)
                url = None
                if "url" in entry:
                    url = entry["url"]
                    if self.verbose:
                        print(f"[DEBUG] Found URL: {url} for key {bibtex_key}")
                elif "file" in entry:
                    file_field = entry["file"]
                    # Check if file field contains a URL (http/https)
                    url_match = re.search(r"(https?://[^\s;:]+)", file_field)
                    if url_match:
                        url = url_match.group(1)
                        if self.verbose:
                            print(
                                f"[DEBUG] Found URL in file field: {url} for key {bibtex_key}"
                            )
                    else:
                        # Extract PDF path (first part before semicolon) as fallback
                        pdf_match = re.search(r"^([^;:]+\.pdf)", file_field)
                        if pdf_match:
                            pdf_path = pdf_match.group(1)
                            if self.verbose:
                                print(
                                    f"[DEBUG] Found PDF path: {pdf_path} for key {bibtex_key}"
                                )
                            # Use PDF path as URL for local files
                            url = pdf_path

                # Extract metadata directly from parsed entry
                metadata = self._extract_metadata_from_entry(entry)

                # Reconstruct entry text for compatibility with existing code
                entry_text = self._reconstruct_entry_text(entry)

                pdf_mappings.append(
                    {
                        "pdf_path": url,  # Now contains URL or PDF path
                        "bibtex_key": bibtex_key,
                        "entry_text": entry_text,
                        "is_url": url
                        and (url.startswith("http://") or url.startswith("https://")),
                        "metadata": metadata,  # Add pre-extracted metadata
                    }
                )

        except Exception as e:
            if self.verbose:
                print(
                    f"[DEBUG] bibtexparser failed, falling back to regex parsing: {e}"
                )

            # Fallback to regex parsing
            pdf_mappings = self._extract_pdfs_regex(bibtex_file)

        if self.verbose:
            print(f"[DEBUG] Extracted {len(pdf_mappings)} URL/PDF mappings from BibTeX")
        return pdf_mappings

    def _reconstruct_entry_text(self, entry: Dict[str, str]) -> str:
        """Reconstruct BibTeX entry text from parsed entry"""
        entry_type = entry.get("ENTRYTYPE", "article")
        entry_id = entry.get("ID", "unknown")

        lines = [f"@{entry_type}{{{entry_id},"]

        for key, value in entry.items():
            if key not in ["ENTRYTYPE", "ID"]:
                lines.append(f"  {key} = {{{value}}},")

        lines.append("}")
        return "\n".join(lines)

    def _extract_pdfs_regex(self, bibtex_file: str) -> List[Dict[str, Any]]:
        """Fallback regex-based URL/PDF extraction"""
        try:
            with open(bibtex_file, "r", encoding="utf-8") as f:
                content = f.read()
        except FileNotFoundError:
            print(f"BibTeX file not found: {bibtex_file}")
            return []

        pdf_mappings = []
        # Split by @ to get entries
        entries = re.split(r"@", content)[1:]  # Skip first empty part

        if self.verbose:
            print(f"[DEBUG] Found {len(entries)} BibTeX entries (regex)")

        for entry_idx, entry in enumerate(entries):
            lines = entry.split("\n")
            if not lines:
                continue

            # Extract entry key from first line
            key_match = re.search(r"^[^{]*\{([^,]+)", lines[0])
            if not key_match:
                if self.verbose:
                    print(f"[DEBUG] Entry {entry_idx} has no valid key, skipping")
                continue

            bibtex_key = key_match.group(1).strip()
            full_entry = "@" + entry  # Store full entry for metadata extraction

            if self.verbose:
                print(f"[DEBUG] Processing BibTeX entry: {bibtex_key}")

            # Look for URL or file field
            url = None
            for line in lines:
                # Check for url field first
                url_match = re.search(r'url\s*=\s*["{]([^"}]+)', line, re.IGNORECASE)
                if url_match:
                    url = url_match.group(1)
                    if self.verbose:
                        print(f"[DEBUG] Found URL: {url} for key {bibtex_key}")
                    break

                # Check for file field
                file_match = re.search(r'file\s*=\s*["{]([^"}]+)', line)
                if file_match:
                    file_path = file_match.group(1)
                    # Check if it's a URL
                    if file_path.startswith("http://") or file_path.startswith(
                        "https://"
                    ):
                        url = file_path
                        if self.verbose:
                            print(
                                f"[DEBUG] Found URL in file field: {url} for key {bibtex_key}"
                            )
                        break
                    else:
                        # Extract PDF path (first part before semicolon)
                        pdf_match = re.search(r"^([^;:]+\.pdf)", file_path)
                        if pdf_match:
                            url = pdf_match.group(1)
                            if self.verbose:
                                print(
                                    f"[DEBUG] Found PDF path: {url} for key {bibtex_key}"
                                )
                            break

            # Store mapping with full entry text
            pdf_mappings.append(
                {
                    "pdf_path": url,
                    "bibtex_key": bibtex_key,
                    "entry_text": full_entry,
                    "is_url": url
                    and (url.startswith("http://") or url.startswith("https://")),
                }
            )

        return pdf_mappings
