semantic-scholar: true
fields-of-study: Computer Science

music + (similarity | k-NN | cluster*) + (symbolic | lyrics)

===
semantic-scholar: true

(medieval | gregorian) + music + ( similarity | k-NN | cluster* )

===
model-name: gemini-2.5-flash
temperature: 0.0
google-search: false

Is this paper describing any practical algorithm for computing the similarity between music excerpts or texts in the context of music?

```json
{
  "type": "object",
  "properties": {
    "relevance": {
      "type": "boolean",
      "description": "Indicates whether the paper describes a practical algorithm for computing similarity between music excerpts or texts in the context of music"
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

- For which type of information the methods described in the paper are designed?
- For which kind of music the methods described in the paper are designed?
- For which historical period the methods described in the paper are designed?
- Are the methods described in the paper include fuzzy methods?
- How much are you confident in your answer? Consider the availability of PDF and the alignment
  between the PDF (if any) and the metadata (0-1)

```json
{
  "type": "object",
  "properties": {
    "data type": {
      "type": "string",
      "description": "The type of data the methods are designed for",
      "enum": [
        "text/lyrics",
        "symbolic music",
        "audio",
        "audio and text",
        "symbolic music and text",
        "other"
      ]
    },
    "music type": {
      "type": "string",
      "description": "The type of music the methods are designed for",
      "enum": [
        "monophonic",
        "polyphonic"
      ]
    },
    "historical period": {
      "type": "string",
      "description": "The historical period the methods are designed for",
      "enum": [
        "medieval",
        "renaissance",
        "baroque",
        "classical",
        "romantic",
        "mdern",
        "folk",
        "popular music",
        "baroque/classical/romantic"
      ]
    },
    "fuzzy": {
      "type": "boolean",
      "description": "Indicates whether the methods include fuzzy methods or not"
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
    "music type",
    "data type",
    "historical period",
    "fuzzy",
    "certainty"
  ]
}
```

===
model-name: gemini-2.5-flash

Briefly describe the methods presented in the paper. Use 2 sentences max.

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
