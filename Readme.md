# ask-llm.py — Batch PDF Analysis with Gemini LLM

## NAME

**ask-llm.py** — Analyze PDF documents (and optionally BibTeX bibliographies) using the Gemini LLM API, producing structured, aggregated Markdown reports.

---

## SYNOPSIS

```sh
python3 ask-llm.py [PDF|BIB]...
```

---

## DESCRIPTION

**ask-llm.py** is a Python script for batch-analyzing PDF files (and optionally BibTeX bibliographies) using the Gemini LLM API. It sends each PDF to the API with a user-defined prompt and schema, collects structured JSON responses, and generates a Markdown report summarizing the results.

The script supports:

- Direct PDF file input
- Extraction and processing of PDFs referenced in `.bib` files
- Aggregated reporting with summary statistics
- Logging of raw API responses

This is especially useful for conducting systematic surveys and producing material for further LLM processing without the need for lower accuracy RAG and vector databases.

---

## REQUIREMENTS

- **Gemini API key** stored in [rbw](https://github.com/doy/rbw) as `gemini_key`
- Python 3.7 or newer
- **External tools:**
  - `rbw` (for API key retrieval)
- `query.txt` — your instruction prompt
- `structure.json` — JSON schema for the expected output

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

---

## INPUT FILES

- **query.txt**  
  The prompt sent to the LLM (e.g., "Summarize the main contributions and extract keywords.")

- **structure.json**  
  The expected JSON structure for the LLM response (e.g., fields like `title`, `summary`, `keywords`).

---

## OUTPUT FILES

- **analysis_report.md**  
  Aggregated Markdown report with per-document results and summary statistics.

- **log.txt**  
  Raw API responses for each processed file.

- **processed_files.txt**  
  List of processed files and BibTeX keys.

---

## OPTIONS

None. All arguments are treated as input files (PDF or BibTeX).

---

## EXAMPLES

Analyze two PDFs:

```sh
python3 ask-llm.py mypaper.pdf relatedwork.pdf
```

Analyze all PDFs referenced in a BibTeX file:

```sh
python3 ask-llm.py myrefs.bib
```

Analyze a mix of PDFs and BibTeX files:

```sh
python3 ask-llm.py mypaper.pdf myrefs.bib
```

---

## ENVIRONMENT

- **rbw**: Used to retrieve the Gemini API key (`gemini_key`).
- **PATH**: Must include `rbw` and, if using BibTeX, `bibtool`.

---

## DEPENDENCIES

- Python 3.7+
- [requests](https://pypi.org/project/requests/)
- [PyPDF2](https://pypi.org/project/PyPDF2/)
- `rbw`
- `bibtool` (for `.bib` files)

Install Python dependencies with:

```sh
pip install requests PyPDF2
```

---

## EXIT STATUS

- `0` on success
- Non-zero on error (e.g., missing dependencies, API errors, file not found)

---

## SEE ALSO

- [Gemini API Documentation](https://ai.google.dev/)
- [rbw Password Manager](https://github.com/doy/rbw)
- [bibtool](https://ctan.org/pkg/bibtool)

---

## AUTHOR

[Your Name or Organization]

---

## LICENSE

MIT License (or specify your own).

---

**Example directory structure:**

```
ask-llm.py
query.txt
structure.json
paper1.pdf
references.bib
```

---

**Note:**  
Edit `query.txt` and `structure.json` to customize the analysis. Ensure your Gemini API key is stored in `rbw` as `gemini_key`.
