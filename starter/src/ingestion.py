"""Read and normalize the Datio workbook PDF, keeping page-level traceability."""
import logging
import re
import unicodedata
from pathlib import Path

from pypdf import PdfReader

# The workbook PDF has harmless broken xref offsets; pypdf repairs them but logs
# "Ignoring wrong pointing object" per object. Keep real errors only.
logging.getLogger("pypdf").setLevel(logging.ERROR)

from .models import DocumentPage

# Footer printed on every page; everything after it is the page header that
# pypdf emits last because of the layout.
FOOTER_RE = re.compile(r"Datio English\s*[|·][^\n]*ieltsdatio\.edu\.vn[^\n]*$", re.MULTILINE)
PRINTED_PAGE_RE = re.compile(r"(\d{2})\s*$")

# Physical PDF pages counted as content (see data/manifest.json for the rule).
CONTENT_PAGES = list(range(5, 45))
EXCLUDED_PAGES = {
    1: "bìa",
    2: "quảng cáo placement test",
    3: "hướng dẫn cách học (front matter)",
    4: "bản đồ 30 ngày (tương đương mục lục)",
    45: "quảng cáo placement test (lặp trang 2)",
    46: "quảng cáo TestLab",
    47: "quảng cáo khóa học / liên hệ",
}


def normalize_text(text: str) -> str:
    """NFKC (also expands ligatures such as 'ﬁ'), unify whitespace, keep line breaks."""
    text = unicodedata.normalize("NFKC", text)
    text = text.replace(" ", " ").replace("​", "")
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.splitlines()]
    return "\n".join(line for line in lines if line)


def _move_header_to_top(text: str) -> tuple[str, int | None]:
    """Drop the footer line, put the header lines that follow it at the top."""
    match = FOOTER_RE.search(text)
    if not match:
        return text, None
    printed = PRINTED_PAGE_RE.search(match.group(0))
    body = text[: match.start()].strip()
    header = text[match.end():].strip()
    return (f"{header}\n{body}" if header else body), (int(printed.group(1)) if printed else None)


def extract_metadata(text: str) -> dict:
    """Derive filter metadata only from labels printed on the page."""
    meta: dict = {}
    head = text[:400]
    if m := re.search(r"NGÀY (\d{2}) • TUẦN (\d)", head):
        meta.update(page_type="lesson", day_start=int(m[1]), day_end=int(m[1]), week=int(m[2]))
    elif m := re.search(r"Đáp án & giải thích ngày (\d{2})-(\d{2})", text):
        meta.update(page_type="answer_key", day_start=int(m[1]), day_end=int(m[2]))
    elif m := re.search(r"NGÀY (\d{2}) / 30", head):
        day = int(m[1])
        meta.update(day_start=day, day_end=day)
        if w := re.search(r"Mini Test tuần (\d)", head):
            meta.update(page_type="mini_test", week=int(w[1]))
        elif w := re.search(r"ÔN TẬP TUẦN (\d)", head):
            meta.update(page_type="review", week=int(w[1]))
        elif "ERROR CLINIC" in head:
            meta["page_type"] = "error_clinic"
        elif "Final Check" in head:
            meta["page_type"] = "final_test"
    elif "Grammar Cheat Sheet" in head:
        meta["page_type"] = "appendix"
    lines = text.splitlines()
    for i, line in enumerate(lines[:-1]):
        if re.match(r"NGÀY \d{2} • TUẦN \d$", line):
            meta["title"] = lines[i + 1]
            break
    return meta


def load_pdf(path: Path, document_id: str, source: str,
             pages: list[int] | None = None) -> tuple[list[DocumentPage], list[dict]]:
    """Extract each physical page (1-based) with source/page; log empty or failed pages."""
    reader = PdfReader(str(path))
    wanted = pages or list(range(1, len(reader.pages) + 1))
    result, log = [], []
    for number in wanted:
        try:
            raw = reader.pages[number - 1].extract_text() or ""
        except Exception as exc:  # keep going, but record the failure
            log.append({"page": number, "status": "error", "detail": repr(exc)})
            continue
        text, printed = _move_header_to_top(normalize_text(raw))
        if not text.strip():
            log.append({"page": number, "status": "empty", "detail": "no extractable text; OCR needed"})
            continue
        meta = extract_metadata(text)
        meta["printed_page"] = printed
        if "page_type" not in meta:
            log.append({"page": number, "status": "warning", "detail": "page_type not detected"})
        result.append(DocumentPage(document_id, source, number, text, meta))
    return result, log
