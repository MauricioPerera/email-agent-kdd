"""Extraccion determinista de temas desde el asunto de un email.

Conforme a knowledge/contracts/extract-topics.md. Funcion pura: solo lee
``record["subject"]``, nunca el cuerpo ni otras claves; no muta el record,
sin I/O, sin red ni modelos externos.
"""

import re

STOPWORDS = frozenset({
    # español
    "de", "la", "el", "los", "las", "del", "al", "a", "y", "o", "en", "con",
    "para", "por", "que", "se", "su", "sus", "lo", "un", "una", "es", "no",
    "sobre", "re", "rv", "fw", "fwd",
    # inglés
    "the", "an", "and", "or", "of", "to", "in", "on", "for", "with",
    "is", "it", "this", "that",
})

_PREFIXES = ("re:", "fwd:", "rv:")


def extract_topics(record: dict) -> list[str]:
    """Devuelve hasta 12 etiquetas de tema normalizadas desde el asunto."""
    subject = record.get("subject", "")
    if not isinstance(subject, str):
        subject = ""
    subject = subject.strip()
    changed = True
    while changed:
        changed = False
        folded = subject.casefold()
        for prefix in _PREFIXES:
            if folded.startswith(prefix):
                subject = subject[len(prefix):].strip()
                changed = True
                break
    tokens = re.findall(r"\w+", subject, flags=re.UNICODE)
    seen: set[str] = set()
    for token in tokens:
        normalized = token.casefold()
        if normalized and normalized not in STOPWORDS:
            seen.add(normalized)
    return sorted(seen)[:12]