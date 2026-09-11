"""Tests congelados del contrato persist_email_okf_at.

Oracle independiente: no importa src.email. La parte de referencia renderiza
el nodo OKF desde el frozen-example del contrato; los casos de comportamiento
contra el target se activan solo cuando el target existe en disco.
"""

from pathlib import Path
import importlib.util
import re
import tempfile

import pytest

CONTRACT = (
    Path(__file__).resolve().parents[1]
    / "knowledge"
    / "contracts"
    / "persist-email-okf-at.md"
)
TARGET = (
    Path(__file__).resolve().parents[3] / "src" / "email" / "persist_at.py"
)

FROZEN_RECORD = {
    "account_id": "personal",
    "headers": {},
    "subject": "Hola",
    "from": "Ana Garcia <ana@example.com>",
    "to": "user@example.com",
    "date": "",
    "body": "Hola desde el MVP.\n",
    "attachments": [],
    "raw_sha256": "33399744d24298f2a37e46f7a04758ee47549ecf83f36310278583703d483337",
    "raw": b"raw-bytes-nunca-escritos",
}

# Registro con destinatario real de entrega: la linea delivered_to se emite
# solo si la clave existe (compatibilidad con nodos ya persistidos). Las
# direcciones van verbatim, sin canonicalizar variantes de puntos/+tag.
FROZEN_RECORD_DELIVERED = {
    **FROZEN_RECORD,
    "delivered_to": ["user+newsletters@example.com", "user@example.com"],
}


def _contract_text():
    return CONTRACT.read_text(encoding="utf-8")


def _fenced_block(text, label):
    match = re.search(
        r"```" + label + r"\n(.*?)\n```", text, re.DOTALL
    )
    assert match is not None, "bloque " + label + " ausente en el contrato"
    return match.group(1)


# ---------------------------------------------------------------------------
# Oraculo de referencia: renderiza el nodo OKF sin tocar el target.
# ---------------------------------------------------------------------------


def _scalar(value):
    if value is None or value == "":
        return '""'
    return str(value)


def _render_expected(record):
    lines = ["---"]
    for label, key in (
        ("type", None),
        ("account_id", "account_id"),
        ("subject", "subject"),
        ("from", "from"),
        ("to", "to"),
        ("date", "date"),
        ("raw_sha256", "raw_sha256"),
    ):
        if label == "type":
            lines.append("type: Email Message")
        else:
            lines.append(label + ": " + _scalar(record.get(key)))
        # delivered_to: solo si la clave trae lista no vacia; direcciones
        # verbatim unidas por ", ", SIN canonicalizar, inmediatamente tras `to`.
        if label == "to":
            delivered = record.get("delivered_to")
            if delivered:
                lines.append(
                    "delivered_to: " + ", ".join(str(addr) for addr in delivered)
                )
    if record.get("attachments"):
        lines.append("attachments:")
        for attachment in record["attachments"]:
            lines.append("  - " + _scalar(attachment.get("sha256", "")))
    return "\n".join(lines) + "\n---\n" + record["body"]


# ---------------------------------------------------------------------------
# Estructura del contrato.
# ---------------------------------------------------------------------------


def test_contract_frontmatter_and_budgets():
    text = _contract_text()
    frontmatter = text.split("---\n", 2)[1]
    assert "task: persist_email_okf_at" in frontmatter
    assert (
        "signature: \"def persist_email_okf_at(record: dict, root: str, rel_path: str) -> str\""
        in frontmatter
    )
    assert "cyclomatic_max:" in frontmatter
    assert "nesting_max:" in frontmatter
    assert "lines_max:" in frontmatter
    assert "params_max:" in frontmatter
    assert "deps_allowed:" in frontmatter
    assert "forbids:" in frontmatter


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


def test_contract_declares_root_and_relpath_rules():
    text = _contract_text()
    assert "str` no vac" in text or "str` no vacio" in text, "raiz no vacia no declarada"
    assert "ValueError" in text, "el contrato no declara rechazo con ValueError"
    assert "OSError" in text, "el contrato no declara conflicto con OSError"
    assert "atomica" in text or "atómica" in text, "escritura atomica no declarada"
    assert "LF" in text, "saltos LF no declarados"
    assert "idempotente" in text or "idempotencia" in text, "idempotencia no declarada"


def test_frozen_example_frontmatter_and_body():
    node = _fenced_block(_contract_text(), "frozen-example")
    node_frontmatter = node.split("---\n", 2)[1]
    assert "type: Email Message" in node_frontmatter
    assert "account_id: personal" in node_frontmatter
    assert (
        "raw_sha256: 33399744d24298f2a37e46f7a04758ee47549ecf83f36310278583703d483337"
        in node_frontmatter
    )
    assert node.split("---\n", 2)[2] == "Hola desde el MVP.\n"
    # El oraculo independiente coincide byte a byte con el frozen-example.
    assert _render_expected(FROZEN_RECORD) == node


def test_frozen_example_rejects_unsafe_paths():
    text = _contract_text()
    unsafe = eval(  # noqa: S307 - contenido propio del contrato congelado
        _fenced_block(text, "frozen-unsafe-paths")
    )
    assert unsafe, "lista de rutas inseguras vacia"
    for path in unsafe:
        assert (
            ".." in path.replace("\\", "/").split("/")
            or path.startswith(("/", "C:\\", "~"))
        ), "ruta insegura mal catalogada: " + path


# ---------------------------------------------------------------------------
# Casos de comportamiento contra el target (solo cuando existe).
# ---------------------------------------------------------------------------


def _load_target():
    if not TARGET.exists():
        return None
    spec = importlib.util.spec_from_file_location(
        "target_persist_email_okf_at", TARGET
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _target():
    module = _load_target()
    if module is None:
        pytest.skip(
            "target no implementado todavia: este archivo es contrato/oraculo"
        )
    if not hasattr(module, "persist_email_okf_at"):
        pytest.skip("target sin persist_email_okf_at")
    return module.persist_email_okf_at


def test_target_rejects_empty_root():
    persist = _target()
    for bad_root in ("", "   "):
        with pytest.raises(ValueError):
            persist(FROZEN_RECORD, bad_root, "emails/msg.md")


def test_target_rejects_bad_record():
    persist = _target()
    with pytest.raises(ValueError):
        persist({}, tempfile.gettempdir(), "emails/msg.md")


def test_target_rejects_unsafe_relpaths():
    persist = _target()
    unsafe = eval(  # noqa: S307 - contenido propio del contrato congelado
        _fenced_block(_contract_text(), "frozen-unsafe-paths")
    )
    with tempfile.TemporaryDirectory() as tmp:
        for rel_path in unsafe:
            with pytest.raises(ValueError):
                persist(FROZEN_RECORD, tmp, rel_path)
        # Nada fue escrito fuera de raiz durante los rechazos.
        assert list(Path(tmp).rglob("*")) == [], "escritura parcial tras rechazo"


def test_target_writes_frozen_example_with_lf_and_creates_parents():
    persist = _target()
    with tempfile.TemporaryDirectory() as tmp:
        root = str(Path(tmp) / "store")
        returned = persist(FROZEN_RECORD, root, "emails/msg-0001.md")
        node = Path(returned)
        assert node.is_absolute(), "la ruta devuelta no es absoluta"
        assert Path(root).resolve() in node.resolve().parents, (
            "el nodo quedo fuera de la raiz permitida"
        )
        expected = _render_expected(FROZEN_RECORD)
        assert node.read_bytes() == expected.encode("utf-8")
        assert b"\r" not in node.read_bytes(), "saltos no son LF puros"
        assert list(Path(root).glob("**/*.tmp")) == [], "tmp remanente tras escritura"


def test_target_is_idempotent():
    persist = _target()
    with tempfile.TemporaryDirectory() as tmp:
        root = str(Path(tmp) / "store")
        first = persist(FROZEN_RECORD, root, "emails/msg.md")
        second = persist(FROZEN_RECORD, root, "emails/msg.md")
        assert first == second, "idempotencia: rutas distintas"
        assert Path(first).read_bytes() == _render_expected(FROZEN_RECORD).encode(
            "utf-8"
        )


def test_target_writes_delivered_to_line_after_to_verbatim():
    persist = _target()
    with tempfile.TemporaryDirectory() as tmp:
        root = str(Path(tmp) / "store")
        returned = persist(FROZEN_RECORD_DELIVERED, root, "emails/msg-d.md")
        content = Path(returned).read_text(encoding="utf-8")
        assert content == _render_expected(FROZEN_RECORD_DELIVERED)
        # La linea va despues de `to` y las direcciones van verbatim.
        frontmatter = content.split("---\n", 2)[1]
        lines = frontmatter.splitlines()
        to_index = lines.index("to: user@example.com")
        assert lines[to_index + 1] == (
            "delivered_to: user+newsletters@example.com, user@example.com"
        )


def test_target_omits_delivered_to_line_without_key():
    persist = _target()
    with tempfile.TemporaryDirectory() as tmp:
        root = str(Path(tmp) / "store")
        returned = persist(FROZEN_RECORD, root, "emails/msg-s.md")
        content = Path(returned).read_text(encoding="utf-8")
        assert "delivered_to" not in content, (
            "sin clave delivered_to el nodo se renderiza igual que antes"
        )


def test_target_conflict_is_atomic():
    persist = _target()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "store"
        target = root / "emails" / "msg.md"
        target.parent.mkdir(parents=True)
        target.write_text("contenido previo distinto\n", encoding="utf-8")
        with pytest.raises(OSError):
            persist(FROZEN_RECORD, str(root), "emails/msg.md")
        assert target.read_text(encoding="utf-8") == "contenido previo distinto\n", (
            "el destino existente fue alterado en el conflicto"
        )
        assert list(root.glob("**/*.tmp")) == [], "tmp remanente tras conflicto"