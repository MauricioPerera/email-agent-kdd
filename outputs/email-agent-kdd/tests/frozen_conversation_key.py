"""Tests congelados del contrato conversation_key.

Oracle independiente: no importa el target a nivel de modulo. Verifica la
estructura del contrato (frontmatter, firma, 7 secciones, frase de PARAR)
y los casos congelados (prioridad References > In-Reply-To > Message-ID,
fallback subject+participantes, normalizacion de case/orden, hash hex de
64, determinismo y no mutacion) reimplementando la normalizacion y el
hashing esperados. Los casos de comportamiento hacen pytest.skip si
src.email.conversation.conversation_key todavia no existe.
"""

import hashlib
import json
import re
import sys
from pathlib import Path

import pytest

CONTRACT = (
    Path(__file__).resolve().parents[1]
    / "knowledge"
    / "contracts"
    / "conversation-key.md"
)


def _contract_text():
    return CONTRACT.read_text(encoding="utf-8")


def _fenced_block(text, label):
    match = re.search(r"```" + label + r"\n(.*?)\n```", text, re.DOTALL)
    assert match is not None, "bloque " + label + " ausente en el contrato"
    return match.group(1)


# ---------------------------------------------------------------------------
# Oracle: reimplementa el comportamiento esperado segun el contrato
# (seccion Tests). NO importa el target.
# ---------------------------------------------------------------------------


def _norm_id(value):
    if value is None:
        return []
    if isinstance(value, str):
        value = [value]
    out = []
    for item in value:
        text = str(item).strip().strip("<>").strip()
        if text:
            out.append(text.lower())
    return out


def _norm_subject(subject):
    text = (subject or "").strip()
    while True:
        low = text.lower()
        for prefix in ("re:", "fwd:", "rv:"):
            if low.startswith(prefix):
                text = text[len(prefix):].strip()
                break
        else:
            return re.sub(r"\s+", " ", text).lower()


def _oracle(record):
    ids = _norm_id(record.get("references")) + _norm_id(record.get("in_reply_to")) or _norm_id(
        record.get("message_id")
    )
    if not ids:
        parts = set()
        for key in ("from", "to", "cc"):
            value = record.get(key)
            if isinstance(value, str):
                value = [value]
            parts |= {str(x).strip().lower() for x in (value or []) if x and str(x).strip()}
        ids = [_norm_subject(record.get("subject"))] + sorted(parts)
    return hashlib.sha256("|".join(ids).encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Checks estructurales del contrato
# ---------------------------------------------------------------------------


def test_contract_frontmatter_signature_and_budget():
    text = _contract_text()
    frontmatter = text.split("---\n", 2)[1]
    assert "task: conversation-key" in frontmatter
    assert (
        'signature: "def conversation_key(record: dict) -> str"' in frontmatter
    ), "firma pactada ausente o alterada en el frontmatter"
    assert "target: ../../../../src/email/conversation.py" in frontmatter
    assert "max_complexity: 10" in frontmatter
    assert "max_nesting: 3" in frontmatter
    assert "max_params: 1" in frontmatter
    assert "tests_frozen: true" in frontmatter


def test_contract_has_seven_sections_and_stop_phrase():
    text = _contract_text()
    for section in (
        "## Intent",
        "## Interface",
        "## Invariants",
        "## Examples",
        "## Do / Don't",
        "## Tests",
        "## Constraints",
    ):
        assert section in text, "seccion ausente: " + section
    assert "PARAR y reportar si" in text


def test_contract_frozen_examples_present():
    text = _contract_text()
    examples = _fenced_block(text, "python")
    for marker in (
        "E1",
        "E6",
        "E8",
        "E10",
    ):
        assert marker in examples, "caso congelado ausente en Examples: " + marker
    tests_block = re.search(
        r"## Tests\n.*?```python\n(.*?)\n```", text, re.DOTALL
    )
    assert tests_block is not None, "bloque de property-tests ausente en ## Tests"
    for name in (
        "test_formato_ruta_seguro",
        "test_prioridad_references",
        "test_normalizacion_ids",
        "test_fallback_subject_participantes",
        "test_no_mutacion_y_pureza",
        "test_oracle_consistente",
    ):
        assert "def " + name + "(" in tests_block.group(1), (
            "property-test congelado ausente: " + name
        )


def test_oracle_matches_frozen_examples():
    # E1 — References gana sobre message_id y subject
    assert _oracle({"references": "<a@x>", "message_id": "<b@x>", "subject": "Hola"}) == _oracle(
        {"references": "<a@x>", "subject": "Otro asunto"}
    )
    # E2 — In-Reply-To, sin References: angulos/case no importan
    assert _oracle({"in_reply_to": "<r@y>", "subject": "Re: Hola"}) == _oracle(
        {"in_reply_to": "r@y", "subject": "Fwd: Hola"}
    )
    # E3 — Solo Message-ID: subject irrelevante
    assert _oracle({"message_id": "<m1@z>", "subject": "Presupuesto"}) == _oracle(
        {"message_id": "m1@z"}
    )
    # E4 — Fallback: prefijos y case de subject/participantes no importan
    assert _oracle(
        {"subject": "Re: Re: FWD: Presupuesto Q3", "from": "Ana@X.com", "to": ["bob@y.com"]}
    ) == _oracle({"subject": "Presupuesto Q3", "from": "ana@x.com", "to": "BOB@Y.COM"})
    # E5 — Fallback: orden y duplicados de participantes irrelevantes
    assert _oracle({"subject": "S", "from": "a@x", "to": ["b@y", "a@x"]}) == _oracle(
        {"subject": "S", "from": "a@x", "to": ["a@x", "b@y", "b@y"]}
    )
    # E9 — Conversaciones distintas -> claves distintas
    assert _oracle({"subject": "A"}) != _oracle({"subject": "B"})


# ---------------------------------------------------------------------------
# Casos de comportamiento contra el target (pytest.skip si no existe)
# ---------------------------------------------------------------------------


def _conversation_key():
    try:
        from src.email.conversation import conversation_key  # noqa: PLC0415
    except (ImportError, AttributeError):
        pytest.skip("src.email.conversation.conversation_key no existe todavia")
    return conversation_key


def test_formato_ruta_seguro():
    conversation_key = _conversation_key()
    for record in ({}, {"subject": "x"}, {"references": "<a@b>"}):
        assert re.fullmatch(r"[0-9a-f]{64}", conversation_key(record))


def test_prioridad_references():
    conversation_key = _conversation_key()
    assert conversation_key({"references": "<a@x>", "subject": "uno"}) == conversation_key(
        {"references": "<a@x>", "subject": "dos"}
    )
    assert conversation_key({"references": "<a@x>"}) != conversation_key(
        {"references": "<b@x>"}
    )


def test_prioridad_in_reply_to():
    conversation_key = _conversation_key()
    assert conversation_key({"in_reply_to": "<r@y>", "subject": "Re: Hola"}) == conversation_key(
        {"in_reply_to": "r@y", "subject": "Fwd: Hola"}
    )
    # In-Reply-To sin References: el subject no debe influir
    assert conversation_key({"in_reply_to": "<r@y>", "subject": "uno"}) == conversation_key(
        {"in_reply_to": "r@y", "subject": "dos"}
    )
    assert conversation_key({"in_reply_to": "<r@y>"}) != conversation_key(
        {"in_reply_to": "<s@y>"}
    )


def test_prioridad_message_id():
    conversation_key = _conversation_key()
    assert conversation_key({"message_id": "<m1@z>", "subject": "Presupuesto"}) == conversation_key(
        {"message_id": "m1@z"}
    )
    assert conversation_key({"message_id": "<m1@z>"}) != conversation_key(
        {"message_id": "m2@z"}
    )


def test_fallback_subject_participantes():
    conversation_key = _conversation_key()
    assert conversation_key(
        {"subject": "Re: FWD: Presupuesto", "from": "A@x"}
    ) == conversation_key({"subject": "Presupuesto", "from": "a@x", "to": ["a@x"]})
    assert conversation_key({"subject": "S", "to": ["b@y", "a@x"]}) == conversation_key(
        {"subject": "S", "to": ["a@x", "b@y"]}
    )
    assert conversation_key({"subject": "A"}) != conversation_key({"subject": "B"})


def test_normalizacion_ids_case_y_orden():
    conversation_key = _conversation_key()
    assert conversation_key({"message_id": "<M1@Z>"}) == conversation_key(
        {"message_id": " m1@z "}
    )
    refs = {"references": ["<a@x>", "b@y"]}
    refs_alt = {"references": ["a@x", "<B@Y>"]}
    assert conversation_key(refs) == conversation_key(refs_alt)


def test_determinismo():
    conversation_key = _conversation_key()
    record = {"references": "<a@x>", "message_id": "<b@x>", "subject": "Re: Hola"}
    assert conversation_key(record) == conversation_key(record) == _oracle(record)


def test_no_mutacion_y_pureza():
    conversation_key = _conversation_key()
    record = {"subject": "Hola", "to": ["a@x"], "message_id": "<m@z>"}
    snapshot = repr(record)
    key1 = conversation_key(record)
    key2 = conversation_key(record)
    assert repr(record) == snapshot, "conversation_key muto el record"
    assert key1 == key2 == _oracle(record), "no es pura/determinista"


def test_degradacion_record_minimo_y_basura():
    conversation_key = _conversation_key()
    for record in (
        {},
        {"references": "   ", "message_id": None, "subject": "", "to": []},
        {"references": None, "in_reply_to": "", "from": None, "cc": ""},
    ):
        assert re.fullmatch(r"[0-9a-f]{64}", conversation_key(record))


def test_oracle_consistente():
    conversation_key = _conversation_key()
    casos = [
        {},
        {"subject": "x"},
        {"references": "<a@x>", "message_id": "<b@x>"},
        {"in_reply_to": "r@y"},
        {"message_id": "<m@z>", "subject": "Re: s"},
        {"subject": "Fwd: hola", "from": "ana@x.com", "to": ["bob@y.com"], "cc": "car@z.io"},
        {"references": "  ", "subject": "", "to": []},
    ]
    for caso in casos:
        assert conversation_key(caso) == _oracle(caso), "desvio del oracle en caso: " + repr(caso)