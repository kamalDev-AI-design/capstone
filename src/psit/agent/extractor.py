"""Deterministic entity extraction (regex). No model involved."""
import re

REF_RE = re.compile(r"\bREF-\d{4}-\d{4}\b", re.I)
LOT_RE = re.compile(r"\bLOT-\d{5}\b", re.I)
SOP_RE = re.compile(r"\bSOP-[A-Z]{2,6}-\d{3}\b", re.I)
APPROVAL_RE = re.compile(r"\bapproval\s*(?:id\s*)?#?\s*(\d+)\b|\bapproval\b.{0,20}?#\s*(\d+)", re.I)

_KV_KEYS = {
    "product": "product_name", "product_name": "product_name", "lot": "lot_number", "lot_number": "lot_number",
    "date": "date_received", "date_received": "date_received", "reporter": "reporter_type",
    "reporter_type": "reporter_type", "channel": "intake_channel", "intake_channel": "intake_channel",
    "description": "description", "event": "event_description", "event_description": "event_description",
    "onset": "event_onset_date", "event_onset_date": "event_onset_date", "note": "note",
}
_KV_RE = re.compile(r"\b(" + "|".join(sorted(_KV_KEYS, key=len, reverse=True)) + r")\s*[:=]\s*", re.I)


def _kv(message: str) -> dict:
    out, hits = {}, list(_KV_RE.finditer(message))
    for i, m in enumerate(hits):
        end = hits[i + 1].start() if i + 1 < len(hits) else len(message)
        val = message[m.end():end].strip().rstrip(",;").strip()
        if val:
            out[_KV_KEYS[m.group(1).lower()]] = val
    for k in ("reporter_type", "intake_channel"):
        if k in out:
            out[k] = re.sub(r"\s+", "_", out[k].strip()).upper()
    return out


def extract(message: str) -> dict:
    low = message.lower()
    status = None
    if re.search(r"\bin[ _-]?review\b|\bunder review\b|\bstart(ed)? review", low):
        status = "IN_REVIEW"
    elif re.search(r"\bclos(e|ed|ure)\b", low):
        status = "CLOSED"
    elif re.search(r"\bnew\b", low):
        status = "NEW"
    rtype = None
    if re.search(r"adverse[ _-]?event|\bsae\b|\bae\b", low):
        rtype = "SUSPECTED_ADVERSE_EVENT"
    elif re.search(r"complaint|quality|\bpqc\b", low):
        rtype = "PRODUCT_QUALITY_COMPLAINT"
    am = APPROVAL_RE.search(message)
    return {
        "refs": list(dict.fromkeys(m.upper() for m in REF_RE.findall(message))),
        "lots": list(dict.fromkeys(m.upper() for m in LOT_RE.findall(message))),
        "sops": list(dict.fromkeys(m.upper() for m in SOP_RE.findall(message))),
        "approval_id": int(next(g for g in am.groups() if g)) if am else None,
        "status": status, "report_type": rtype, "fields": _kv(message),
    }
