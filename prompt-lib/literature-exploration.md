semantic-scholar: true
fields-of-study: Computer Science
limit: 30
relevance-search: true

trocr historical ocr

===
semantic-scholar: true
fields-of-study: Computer Science
limit: 30
relevance-search: true

trocr medieval text transcription

===
semantic-scholar: true
fields-of-study: Computer Science
limit: 30
relevance-search: true

ocr attention analysis

===
semantic-scholar: true
fields-of-study: Computer Science
limit: 30
relevance-search: true

ocr transformer explainability

===
semantic-scholar: true
fields-of-study: Computer Science
limit: 30
relevance-search: true

trocr explainability

===
model-name: gemini-2.5-flash
temperature: 0.0
google-search: false

Is this paper using visual transformers/attention for OCR?

```json
{
  "type": "object",
  "properties": {
    "relevance": {
      "type": "boolean",
      "description": "Indicates whether the paper is using visual transformer/attention for OCR."
    }
  },
  "required": [
    "relevance"
  ]
}
```

filter-on: relevance

===
model-name: gemini-2.5-flash
temperature: 0.0
google-search: false

Is this paper relevant for the "Related Works" section of a conference/journal paper entitled "Is
this paper describing any practical algorithm for computing the similarity between music excerpts or
texts in the context of music?", where trOCR is applied to medieval Italian manuscripts?

```json
{
  "type": "object",
  "properties": {
    "relevance": {
      "type": "boolean",
      "description": "Indicates wether the paper is relevant for the 'Related Works' section"
    }
  },
  "required": [
    "relevance"
  ]
}
```

filter-on: relevance

===
model-name: gemini-2.5-pro

Answer to the following questions:

- How do the authors use transformers for doing OCR?
- How do the authors inspect the model?
- Which kind of analysis do the authors use for inspecting the model and how does it work?
- What are the takeaways of this paper?

```json
{
  "type": "object",
  "properties": {
    "transformers": {
      "type": "string",
      "description": "How transformers are used for OCR (2 sentences max)"
    },
    "inspection": {
      "type": "string",
      "description": "How the model is inspected (2 sentences max)"
    },
    "analysis": {
      "type": "string",
      "description": "Description of the analysis methodology (2 sentences max)"
    },
    "takeaways": {
      "type": "string",
      "description": "The key takeaways of these paper (1 sentence)"
    },
    "certainty": {
      "type": "number",
      "description": "Confidence in the answer, between 0 and 1",
      "minimum": 0,
      "maximum": 1,
      "format": "float"
    }
  },
  "required": [
    "inspection",
    "analysis",
    "takeaways",
    "certainty"
  ]
}
```

===
model-name: gemini-2.5-flash

Create a concise, dense, and concrete summary of the paper. 3 sentences max.

```json
{
  "type": "object",
  "properties": {
    "methods": {
      "type": "string",
      "description": "A brief description of the methods described in the paper"
    }
  },
  "required": [
    "methods"
  ]
}
```
