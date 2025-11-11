# ask-llm Dual-Backend Architecture Design

## Overview

This document outlines the design decisions for adding litellm support to ask-llm while maintaining full backwards compatibility with the existing Gemini-only implementation.

## Background

ask-llm was originally designed as a Gemini-specific tool leveraging unique Google AI features for academic paper discovery and analysis. The core workflow relies heavily on:

- **Google Search tool**: Real-time web search for PDF discovery
- **Grounding Metadata**: URL extraction from search results  
- **URL Context tool**: Web content fetching and analysis
- **Structured JSON output**: Reliable data extraction

## Current Architecture Analysis

### Core Workflow: PDF Discovery Pipeline
```
Query → Google Search Tool → Grounding Metadata → Extract URLs → Download PDFs → Analyze with Structured Output
```

### Gemini-Specific Feature Usage

| Feature | Location | Purpose | Criticality | Fallback |
|---------|----------|---------|-------------|----------|
| **Google Search Tool** | `api.py:90`, `google_grounding.py:48` | Real-time web search for PDF discovery | **HIGH** | Qwant search |
| **Grounding Metadata** | `api.py:252-280`, `document_processor.py:344-386` | URL extraction from search results | **VERY HIGH** | Qwant search |
| **URL Context Tool** | `api.py:73`, `api.py:255-282` | Fetch and analyze web content | **MEDIUM** | None |
| **Structured JSON** | `api.py:104-108` | Reliable data extraction | **HIGH** | None |

## Design Decisions

### 1. Backend Selection Strategy

**Decision**: Automatic backend selection based on model name prefix

```python
def determine_backend(model_name: str) -> str:
    if model_name.startswith(('gemini', 'gemma')):
        return 'gemini'
    else:
        return 'litellm'
```

**Rationale**: 
- Simple and intuitive for users
- No additional configuration required
- Clear model-to-backend mapping

### 2. Feature Support Strategy

**Decision**: Strict feature validation with no complex fallbacks

#### Gemini Backend (Full Feature Set)
- ✅ Google Search tool
- ✅ URL Context tool  
- ✅ Grounding Metadata
- ✅ PDF upload
- ✅ Structured JSON output

#### LiteLLM Backend (Limited Feature Set)
- ❌ Google Search tool → **ERROR**: "google-search not supported with litellm models"
- ❌ URL Context tool → URLs processed as plain text only
- ❌ Grounding Metadata → No source attribution available
- ✅ PDF upload (capable models only)
- ✅ Structured JSON output (capable models only)

**Rationale**:
- Clear expectations for users
- Avoid complex fallback logic that could hide limitations
- Maintain code simplicity and reliability
- Early error detection prevents confusing runtime failures

### 3. Architecture Pattern

**Decision**: Abstract base class with factory pattern

```
BaseAPIClient (abstract)
├── GeminiAPIClient (existing, refactored)
└── LiteLLMAPIClient (new)

BackendFactory.create_client(model_name) → BaseAPIClient
```

**Interface Definition**:
```python
class BaseAPIClient(ABC):
    @abstractmethod
    def create_pdf_payload(self, encoded_pdf: str, query_text: str) -> Dict[str, Any]
    
    @abstractmethod
    def create_text_payload(self, query_text: str) -> Dict[str, Any]
    
    @abstractmethod
    def create_url_payload(self, query_text: str, urls: list) -> Dict[str, Any]
    
    @abstractmethod
    def apply_query_params(self, payload: Dict[str, Any], query_info: QueryConfig) -> Dict[str, Any]
    
    @abstractmethod
    def make_request(self, payload: Dict[str, Any], query_info: QueryConfig) -> Dict[str, Any]
    
    @abstractmethod
    def extract_response(self, response_data: Dict[str, Any]) -> Tuple[str, Optional[Dict[str, Any]]]
    
    @abstractmethod
    def validate_features(self, query_info: QueryConfig) -> None
```

**Rationale**:
- Minimal changes to existing codebase
- Clean separation of backend-specific logic
- Easy to extend with additional backends
- Enforces consistent interface across implementations

### 4. Model Compatibility Strategy

**Decision**: Restrict litellm to models supporting both PDF upload AND structured JSON output

**Supported LiteLLM Models** (examples):
- `gpt-4o` (OpenAI)
- `claude-3-5-sonnet-20241022` (Anthropic)
- `gemini-1.5-pro` (would use litellm backend, not Gemini backend)

**Rationale**:
- Ensures core ask-llm functionality works
- Prevents runtime errors with unsupported features
- Maintains user experience quality

### 5. Error Handling Strategy

**Decision**: Simple error approach with clear messaging

**Feature Validation Errors**:
```python
# Early validation in apply_query_params()
if query_info.params.get("google_search") and backend_type == "litellm":
    raise ValueError("google-search feature is not supported with litellm models. Use a gemini model for web search capabilities.")
```

**Runtime Errors**:
- Generic error handling for API failures
- Backend-specific errors wrapped in common exception types
- Preserve existing error handling patterns

**Rationale**:
- Users get immediate, clear feedback
- No hidden fallbacks that could confuse users
- Maintains existing error handling behavior

### 6. Configuration Strategy

**Decision**: Extend existing configuration to support multiple authentication patterns

**Gemini Backend**:
- `GEMINI_API_KEY` environment variable
- `--api-key-command` for dynamic key retrieval

**LiteLLM Backend**:
- Provider-specific environment variables (e.g., `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`)
- Automatic provider detection based on model name

**Rationale**:
- Backwards compatible with existing Gemini configuration
- Follows litellm's standard authentication patterns
- No additional configuration burden for users

## Implementation Phases

### Phase 1: Backend Abstraction
1. Create `BaseAPIClient` abstract class
2. Refactor `GeminiAPIClient` to inherit from base class
3. Create `BackendFactory` with model-based selection

### Phase 2: LiteLLM Implementation  
4. Implement `LiteLLMAPIClient` with interface compatibility
5. Add feature validation for incompatible combinations
6. Update dependencies to include litellm

### Phase 3: Integration
7. Update `DocumentAnalyzer` to use factory pattern
8. Modify configuration to support multi-backend auth
9. Update CLI help text to be backend-agnostic

## Business Impact Assessment

### Core Value Proposition Impact

| Use Case | Gemini Backend | LiteLLM Backend | Impact |
|----------|----------------|-----------------|--------|
| **PDF Discovery** | Full (Google Search + Grounding) | Limited (Qwant only) | **HIGH** - Core value prop affected |
| **PDF Analysis** | Full | Full (capable models) | **LOW** - Mostly preserved |
| **URL Processing** | Full (URL Context tool) | Limited (text only) | **MEDIUM** - Web analysis degraded |
| **Structured Extraction** | Full | Full (capable models) | **LOW** - Analysis quality maintained |

### Strategic Positioning

**Gemini Backend**: 
- **Recommended** for full ask-llm experience
- Optimal for PDF discovery workflows
- Complete feature set

**LiteLLM Backend**:
- **Alternative** for users requiring specific models
- Focused on document analysis rather than discovery
- Clear feature limitations documented

## User Experience Considerations

### Transparent Backend Switching
- Users specify model names, backend selection is automatic
- No need to understand backend concepts
- Consistent interface across both backends

### Clear Error Messages
- Immediate feedback for incompatible feature combinations
- Explicit documentation of feature limitations
- Guidance on alternative approaches

### Migration Path
- Existing Gemini users: No changes required
- New litellm users: Clear setup documentation
- Mixed usage: Switch backends by changing model names

## Future Extensibility

The abstract base class pattern enables future backend additions:
- Additional AI providers (e.g., Cohere, Together AI)
- Custom API integrations
- Local model support

## Conclusion

This design preserves ask-llm's core value proposition while enabling model diversity through litellm. The architecture maintains backwards compatibility, provides clear user expectations, and allows for future extensibility while acknowledging the fundamental limitations when moving away from Gemini's unique features.

The dual-backend approach positions ask-llm as:
1. **Gemini-optimized** for full PDF discovery and analysis workflows
2. **LiteLLM-compatible** for users requiring specific models with understood trade-offs
3. **Future-ready** for additional backend integrations