"""Conservative text normalization. Identifiers, dates, negations and section numbers are preserved."""
import hashlib
import re
import unicodedata

_DASHES = {ord(c): "-" for c in "‐‑‒–—―−"}
_QUOTES = {0x2018: "'", 0x2019: "'", 0x201C: '"', 0x201D: '"', 0x00A0: " "}
_ZERO_WIDTH = re.compile("[​‌‍⁠﻿]")


def normalize(text: str) -> str:
    t = unicodedata.normalize("NFKC", text)
    t = _ZERO_WIDTH.sub("", t).translate(_DASHES).translate(_QUOTES)
    t = t.replace("\r\n", "\n").replace("\r", "\n")
    t = "\n".join(re.sub(r"[ \t\f\v]+", " ", ln).strip() for ln in t.split("\n"))
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t.strip()


def document_hash(normalized_text: str) -> str:
    return hashlib.sha256(normalized_text.encode("utf-8")).hexdigest()


def text_hash(text: str) -> str:
    return hashlib.sha256(re.sub(r"\s+", " ", text).strip().lower().encode("utf-8")).hexdigest()
