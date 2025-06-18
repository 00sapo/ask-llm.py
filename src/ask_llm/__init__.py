"""Ask LLM - Process documents using Gemini API."""

__version__ = "1.0.0"

from .analyzer import DocumentAnalyzer
from .config import ConfigManager
from .bibtex import BibtexProcessor
from .api import GeminiAPIClient
from .reports import ReportManager
from .semantic_scholar import SemanticScholarClient
from .document_processor import DocumentProcessor
from .semantic_scholar_processor import SemanticScholarProcessor

__all__ = [
    "DocumentAnalyzer",
    "ConfigManager",
    "BibtexProcessor",
    "GeminiAPIClient",
    "ReportManager",
    "SemanticScholarClient",
    "DocumentProcessor",
    "SemanticScholarProcessor",
]
