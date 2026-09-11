"""Oráculo congelado para el contrato outputs/email-agent-kdd/knowledge/contracts/persist-topic-index.md.

Independiente: no importa el target para validar el contrato; si el target existe en disco,
ejecuta los tests de comportamiento inyectando `extract_topics` (sin red).
"""

import importlib
import re
import sys
from pathlib import Path

import pytest

TARGET = Path(__file__).resolve().parents[3] / "src" / "email" / "topic_index.py"
CONTRACT = Path(__file__).resolve().parents[1] / "knowledge" / "contracts" / "persist-topic-index.md"
REPO_ROOT = TARGET.parents[2]
SECTIONS = {
    "## Intent",
    "## Interface",
    "## Invariants",
    "## Examples",
    "## Do / Don't",
    "## Tests",
    "## Constraints",
}


def _frontmatter(text):
    body = text.lstrip("\ufeff")
    assert body.startswith("---\n")
    return body.split("\n---\n", 1)[0][4:]


def _load_target():
    if not TARGET.exists():
        pytest.skip(f"target ausente: {TARGET}")
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    try:
        return importlib.import_module("src.email.topic_index")
    except Exception as exc:  # paquete `src` o dependencias del target no resolubles
        pytest.skip(f"target no importable ({exc})")


def _node_text(topic, paths):
    entries = sorted(set(paths))
    head = f"---\ntype: Topic\ntopic: {topic}\nmessage_count: {len(entries)}\n---\n"
    return head + "".join(f"- {p}\n" for p in entries)


def _node(root, topic):
    return Path(root) / "store" / "topics" / f"{topic}.md"


# --------------------------------------------------------------------------- contrato


def test_contrato_frontmatter_target_firma():
    text = CONTRACT.read_text(encoding="utf-8")
    fm = {}
    for line in _frontmatter(text).splitlines():
        if ": " in line:
            key, value = line.split(": ", 1)
            fm[key.strip()] = value.strip()
    assert fm.get("task") == "persist-topic-index"
    assert fm.get("language") == "python"
    assert fm.get("tests_frozen") is not None
    resolved = (CONTRACT.parent / fm["target"]).resolve()
    assert resolved == TARGET
    signature = fm["signature"].strip().strip('"')
    assert re.fullmatch(
        r"def persist_topic_index\(root: str, record: dict, message_path: str\) -> int",
        signature,
    )


def test_contrato_siete_secciones_y_parar():
    text = CONTRACT.read_text(encoding="utf-8")
    assert len(SECTIONS) == 7
    assert SECTIONS <= set(text.splitlines())
    assert "## PARAR y reportar si" in text
    assert "PARAR y reportar si" in text


# ----------------------------------------------------------------------- comportamiento


@pytest.fixture
def target():
    return _load_target()


@pytest.fixture
def patch_topics(monkeypatch, target):
    try:
        topics_mod = importlib.import_module("src.email.topics")
    except Exception:
        topics_mod = None

    def install(returned):
        stub = lambda record: list(returned)  # noqa: E731
        patched = False
        if topics_mod is not None and hasattr(topics_mod, "extract_topics"):
            monkeypatch.setattr(topics_mod, "extract_topics", stub)
            patched = True
        if hasattr(target, "extract_topics"):
            monkeypatch.setattr(target, "extract_topics", stub)
            patched = True
        if not patched:
            pytest.skip("no se puede inyectar extract_topics")

    return install


def test_persistir_un_tema_frontmatter(tmp_path, target, patch_topics):
    patch_topics(["factura"])
    n = target.persist_topic_index(str(tmp_path), {"subject": "x"}, "store/emails/msg-0001.md")
    assert n == 1
    node = _node(tmp_path, "factura")
    assert node.exists()
    text = node.read_text(encoding="utf-8")
    assert text == _node_text("factura", ["store/emails/msg-0001.md"])
    head = text.split("\n---\n", 1)[0]
    assert "type: Topic" in head
    assert f"topic: factura" in head
    assert "message_count: 1" in head
    assert not list((_node(tmp_path, "factura").parent).glob("*.tmp"))


def test_merge_dedupe_orden(tmp_path, target, patch_topics):
    patch_topics(["informe"])
    assert target.persist_topic_index(str(tmp_path), {"subject": "x"}, "store/emails/b.md") == 1
    assert target.persist_topic_index(str(tmp_path), {"subject": "x"}, "store/emails/a.md") == 1
    assert target.persist_topic_index(str(tmp_path), {"subject": "x"}, "store\\emails\\a.md") == 1
    node = _node(tmp_path, "informe")
    text = node.read_text(encoding="utf-8")
    assert text == _node_text("informe", ["store/emails/a.md", "store/emails/b.md"])
    assert text.count("store/emails/a.md") == 1
    assert "store\\emails" not in text


def test_idempotencia_byte_a_byte(tmp_path, target, patch_topics):
    patch_topics(["dato"])
    record = {"subject": "x"}
    first = target.persist_topic_index(str(tmp_path), record, "store/emails/a.md")
    before = _node(tmp_path, "dato").read_bytes()
    second = target.persist_topic_index(str(tmp_path), record, "store/emails/a.md")
    after = _node(tmp_path, "dato").read_bytes()
    assert first == second == 1
    assert before == after


def test_temas_inseguros_ignorados(tmp_path, target, patch_topics):
    patch_topics(["../escape", "a/b", "a\\b", "", ".".ljust(65, "x"), "ok", "ok"])
    n = target.persist_topic_index(str(tmp_path), {"subject": "x"}, "store/emails/a.md")
    assert n == 1
    topics_dir = _node(tmp_path, "ok").parent
    assert sorted(p.name for p in topics_dir.glob("*.md")) == ["ok.md"]
    assert (_node(tmp_path, "ok").read_text(encoding="utf-8")).count("- store/emails/a.md") == 1


def test_root_y_message_path_invalidos_rechazados(tmp_path, target, patch_topics):
    patch_topics(["dato"])
    persist = target.persist_topic_index
    record = {"subject": "x"}
    with pytest.raises(ValueError):
        persist("no-existe-directorio", record, "store/emails/a.md")
    with pytest.raises(ValueError):
        persist(str(tmp_path), "no-dict", "store/emails/a.md")
    with pytest.raises(ValueError):
        persist(str(tmp_path), record, "")
    with pytest.raises(ValueError):
        persist(str(tmp_path), record, "   ")
    with pytest.raises(ValueError):
        persist(str(tmp_path), record, "a\x00b.md")
    assert not (_node(tmp_path, "dato").parent).exists()


def test_record_no_mutado_y_sin_secretos(tmp_path, target, patch_topics):
    patch_topics(["factura"])
    record = {"subject": "x", "body": "SECRETO-xyz", "password": "hunter2"}
    snapshot = repr(record)
    n = target.persist_topic_index(str(tmp_path), record, "store/emails/msg-0001.md")
    assert n == 1
    assert repr(record) == snapshot
    text = _node(tmp_path, "factura").read_text(encoding="utf-8")
    assert "SECRETO-xyz" not in text
    assert "hunter2" not in text
    assert "subject" not in text
