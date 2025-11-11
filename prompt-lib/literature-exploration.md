semantic-scholar: true
fields-of-study: Computer Science
limit: 200
relevance-search: true

trocr + ( historical | medieval ) + ( transcription | recognition )

===
semantic-scholar: true
fields-of-study: Computer Science
limit: 200
relevance-search: true

( trocr | transformers | attention ) + ( inspection | explainability )

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
- Does the model use the READ 2016 dataset?
- What are the best CER and WER obtained on the READ 2016 dataset?
- How confident are you in your answer? Consider the availability of the PDF and the correspondence between the PDF (if any) and the metadata (0-1).

```json
{
  "type": "object",
  "properties": {
    "transformers": {
      "type": "string",
      "description": "How transformers are used for OCR (2 sentences max)",
    },
    "inspection": {
      "type": "string",
      "description": "How the model is inspected (2 sentences max)",
    },
    "analysis": {
      "type": "string",
      "description": "Description of the analysis methodology (2 sentences max)",
    },
    "takeaways": {
      "type": "string",
      "description": "The key takeaways of these paper (1 sentence)"
    },
    "read2016":{
      "type": "boolean",
      "description": "Does the paper use READ2016 for testing the models?"
    },
    "wer":{
      "type": "number",
      "description": "The WER on the READ 2016 test set"
      "minimum": 0,
      "maximum": 1,
      "format": "float"
    },
    "cer":{
      "type": "number",
      "description": "The CER on the READ 2016 test set"
      "minimum": 0,
      "maximum": 1,
      "format": "float"
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
    "read2016",
    "wer",
    "cer",
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
