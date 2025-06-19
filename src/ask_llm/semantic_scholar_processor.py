#!/usr/bin/env python3


from .semantic_scholar import SemanticScholarClient


class SemanticScholarProcessor:
    def __init__(self, semantic_scholar_client: SemanticScholarClient, verbose=False):
        self.semantic_scholar_client = semantic_scholar_client
        self.verbose = verbose

    def process_semantic_scholar_queries(self, queries) -> str:
        """Process all Semantic Scholar queries and return combined BibTeX content"""
        if self.verbose:
            print("[DEBUG] Processing all Semantic Scholar queries")

        all_bibtex_entries = []
        entry_counter = 1

        # Process each Semantic Scholar query
        semantic_scholar_queries = [
            q for q in queries if q.params.get("semantic_scholar", False)
        ]

        print(f"🔍 Processing {len(semantic_scholar_queries)} Semantic Scholar queries")

        for query_idx, query_info in enumerate(semantic_scholar_queries):
            if self.verbose:
                print(
                    f"[DEBUG] Processing Semantic Scholar query {query_idx + 1}: {query_info.text[:100]}..."
                )

            print(
                f"🔎 Semantic Scholar query {query_idx + 1}: {query_info.text[:100]}..."
            )

            # Extract Semantic Scholar parameters from query params
            ss_params = {}
            for key, value in query_info.params.items():
                if key.startswith("ss_"):
                    # Remove 'ss_' prefix and convert back to API parameter name
                    api_key = key[3:].replace("_", "")
                    if api_key == "publicationdateoryear":
                        api_key = "publicationDateOrYear"
                    elif api_key == "fieldsofstudy":
                        api_key = "fieldsOfStudy"
                    elif api_key == "publicationtypes":
                        api_key = "publicationTypes"
                    elif api_key == "mincitationcount":
                        api_key = "minCitationCount"
                    elif api_key == "openaccesspdf":
                        api_key = "openAccessPdf"
                    ss_params[api_key] = value

            if self.verbose:
                print(f"[DEBUG] Semantic Scholar parameters: {ss_params}")

            # Perform the search
            try:
                papers = self.semantic_scholar_client.search_papers(
                    query_info.text, ss_params
                )

                print(f"📚 Found {len(papers)} papers for query {query_idx + 1}")

                # Create BibTeX entries for each paper
                for paper in papers:
                    entry_key = f"semanticscholar{entry_counter}"
                    bibtex_entry = self.semantic_scholar_client.create_bibtex_entry(
                        paper, entry_key
                    )
                    all_bibtex_entries.append(bibtex_entry)
                    entry_counter += 1

                if self.verbose:
                    print(f"[DEBUG] Query {query_idx + 1} added {len(papers)} papers")

            except Exception as e:
                print(
                    f"❌ Error processing Semantic Scholar query {query_idx + 1}: {e}"
                )
                if self.verbose:
                    print(f"[DEBUG] Exception details: {type(e).__name__}: {e}")
                continue

        if all_bibtex_entries:
            combined_bibtex = "\n\n".join(all_bibtex_entries)

            # Save Semantic Scholar BibTeX to permanent file
            semantic_scholar_file = "semantic_scholar.bib"
            with open(semantic_scholar_file, "w", encoding="utf-8") as f:
                f.write(combined_bibtex)

            if self.verbose:
                print(
                    f"[DEBUG] Created combined BibTeX with {len(all_bibtex_entries)} entries"
                )
                print(
                    f"[DEBUG] Saved Semantic Scholar BibTeX to: {semantic_scholar_file}"
                )

            print(
                f"💾 Semantic Scholar BibTeX saved: {semantic_scholar_file} ({len(all_bibtex_entries)} entries)"
            )
            return combined_bibtex
        else:
            if self.verbose:
                print("[DEBUG] No Semantic Scholar entries generated")
            print("⚠️  No Semantic Scholar entries generated")
            return ""

    def merge_bibtex_files(
        self, original_bibtex_file: str = None, semantic_scholar_bibtex: str = ""
    ) -> str:
        """Merge original BibTeX file with Semantic Scholar results"""
        merged_content = ""

        # Add original BibTeX content if provided
        if original_bibtex_file:
            try:
                with open(original_bibtex_file, "r", encoding="utf-8") as f:
                    original_content = f.read().strip()
                    if original_content:
                        merged_content += original_content
                        if self.verbose:
                            print(
                                f"[DEBUG] Added original BibTeX content from {original_bibtex_file}"
                            )
            except FileNotFoundError:
                if self.verbose:
                    print(
                        f"[DEBUG] Original BibTeX file {original_bibtex_file} not found"
                    )
            except Exception as e:
                print(
                    f"Warning: Could not read original BibTeX file {original_bibtex_file}: {e}"
                )

        # Add Semantic Scholar content
        if semantic_scholar_bibtex:
            if merged_content:
                merged_content += "\n\n"
            merged_content += semantic_scholar_bibtex
            if self.verbose:
                print("[DEBUG] Added Semantic Scholar BibTeX content")

        return merged_content
