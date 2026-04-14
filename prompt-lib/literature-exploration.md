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

calamari historical ocr

===
semantic-scholar: true
fields-of-study: Computer Science
limit: 30
relevance-search: true

kraken historical ocr

===
semantic-scholar: true
fields-of-study: Computer Science
limit: 30
relevance-search: true

detr historical manuscript

===
semantic-scholar: true
fields-of-study: Computer Science
limit: 30
relevance-search: true

yolo historical manuscript

===
semantic-scholar: true
fields-of-study: Computer Science
limit: 30
relevance-search: true

htr for music transcription

===
semantic-scholar: true
fields-of-study: Computer Science
limit: 30
relevance-search: true

ocr for omr

===
semantic-scholar: true
fields-of-study: Computer Science
limit: 30
relevance-search: true

handwritten music recognition manuscript

===
model-name: deepseek-reasoner
temperature: 0.0
web-search: false

Is this paper relevant for the "Related Works" section of a conference/journal paper with these
contributions:
1. using HTR and layout recognition models in music-text medieval manuscripts
2. standardize evaluation protocols (5-fold cross-validation, held-out, cross-manuscript, synthetic
   pretraining, sequential learning)
3. Doing both HTR and HMR

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
model-name: deepseek-chat

Answer to the following questions:

- How do the authors do OCR/OMR?
- What are the dataset splits used by the paper (e.g. held-out, 5-fold cross-validation, sequential
learning, cross-manuscript validation, etc.)?
- What was the content of the dataset? Add the dataset's name.
- What are the takeaways of this paper?

```json
{
  "type": "object",
  "properties": {
    "transformers": {
      "type": "string",
      "description": "How do the authors do OCR/OMR (2 sentences max)"
    },
    "inspection": {
      "type": "string",
      "description": "What are the dataset splits (1 sentences max)"
    },
    "analysis": {
      "type": "string",
      "description": "Dataset content and name (1 sentences max)"
    },
    "takeaways": {
      "type": "string",
      "description": "The key takeaways of these paper (1 sentence)"
    },
    "certainty": {
      "type": "number",
      "description": "Confidence in the answers, between 0 and 1",
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
model-name: deepseek-chat

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
