"""Structure-aware parent/child chunking for SOPs and controlled projections for reports."""
import re
from collections.abc import Callable
from dataclasses import dataclass, field

from psit.domain.models import Report

SOP_TARGET, SOP_OVERLAP = 350, 50
REPORT_TARGET, REPORT_OVERLAP = 220, 30

_HEADING = re.compile(r"^(#{1,6})\s+(.+)$")
_NUMBERED = re.compile(r"^(\d+(?:\.\d+)*)\.?\s+([A-Z][^\n]{0,90}[^.\s:])$")  # headings never end with '.'
_ATTACH = re.compile(r"^(WARNING|CAUTION|NOTE|EXCEPTION|IMPORTANT)\b", re.I)
_META_LINE = re.compile(r"^(Version|Effective(?: Date)?|Status|Owner)\s*:", re.I)
_SENT = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9(\"'])")


@dataclass
class ChunkDraft:
    chunk_id: str
    parent_id: str
    text: str
    section_path: str | None
    page_number: int | None
    sequence: int
    meta: dict = field(default_factory=dict)


def split_sentences(text: str) -> list[str]:
    return [s.strip() for s in _SENT.split(text) if s.strip()]


def _hard_split(s: str, count: Callable[[str], int], target: int) -> list[str]:
    words, out, cur = s.split(), [], []
    for w in words:
        cur.append(w)
        if count(" ".join(cur)) >= target:
            out.append(" ".join(cur))
            cur = []
    if cur:
        out.append(" ".join(cur))
    return out


def pack(units: list[str], count: Callable[[str], int], target: int, overlap: int) -> list[str]:
    """Greedy sentence-aware packing with token overlap. Units that fit are kept atomic
    (e.g. a procedure step together with its attached warning/exception)."""
    pieces: list[str] = []
    for u in units:
        if count(u) <= target:
            pieces.append(u)
            continue
        for s in split_sentences(u):
            pieces.extend([s] if count(s) <= target else _hard_split(s, count, target))
    chunks, cur, cur_t, fresh = [], [], 0, False
    for p in pieces:
        t = count(p)
        if cur and cur_t + t > target:
            if fresh:
                chunks.append("\n".join(cur))
            tail, tt = [], 0
            for x in reversed(cur):
                c = count(x)
                if tt + c > overlap:
                    break
                tail.insert(0, x)
                tt += c
            cur, cur_t, fresh = tail, tt, False
        cur.append(p)
        cur_t += t
        fresh = True
    if cur and fresh:
        chunks.append("\n".join(cur))
    return chunks


@dataclass
class _Section:
    path: list[str]
    number: str
    page: int
    paragraphs: list[str] = field(default_factory=list)


def _sections(pages: list[tuple[int, str]], root: str) -> list[_Section]:
    sections: list[_Section] = [_Section([root], "0", pages[0][0] if pages else 1)]
    stack: list[tuple[int, str]] = []
    buf: list[str] = []

    def flush():
        body = "\n".join(buf).strip()
        buf.clear()
        if not body:
            return
        paras = []
        for para in re.split(r"\n\s*\n", body):
            para = para.strip()
            if not para:
                continue
            if paras and _ATTACH.match(para):          # keep warning/exception with its procedure
                paras[-1] += "\n" + para
            else:
                paras.append(para)
        sections[-1].paragraphs.extend(paras)

    for page_no, text in pages:
        for line in text.split("\n"):
            s = line.strip()
            m, n = _HEADING.match(s), _NUMBERED.match(s)
            if m or n:
                flush()
                if m:
                    level, title = len(m.group(1)), m.group(2).strip()
                    num = (re.match(r"(\d+(?:\.\d+)*)", title) or [None, None])[1]
                    if level == 1 and title.upper().startswith("SOP-"):
                        continue  # document title line
                else:
                    num = n.group(1)
                    level, title = num.count(".") + 2, s
                level = max(level, 2)
                while stack and stack[-1][0] >= level:
                    stack.pop()
                stack.append((level, title))
                sections.append(_Section([root] + [t for _, t in stack], num or title[:20], page_no))
            elif _META_LINE.match(s) and not sections[-1].paragraphs and len(sections) == 1:
                continue
            else:
                buf.append(line)
    flush()
    return [s for s in sections if s.paragraphs]


def chunk_sop(pages: list[tuple[int, str]], meta: dict, count: Callable[[str], int]) -> list[ChunkDraft]:
    sop_id, version = meta["sop_id"], meta["version"]
    drafts: list[ChunkDraft] = []
    seq = 0
    for sec in _sections(pages, sop_id):
        parent = f"{sop_id}@{version}#{sec.number}"
        for body in pack(sec.paragraphs, count, SOP_TARGET, SOP_OVERLAP):
            seq += 1
            drafts.append(ChunkDraft(
                chunk_id=f"{sop_id}@{version}:{seq:03d}", parent_id=parent, text=body,
                section_path=" > ".join(sec.path), page_number=sec.page, sequence=seq,
                meta={"sop_id": sop_id, "sop_title": meta["sop_title"], "version": version,
                      "effective_date": meta["effective_date"].isoformat()}))
    return drafts


# ---- reports --------------------------------------------------------------------------------------
def report_projection_units(r: Report) -> list[str]:
    """Controlled textual projection - only fields intended for search; never arbitrary DB columns."""
    kind = "Suspected adverse event" if r.report_type == "SUSPECTED_ADVERSE_EVENT" else "Product quality complaint"
    units = [f"{kind} received {r.date_received.isoformat()} via {r.intake_channel.lower()} from a "
             f"{r.reporter_type.replace('_', ' ').lower()}.", f"Description: {r.description}"]
    if r.event_description:
        units.append(f"Event: {r.event_description} Onset date: {r.event_onset_date.isoformat() if r.event_onset_date else 'unknown'}.")
    return units


def chunk_report(r: Report, count: Callable[[str], int]) -> list[ChunkDraft]:
    out = []
    for i, body in enumerate(pack(report_projection_units(r), count, REPORT_TARGET, REPORT_OVERLAP), 1):
        out.append(ChunkDraft(
            chunk_id=f"{r.reference_id}:{i:02d}", parent_id=r.reference_id, text=body, section_path=None,
            page_number=None, sequence=i,
            meta={"reference_id": r.reference_id, "report_type": r.report_type, "product_name": r.product_name,
                  "lot_number": r.lot_number, "date_received": r.date_received.isoformat(), "status": r.status.value,
                  "created_at": r.created_at.isoformat(), "synthetic": r.synthetic, "record_version": r.record_version}))
    return out


def index_text(source_type: str, meta: dict, section_path: str | None, text: str) -> str:
    """Text actually indexed (FTS + embedding): identifying header + body, so IDs match in every chunk."""
    if source_type == "SOP":
        return f"{meta['sop_id']} v{meta['version']} {meta['sop_title']} | {section_path}\n{text}"
    return f"{meta['reference_id']} {meta['product_name']} {meta['lot_number']}\n{text}"
