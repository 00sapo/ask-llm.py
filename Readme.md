# ask-llm.py — Batch PDF Analysis with Gemini LLM

## NAME

**ask-llm.py** — Analyze PDF documents (and optionally BibTeX bibliographies) using the Gemini LLM API, producing structured JSON reports. The installed command is typically `ask-llm`.

---

## SYNOPSIS

```sh
ask-llm [OPTIONS] [PDF|BIB]...
```

---

## DESCRIPTION

**ask-llm.py** is a Python script for batch-analyzing PDF files (and optionally BibTeX bibliographies) using Google's Gemini LLM API. It sends each PDF (or its extracted metadata if the PDF is not found) to the API with user-defined prompts and optional JSON schemas, collects structured JSON responses (if specified), and generates a JSON report containing all results.

The script supports:

- Direct PDF file input.
- Extraction and processing of PDFs referenced in `.bib` files. If a PDF is not found, analysis can proceed using its BibTeX metadata.
- Multiple queries defined in a `query.md` file, each with its own parameters (e.g., model, temperature, Google Search enablement) and optional JSON output schema.
- Google Search grounding for queries to enhance factual accuracy.
- JSON output format for easy programmatic processing.
- CSV output format (specify `.csv` extension) for spreadsheet analysis.
- Logging of raw API responses.
- Verbose output for debugging.
- Customizable output filenames and an append mode for reports.

This is especially useful for conducting systematic surveys and producing material for further LLM processing.

---

## INSTALLATION

It is recommended to install **ask-llm** using `pipx` for a clean, isolated installation:

```sh
pipx install ask-llm
```

*(This assumes the package is available on PyPI as `ask-llm`.)*

Alternatively, you can install directly from a Git repository:

```sh
pipx install git+https://github.com/your-org/ask-llm.git  # Replace with the actual repository URL
```

Ensure `pipx` is installed on your system. If not, follow the [official pipx installation guide](https://pipx.pypa.io/stable/installation/).

Python package dependencies (such as `typer`, `requests`, `pydantic`, `bibtexparser`) are managed by the packaging setup and will be installed automatically.

---

## REQUIREMENTS

- **Python:** Python 3.8 or newer.
- **Gemini API Key:** An active API key for Google's Gemini LLM.

---

## USAGE

You should set up a `query.md` file, or use one of the examples provided in the `prompt-lib/`
directory of this repo. The following is the CLI interface.

```sh
 Usage: python -m src.ask_llm.cli [OPTIONS] [FILES]... COMMAND [ARGS]...

 Process PDF files and BibTeX bibliographies using the Gemini API with structured output.


╭─ Arguments ─────────────────────────────────────────────────────────────────────────────╮
│   files      [FILES]...  PDF files and/or BibTeX files to process [default: None]       │
╰─────────────────────────────────────────────────────────────────────────────────────────╯
╭─ Options ───────────────────────────────────────────────────────────────────────────────╮
│ --no-clear                       Do not clear output files before processing (append    │
│                                  mode)                                                  │
│ --query-file               PATH  Override query file (default: query.md)                │
│                                  [default: None]                                        │
│ --report                   PATH  Override report output file (default:                  │
│                                  analysis_report.json, use .csv extension for CSV       │
│                                  format)                                                │
│                                  [default: None]                                        │
│ --log                      PATH  Override log output file (default: log.txt)            │
│                                  [default: None]                                        │
│ --processed-list           PATH  Override processed files list output (default:         │
│                                  processed_files.txt)                                   │
│                                  [default: None]                                        │
│ --api-key                  TEXT  Override Gemini API key (default: from GEMINI_API_KEY  │
│                                  env var)                                               │
│                                  [default: None]                                        │
│ --api-key-command          TEXT  Override command to retrieve API key (default: rbw get │
│                                  gemini_key)                                            │
│                                  [default: None]                                        │
│ --base-url                 TEXT  Override Gemini API base URL (default:                 │
│                                  https://generativelanguage.googleapis.com/v1beta)      │
│                                  [default: None]                                        │
│ --verbose          -v            Enable verbose debug output                            │
│ --help                           Show this message and exit.                            │
╰─────────────────────────────────────────────────────────────────────────────────────────╯
╭─ Commands ──────────────────────────────────────────────────────────────────────────────╮
│ version   Show version information.                                                     │
╰─────────────────────────────────────────────────────────────────────────────────────────╯
```

### Basic PDF Analysis

```sh
ask-llm paper1.pdf paper2.pdf
```

### Analyze PDFs Referenced in a BibTeX File

```sh
ask-llm references.bib --
```

### Mix PDFs and BibTeX Files

```sh
ask-llm paper1.pdf references.bib paper2.pdf
```

### Use Google Search for Grounding

```sh
ask-llm --google-search paper1.pdf
```

### Specify a Different Model

```sh
ask-llm --model gemini-1.5-pro-latest paper1.pdf
```

### Generate CSV Output

```sh
ask-llm --report results.csv paper1.pdf
```

### Run in Verbose Mode

```sh
ask-llm -v paper1.pdf
```

---

## INPUT FILES

- **query.md** (default name)
  A text file defining one or more queries to be run against each document. Queries are separated by three or more equals signs (`===`).
  Each query can specify:
  - **Model Name:** `Model-Name: <model_identifier>` (e.g., `gemini-1.5-pro-latest`)
  - **Temperature:** `Temperature: <float_value>` (e.g., `0.5`)
  - **Google Search:** `Google-Search: <true|false>`
  - **JSON Output Structure:** An embedded JSON code block (```json ...```) defining the desired output schema.
  The rest of the text in a query section is treated as the prompt.

  Example `query.md`:

  ```markdown
  Model-Name: gemini-1.5-flash-latest
  Temperature: 0.7
  Google-Search: true
  ```json
  {
    "type": "object",
    "properties": {
      "main_finding": { "type": "string" },
      "confidence_score": { "type": "number" }
    },
    "required": ["main_finding"]
  }
  ```

  Summarize the main contributions of this paper and extract up to 5 relevant keywords.

  ===
  Google-Search: false
  Identify the core methodology used in this research.

  ```

---

## OUTPUT FILES

(Default names, can be overridden by command-line options)

- **analysis_report.json** (or **analysis_report.csv** if CSV format is specified)
  Structured report containing all results organized by document and query.

- **log.txt**
  Raw API responses for each processed file and query.

- **processed_files.txt**
  List of processed files (or BibTeX keys for metadata-only entries) and their associated BibTeX keys.

### JSON Output Structure

The generated JSON report has the following structure:

```json
{
  "metadata": {
    "generated": "2023-12-07T10:30:00",
    "total_documents": 3,
    "model_used": "gemini-2.5-flash-preview-05-20",
    "queries": [
      {
        "id": 1,
        "text": "Summarize the main contributions...",
        "parameters": {"temperature": 0.7},
        "structure": {...}
      }
    ]
  },
  "documents": [
    {
      "id": 1,
      "file_path": "paper1.pdf",
      "bibtex_key": "smith2023",
      "is_metadata_only": false,
      "queries": [
        {
          "query_id": 1,
          "response": {"title": "...", "summary": "..."},
          "grounding_metadata": {...}
        }
      ]
    }
  ]
}
```

### CSV Output Structure

When CSV format is specified (by using a `.csv` file extension), the output will be a spreadsheet-compatible format with:

- Rows representing documents
- Columns for document metadata (ID, BibTeX Key, File Path, Metadata Only status)
- Additional columns for each query response
- JSON responses are serialized as compact JSON strings
- Text responses have newlines replaced with spaces for CSV compatibility

---

## DEVELOPMENT

To set up the project for development, use `uv run src.ask_llm.cli` to run the CLI with the
development environment. This allows you to test changes without needing to reinstall the package.

---

## LICENSE

MIT License
