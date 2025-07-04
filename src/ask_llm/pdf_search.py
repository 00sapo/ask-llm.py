#!/usr/bin/env python3

import os
import re
from typing import Optional

import requests_cache


class PDFDownloader:
    def __init__(self, verbose=False):
        self.verbose = verbose
        # Use requests_cache instead of requests
        self.session = requests_cache.CachedSession(
            cache_name="pdf_download_cache",
            expire_after=3600,  # Cache for 1 hour
            backend="sqlite",
            match_headers=True,
        )
        self.session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            }
        )

        # Create local downloads directory
        self.downloads_dir = "ask_llm_downloads"
        os.makedirs(self.downloads_dir, exist_ok=True)

        if self.verbose:
            print(
                f"[DEBUG] Initialized PDF downloader with local directory: {self.downloads_dir}"
            )

    def download_pdf(self, url: str, title: str) -> Optional[str]:
        """Download PDF file to local downloads directory"""
        try:
            if self.verbose:
                print(f"[DEBUG] Downloading PDF from: {url}")

            # Create safe filename from title
            safe_title = re.sub(r"[^\w\s\-]", "", title)[:50]  # Limit length
            safe_title = re.sub(r"\s+", "_", safe_title).strip("_")
            if not safe_title:
                safe_title = "downloaded_paper"

            # Create local file path
            pdf_filename = f"ask_llm_{safe_title}_{hash(url) % 10000}.pdf"
            pdf_path = os.path.join(self.downloads_dir, pdf_filename)

            # Skip download if file already exists
            if os.path.exists(pdf_path):
                if self.verbose:
                    print(f"[DEBUG] PDF already exists locally: {pdf_path}")
                return pdf_path

            # Download with timeout and size limit
            response = self.session.get(url, timeout=30, stream=True)

            if self.verbose and hasattr(response, "from_cache"):
                cache_status = "from cache" if response.from_cache else "fresh download"
                print(f"[DEBUG] PDF download: {cache_status}")

            response.raise_for_status()

            # Check content type
            content_type = response.headers.get("content-type", "").lower()
            if "pdf" not in content_type and not url.lower().endswith(".pdf"):
                if self.verbose:
                    print(f"[DEBUG] URL doesn't appear to be a PDF: {content_type}")
                return None

            # Download with size limit (50MB)
            max_size = 50 * 1024 * 1024
            downloaded_size = 0

            with open(pdf_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        downloaded_size += len(chunk)
                        if downloaded_size > max_size:
                            if self.verbose:
                                print("[DEBUG] PDF too large, skipping")
                            os.remove(pdf_path)
                            return None
                        f.write(chunk)

            # Verify it's a valid PDF by checking header
            with open(pdf_path, "rb") as f:
                header = f.read(5)
                if header != b"%PDF-":
                    if self.verbose:
                        print("[DEBUG] Downloaded file is not a valid PDF")
                    os.remove(pdf_path)
                    return None

            if self.verbose:
                print(
                    f"[DEBUG] Successfully downloaded PDF: {pdf_path} ({downloaded_size} bytes)"
                )

            return pdf_path

        except Exception as e:
            if self.verbose:
                print(f"[DEBUG] PDF download failed: {e}")
            return None

    def cleanup_temp_files(self, pdf_paths: list):
        """Keep all downloaded files permanently"""
        if self.verbose:
            print(
                f"[DEBUG] Keeping {len(pdf_paths)} downloaded PDF files permanently in {self.downloads_dir}"
            )
