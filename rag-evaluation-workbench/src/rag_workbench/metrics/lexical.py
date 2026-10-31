"""Offline, deterministic lexical metrics.

These metrics measure *surface overlap*, not meaning. They are cheap, reproducible and need no
network, which makes them useful as regression signals and sanity checks, but a paraphrased
correct answer can score low and a fluent wrong answer that reuses the reference's words can
score high. See the project book, Part VI, for formulas and failure modes.
"""

from __future__ import annotations

from collections import Counter

from ..text import content_tokens, is_abstention, squad_normalize
from .base import Metric, MetricInput, MetricSkipped, MetricSpec


def exact_match(inp: MetricInput) -> tuple[float, str]:
    """1.0 when the SQuAD-normalised answer equals the normalised reference."""
    equal = squad_normalize(inp.answer) == squad_normalize(inp.expected_answer or "")
    return (1.0 if equal else 0.0), ("normalised strings are identical" if equal else "normalised strings differ")


def token_f1(inp: MetricInput) -> tuple[float, str]:
    """SQuAD token-level F1 between answer and reference (multiset overlap of normalised tokens)."""
    pred = squad_normalize(inp.answer).split()
    gold = squad_normalize(inp.expected_answer or "").split()
    if not pred or not gold:
        return 0.0, "answer or reference is empty after normalisation"
    common = Counter(pred) & Counter(gold)
    overlap = sum(common.values())
    if overlap == 0:
        return 0.0, "no shared tokens"
    precision = overlap / len(pred)
    recall = overlap / len(gold)
    f1 = 2 * precision * recall / (precision + recall)
    return f1, f"precision {precision:.2f}, recall {recall:.2f} ({overlap} shared tokens)"


def _lcs_length(a: list[str], b: list[str]) -> int:
    # O(len(a) * len(b)) dynamic programme with a single rolling row.
    if not a or not b:
        return 0
    prev = [0] * (len(b) + 1)
    for x in a:
        curr = [0]
        for j, y in enumerate(b, start=1):
            curr.append(prev[j - 1] + 1 if x == y else max(prev[j], curr[j - 1]))
        prev = curr
    return prev[-1]


def rouge_l(inp: MetricInput) -> tuple[float, str]:
    """ROUGE-L F1 (Lin, 2004): longest common subsequence of normalised tokens."""
    pred = squad_normalize(inp.answer).split()
    gold = squad_normalize(inp.expected_answer or "").split()
    lcs = _lcs_length(pred, gold)
    if lcs == 0:
        return 0.0, "no common subsequence"
    precision, recall = lcs / len(pred), lcs / len(gold)
    return 2 * precision * recall / (precision + recall), f"LCS {lcs} tokens; P {precision:.2f}, R {recall:.2f}"


def context_recall(inp: MetricInput) -> tuple[float, str]:
    """Share of the reference answer's distinct content terms that appear in the retrieved context.

    A retrieval-quality proxy: if the reference's key terms are absent from the context, the
    generator could not have produced the reference answer from it.
    """
    if is_abstention(inp.expected_answer or ""):
        # An unanswerable case: the reference's words ("not enough information") say nothing about retrieval.
        raise MetricSkipped("reference answer is an abstention (unanswerable case)")
    gold = set(content_tokens(inp.expected_answer or ""))
    if not gold:
        raise MetricSkipped("reference answer has no content terms")
    ctx = set(content_tokens(" ".join(inp.contexts)))
    found = gold & ctx
    missing = sorted(gold - ctx)
    reason = f"{len(found)}/{len(gold)} reference terms found in context"
    if missing:
        reason += f"; missing: {', '.join(missing[:8])}"
    return len(found) / len(gold), reason


def groundedness(inp: MetricInput) -> tuple[float, str]:
    """Share of the answer's distinct content terms that appear in the retrieved context.

    A lexical faithfulness proxy: unsupported terms suggest content not drawn from the context.
    Abstentions are skipped because they make no claim to ground.
    """
    if is_abstention(inp.answer):
        raise MetricSkipped("answer abstained; nothing to ground")
    terms = set(content_tokens(inp.answer))
    if not terms:
        raise MetricSkipped("answer has no content terms")
    ctx = set(content_tokens(" ".join(inp.contexts)))
    unsupported = sorted(terms - ctx)
    reason = f"{len(terms) - len(unsupported)}/{len(terms)} answer terms found in context"
    if unsupported:
        reason += f"; unsupported: {', '.join(unsupported[:8])}"
    return (len(terms) - len(unsupported)) / len(terms), reason


LEXICAL_METRICS: dict[str, Metric] = {
    m.name: m
    for m in (
        Metric(MetricSpec("exact_match", "Exact match", "lexical",
                          "Normalised answer string equals the reference", 1.0, requires_reference=True), exact_match),
        Metric(MetricSpec("token_f1", "Token F1", "lexical",
                          "SQuAD token-overlap F1 between answer and reference", 0.5,
                          requires_reference=True), token_f1),
        Metric(MetricSpec("rouge_l", "ROUGE-L", "lexical",
                          "Longest-common-subsequence F1 between answer and reference", 0.5,
                          requires_reference=True), rouge_l),
        Metric(MetricSpec("context_recall", "Context recall (lexical)", "lexical",
                          "Share of reference terms present in the retrieved context", 0.7,
                          requires_reference=True, requires_context=True), context_recall),
        Metric(MetricSpec("groundedness", "Groundedness (lexical)", "lexical",
                          "Share of answer terms present in the retrieved context", 0.7,
                          requires_context=True), groundedness),
    )
}
