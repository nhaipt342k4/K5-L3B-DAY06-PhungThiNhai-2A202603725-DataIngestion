"""Fixed-size (strategy A) and structure-aware (strategy B/C) chunking."""
import re

from .models import Chunk, DocumentPage

# Labels that start a new logical block in this workbook.
HEADING_PREFIXES = (
    "Mục tiêu:", "PHÁT ÂM:", "HIỂU SÂU HƠN:", "CÔNG THỨC", "Giải thích trọng tâm:",
    "CÂU 13-20", "Checklist", "Tự chấm & học lại", "HỌC LẠI:", "Mini Test - 20 câu",
    "Error Clinic", "Error Log", "Quy trình chọn", "SAU KHI CHẤM", "20 động từ",
    "Chủ điểm", "Đọc kết quả", "Sai đâu", "Bài kiểm tra", "Cách tự sửa", "Mẹo học:",
    "Trang này gồm:", "Câu 1-12 là phần",
)


def collapse(text: str) -> str:
    """Single-line view used for fixed windows and evidence matching."""
    return re.sub(r"\s+", " ", text).strip()


def _chunk(page: DocumentPage, kind: str, index: int, text: str, **extra) -> Chunk:
    meta = dict(page.metadata, chunk_index=index, char_count=len(text), **extra)
    chunk_id = f"{page.document_id}:p{page.page:02d}:{kind}{index:02d}"
    return Chunk(chunk_id, page.document_id, page.source, page.page, text, meta)


def fixed_size(page: DocumentPage, size: int, overlap: int) -> list[Chunk]:
    """Overlapping character windows over the whitespace-collapsed page text."""
    if not 0 <= overlap < size:
        raise ValueError("overlap must be in [0, size)")
    text = collapse(page.text)
    chunks, start, index = [], 0, 0
    while start < len(text):
        end = min(start + size, len(text))
        chunks.append(_chunk(page, "f", index, text[start:end], char_start=start))
        if end == len(text):
            break
        start, index = end - overlap, index + 1
    return chunks


def is_heading(line: str) -> bool:
    if re.match(r"NGÀY \d{2}\b", line) or line.startswith(HEADING_PREFIXES):
        return True
    if re.match(r"^\d ?[A-ZÀ-ỸĐ][a-zà-ỹđ]", line):  # Grammar Map items: "1 Câu hoàn chỉnh"
        return True
    letters = [c for c in line if c.isalpha()]
    return len(letters) >= 4 and all(c.isupper() for c in letters)


def split_blocks(text: str) -> list[str]:
    """Start a new block at each heading; join wrapped lines inside a block."""
    blocks: list[list[str]] = []
    for line in text.splitlines():
        if not blocks or is_heading(line):
            blocks.append([line])
        else:
            blocks[-1].append(line)
    return [collapse(" ".join(b)) for b in blocks]


def _split_long(block: str, max_size: int) -> list[str]:
    """Split an oversized block at sentence ends, hard-cut only as a last resort."""
    sentences = re.split(r"(?<=[.?!])\s+", block)
    parts, current = [], ""
    for sentence in sentences:
        while len(sentence) > max_size:
            if current:
                parts.append(current)
                current = ""
            parts.append(sentence[:max_size])
            sentence = sentence[max_size:]
        if current and len(current) + 1 + len(sentence) > max_size:
            parts.append(current)
            current = sentence
        else:
            current = f"{current} {sentence}".strip()
    if current:
        parts.append(current)
    return parts


def by_paragraph(page: DocumentPage, max_size: int) -> list[Chunk]:
    """Group heading-delimited blocks up to max_size; split oversized blocks."""
    return [_chunk(page, "p", i, text) for i, text in enumerate(_pack(split_blocks(page.text), max_size))]


PAGE_TYPE_LABEL = {
    "lesson": "Bài học", "review": "Ôn tập", "mini_test": "Mini Test", "error_clinic": "Error Clinic",
    "final_test": "Final Check", "answer_key": "Đáp án", "appendix": "Phụ lục",
}
DAY_BLOCK_RE = re.compile(r"^NGÀY (\d{2})\b")


def context_header(meta: dict) -> str:
    """Breadcrumb built only from metadata extracted from printed page labels."""
    parts = []
    if meta.get("week"):
        parts.append(f"Tuần {meta['week']}")
    if meta.get("day_start"):
        a, b = meta["day_start"], meta["day_end"]
        parts.append(f"Ngày {a:02d}" if a == b else f"Ngày {a:02d}-{b:02d}")
    if meta.get("page_type"):
        parts.append(PAGE_TYPE_LABEL.get(meta["page_type"], meta["page_type"]))
    if meta.get("title"):
        parts.append(meta["title"])
    return f"[{' | '.join(parts)}]" if parts else ""


def by_paragraph_ctx(page: DocumentPage, max_size: int) -> list[Chunk]:
    """Strategy D: like by_paragraph, but (1) answer-key pages never merge blocks of
    different 'NGÀY xx' sections and each chunk gets that day as day_start/day_end;
    (2) every chunk text starts with a context header '[Tuần | Ngày | Loại trang | Tên bài]'."""
    blocks = split_blocks(page.text)
    segments: list[tuple[int | None, list[str]]] = [(None, [])]
    for block in blocks:
        m = DAY_BLOCK_RE.match(block)
        if page.metadata.get("page_type") == "answer_key" and m:
            segments.append((int(m[1]), [block]))
        else:
            segments[-1][1].append(block)
    chunks, index = [], 0
    for day, seg_blocks in segments:
        if not seg_blocks:
            continue
        meta = dict(page.metadata)
        if day is not None:
            meta.update(day_start=day, day_end=day)
        header = context_header(meta)
        for body in _pack(seg_blocks, max_size):
            text = f"{header} {body}".strip()
            chunk = _chunk(page, "c", index, text, context_header=header)
            chunk.metadata.update({k: meta[k] for k in ("day_start", "day_end") if k in meta})
            chunks.append(chunk)
            index += 1
    return chunks


def _pack(blocks: list[str], max_size: int) -> list[str]:
    """Greedy packing of blocks up to max_size characters."""
    pieces: list[str] = []
    current = ""
    for block in blocks:
        if len(block) > max_size:
            if current:
                pieces.append(current)
                current = ""
            *full, current = _split_long(block, max_size)
            pieces.extend(full)
        elif current and len(current) + 1 + len(block) > max_size:
            pieces.append(current)
            current = block
        else:
            current = f"{current} {block}".strip()
    if current:
        pieces.append(current)
    return pieces
