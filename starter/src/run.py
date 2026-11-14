"""Day 06 pipeline entry point.

Run from starter/ (venv active):
    python -m src.run index                 # chunk A/B, embed, store, re-ingest check
    python -m src.run evaluate --split dev  # needs benchmark status != DRAFT
    python -m src.run select                # apply the pre-registered criterion to dev metrics
    python -m src.run evaluate --split test # only after select
    python -m src.run audit                 # CSV templates for manual coherence/metadata/grounding labels
    # Post-hoc improvement D (designed after reading test errors):
    python -m src.run evaluate --split dev --strategies D
    python -m src.run evaluate --split test2              # new frozen test set, all strategies
    python -m src.run evaluate --split test --strategies D  # labelled __posthoc, not independent
"""
import argparse
import csv
import json
import statistics
import sys
import time
from datetime import datetime
from pathlib import Path

from .chunking import by_paragraph, by_paragraph_ctx, collapse, fixed_size
from .embeddings import MyEmbedder
from .evaluation import evaluate_query, key, summarize
from .ingestion import CONTENT_PAGES, load_pdf
from .store import ChromaStore

STARTER = Path(__file__).resolve().parents[1]
ROOT = STARTER.parent
PDF = STARTER / "data" / "Datio_English_Grammar_Foundation_30_Days.pdf"
DOC_ID = "datio-grammar-30d"
RESULTS = STARTER / "results"
CHROMA_PATH = STARTER / "chroma_db"
MODEL = "intfloat/multilingual-e5-small"
TOP_K = 3

# Strategy -> (index name, chunker, uses metadata filter). C reuses B's index: only filtering differs.
STRATEGIES = {
    "A": {"index": "A_fixed500", "chunking": "fixed_size(size=500, overlap=50)", "filter": False},
    "B": {"index": "B_para800", "chunking": "by_paragraph(max_size=800)", "filter": False},
    "C": {"index": "B_para800", "chunking": "by_paragraph(max_size=800)", "filter": True},
    # Post-hoc improvement designed AFTER inspecting test errors (t04, t05): evaluate on test2.
    "D": {"index": "D_ctx800", "chunking": "by_paragraph_ctx(max_size=800): header + answer key split per NGÀY",
          "filter": True},
}
ORIGINAL = ("A", "B", "C")  # strategies whose selection criterion was fixed before any test run
CHUNKERS = {
    "A_fixed500": lambda p: fixed_size(p, 500, 50),
    "B_para800": lambda p: by_paragraph(p, 800),
    "D_ctx800": lambda p: by_paragraph_ctx(p, 800),
}
BENCHMARK_FILES = {"dev": "questions.json", "test": "questions.json", "test2": "questions_test2.json"}


def load_pages():
    if not PDF.exists():
        sys.exit(f"Missing corpus {PDF}; see data/manifest.json.")
    pages, log = load_pdf(PDF, DOC_ID, PDF.name, CONTENT_PAGES)
    if len(pages) < 30:
        sys.exit(f"Only {len(pages)} content pages (<30).")
    return pages, log


def cmd_index(_args) -> None:
    pages, log = load_pages()
    embedder = MyEmbedder(MODEL)
    store = ChromaStore(str(CHROMA_PATH), embedder.dimensions)
    stats = {"run_at": datetime.now().isoformat(timespec="seconds"), "model": MODEL,
             "dimensions": embedder.dimensions, "max_seq_length": embedder.max_seq_length,
             "pages": len(pages), "ingestion_log": log, "indexes": {}}
    for index, chunker in CHUNKERS.items():
        chunks = [c for p in pages for c in chunker(p)]
        lengths = [len(c.text) for c in chunks]
        tokens = [embedder.token_count(c.text) for c in chunks]
        t0 = time.perf_counter()
        vectors = embedder.embed_documents([c.text for c in chunks])
        embed_s = time.perf_counter() - t0
        first = store.upsert(index, chunks, vectors)
        second = store.upsert(index, chunks, vectors)  # re-ingest same version: must not grow
        stats["indexes"][index] = {
            "chunks": len(chunks), "total_chars": sum(lengths),
            "chars_min_median_mean_max": [min(lengths), statistics.median(lengths),
                                          round(statistics.mean(lengths), 1), max(lengths)],
            "tokens_total": sum(tokens), "tokens_max": max(tokens),
            "chunks_truncated": sum(t > embedder.max_seq_length for t in tokens),
            "embed_seconds": round(embed_s, 2), "cost_usd": 0,
            "first_upsert": first, "reingest_upsert": second,
            "reingest_no_duplicates": first["count_after"] == second["count_after"] == len(chunks),
        }
        print(index, stats["indexes"][index])
    RESULTS.mkdir(exist_ok=True)
    (RESULTS / "index_stats.json").write_text(json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8")


def load_benchmark(split: str = "dev") -> dict:
    bench = json.loads((ROOT / "benchmark" / BENCHMARK_FILES[split]).read_text(encoding="utf-8"))
    if str(bench.get("status", "")).upper().startswith("DRAFT"):
        sys.exit("Benchmark is still DRAFT: verify evidence, fix the split, then set status to 'frozen'.")
    return bench


def cmd_evaluate(args) -> None:
    bench = load_benchmark(args.split)
    if args.split == "test":
        sel_path = RESULTS / "selection.json"
        sel = json.loads(sel_path.read_text(encoding="utf-8")) if sel_path.exists() else {}
        if not sel.get("chosen_strategy"):
            sys.exit("Run 'evaluate --split dev' then 'select' before running test.")
    names = args.strategies.split(",") if args.strategies else list(STRATEGIES)
    unknown = [n for n in names if n not in STRATEGIES]
    if unknown:
        sys.exit(f"Unknown strategies: {unknown}")
    # A subset run (e.g. post-hoc D on the original test) never overwrites the main results.
    tag = args.split if not args.strategies else f"{args.split}__{'_'.join(names)}"
    if args.split == "test" and "D" in names:
        tag += "__posthoc"
    questions = [q for q in bench["questions"] if q["split"] == args.split]
    embedder = MyEmbedder(MODEL)
    store = ChromaStore(str(CHROMA_PATH), embedder.dimensions)
    traces = []
    for q in questions:
        qvec = embedder.embed_query(q["question"])
        for name in names:
            cfg = STRATEGIES[name]
            applied = q.get("filter") if cfg["filter"] else None
            t0 = time.perf_counter()
            hits = store.search(cfg["index"], qvec, TOP_K, applied)
            trace = evaluate_query(q, hits, applied)
            trace.update(strategy=name, index=cfg["index"], latency_ms=round((time.perf_counter() - t0) * 1000, 1))
            traces.append(trace)
    RESULTS.mkdir(exist_ok=True)
    with open(RESULTS / f"traces_{tag}.jsonl", "w", encoding="utf-8") as f:
        for t in traces:
            f.write(json.dumps(t, ensure_ascii=False) + "\n")
    metrics_path = RESULTS / "metrics.json"
    metrics = json.loads(metrics_path.read_text(encoding="utf-8")) if metrics_path.exists() else {}
    metrics[tag] = {"run_at": datetime.now().isoformat(timespec="seconds"), "model": MODEL,
                    "top_k": TOP_K, "strategies": names, "summary": summarize(traces)}
    if tag.endswith("__posthoc"):
        metrics[tag]["note"] = "Post-hoc: D was designed after inspecting these test errors; not an independent holdout."
    metrics_path.write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[{tag}]")
    for name, splits in metrics[tag]["summary"].items():
        c = splits[args.split]
        print(f"{name} {args.split}: Hit@1 {c['hit_at_1']}/{c['N']}  Evidence Hit@3 {c['hit_at_3']}/{c['N']}  "
              f"filter {c['filter_compliant']}/{c['filter_questions']}")


def cmd_select(_args) -> None:
    """Apply the criterion fixed in results/selection.json to dev metrics only."""
    sel_path = RESULTS / "selection.json"
    sel = json.loads(sel_path.read_text(encoding="utf-8"))
    metrics = json.loads((RESULTS / "metrics.json").read_text(encoding="utf-8"))
    if "dev" not in metrics:
        sys.exit("Run 'evaluate --split dev' first.")
    stats = json.loads((RESULTS / "index_stats.json").read_text(encoding="utf-8"))["indexes"]
    summary = metrics["dev"]["summary"]
    ranking = sorted(
        ORIGINAL,
        key=lambda s: (-summary[s]["dev"]["hit_at_3"], -summary[s]["dev"]["hit_at_1"],
                       stats[STRATEGIES[s]["index"]]["chunks"]),
    )
    sel.update(chosen_strategy=ranking[0], ranking=ranking,
               dev_scores={s: summary[s]["dev"] for s in ORIGINAL},
               selected_at=datetime.now().isoformat(timespec="seconds"))
    sel_path.write_text(json.dumps(sel, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Ranking on dev: {ranking} -> chosen {ranking[0]}")


def cmd_audit(_args) -> None:
    """Templates for manual labels. Positions are fixed BEFORE looking at scores."""
    pages, _ = load_pages()
    store = ChromaStore(str(CHROMA_PATH), 0)
    rows = []
    # Coherence: first 10 counted pages (sorted page IDs); anchor = 40 chars at the middle of the page.
    for page in pages[:10]:
        text = collapse(page.text)
        mid = len(text) // 2
        anchor = text[mid: mid + 40]
        for name in ("A", "B", "C"):
            index = STRATEGIES[name]["index"]
            got = store._collection(index).get(where={"page": page.page}, include=["documents"])
            match = next(((cid, doc) for cid, doc in zip(got["ids"], got["documents"])
                          if key(anchor[:20]) in key(doc)), ("NOT_FOUND", ""))
            rows.append({"position": f"p{page.page:02d}@{mid}", "anchor": anchor, "strategy": name,
                         "chunk_id": match[0], "chunk_text": match[1], "score_0_2": "", "reason": ""})
    RESULTS.mkdir(exist_ok=True)
    _write_csv(RESULTS / "audit_coherence.csv", rows)

    test_path = RESULTS / "traces_test.jsonl"
    if not test_path.exists():
        print("audit_coherence.csv written; run evaluate --split test before metadata/grounding templates.")
        return
    traces = [json.loads(line) for line in test_path.read_text(encoding="utf-8").splitlines()]
    meta_rows, ground_rows = [], []
    for t in traces:
        row = {"strategy": t["strategy"], "id": t["id"], "question": t["question"],
               "expected_answer": next(q["expected_answer"] for q in load_benchmark()["questions"]
                                       if q["id"] == t["id"]),
               "applied_filter": json.dumps(t["applied_filter"], ensure_ascii=False) if t["applied_filter"] else ""}
        for h in t["hits"]:
            row[f"top{h['rank']}"] = f"[{h['chunk_id']}] {h['text']}"
        ground_rows.append({**row, "grounding_0_2": "", "reason": ""})
        for h in t["hits"]:
            m = h["metadata"]
            meta_rows.append({"strategy": t["strategy"], "id": t["id"], "rank": h["rank"],
                              "chunk_id": h["chunk_id"], "source": m.get("source"), "page": m.get("page"),
                              "page_type": m.get("page_type"), "week": m.get("week", ""),
                              "day_start": m.get("day_start", ""), "text_preview": h["text"][:160],
                              "metadata_correct_Y_N": "", "error_note": ""})
    _write_csv(RESULTS / "audit_metadata.csv", meta_rows)
    _write_csv(RESULTS / "audit_grounding.csv", ground_rows)
    print("audit_coherence.csv, audit_metadata.csv, audit_grounding.csv written.")


LABEL_COLUMNS = ("score_0_2", "metadata_correct_Y_N", "grounding_0_2")


def _write_csv(path: Path, rows: list[dict]) -> None:
    if path.exists():
        with open(path, encoding="utf-8-sig") as f:
            if any(r.get(c) for r in csv.DictReader(f) for c in LABEL_COLUMNS):
                print(f"SKIP {path.name}: already contains manual labels (delete it to regenerate).")
                return
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("index")
    ev = sub.add_parser("evaluate")
    ev.add_argument("--split", choices=["dev", "test", "test2"], required=True)
    ev.add_argument("--strategies", help="comma list, e.g. D; subset runs are saved under a separate tag")
    sub.add_parser("select")
    sub.add_parser("audit")
    args = parser.parse_args()
    {"index": cmd_index, "evaluate": cmd_evaluate, "select": cmd_select, "audit": cmd_audit}[args.cmd](args)


if __name__ == "__main__":
    main()
