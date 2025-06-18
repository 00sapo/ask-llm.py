"""Ask LLM - Process documents using Gemini API."""

__version__ = "1.0.0"

from .analyzer import DocumentAnalyzer
from .config import ConfigManager
from .bibtex import BibtexProcessor
from .api import GeminiAPIClient
from .reports import ReportManager

__all__ = [
    "DocumentAnalyzer",
    "ConfigManager",
    "BibtexProcessor",
    "GeminiAPIClient",
    "ReportManager",
]
