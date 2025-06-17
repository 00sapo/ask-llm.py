# ask-llm.py — Batch PDF Analysis with Gemini LLM

## NAME

**ask-llm.py** — Analyze PDF documents (and optionally BibTeX bibliographies) using the Gemini LLM API, producing structured JSON reports.

---

## SYNOPSIS

```sh
python3 ask-llm.py [OPTIONS] [PDF|BIB]...
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
- Logging of raw API responses.
- Verbose output for debugging.
- Customizable output filenames and an append mode for reports.

This is especially useful for conducting systematic surveys and producing material for further LLM processing.

---

## REQUIREMENTS

- **Gemini API key** stored in [rbw](https://github.com/doy/rbw) as `gemini_key`.
- Python 3.7 or newer.
- **External tools:**
  - `rbw` (for API key retrieval).
- **Input files (defaults):**
  - `query.md` — Contains your instruction prompts, parameters, and optional JSON schemas.

---

## USAGE

### Basic PDF Analysis

```sh
python3 ask-llm.py paper1.pdf paper2.pdf
```

### Analyze PDFs Referenced in a BibTeX File

```sh
python3 ask-llm.py references.bib
```

### Mix PDFs and BibTeX Files

```sh
python3 ask-llm.py paper1.pdf references.bib paper2.pdf
```

### Use Google Search for Grounding

```sh
python3 ask-llm.py --google-search paper1.pdf
```

### Specify a Different Model

```sh
python3 ask-llm.py --model gemini-1.5-pro-latest paper1.pdf
```

### Run in Verbose Mode

```sh
python3 ask-llm.py -v paper1.pdf
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
  \`\`\`json
  {
    "type": "object",
    "properties": {
      "main_finding": { "type": "string" },
      "confidence_score": { "type": "number" }
    },
    "required": ["main_finding"]
  }
  \`\`\`

  Summarize the main contributions of this paper and extract up to 5 relevant keywords.

  ===
  Google-Search: false
  Identify the core methodology used in this research.


---

## OUTPUT FILES

(Default names, can be overridden by command-line options)

- **analysis_report.json**
  Structured JSON report containing all results organized by document and query.

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
    "model_used": "gemini-1.5-flash-preview-05-20",
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

---

## OPTIONS

- `files` (Positional arguments)
    PDF files and/or BibTeX files to process.

- `--no-clear`
    Do not clear output files (`analysis_report.json`, `log.txt`, `processed_files.txt`) before processing. New results will be appended to existing JSON structure.

- `--model <MODEL_IDENTIFIER>`
    Override the default Gemini model for all queries (e.g., `gemini-1.5-pro-latest`). Default is `gemini-1.5-flash-preview-05-20`. This can be overridden on a per-query basis in `query.md`.

- `--query <QUERY_TEXT | FILE_PATH>`
    Override the query prompts. If a file path is given, it's treated like `query.md`. If a string is given, it's used as a single prompt for all documents. This overrides `query.md`.

- `--report <FILE_PATH>`
    Override the report output file (default: `analysis_report.json`).

- `--log <FILE_PATH>`
    Override the log output file (default: `log.txt`).

- `--processed-list <FILE_PATH>`
    Override the processed files list output file (default: `processed_files.txt`).

- `--google-search`
    Enable Google Search grounding for all queries by default. This can be overridden on a per-query basis in `query.md`.

- `--verbose`, `-v`
    Enable verbose debug output to the console.

- `--version`
    Show the script's version number and exit.

---

## EXAMPLES

Analyze two PDFs with default settings:

```sh
python3 ask-llm.py mypaper.pdf relatedwork.pdf
```

Analyze all PDFs referenced in a BibTeX file, appending to existing reports:

```sh
python3 ask-llm.py --no-clear myrefs.bib
```

Analyze a PDF using a specific query file and enabling Google Search for all queries:

```sh
python3 ask-llm.py --query custom_prompts.md --google-search mypaper.pdf
```

Specify a custom report file and run in verbose mode:

```sh
python3 ask-llm.py --report detailed_analysis.json -v document.pdf
```

---

## ENVIRONMENT

- **rbw**: Used to retrieve the Gemini API key (`gemini_key`). Ensure `rbw` is in your `PATH`.

---

## DEPENDENCIES

- Python 3.7+
- `rbw` (Bitwarden CLI)

The script uses standard Python libraries such as `json`, `base64`, `urllib.request`, `subprocess`, `sys`, `os`, `re`, `datetime`, `pathlib`, and `argparse`. No external Python packages like `requests` or `PyPDF2` need to be installed via pip for the core functionality.

---

## EXIT STATUS

- `0` on success
- Non-zero on error (e.g., missing API key, API errors, file not found)

---

## SEE ALSO

- [Gemini API Documentation](https://ai.google.dev/)
- [rbw Password Manager](https://github.com/doy/rbw)

---

## AUTHOR

[Your Name or Organization]

---

## LICENSE

MIT License (or specify your own).
