import re


_NON_ALNUM_RE = re.compile(r"[^a-z0-9\s]+")
_WHITESPACE_RE = re.compile(r"\s+")


def normalize_lookup_text(value: str) -> str:
    """
    Normalize lookup text for deterministic Neo4j matching.

    Rules:
    - lowercase
    - trim outer whitespace
    - replace newlines/tabs with spaces
    - collapse repeated spaces
    - remove punctuation/special characters
    - remove remaining spaces so variants like 'dv / dt' and 'dv/dt'
      normalize to the same key: 'dvdt'
    """
    text = (value or "").lower().strip()
    text = text.replace("\r", " ").replace("\n", " ").replace("\t", " ")
    text = _WHITESPACE_RE.sub(" ", text)
    text = _NON_ALNUM_RE.sub("", text)
    return _WHITESPACE_RE.sub("", text)
