# -*- coding: utf-8 -*-
"""Oráculo para el contrato persist-conversation-index.

Estructura: valida el front-matter, el target, la firma y las 7 secciones del
contrato, sin importar el target. Comportamiento: ejercita
persist_conversation_index contra un store temporal; se salta (skip) si el
módulo src.email.conversation_index no existe.
"""
import hashlib
import re
from pathlib import Path

import pytest

CONTRACT_PATH = Path(__file__).resolve().parent.parent / "knowledge" / "contracts" / "persist-conversation-index.md"

EXPECTED_TARGET = Path("src/email/conversation_index.py")
EXPECTED_SIGNATURE = "def persist_conversation_index(root: str, record: dict, message_path: str) -> str"
EXPECTED_SECTIONS = (
    "## Intent",
    "## Interface",
    "## Invariants",
    "## Examples",
    "## Do / Don't",
    "## Tests",
    "## Constraints",
)
STOP_PHRASE = "PARAR y reportar si"


# ---------------------------------------------------------------------------
# Estructura del contrato (oráculo independiente, sin importar el target)
# ---------------------------------------------------------------------------

def test_contrato_existe():
    assert CONTRACT_PATH.is_file(), f"falta el contrato: {CONTRACT_PATH}"


def test_contrato_frontmatter():
    text = CONTRACT_PATH.read_text(encoding="utf-8")
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    assert m, "falta el bloque de front-matter '---\\n...\\n---\\n'"
    fm = m.group(1)
    for key in ("task:", "intent:", "target:", "signature:", "language:", "budget:", "deps_allowed:"):
        assert re.search(rf"^{key}", fm, re.M), f"front-matter sin clave requerida: {key}"
    assert re.search(r"^task:\s+\S", fm, re.M), "task vacío en front-matter"
    assert re.search(r"^language:\s*python\s*$", fm, re.M), "language debe ser python"
    assert re.search(r"^intent:\s*\S", fm, re.M), "intent vacío en front-matter"


def test_contrato_target():
    text = CONTRACT_PATH.read_text(encoding="utf-8")
    m = re.search(r"^target:\s*(\S+)\s*$", text, re.M)
    assert m, "front-matter sin campo target"
    resolved = (CONTRACT_PATH.parent / m.group(1)).resolve()
    project_root = CONTRACT_PATH.resolve().parents[4]
    assert resolved == project_root / EXPECTED_TARGET, f"target inesperado: {resolved}"


def test_contrato_firma_y_secciones_y_parada():
    text = CONTRACT_PATH.read_text(encoding="utf-8")
    assert EXPECTED_SIGNATURE in text, "firma esperada no presente en el contrato"
    positions = [text.index(section) for section in EXPECTED_SECTIONS]
    assert positions == sorted(positions), "secciones en orden incorrecto"
    assert positions[0] > text.index("---", text.index("---") + 3), "secciones antes del front-matter"
    assert len(positions) == 7, "deben ser exactamente 7 secciones"
    assert STOP_PHRASE in text, "falta la frase de parada"


# ---------------------------------------------------------------------------
# Comportamiento (importa el target; skip si no existe)
# ---------------------------------------------------------------------------

RECORD = {
    "message_id": "msg-0001@example.com",
    "in_reply_to": "",
    "references": [],
    "subject": "Asunto de prueba",
    "from": "alice@example.com",
    "to": ["bob@example.com"],
    "cc": [],
}


def _load():
    try:
        import src.email.conversation_index as mod
    except ImportError:
        pytest.skip("src.email.conversation_index no existe todavía")
    return mod


def _key(record):
    try:
        from src.email.conversation import conversation_key
    except ImportError:
        pytest.skip("src.email.conversation.conversation_key no existe todavía")
    return conversation_key(record)


def _read_node(root: Path, key: str) -> str:
    return (root / "store" / "conversations" / f"{key}.md").read_text(encoding="utf-8")


def test_crea_archivo_en_ubicacion_pactada(tmp_path):
    mod = _load()
    key = _key(RECORD)
    out = mod.persist_conversation_index(str(tmp_path), RECORD, "store/emails/msg-0001.md")
    expected = tmp_path / "store" / "conversations" / f"{key}.md"
    assert expected.is_file(), "el nodo no está en root/store/conversations/<clave>.md"
    assert out == str(expected.resolve()), "debe devolver la ruta absoluta del nodo"


def test_frontmatter_type_conversation_y_clave_sha256(tmp_path):
    mod = _load()
    key = _key(RECORD)
    assert len(key) == 64 and re.fullmatch(r"[0-9a-f]{64}", key), "clave no es sha256 hex de 64"
    mod.persist_conversation_index(str(tmp_path), RECORD, "store/emails/msg-0001.md")
    text = _read_node(tmp_path, key)
    assert re.search(r"^type: Conversation$", text, re.M), "frontmatter sin 'type: Conversation'"
    assert re.search(rf"^conversation_key: {key}$", text, re.M), "frontmatter sin la clave"
    assert re.search(r"^message_count: 1$", text, re.M), "message_count incorrecto"


def test_message_path_normalizado_ordenado_y_deduplicado(tmp_path):
    mod = _load()
    key = _key(RECORD)
    mod.persist_conversation_index(str(tmp_path), RECORD, "store\\emails\\msg-0002.md")
    mod.persist_conversation_index(str(tmp_path), RECORD, "store/emails/msg-0001.md")
    mod.persist_conversation_index(str(tmp_path), RECORD, "store\\emails\\msg-0001.md")
    text = _read_node(tmp_path, key)
    body = [line for line in text.splitlines() if line.startswith("- ")]
    assert body == [
        "- store/emails/msg-0001.md",
        "- store/emails/msg-0002.md",
    ], f"cuerpo no ordenado/deduplicado/normalizado: {body}"
    assert re.search(r"^message_count: 2$", text, re.M)


def test_repeticion_idempotente(tmp_path):
    mod = _load()
    key = _key(RECORD)
    first = mod.persist_conversation_index(str(tmp_path), RECORD, "store/emails/msg-0001.md")
    before = Path(first).read_text(encoding="utf-8")
    out2 = mod.persist_conversation_index(str(tmp_path), RECORD, "store/emails/msg-0001.md")
    after = Path(out2).read_text(encoding="utf-8")
    assert before == after, "repetir la llamada cambió el nodo (no idempotente)"
    assert out2 == first, "ruta devuelta inestable entre llamadas"
    body = [line for line in after.splitlines() if line.startswith("- ")]
    assert body == ["- store/emails/msg-0001.md"], f"duplicado en el nodo: {body}"


def test_rechaza_root_invalido(tmp_path):
    mod = _load()
    with pytest.raises(ValueError):
        mod.persist_conversation_index(str(tmp_path / "no-existe"), RECORD, "store/emails/a.md")
    with pytest.raises(ValueError):
        mod.persist_conversation_index("", RECORD, "store/emails/a.md")


def test_rechaza_message_path_invalido(tmp_path):
    mod = _load()
    with pytest.raises(ValueError):
        mod.persist_conversation_index(str(tmp_path), RECORD, "")
    with pytest.raises(ValueError):
        mod.persist_conversation_index(str(tmp_path), RECORD, "   ")
    with pytest.raises(ValueError):
        mod.persist_conversation_index(str(tmp_path), RECORD, "store/emails/a\x00b.md")


def test_rechaza_record_invalido(tmp_path):
    mod = _load()
    with pytest.raises(ValueError):
        mod.persist_conversation_index(str(tmp_path), "no-dict", "store/emails/a.md")


def test_record_no_mutado_y_sin_secretos(tmp_path):
    mod = _load()
    import copy

    record = dict(RECORD)
    record["subject"] = "SECRETO-subject-x9"
    record["password"] = "pw-secret-x9"
    snapshot = copy.deepcopy(record)
    out = mod.persist_conversation_index(str(tmp_path), record, "store/emails/msg-0001.md")
    text = Path(out).read_text(encoding="utf-8")
    assert record == snapshot, "record mutado por la llamada"
    assert "SECRETO-subject-x9" not in text and "pw-secret-x9" not in text, "secretos en el nodo"
    assert "raw" not in text, "campo raw en el nodo"