#!/usr/bin/env python3

import re
from typing import List, Dict, Any
from pathlib import Path

import bibtexparser
from bibtexparser.bparser import BibTexParser
from bibtexparser.customization import convert_to_unicode, author, editor


class BibtexProcessor:
    def __init__(self, verbose=False, auto_download_pdfs=True):
        self.verbose = verbose
        self.auto_download_pdfs = auto_download_pdfs

        # Initialize PDF searcher only if needed
        if self.auto_download_pdfs:
            from .pdf_search import PDFSearcher

            self.pdf_searcher = PDFSearcher(verbose=verbose, enabled=auto_download_pdfs)
        else:
            self.pdf_searcher = None

        # Configure bibtexparser
        self.parser = BibTexParser(common_strings=True)
        self.parser.customization = self._customize_entry

    def _customize_entry(self, record):
        """Customize entry parsing"""
        record = convert_to_unicode(record)
        record = author(record)
        record = editor(record)
        return record

    def extract_metadata(self, entry_text: str, bibtex_key: str) -> Dict[str, Any]:
        """Extract metadata from a BibTeX entry"""
        metadata = {"bibtex_key": bibtex_key}

        # Parse using bibtexparser for better accuracy
        try:
            bib_database = bibtexparser.loads(entry_text, parser=self.parser)
            if bib_database.entries:
                entry = bib_database.entries[0]

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
                        # Clean up LaTeX formatting
                        value = self._clean_latex(value)
                        metadata[field] = value

                if self.verbose:
                    print(
                        f"[DEBUG] Extracted {len(metadata) - 1} metadata fields for {bibtex_key}"
                    )

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

        # Remove common LaTeX commands
        text = re.sub(r"\\[a-zA-Z]+\{([^}]*)\}", r"\1", text)  # \emph{text} -> text
        text = re.sub(r"[{}]", "", text)  # Remove remaining braces
        text = text.replace("\\&", "&").replace("\\_", "_")  # Common escapes
        text = text.replace("\\textquoteright", "'")
        text = text.replace("\\textquoteleft", "'")
        text = text.replace("--", "–")  # em dash
        text = text.replace("---", "—")  # en dash

        return text.strip()

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

    def extract_pdfs_from_bibtex(self, bibtex_file: str) -> List[Dict[str, Any]]:
        """Extract PDF paths and keys from BibTeX file"""
        if self.verbose:
            print(f"[DEBUG] Extracting PDFs from BibTeX file: {bibtex_file}")

        file_path = Path(bibtex_file)
        if not file_path.exists():
            print(f"BibTeX file not found: {bibtex_file}")
            return []

        pdf_mappings = []

        try:
            # Try using bibtexparser first
            with open(file_path, "r", encoding="utf-8") as f:
                bib_database = bibtexparser.load(f, parser=self.parser)

            if self.verbose:
                print(f"[DEBUG] Found {len(bib_database.entries)} BibTeX entries")

            for entry in bib_database.entries:
                bibtex_key = entry.get("ID", "")

                if self.verbose:
                    print(f"[DEBUG] Processing BibTeX entry: {bibtex_key}")

                # Look for file field
                pdf_path = None
                if "file" in entry:
                    file_field = entry["file"]
                    # Extract PDF path (first part before semicolon)
                    pdf_match = re.search(r"^([^;:]+\.pdf)", file_field)
                    if pdf_match:
                        pdf_path = pdf_match.group(1)
                        if self.verbose:
                            print(f"[DEBUG] Found PDF: {pdf_path} for key {bibtex_key}")
                elif self.auto_download_pdfs and self.pdf_searcher:
                    # No file field, try to search for PDF
                    title = entry.get("title", "")
                    authors = entry.get("author", "")

                    if title:
                        if self.verbose:
                            print(
                                f"[DEBUG] No file field found for {bibtex_key}, searching for PDF..."
                            )

                        pdf_path = self.pdf_searcher.search_pdf(title, authors)
                        if pdf_path:
                            if self.verbose:
                                print(
                                    f"[DEBUG] Downloaded PDF for {bibtex_key}: {pdf_path}"
                                )
                        else:
                            if self.verbose:
                                print(f"[DEBUG] No PDF found for {bibtex_key}")

                # Reconstruct entry text for metadata extraction
                entry_text = self._reconstruct_entry_text(entry)

                pdf_mappings.append(
                    {
                        "pdf_path": pdf_path,
                        "bibtex_key": bibtex_key,
                        "entry_text": entry_text,
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
            print(f"[DEBUG] Extracted {len(pdf_mappings)} PDF mappings from BibTeX")
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
        """Fallback regex-based PDF extraction with PDF search"""
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

            # Look for file field
            pdf_path = None
            title = ""
            authors = ""

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

                # Extract title and authors for potential PDF search
                title_match = re.search(
                    r'title\s*=\s*["{]([^"}]+)', line, re.IGNORECASE
                )
                if title_match:
                    title = title_match.group(1)

                author_match = re.search(
                    r'author\s*=\s*["{]([^"}]+)', line, re.IGNORECASE
                )
                if author_match:
                    authors = author_match.group(1)

            # If no file field found and auto download is enabled, search for PDF
            if not pdf_path and self.auto_download_pdfs and self.pdf_searcher and title:
                if self.verbose:
                    print(
                        f"[DEBUG] No file field found for {bibtex_key}, searching for PDF..."
                    )

                pdf_path = self.pdf_searcher.search_pdf(title, authors)
                if pdf_path:
                    if self.verbose:
                        print(f"[DEBUG] Downloaded PDF for {bibtex_key}: {pdf_path}")
                else:
                    if self.verbose:
                        print(f"[DEBUG] No PDF found for {bibtex_key}")

            # Store mapping with full entry text
            pdf_mappings.append(
                {
                    "pdf_path": pdf_path,
                    "bibtex_key": bibtex_key,
                    "entry_text": full_entry,
                }
            )

        return pdf_mappings
