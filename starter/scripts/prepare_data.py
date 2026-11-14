"""Build data/manifest.json, the ingestion log, and verify benchmark evidence.

Run from starter/:  python -m scripts.prepare_data
"""
import json
import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STARTER = ROOT / "starter"
sys.path.insert(0, str(STARTER))

from src.ingestion import CONTENT_PAGES, EXCLUDED_PAGES, load_pdf  # noqa: E402

PDF = STARTER / "data" / "Datio_English_Grammar_Foundation_30_Days.pdf"
DOC_ID = "datio-grammar-30d"


def key(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().casefold()


def main() -> None:
    if not PDF.exists():
        sys.exit(f"Missing corpus: {PDF}. See data/manifest.json for how to obtain it.")
    pages, log = load_pdf(PDF, DOC_ID, PDF.name, CONTENT_PAGES)
    all_pages, _ = load_pdf(PDF, DOC_ID, PDF.name)

    manifest = {
        "source_id": DOC_ID,
        "title": "Xây nền ngữ pháp trong 30 ngày (30-Day Grammar Foundation Workbook)",
        "publisher": "Datio English",
        "source_path_or_url": "https://ieltsdatio.edu.vn (tài liệu tự học miễn phí); bản local: starter/data/Datio_English_Grammar_Foundation_30_Days.pdf",
        "how_to_obtain": "Tải file 'Datio_English_Grammar_Foundation_30_Days.pdf' từ ieltsdatio.edu.vn, đặt vào starter/data/.",
        "license_or_permission": "Tài liệu tự học phát miễn phí của Datio English; không ghi giấy phép tái phân phối. Chỉ dùng cho bài tập học thuật, xử lý local (không gửi API), KHÔNG commit PDF vào repo.",
        "accessed_at": "2026-11-14 (theo thời điểm tạo file trong thư mục Downloads)",
        "manifest_generated_at": date.today().isoformat(),
        "physical_pages": len(all_pages) + len([e for e in log if e["status"] != "warning"]),
        "page_counting_rule": "Đếm trang PDF vật lý có nội dung ngữ pháp/bài tập/đáp án. Loại bìa, quảng cáo, trang hướng dẫn cách học và bản đồ 30 ngày (tương đương mục lục). Số trang in ở chân trang = trang PDF - 1.",
        "counted_pages": len(pages),
        "excluded_pages": [{"page": p, "reason": r} for p, r in EXCLUDED_PAGES.items()],
        "pages": [
            {"page_id": f"{DOC_ID}:p{p.page:02d}", "page": p.page,
             "char_count": len(p.text), **p.metadata}
            for p in pages
        ],
        "total_chars": sum(len(p.text) for p in pages),
        "ingestion_log": log,
    }
    (ROOT / "data" / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"manifest: {len(pages)} counted pages, {manifest['total_chars']} chars, log={log}")

    questions = []
    for name in ("questions.json", "questions_test2.json"):
        path = ROOT / "benchmark" / name
        if path.exists():
            questions += json.loads(path.read_text(encoding="utf-8"))["questions"]
    report, problems = [], 0
    by_page = {p.page: key(p.text) for p in pages}
    for q in questions:
        quote = key(q["evidence_quote"])
        found = sorted(n for n, text in by_page.items() if quote in text)
        missing = [g for g in q["gold_pages"] if g not in found]
        extra = [n for n in found if n not in q["gold_pages"]]
        ok = q["gold_page"] in found and not missing
        problems += not ok
        report.append({"id": q["id"], "split": q["split"], "ok": ok, "found_on_pages": found,
                       "gold_pages_missing_quote": missing, "pages_with_quote_not_in_gold": extra})
        flag = "OK " if ok else "ERR"
        print(f"{flag} {q['id']} gold={q['gold_pages']} found={found}" + (f" extra={extra}" if extra else ""))
    split_names = ("dev", "test", "test2")
    splits = {s: sum(q["split"] == s for q in questions) for s in split_names}
    filters = {s: sum(bool(q["filter"]) and q["split"] == s for q in questions) for s in split_names}
    print(f"split={splits} filter_questions={filters} problems={problems}")
    out = STARTER / "results"
    out.mkdir(exist_ok=True)
    (out / "evidence_verification.json").write_text(
        json.dumps({"splits": splits, "filters": filters, "report": report}, ensure_ascii=False, indent=2),
        encoding="utf-8")


if __name__ == "__main__":
    main()
