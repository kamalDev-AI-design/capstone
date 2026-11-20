"""Deterministic intent routing. An LLM classifier (optional) is consulted ONLY for unmatched free text."""
import re
from enum import StrEnum


class Route(StrEnum):
    DIRECT_RESPONSE = "DIRECT_RESPONSE"
    NEW_INTAKE = "NEW_INTAKE"
    REPORT_LOOKUP = "REPORT_LOOKUP"
    SOP_LOOKUP = "SOP_LOOKUP"
    HYBRID_KNOWLEDGE_LOOKUP = "HYBRID_KNOWLEDGE_LOOKUP"
    STATUS_UPDATE = "STATUS_UPDATE"
    CLOSURE_APPROVAL = "CLOSURE_APPROVAL"
    PROHIBITED_REQUEST = "PROHIBITED_REQUEST"


_GREETING = re.compile(r"^\s*(hi|hello|hey|help|thanks|thank you|what can you do|who are you)\b[\s!.?]*$", re.I)
_CREATE = re.compile(r"\b(create|log|record|file|open|register|add|enter|submit)\b.{0,30}\b(report|complaint|case|adverse event|intake|record)\b", re.I)
_CLOSE = re.compile(r"\b(clos(e|ure)|approv(e|al))\b", re.I)
_STATUS = re.compile(r"\b(move|set|change|update|mark|start|put|transition)\b.{0,50}\b(in[ _-]?review|review|new)\b", re.I)
_AUDIT = re.compile(r"\baudit\b|\bhash[- ]chain\b|\bverify\b.{0,15}\bchain\b", re.I)
_LOOKUP = re.compile(r"\b(show|get|open|display|status of|details? (of|for)|list|how many|count|which reports)\b", re.I)
_SOP = re.compile(r"\b(sop|procedure|policy|guideline|work instruction|training document)\b", re.I)
_HISTORY = re.compile(r"\b(similar|previous|past|historical|history|earlier|other (reports|complaints)|reports? (about|with|for)|complaints? (about|with|for))\b", re.I)
_DOMAIN = re.compile(r"\b(complaint|report|lot|seal|tablet|label|vial|packaging|quarantine|acknowledg|intake|review|closure|adverse|event|sop|audit)\w*\b", re.I)


def route(message: str, ent: dict) -> tuple[Route, bool]:
    """Returns (route, ambiguous). `ambiguous` means no deterministic rule matched."""
    if _GREETING.match(message):
        return Route.DIRECT_RESPONSE, False
    if _CREATE.search(message) and not ent["refs"]:
        return Route.NEW_INTAKE, False
    if _CLOSE.search(message) and (ent["refs"] or ent["approval_id"] is not None):
        return Route.CLOSURE_APPROVAL, False
    if _STATUS.search(message) and ent["refs"]:
        return Route.STATUS_UPDATE, False
    if _AUDIT.search(message):
        return Route.REPORT_LOOKUP, False
    if ent["refs"] and not _SOP.search(message):
        return Route.REPORT_LOOKUP, False
    if _LOOKUP.search(message) and re.search(r"\breports?\b|\bcomplaints?\b|\bcases?\b", message, re.I) and not _SOP.search(message) \
            and not _HISTORY.search(message):
        return Route.REPORT_LOOKUP, False
    if _SOP.search(message) or ent["sops"]:
        return (Route.HYBRID_KNOWLEDGE_LOOKUP if _HISTORY.search(message) else Route.SOP_LOOKUP), False
    if _HISTORY.search(message) or ent["lots"] or _DOMAIN.search(message):
        return Route.HYBRID_KNOWLEDGE_LOOKUP, False
    return Route.HYBRID_KNOWLEDGE_LOOKUP, True
