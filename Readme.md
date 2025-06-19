# ask-llm.py

Automate researcher life. Peer-review, systematic surveys, paper writing, and more.

## Table of Contents

- [Name](#name)
- [Synopsis](#synopsis)
- [Description](#description)
- [Installation](#installation)
- [Requirements](#requirements)
- [Usage](#usage)
  - [Command-Line Interface](#command-line-interface)
  - [Quick Examples](#quick-examples)
- [Input Files](#input-files)
  - [`query.md`](#querymd-default-or-specify-with---query-file)
  - [BibTeX Files (`.bib`)](#bibtex-files-bib)
- [Output Files](#output-files)
  - [Report Structure Overview (`analysis_report.json`)](#report-structure-overview-analysis_reportjson)
- [Development](#development)
- [TODO](#todo)
- [License](#license)

---

## SYNOPSIS

```sh
ask-llm [OPTIONS] [PDF|BIB]...
```

---

## DESCRIPTION

**ask-llm** analyzes PDF documents, BibTeX bibliographies, search on Semantic Scholar, and retrieves PDFs from the web. It processes files based on custom queries (defined in `query.md`), supports structured JSON/CSV outputs, and can use BibTeX metadata if PDFs are missing. Key features include Gemini LLM for text analysis and generation, Semantic Scholar integration for paper discovery, Google Search for grounding and PDF retrieval, Qwant for PDF retrieval.

### Things you can do with **ask-llm**

- assist during peer-review of a paper
- perform a systematic screening of papers
- search for papers on a specific topic and analyze them
- retrieve PDF urls of items in a bibtex

### Things you will be able to do in the future

- use the output of queries (i.e. JSON output) as input to further queries
- use the output JSON to build a discursive report/paper

---

## INSTALLATION

The recommended way to install **ask-llm** is using `pipx`:

```sh
pipx install ask-llm
```

*(Assumes the package `ask-llm` is on PyPI.)*

Or, install from a Git repository:

```sh
pipx install git+https://github.com/your-org/ask-llm.git # Replace with actual URL
```

Ensure `pipx` is installed ([official guide](https://pipx.pypa.io/stable/installation/)). Dependencies are handled automatically.

---

## REQUIREMENTS

- **Python:** Python 3.8 or newer.
- **Gemini API Key:** An active API key for Google's Gemini LLM.

---

## USAGE

First, set up a `query.md` file (see [Input Files](#input-files) section or examples in `prompt-lib/`). Then, use the command-line interface:

### Command-Line Interface

```sh
 Usage: ask-llm [OPTIONS] [FILES]... COMMAND [ARGS]...

 Process PDF files and BibTeX bibliographies using the Gemini API with structured output.


╭─ Arguments ────────────────────────────────────────────────────────────────────────────────────────────────────╮
│   files      [FILES]...  PDF files and/or BibTeX files to process (optional when using Semantic Scholar)       │
│                          [default: None]                                                                       │
╰────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
╭─ Options ──────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ --no-clear                       Do not clear output files before processing (append mode)                     │
│ --qwant                          Use Qwant search strategy instead of Google grounding (default)               │
│ --load-state               PATH  Load and resume from saved state file [default: None]                         │
│ --resume                         Resume from default state file (ask_llm_state.json)                           │
│ --query-file               PATH  Override query file (default: query.md) [default: None]                       │
│ --report                   PATH  Override report output file (default: analysis_report.json and                │
│                                  analysis_report.csv)                                                          │
│                                  [default: None]                                                               │
│ --log                      PATH  Override log output file (default: log.txt) [default: None]                   │
│ --processed-list           PATH  Override processed files list output (default: processed_files.txt)           │
│                                  [default: None]                                                               │
│ --api-key                  TEXT  Override Gemini API key (default: from GEMINI_API_KEY env var)                │
│                                  [default: None]                                                               │
│ --api-key-command          TEXT  Override command to retrieve API key (default: rbw get gemini_key)            │
│                                  [default: None]                                                               │
│ --base-url                 TEXT  Override Gemini API base URL (default:                                        │
│                                  https://generativelanguage.googleapis.com/v1beta)                             │
│                                  [default: None]                                                               │
│ --verbose          -v            Enable verbose debug output                                                   │
│ --help                           Show this message and exit.                                                   │
╰────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
╭─ Commands ─────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ version   Show version information.                                                                            │
╰────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
```

### Quick Examples

1. **Analyze PDFs:**

    ```sh
    ask-llm paper1.pdf paper2.pdf
    ```

2. **Analyze PDFs from a BibTeX file:**

    ```sh
    ask-llm references.bib
    ```

3. **Use Semantic Scholar (queries defined in `query.md`):**

    ```sh
    ask-llm
    ```

4. **Custom query file and CSV output:**

    ```sh
    ask-llm --query-file custom_queries.md --report results.csv my_document.pdf
    ```

---

## INPUT FILES

- **`query.md`** (default, or specify with `--query-file`)
  Defines queries to run on each document. Queries are separated by three or more equals signs (`===`). Each query section includes the prompt text and can specify parameters:
  - `Model-Name: <model_identifier>` (e.g., `gemini-1.5-pro-latest`)
  - `Temperature: <float_value>` (e.g., `0.7`)
  - `Google-Search: <true|false>` (enables Google Search grounding for the LLM)
  - `Semantic-Scholar: <true|false>` (enables paper search via Semantic Scholar API. The query text becomes the search term. See [Semantic Scholar API docs](https://api.semanticscholar.org/api-docs/#tag/Paper-Data/operation/get_graph_paper_bulk_search) for advanced syntax. PDFs for found papers are searched using DuckDuckGo if not directly available from Semantic Scholar.)
    - Additional Semantic Scholar parameters (e.g., `Sort: citationCount:desc`, `Fields-of-study: Computer Science`) can be included.
  - `Filter-On: <field_name>` (for JSON output, filters documents where this boolean field in the response is `false`)
  - **JSON Output Structure:** Embed a ```json ...``` code block to define the desired output schema for the LLM.

  Parameter names are case-insensitive, and they generally persist to subsequent queries unless
  overridden, except for *one-shot* parameters (currently `filter-on` and `Semantic-Scholar`). See
  `prompt-lib/` for more examples.

  Basic `query.md` structure:

  ```markdown
  Model-Name: gemini-1.5-flash-latest
  Temperature: 0.7
  Google-Search: true
  ```json
  {
    "type": "object",
    "properties": { "main_finding": { "type": "string" } },
    "required": ["main_finding"]
  }
  ``\`
  Summarize the main contributions of this paper.

  ===
  Semantic-Scholar: true
  Limit: 10 # Search for 10 papers

  Find recent papers on LLM applications in systematic reviews.
  ```

- **BibTeX Files (`.bib`)**
  Processes PDFs linked in `file` fields (relative paths to the BibTeX file are supported). If a PDF is missing, DuckDuckGo attempts to find it online using title/authors; otherwise, analysis proceeds using only the BibTeX metadata. Automatic PDF download can be disabled with `--no-pdf-download`.

---

## OUTPUT FILES

Default names (can be overridden via CLI options):

- **`analysis_report.json`**: Main structured report in JSON format.
- **`analysis_report.csv`**: Main structured report in CSV format.
- **`log.txt`**: Raw API responses from the LLM.
- **`processed_files.txt`**: List of processed files/BibTeX keys.
- **`filtered_out_documents.txt`**: List of documents excluded by `Filter-On` criteria in `query.md`.
- **`semantic_scholar.bib`**: BibTeX entries for papers found by Semantic Scholar queries.
- **\*.sqlite**: caches for the requests in order to respect retry. To zeroing the cache, delete the
  `.sqlite` files corresponding to the requests that you want to reset.

### Report Structure Overview (`analysis_report.json`)

The JSON report includes `metadata` (generation time, model used, query details) and a `documents` array. Each document object in the array contains:

- `id`: A unique identifier for the document in this report.
- `file_path`: Path to the PDF file or URL.
- `bibtex_key`: BibTeX key, if applicable.
- `is_metadata_only`: Boolean, true if only BibTeX metadata was processed (PDF not found/used).
- `is_url`: Boolean, true if the input was a URL.
- `queries`: An array of results, one for each query run on the document. Each query result includes:
  - `query_id`: Identifier for the query (from `query.md`).
  - `response`: The LLM's response (parsed JSON if a schema was provided, otherwise text).
  - `grounding_metadata`: Metadata from Google Search or URL context, if applicable.

Example snippet:

```json
{
  "metadata": {
    "generated": "2023-12-07T10:30:00",
    "model_used": "gemini-1.5-flash-latest",
    "queries": [ { "id": 1, "text": "Summarize..." } ]
  },
  "documents": [
    {
      "id": 1,
      "file_path": "paper1.pdf",
      "bibtex_key": "smith2023",
      "is_metadata_only": false,
      "is_url": false,
      "queries": [
        {
          "query_id": 1,
          "response": {"main_finding": "This paper introduces X."},
          "grounding_metadata": null
        }
      ]
    }
  ]
}
```

For CSV output, document metadata and query responses (JSON serialized if structured, otherwise plain text with newlines removed) are organized into columns.

---

## DEVELOPMENT

To set up the project for development, use `uv run src.ask_llm.cli` to run the CLI with the
development environment. This allows you to test changes without needing to reinstall the package.

---

## TODO

- Support other models via litellm
- Pass output of previous queries to subsequent queries

---

## LICENSE

MIT License
