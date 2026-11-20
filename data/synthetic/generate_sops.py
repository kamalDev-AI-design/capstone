"""Generates FICTIONAL training SOP documents in MD / DOCX / PDF / TXT (plus negative-test files).
Run: python data/synthetic/generate_sops.py   -> data/synthetic/sops/
"""
import re
from pathlib import Path

OUT = Path(__file__).parent / "sops"

SOPS: dict[str, str] = {}

SOPS["SOP-QC-001_v2.0.md"] = """# SOP-QC-001: Product Quality Complaint Intake and Triage
Version: 2.0
Effective Date: 2026-01-01
Status: Active

## 1. Purpose
This fictional training SOP describes how an intake operator logs and triages a product quality complaint received by email or telephone.

## 2. Scope
It applies to all product quality complaints about fictional marketed products. It does not apply to suspected adverse events, which follow SOP-AE-002.

## 3. Responsibilities
The intake operator records the complaint and assigns a reference identifier. The human reviewer decides when a complaint is ready for closure.

## 4. Procedure
### 4.1 Logging the complaint
Step 1. Record the product name, lot number, date received, reporter type and intake channel in the intake form.
Step 2. Enter the lot number in the format LOT-NNNNN. A lot number that does not match this format must be corrected before the record can be saved.
WARNING: Never enter patient names, addresses, email addresses or telephone numbers. Only fictional training data is permitted.

### 4.2 Acknowledgement
Acknowledge receipt of the complaint to the reporter within 2 business days of the date received.
EXCEPTION: If the reporter declined contact, document the refusal in the description and skip the acknowledgement.

### 4.3 Sample handling
Ask the reporter to retain the physical sample in its original packaging. Do not ask the reporter to ship the sample until the quality team provides a prepaid return label.

## 5. Escalation
### 5.1 Repeated lots
When three or more complaints reference the same lot number within 30 days, notify the quality lead so that SOP-LOT-004 can be started.
NOTE: Complaints about cracked seals, particulate matter and leaking containers are counted together for this threshold.

## 6. Records
Every complaint must keep its reference identifier, status history and audit trail. Records are never deleted by the intake operator.
"""

SOPS["SOP-QC-001_v1.0.md"] = """# SOP-QC-001: Product Quality Complaint Intake and Triage
Version: 1.0
Effective Date: 2025-01-01
Status: Superseded

## 1. Purpose
This fictional training SOP describes how an intake operator logs a product quality complaint.

## 4. Procedure
### 4.2 Acknowledgement
Acknowledge receipt of the complaint to the reporter within 5 business days of the date received.

## 5. Escalation
### 5.1 Repeated lots
When five or more complaints reference the same lot number within 60 days, notify the quality lead.
"""

SOPS["SOP-AE-002_v1.0.md"] = """# SOP-AE-002: Suspected Adverse Event Intake Data Capture
Version: 1.0
Effective Date: 2025-06-01
Status: Active

## 1. Purpose
This fictional training SOP defines the minimum data an intake operator captures for a suspected adverse event report.

## 2. Mandatory fields
### 2.1 Common fields
Capture the product name, lot number, date received, reporter type, intake channel and a description of the report.

### 2.2 Adverse event fields
An adverse event report additionally requires an event description and an event onset date. The record cannot be saved without both fields.
WARNING: Do not record patient names, addresses, email addresses or telephone numbers. Describe the patient only in neutral, non-identifying terms.

## 3. Boundaries of the intake role
### 3.1 What the operator does not decide
The intake operator and this application do not assess causality, seriousness, expectedness or reportability. These determinations belong to a qualified human safety reviewer.
EXCEPTION: If the reporter states that a medical emergency is in progress, the operator tells the reporter to contact local emergency services and then records the call. The operator gives no medical advice.

## 4. Follow-up
### 4.1 Missing information
If the onset date is unknown, record the earliest date the reporter can estimate and note the uncertainty in the event description.
"""

SOPS["SOP-REV-003_v1.0.md"] = """# SOP-REV-003: Report Review and Closure Approval
Version: 1.0
Effective Date: 2025-09-01
Status: Active

## 1. Purpose
This fictional training SOP explains how a report moves from NEW to IN_REVIEW and finally to CLOSED.

## 2. Status lifecycle
### 2.1 Allowed transitions
A report moves from NEW to IN_REVIEW when a reviewer starts work. A report moves from IN_REVIEW to CLOSED only after a documented human approval.
WARNING: A report must never move directly from NEW to CLOSED. A closed report cannot be reopened in this prototype.

## 3. Closure approval
### 3.1 Requesting closure
The intake operator or reviewer submits a closure request for a report that is IN_REVIEW. The request records who asked and the record version at the time.
### 3.2 Approving closure
A different human reviewer approves the request. The person who requested closure cannot approve it. Software agents and AI assistants can never approve closure.
EXCEPTION: If the record changed after the request was made, the approval is rejected and closure must be requested again.

## 4. Audit
Every status change and approval is written to the audit trail with the actor, timestamp and outcome.
"""

SOPS["SOP-LOT-004_v1.0.md"] = """# SOP-LOT-004: Lot Investigation and Quarantine Communication
Version: 1.0
Effective Date: 2025-11-15
Status: Active

## 1. Purpose
This fictional training SOP describes how the quality lead investigates a lot that appears in several complaints.

## 2. Investigation
### 2.1 Gathering evidence
Search historical reports by lot number to collect every complaint for the lot. Review the packaging, label and seal descriptions across the complaints.

### 2.2 Quarantine recommendation
The quality lead may place a lot on internal quarantine hold while the investigation is open. Warehouse staff must not release quarantined stock.
WARNING: A quarantine hold is an internal quality action. It is not a regulatory notification and is not decided by the intake application.
EXCEPTION: Stock already dispatched to a distributor is traced by the distribution team and is not covered by the internal hold.

## 3. Communication
Inform the intake team when a lot enters or leaves quarantine so that new complaints can reference the investigation record.
"""

SOPS["SOP-CALL-006_v1.0.txt"] = """SOP-CALL-006: Telephone Intake Procedure
Version: 1.0
Effective Date: 2025-08-01
Status: Active

1. Purpose
This fictional training SOP describes how the intake operator handles a telephone report.

2. Opening the call
2.1 Greeting and consent
Greet the caller and explain that the call details will be typed into the intake form. Telephone calls are not recorded and no speech-to-text is used.
WARNING: Do not ask for the caller's own telephone number, address or email address.

3. Capturing information
3.1 Reading back
Read the lot number back to the caller using the format LOT-NNNNN, digit by digit, to avoid transcription errors.
3.2 Closing the call
Tell the caller that a reviewer will follow up if more information is needed. Do not promise outcomes or give medical advice.
"""

SOPS["SOP-DOC-005_v1.0.md"] = """# SOP-DOC-005: Documentation and Record Retention
Version: 1.0
Effective Date: 2025-03-01
Status: Active

## 1. Purpose
This fictional training SOP defines how safety intake records are documented and retained.

## 2. Record contents
Each record keeps its reference identifier in the format REF-YYYY-NNNN, the lot number, the dates, the status history and the audit events.

## 3. Retention
Training records are retained for the duration of the course plus 12 months.
EXCEPTION: Records referenced by an open investigation are retained until the investigation is closed.

## 4. Corrections
A wrong value is corrected by adding a documented correction. Existing audit events are never edited or deleted.
"""


def to_plain(md: str) -> str:
    return re.sub(r"^#+\s*", "", md, flags=re.M).replace("## ", "")


def write_docx(path: Path, md: str) -> None:
    from docx import Document
    doc = Document()
    for line in md.split("\n"):
        m = re.match(r"^(#+)\s+(.*)", line)
        if m:
            level = min(len(m.group(1)), 4)
            doc.add_heading(m.group(2), level=level if level > 1 else 1)
        else:
            doc.add_paragraph(line)
    doc.save(path)


def _esc(s: str) -> str:
    return s.encode("latin-1", "replace").decode("latin-1").replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def write_pdf(path: Path, text: str, lines_per_page: int = 46, blank: bool = False) -> None:
    """Minimal text PDF writer (Helvetica). blank=True creates a page with only a drawn rectangle (image-only stand-in)."""
    lines: list[str] = []
    for ln in text.split("\n"):
        while len(ln) > 95:
            cut = ln.rfind(" ", 0, 95) or 95
            lines.append(ln[:cut]); ln = ln[cut:].strip()
        lines.append(ln)
    pages = [lines[i:i + lines_per_page] for i in range(0, len(lines), lines_per_page)] or [[]]
    objs: list[bytes] = []
    n_pages = len(pages)
    kids = " ".join(f"{3 + 2 * i} 0 R" for i in range(n_pages))
    objs.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    objs.append(f"<< /Type /Pages /Kids [{kids}] /Count {n_pages} >>".encode())
    font_id = 3 + 2 * n_pages
    for i, pg in enumerate(pages):
        content_id = 4 + 2 * i
        objs.append(f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents {content_id} 0 R "
                    f"/Resources << /Font << /F1 {font_id} 0 R >> >> >>".encode())
        if blank:
            stream = b"0.8 g 100 100 400 500 re f"
        else:
            body = ["BT /F1 10 Tf 50 750 Td 14 TL"] + [f"({_esc(l)}) Tj T*" for l in pg] + ["ET"]
            stream = "\n".join(body).encode("latin-1", "replace")
        objs.append(b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream")
    objs.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    out, offsets = bytearray(b"%PDF-1.4\n"), []
    for i, o in enumerate(objs, 1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode() + o + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode()
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode()
    out += f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF".encode()
    path.write_bytes(bytes(out))


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for name, md in SOPS.items():
        (OUT / name).write_text(md, encoding="utf-8")
    # Same SOPs in other formats (different SOP ids so each is a distinct document)
    write_docx(OUT / "SOP-AE-002_v1.0.docx", SOPS["SOP-AE-002_v1.0.md"])
    (OUT / "SOP-AE-002_v1.0.md").unlink()                      # keep AE SOP as DOCX only
    pdf_src = to_plain(SOPS["SOP-REV-003_v1.0.md"])
    write_pdf(OUT / "SOP-REV-003_v1.0.pdf", pdf_src)
    (OUT / "SOP-REV-003_v1.0.md").unlink()                     # keep REV SOP as PDF only
    # Negative / edge-case files
    (OUT / "SOP-DOC-005_v1.0_copy.txt").write_text(SOPS["SOP-DOC-005_v1.0.md"], encoding="utf-8")  # duplicate content
    write_pdf(OUT / "scanned_image_only.pdf", "", blank=True)  # no text layer -> quarantined
    (OUT / "notes_without_metadata.txt").write_text("Random meeting notes with no SOP identifier or version.", encoding="utf-8")
    (OUT / "unsupported.xlsx").write_bytes(b"PK fake spreadsheet")
    print("wrote", sorted(p.name for p in OUT.iterdir()))


if __name__ == "__main__":
    main()
