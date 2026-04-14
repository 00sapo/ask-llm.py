"""Ask LLM - Process documents using provider-agnostic LLM APIs."""

__version__ = "1.0.0"

from .analyzer import DocumentAnalyzer
from .config import ConfigManager
from .bibtex import BibtexProcessor
from .api import LLMAPIClient, GeminiAPIClient
from .reports import ReportManager
from .semantic_scholar import SemanticScholarClient
from .document_processor import DocumentProcessor
from .semantic_scholar_processor import SemanticScholarProcessor
from .url_resolver import URLResolver
from .pdf_search import PDFDownloader
from .search_strategy import (
    SearchStrategy,
    QwantSearchStrategy,
)

__all__ = [
    "DocumentAnalyzer",
    "ConfigManager",
    "BibtexProcessor",
    "LLMAPIClient",
    "GeminiAPIClient",
    "ReportManager",
    "SemanticScholarClient",
    "DocumentProcessor",
    "SemanticScholarProcessor",
    "URLResolver",
    "PDFDownloader",
    "SearchStrategy",
    "QwantSearchStrategy",
]
