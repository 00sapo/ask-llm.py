#!/usr/bin/env python3

import re


class BibtexProcessor:
    def __init__(self, verbose=False):
        self.verbose = verbose

    def extract_metadata(self, entry_text, bibtex_key):
        """Extract metadata from a BibTeX entry"""
        metadata = {"bibtex_key": bibtex_key}

        # Fields to extract
        fields = ["title", "author", "year", "abstract", "journal", "booktitle"]

        for field in fields:
            # Match field = {content} or field = "content"
            pattern = rf'{field}\s*=\s*[{{"]([^{{}}"]*)[\}}"]\s*[,\s]'
            match = re.search(pattern, entry_text, re.IGNORECASE | re.DOTALL)
            if match:
                value = match.group(1).strip()
                # Clean up common LaTeX formatting
                value = re.sub(
                    r"\\[a-zA-Z]+\{([^}]*)\}", r"\1", value
                )  # \emph{text} -> text
                value = re.sub(r"[{}]", "", value)  # Remove remaining braces
                value = value.replace("\\&", "&").replace("\\_", "_")  # Common escapes
                metadata[field] = value

        return metadata

    def format_metadata_for_prompt(self, metadata):
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

    def extract_pdfs_from_bibtex(self, bibtex_file):
        """Extract PDF paths and keys from BibTeX file, including full entry text"""
        if self.verbose:
            print(f"[DEBUG] Extracting PDFs from BibTeX file: {bibtex_file}")
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
            print(f"[DEBUG] Found {len(entries)} BibTeX entries")

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

            # Look for file field
            pdf_path = None
            for line in lines:
                file_match = re.search(r'file\s*=\s*["{]([^"}]+)', line)
                if file_match:
                    file_path = file_match.group(1)
                    # Extract PDF path (first part before semicolon)
                    pdf_match = re.search(r"^([^;:]+\.pdf)", file_path)
                    if pdf_match:
                        pdf_path = pdf_match.group(1)
                        if self.verbose:
                            print(f"[DEBUG] Found PDF: {pdf_path} for key {bibtex_key}")
                        break

            # Store mapping with full entry text
            pdf_mappings.append(
                {
                    "pdf_path": pdf_path,
                    "bibtex_key": bibtex_key,
                    "entry_text": full_entry,
                }
            )

        if self.verbose:
            print(f"[DEBUG] Extracted {len(pdf_mappings)} PDF mappings from BibTeX")
        return pdf_mappings
