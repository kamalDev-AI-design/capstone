"""Local-only document parsers (no external processing APIs)."""
import io
import re
from dataclasses import dataclass
from datetime import date

SUPPORTED = {".pdf", ".docx", ".md", ".txt"}


class DocumentRejected(Exception):
    """Unsupported / malformed / metadata-less document."""


class DocumentQuarantined(Exception):
    """Image-only PDF etc.; needs an (unavailable) approved local OCR capability."""


@dataclass
class ParsedDocument:
    pages: list[tuple[int, str]]  # (page_number, text); non-paginated formats use page 1

    @property
    def page_count(self) -> int:
        return len(self.pages)


def parse_file(filename: str, data: bytes) -> ParsedDocument:
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in SUPPORTED:
        raise DocumentRejected(f"Unsupported file type '{ext or filename}'. Supported: PDF, DOCX, Markdown, TXT.")
    if ext in (".md", ".txt"):
        try:
            return ParsedDocument([(1, data.decode("utf-8-sig"))])
        except UnicodeDecodeError as e:
            raise DocumentRejected("Text file is not valid UTF-8.") from e
    if ext == ".docx":
        return _parse_docx(data)
    return _parse_pdf(data)


def _parse_docx(data: bytes) -> ParsedDocument:
    try:
        from docx import Document
        doc = Document(io.BytesIO(data))
    except Exception as e:
        raise DocumentRejected(f"Could not read DOCX: {e}") from e
    lines = []
    for p in doc.paragraphs:
        style = (p.style.name or "") if p.style is not None else ""
        m = re.match(r"Heading (\d)", style)
        text = p.text.strip()
        if m and text:
            lines.append("#" * int(m.group(1)) + " " + text)
        elif style == "Title" and text:
            lines.append("# " + text)
        else:
            lines.append(p.text)
    text = "\n".join(lines)
    if len(text.strip()) < 20:
        raise DocumentQuarantined("DOCX contains no extractable text.")
    return ParsedDocument([(1, text)])


def _parse_pdf(data: bytes) -> ParsedDocument:
    try:
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            raise DocumentRejected("Encrypted PDFs are not supported.")
        pages = [(i + 1, (pg.extract_text() or "")) for i, pg in enumerate(reader.pages)]
    except DocumentRejected:
        raise
    except Exception as e:
        raise DocumentRejected(f"Could not read PDF: {e}") from e
    if sum(len(t.strip()) for _, t in pages) < 20:
        raise DocumentQuarantined("Image-only PDF (no text layer). Quarantined: no approved local OCR capability.")
    return ParsedDocument(pages)


# ---- SOP metadata -------------------------------------------------------------------------------
_SOP_ID = re.compile(r"\b(SOP-[A-Z]{2,6}-\d{3})\b")


def extract_sop_metadata(text: str) -> dict:
    head = text[:1500]
    sop = _SOP_ID.search(head)
    ver = re.search(r"^\s*Version\s*:\s*([0-9]+(?:\.[0-9]+)*)", head, re.M | re.I)
    eff = re.search(r"^\s*Effective(?: Date)?\s*:\s*(\d{4}-\d{2}-\d{2})", head, re.M | re.I)
    missing = [n for n, v in (("SOP identifier (SOP-XXX-000)", sop), ("Version", ver), ("Effective Date", eff)) if not v]
    if missing:
        raise DocumentRejected("Missing required SOP metadata: " + ", ".join(missing))
    title_m = re.search(r"^#*\s*SOP-[A-Z]{2,6}-\d{3}\s*[:\-]\s*(.+)$", head, re.M)
    return {
        "sop_id": sop.group(1), "version": ver.group(1),
        "effective_date": date.fromisoformat(eff.group(1)),
        "sop_title": (title_m.group(1).strip() if title_m else sop.group(1)),
    }


def version_key(v: str) -> tuple[int, ...]:
    return tuple(int(x) for x in v.split("."))
