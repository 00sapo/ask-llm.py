model-name: gemini-2.5-flash
temperature: 0.3
google-search: false

Please, check if the paper is well structured, if the sections are in a logical order, and if the contributions are clearly stated in the introduction and in the abstract. Also check the consistency of the title and the abstract with the content of the paper: they should not be misleading nor too generic.
Be extremely critical. Spot the unspottable, but do not invent anything.

=====

Please, evaluate if the paper explains clearly the experiments and gives all the information needed for reproducing them.
Be extremely critical. Spot the unspottable, but do not invent anything.

=====

Please, check if there are experimental/methodological flaws in the paper. If so, please, explain them.
Pay special importance to:

- datasets selection and description
- imbalance in datasets
- proper evaluation metrics
- proper separation, including cross-validation with relevant groups for stratified or leave-groups-out validation
- control groups and/or baseline comparison
- correct interpretation of results
- correctness of mathematical formula, demonstrations, and algorithms
Be extremely critical. Spot the unspottable, but do not invent anything.

=====

Please, evaluate the completeness of the discussion of the results. Is the paper able to give meaningful takeaways?
Be extremely critical. Spot the unspottable, but do not invent anything.

=====
google-search: true

Please, use google scholar to search for scholarly sources about similar topics as the paper and check if all the relevant references are included.
Be extremely critical. Spot the unspottable, but do not invent anything.

=====
google-search: true

Please, search for scholarly sources about similar topics as the paper and evaluate the scientific novelty of the contributions paper.
Be extremely critical. Spot the unspottable, but do not invent anything.

=====
google-search: false

Please, check if the paper is well written, if the language is clear and concise, and if it follows the conventions of scientific writing. Look for any spelling or grammatical errors, and check if the paper uses appropriate terminology and style.

====
Please, write a short summary of the paper, including its main contributions and findings. The
summary should be concise and to the point.

```json
{
  "type": "object",
  "properties": {
    "research questions": {
      "type": "string",
      "description": "The research questions addressed by the paper"
    },
    "innovation": {
      "type": "string",
      "description": "The innovative aspects of the paper compared to the state of the art"
    },
    "methods": {
      "type": "string",
      "description": "A two-sentence summary of the methods used in the paper, highlighting the innovative aspects, if any"
    },
    "results": {
      "type": "string",
      "description": "A two-sentence summary of the results obtained in the paper"
    },
    "takeaway": {
      "type": "string",
      "description": "A two-sentence summary of the main takeaways from the paper, including the implications of the results and their relevance to the field"
    }
  },
  "required": [
    "research questions",
    "innovation",
    "methods",
    "results",
    "takeaway"
  ]
}
```
