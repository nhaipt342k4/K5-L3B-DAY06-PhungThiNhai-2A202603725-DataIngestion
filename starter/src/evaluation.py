"""Automatic retrieval metrics + per-query traces. Manual labels are kept separately."""
import re
import unicodedata
from typing import Any


def key(text: str) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", text)).strip().casefold()


def _is_hit(question: dict[str, Any], hit: dict[str, Any]) -> bool:
    """Gold source + one of the gold pages + the FULL evidence quote (or a documented alternative)."""
    meta = hit["metadata"]
    if meta.get("document_id") != question["gold_source_id"] or hit["page"] not in question["gold_pages"]:
        return False
    quotes = [question["evidence_quote"], *question.get("alternative_evidence", [])]
    text = key(hit["text"])
    return any(key(q) in text for q in quotes)


def _complies(filters: dict | None, hit: dict[str, Any]) -> bool:
    return all(hit["metadata"].get(k) == v for k, v in (filters or {}).items())


def evaluate_query(question: dict[str, Any], hits: list[dict[str, Any]],
                   applied_filter: dict | None) -> dict[str, Any]:
    flags = [_is_hit(question, h) for h in hits]
    return {
        "id": question["id"], "split": question["split"], "type": question.get("type"),
        "question": question["question"], "gold_pages": question["gold_pages"],
        "evidence_quote": question["evidence_quote"], "applied_filter": applied_filter,
        "hit_at_1": bool(flags[:1] and flags[0]), "hit_at_3": any(flags[:3]),
        "gold_page_in_top3": any(h["page"] in question["gold_pages"] for h in hits[:3]),
        "filter_compliant": all(_complies(question.get("filter"), h) for h in hits[:3])
        if question.get("filter") else None,
        "hits": [{**h, "is_hit": f} for h, f in zip(hits, flags)],
    }


def summarize(traces: list[dict[str, Any]]) -> dict[str, Any]:
    """Hit@1 / Evidence Hit@3 as n/N per strategy and split."""
    out: dict[str, Any] = {}
    for t in traces:
        cell = out.setdefault(t["strategy"], {}).setdefault(t["split"], {
            "N": 0, "hit_at_1": 0, "hit_at_3": 0, "gold_page_in_top3": 0,
            "filter_questions": 0, "filter_compliant": 0})
        cell["N"] += 1
        cell["hit_at_1"] += t["hit_at_1"]
        cell["hit_at_3"] += t["hit_at_3"]
        cell["gold_page_in_top3"] += t["gold_page_in_top3"]
        if t["filter_compliant"] is not None:
            cell["filter_questions"] += 1
            cell["filter_compliant"] += t["filter_compliant"]
    return out
