"""Deterministic policy boundary check. Runs BEFORE any model or retrieval. Never LLM-based."""
import re
from dataclasses import dataclass

SCOPE_BOUNDARY_RESPONSE = (
    "I can't make that determination. This prototype can retrieve relevant fictional training evidence "
    "(SOP sections and historical reports), but it cannot make clinical or regulatory determinations - "
    "including causality, seriousness, expectedness, listedness, reportability, treatment advice, or "
    "regulatory submission recommendations. Those decisions belong to a qualified human safety reviewer."
)

_F = re.I | re.S
_RULES: list[tuple[str, re.Pattern]] = [
    ("CAUSALITY", re.compile(r"\b(did|does|do|could|can|would|might|may)\b.{0,60}\b(cause[sd]?|causing|trigger(ed)?|lead to|result(ed)? in)\b", _F)),
    ("CAUSALITY", re.compile(r"\b(if|whether)\b.{0,60}\b(caused|cause|causing|triggered|related to|due to)\b", _F)),
    ("CAUSALITY", re.compile(r"\b(caused by|due to the (drug|product)|related to the (drug|product)|causal(ity)?\b.{0,20}\b(assess|determin|evaluat|classif)|(assess|determin|evaluat|classif)\w*\b.{0,30}\bcausal)", _F)),
    ("SERIOUSNESS", re.compile(r"\b(is|was|are|were)\b.{0,50}\bserious\b|\b(assess|determine|evaluate|classify|decide)\w*\b.{0,40}\bseriousness\b", _F)),
    ("EXPECTEDNESS", re.compile(r"\b(is|was|are|were)\b.{0,50}\b(expected|unexpected|listed|unlisted|labell?ed)\b|\b(assess|determine|evaluate|classify)\w*\b.{0,40}\b(expectedness|listedness)\b", _F)),
    ("REPORTABILITY", re.compile(r"\breportab\w*\b|\b(should|must|need to|do we|do i|have to)\b.{0,40}\b(report|submit|notify|file)\b.{0,50}\b(fda|ema|authorit\w+|regulator\w*|agency)\b|\b(expedited|15[- ]day)\b.{0,30}\b(report|submission)\b", _F)),
    ("TREATMENT", re.compile(r"\b(what|which)\b.{0,30}\b(treatment|medication|medicine|dose|dosage)\b.{0,40}\b(should|recommend|give|take|prescribe)\b|\b(should|can|could)\b.{0,30}\b(the patient|patient|he|she|they|i)\b.{0,30}\b(take|stop|continue|discontinue|restart)\b|\b(recommend|advise|prescribe|suggest)\w*\b.{0,40}\b(treatment|therapy|medication|dose|antidote)\b|\bdiagnos(e|is)\b", _F)),
    ("AUTONOMOUS_CLOSURE", re.compile(r"\b(auto(matically)?|on your own|yourself|without (human )?(approval|review))\b.{0,30}\b(close|approve)\b|\b(close|approve)\b.{0,30}\b(without (human )?(approval|review)|on your own|yourself)\b", _F)),
]
_SOP_EXPLAIN = re.compile(r"\b(sop|procedure|policy|guideline|training)\b", re.I)
_SAYS = re.compile(r"\b(say|says|state|states|describe|describes|define|defines|require|requires|cover|covers|explain)\b", re.I)
_CASE_REF = re.compile(r"REF-\d{4}-\d{4}|\b(this|that|the) (report|case|patient|event|complaint)\b|\bpatient\b", re.I)


@dataclass(frozen=True)
class PolicyDecision:
    blocked: bool
    category: str | None = None
    message: str | None = None


def check(text: str) -> PolicyDecision:
    # Questions about what an SOP *says* are knowledge lookups, unless tied to a specific case.
    if _SOP_EXPLAIN.search(text) and _SAYS.search(text) and not _CASE_REF.search(text):
        explicit = [c for c, p in _RULES if c in ("TREATMENT", "AUTONOMOUS_CLOSURE") and p.search(text)]
        if not explicit:
            return PolicyDecision(False)
    for category, pat in _RULES:
        if pat.search(text):
            return PolicyDecision(True, category, SCOPE_BOUNDARY_RESPONSE)
    return PolicyDecision(False)
