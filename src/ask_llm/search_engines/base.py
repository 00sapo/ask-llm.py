#!/usr/bin/env python3

from abc import ABC, abstractmethod
from typing import List


class SearchEngine(ABC):
    """Abstract base class for search engines"""

    def __init__(self, verbose=False):
        self.verbose = verbose

    @abstractmethod
    def search_pdfs(self, title: str, authors: str = "") -> List[str]:
        """Search specifically for PDF URLs"""
        pass
