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

### Some data

In my experiments (see `prompt-lib/` for examples), I found the following:

- 85% of the papers successfully found a PDF online; of these, only 3% had certainty ≤0.8,
indicating a possibly wrong PDF.
- Gemini-2.5-pro had the following distribution of certainty (even if the PDF was wrong and only the
metadata were used)
![Histogram of certainty](https://github.com/00sapo/ask-llm.py/blob/master/chart.png?raw=true)
- Semantic Scholar retrieved 446 items, of which 34% were excluded by the gemini filter-on criteria
- On average, 64 seconds per paper were spent on the analysis (including the time to retrieve the
PDF) using a 500 Mbps connection.
- In total, I spent ~0.75€ for the whole process.
  
---

## INSTALLATION

Install from a Git repository:

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

### Quick Examples

0. **Get help:**

    ```sh
    ask-llm --help
    ```

    ```sh
    ask-llm process --help
    ```

    ```sh
    ask-llm fulltext --help
    ```

1. **Analyze PDFs:**

    ```sh
    ask-llm process paper1.pdf paper2.pdf
    ```

2. **Analyze PDFs from a BibTeX file:**

    ```sh
    ask-llm process references.bib
    ```

3. **Retrieve PDFs for items in a BibTeX file:**

    ```sh
    ask-llm fulltext --bibtex references.bib
    ```

    ```

4. **Custom query file:**

    ```sh
    ask-llm process --query-file custom_queries.md
    ```

5. **Clean artifact files:**

    ```sh
    ask-llm clean
    ```

5. **Generate report (especially useful for peer-review):**

    ```sh
    jq -r '.documents[].queries[].response' ./analysis_report.json >report.md
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
  Processes PDFs linked in `file` fields (relative paths to the BibTeX file are supported). If a PDF is missing, we will attempt to find it online using title/authors; if we can't, analysis proceeds using only the BibTeX metadata.

---

## OUTPUT FILES

Default names (can be overridden via CLI options):

- **`analysis_report.json`**: Main structured report in JSON format.
- **`analysis_report.csv`**: Main structured report in CSV format.
- **`semantic_scholar.bib`**: BibTeX entries for papers found by Semantic Scholar queries.
- **`ask_llm_downloads/`**: Directory containing downloaded PDFs.
- **`log.txt`**: Raw API responses from the LLM.
- **`processed_files.txt`**: List of processed files/BibTeX keys.
- **`filtered_out_documents.txt`**: List of documents excluded by `Filter-On` criteria in `query.md`.
- **\*.sqlite**: caches for the requests in order to respect retry. To zeroing the cache, delete the
  `.sqlite` files corresponding to the requests that you want to reset.

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
