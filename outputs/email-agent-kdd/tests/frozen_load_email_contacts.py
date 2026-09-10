# -*- coding: utf-8 -*-
"""Oracle independiente para load_email_contacts (contrato load-email-contacts).

Verifica la estructura del contrato (frontmatter, 7 secciones, frase de
parada y bloques frozen catalogados) y, cuando el target exista, el
comportamiento real contra una raiz temporal. No importa nada del target a
nivel de modulo: todas las pruebas de comportamiento obtienen la funcion via
_target(), que hace importlib.import_module y pytest.skip si el modulo o la
funcion no existen todavia.
"""
import importlib
import inspect
import json
import re

from pathlib import Path

import pytest

TARGET_MODULE = "src.email.contact_store"
TARGET_ATTR = "load_email_contacts"

CONTRACT = (
    Path(__file__).resolve().parents[1]
    / "knowledge"
    / "contracts"
    / "load-email-contacts.md"
)

STORE_NAME = "contacts.json"

# frozen-example del contrato: lista esperada al cargar el fixture del store.
FROZEN_EXPECTED = [
    {"email": "ana@example.com", "name": "Ana Garcia"},
    {"email": "bob@example.com", "name": ""},
]
# frozen-inputs del contrato: bytes exactos del fixture = JSON determinista
# UTF-8 (claves ordenadas, ensure_ascii=False) con salto de linea final,
# el mismo formato que escribe store_email_contacts (su frozen-example).
FROZEN_STORE_BYTES = (
    '{"contacts": [{"email": "ana@example.com", "name": "Ana Garcia"},'
    ' {"email": "bob@example.com", "name": ""}]}\n'
).encode("utf-8")

INVALID_ROOTS = ["", "   ", None, 123, ["tmp"]]

# Orden distinto del ascendente por email: load no reordena.
UNSORTED_FILE_ORDER = [
    {"email": "bob@example.com", "name": "Bob"},
    {"email": "ana@example.com", "name": "Ana"},
    {"email": "carla@example.com", "name": "Carla"},
]

FORBIDDEN_SOURCE_TOKENS = (
    "smtplib", "socket", "urllib", "requests", "subprocess",
    "eval(", "exec(", "password", "secret", "token",
)


def _target():
    """Devuelve la funcion target; pytest.skip si modulo o funcion faltan."""
    try:
        module = importlib.import_module(TARGET_MODULE)
    except ImportError:
        pytest.skip("falta el modulo %s" % TARGET_MODULE)
    fn = getattr(module, TARGET_ATTR, None)
    if fn is None or not callable(fn):
        pytest.skip("falta %s.%s" % (TARGET_MODULE, TARGET_ATTR))
    return fn


def _contract_text():
    return CONTRACT.read_text(encoding="utf-8")


def _fenced_block(text, label):
    match = re.search(r"```" + label + r"\n(.*?)\n```", text, re.DOTALL)
    assert match is not None, "bloque " + label + " ausente en el contrato"
    return match.group(1).strip()


def _write_store(root, raw):
    root.mkdir(parents=True, exist_ok=True)
    with open(str(root / STORE_NAME), "wb") as fh:
        fh.write(raw)


def _read_store(root):
    with open(str(root / STORE_NAME), "rb") as fh:
        return fh.read()


def test_contract_frontmatter_y_presupuestos():
    text = _contract_text()
    frontmatter = text.split("---\n", 2)[1]
    assert "task: load_email_contacts" in frontmatter
    assert "target: src/email/contact_store.py" in frontmatter
    assert 'signature: "def load_email_contacts(root: str) -> list"' in frontmatter
    assert "budget:" in frontmatter
    assert "cyclomatic_max:" in frontmatter
    assert "nesting_max:" in frontmatter
    assert "lines_max:" in frontmatter
    assert "params_max:" in frontmatter
    assert "tests: tests/frozen_load_email_contacts.py" in frontmatter
    assert "deps_allowed:" in frontmatter
    assert "forbids:" in frontmatter


def test_contract_siete_secciones_y_frase_de_parada():
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
    # Delegacion obligatoria en los helpers existentes del store.
    assert "_load_store" in text and "_validate_contact" in text


def test_contract_bloques_frozen_catalogados():
    text = _contract_text()
    example = json.loads(_fenced_block(text, "frozen-example"))
    assert example == FROZEN_EXPECTED
    # El bloque contiene el documento JSON sin el salto final; los bytes
    # vigentes que escribe store_email_contacts son bloque + "\n".
    inputs = _fenced_block(text, "frozen-inputs") + "\n"
    assert inputs.encode("utf-8") == FROZEN_STORE_BYTES
    corrupt = json.loads(_fenced_block(text, "frozen-corrupt-stores"))
    assert isinstance(corrupt, list) and corrupt
    for payload in corrupt:
        assert isinstance(payload, str)


def test_frozen_example_roundtrip_byte_a_byte(tmp_path):
    load_email_contacts = _target()
    root = tmp_path / "frozen-root"
    _write_store(root, FROZEN_STORE_BYTES)
    returned = load_email_contacts(str(root))
    assert isinstance(returned, list)
    assert returned == FROZEN_EXPECTED
    # Roundtrip: re-serializar lo cargado reproduce los mismos bytes.
    dumped = (
        json.dumps({"contacts": returned}, sort_keys=True, ensure_ascii=False)
        + "\n"
    ).encode("utf-8")
    assert dumped == FROZEN_STORE_BYTES


def test_store_ausente_devuelve_vacio_sin_side_effects(tmp_path):
    load_email_contacts = _target()
    missing = tmp_path / "no-existe"
    assert load_email_contacts(str(missing)) == []
    # Ausencia no crea ni el directorio ni el archivo.
    assert not missing.exists()
    existing = tmp_path / "vacio"
    existing.mkdir()
    assert load_email_contacts(str(existing)) == []
    assert list(p.name for p in existing.iterdir()) == []


def test_orden_preservado_como_esta_en_el_archivo(tmp_path):
    load_email_contacts = _target()
    # Fixture ya ascendente: mismo orden, mismos dicts.
    root = tmp_path / "orden-frozen"
    _write_store(root, FROZEN_STORE_BYTES)
    assert load_email_contacts(str(root)) == FROZEN_EXPECTED
    # Fixture en otro orden: se devuelve tal como esta, sin reordenar.
    other = tmp_path / "orden-otro"
    raw = json.dumps(
        {"contacts": UNSORTED_FILE_ORDER}, sort_keys=True, ensure_ascii=False
    ).encode("utf-8")
    _write_store(other, raw)
    assert load_email_contacts(str(other)) == UNSORTED_FILE_ORDER


def test_store_corrupto_lanza_runtimeerror_y_no_altera_el_archivo(tmp_path):
    load_email_contacts = _target()
    corrupt = json.loads(
        _fenced_block(_contract_text(), "frozen-corrupt-stores")
    )
    for payload in corrupt:
        root = tmp_path / "corrupto"
        _write_store(root, payload.encode("utf-8"))
        with pytest.raises(RuntimeError):
            load_email_contacts(str(root))
        # El archivo queda intacto y no queda ningun .tmp residual.
        assert _read_store(root) == payload.encode("utf-8")
        assert [p.name for p in root.iterdir()] == [STORE_NAME]


def test_raiz_invalida_lanza_valueerror(tmp_path):
    load_email_contacts = _target()
    for bad_root in INVALID_ROOTS:
        with pytest.raises(ValueError):
            load_email_contacts(bad_root)
    # La validacion ocurre antes de abrir nada: nada creado en disco.
    assert not (tmp_path / "no-existe").exists()


def test_solo_lectura_sin_escrituras_ni_red(tmp_path):
    load_email_contacts = _target()
    root = tmp_path / "solo-lectura"
    _write_store(root, FROZEN_STORE_BYTES)
    before = sorted(p.name for p in root.iterdir())
    assert load_email_contacts(str(root)) == FROZEN_EXPECTED
    after = sorted(p.name for p in root.iterdir())
    # Ningun archivo creado, borrado ni modificado por la lectura.
    assert after == before == [STORE_NAME]
    assert _read_store(root) == FROZEN_STORE_BYTES
    # El modulo del target no usa red, procesos ni secretos.
    source = inspect.getsource(importlib.import_module(TARGET_MODULE))
    for token in FORBIDDEN_SOURCE_TOKENS:
        assert token not in source, "token prohibido en el target: " + token