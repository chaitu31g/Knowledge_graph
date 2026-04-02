import re


_WHITESPACE_RE = re.compile(r"\s+")
_JOINER_RE = re.compile(r"\s*[/\-]\s*")
_PARENS_RE = re.compile(r"[()\[\]{}]")
_OTHER_SPECIAL_RE = re.compile(r"[^a-z0-9\s]")


def normalize_lookup_text(value: str) -> str:
    """
    Normalize lookup text for deterministic Neo4j matching.

    Rules:
    - lowercase
    - trim outer whitespace
    - replace newlines/tabs with spaces
    - collapse repeated spaces
    - remove separator characters like '/' and '-' with surrounding spaces
    - remove bracket characters
    - remove remaining non-alphanumeric punctuation
    - collapse repeated spaces again

    Examples:
    - "Pulsed drain current " -> "pulsed drain current"
    - "dv / dt" -> "dvdt"
    """
    text = (value or "").lower().strip()
    text = text.replace("\r", " ").replace("\n", " ").replace("\t", " ")
    text = _WHITESPACE_RE.sub(" ", text)
    text = _JOINER_RE.sub("", text)
    text = _PARENS_RE.sub(" ", text)
    text = _OTHER_SPECIAL_RE.sub(" ", text)
    text = _WHITESPACE_RE.sub(" ", text)
    return text.strip()
