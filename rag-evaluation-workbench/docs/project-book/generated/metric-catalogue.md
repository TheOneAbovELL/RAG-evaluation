# Metric catalogue

From `rag_workbench.metrics.METRIC_SPECS`.

| Name | Label | Family | Default threshold | Needs reference | Needs context | Needs OpenAI | Description |
|---|---|---|---:|---|---|---|---|
| `exact_match` | Exact match | lexical | 1.0 | yes | no | no | Normalised answer string equals the reference |
| `token_f1` | Token F1 | lexical | 0.5 | yes | no | no | SQuAD token-overlap F1 between answer and reference |
| `rouge_l` | ROUGE-L | lexical | 0.5 | yes | no | no | Longest-common-subsequence F1 between answer and reference |
| `context_recall` | Context recall (lexical) | lexical | 0.7 | yes | yes | no | Share of reference terms present in the retrieved context |
| `groundedness` | Groundedness (lexical) | lexical | 0.7 | no | yes | no | Share of answer terms present in the retrieved context |
| `semantic_similarity` | Semantic similarity (local model) | semantic | 0.7 | yes | no | no | Embedding cosine similarity between answer and reference (optional, needs fastembed) |
| `semantic_context_recall` | Semantic context recall (local model) | semantic | 0.7 | yes | yes | no | Best embedding similarity between the reference and any retrieved chunk (optional, needs fastembed) |
| `answer_relevancy` | Answer relevancy (judge) | llm_judge | 0.7 | no | no | yes | Share of answer statements the judge considers relevant to the question (DeepEval AnswerRelevancyMetric) |
| `faithfulness` | Faithfulness (judge) | llm_judge | 0.7 | no | yes | yes | Share of answer claims the judge finds supported by the retrieved context (DeepEval FaithfulnessMetric) |
| `context_relevancy` | Context relevancy (judge) | llm_judge | 0.7 | no | yes | yes | Share of retrieved-context statements the judge considers relevant to the question (DeepEval ContextualRelevancyMetric) |
| `correctness` | Correctness (judge) | llm_judge | 0.7 | yes | no | yes | GEval rubric score of factual agreement between answer and reference |
