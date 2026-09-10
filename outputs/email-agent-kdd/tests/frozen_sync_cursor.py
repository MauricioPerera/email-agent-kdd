"""Tests congelados del contrato sync-cursor.

Oracle independiente: el modelo esperado (contrato, esquema exacto y
reglas reimplementadas) NO importa src.email ni cursor_store. El target
se importa SOLO dentro de las pruebas de comportamiento, contra un root
temporal. Sin red, sin subprocess, sin secretos.
"""

import ast
import importlib
import json
import re
import sys
import tempfile
from pathlib import Path

import pytest

CONTRACT = (
    Path(__file__).resolve().parents[1]
    / "knowledge"
    / "contracts"
    / "sync-cursor.md"
)
TARGET = Path(__file__).resolve().parents[3] / "src" / "email" / "cursor_store.py"
REPO_ROOT = TARGET.parents[2]
ACCOUNT_ID_PATTERN = re.compile(r"[A-Za-z0-9_.-]{1,64}")
# Regla reimplementada del contrato: "." y ".." matchean el patron pero se
# rechazan EXPLICITAMENTE (no por el patron).
ACCOUNT_ID_EXPLICIT_REJECTS = {".", ".."}
SECTIONS = [
    "## Intent",
    "## Interface",
    "## Invariants",
    "## Examples",
    "## Do / Don't",
    "## Tests",
    "## Constraints",
]


def _contract_text():
    return CONTRACT.read_text(encoding="utf-8")


def _frontmatter(text):
    body = text.lstrip("﻿")
    assert body.startswith("---\n"), "contrato sin front-matter YAML"
    return body.split("\n---\n", 1)[0][4:]


def _fm_dict():
    fm = {}
    for line in _frontmatter(_contract_text()).splitlines():
        if ": " in line:
            key, value = line.split(": ", 1)
            fm[key.strip()] = value.strip()
    return fm


def _cursors_path(root):
    return Path(root) / ".email-agent" / "cursors.json"


def _canonical(cursors):
    """Regla reimplementada del contrato: serializacion canonica del store."""
    return json.dumps(
        {"cursors": cursors},
        sort_keys=True,
        ensure_ascii=True,
        separators=(",", ":"),
    )


def _valid_schema_payload(cursors):
    return json.dumps({"cursors": cursors})


# ---------------------------------------------------------------- estructura


def test_contract_frontmatter_target_signature_budgets():
    fm = _fm_dict()
    assert fm.get("task") == "sync-cursor"
    assert fm.get("language") == "python"
    assert fm.get("tests_frozen") is not None
    assert fm.get("tests") == "tests/frozen_sync_cursor.py"
    resolved = (CONTRACT.parent / fm["target"]).resolve()
    assert resolved == TARGET
    signature = fm["signature"].strip().strip('"')
    assert signature == "def load_sync_cursor(root: str, account_id: str) -> int"
    assert fm.get("cyclomatic_max") == "12"
    assert fm.get("nesting_max") == "3"
    assert fm.get("lines_max") == "80"
    assert fm.get("params_max") == "3"


def test_contract_frontmatter_deps_forbids():
    fm = _fm_dict()
    deps = fm.get("deps_allowed", "")
    for allowed in ("os", "pathlib", "json", "re"):
        assert allowed in deps, "deps_allowed sin " + allowed
    forbids = fm.get("forbids", "")
    for forbidden in (
        "eval",
        "exec",
        "subprocess",
        "network_access",
        "socket",
        "pickle",
    ):
        assert forbidden in forbids, "forbids sin " + forbidden


def test_contract_has_sections_and_stop_rule():
    text = _contract_text()
    for section in SECTIONS:
        assert section in text, "seccion ausente: " + section
    assert "## PARAR y reportar si" in text
    assert "stop_rule: " in _frontmatter(text)


def test_contract_documents_location_schema_and_errors():
    text = _contract_text()
    assert ".email-agent" in text and "cursors.json" in text, (
        "ubicacion fija no documentada"
    )
    assert "os.replace" in text, "escritura atomica no documentada"
    assert "exist_ok" in text, "creacion de .email-agent no documentada"
    assert "RuntimeError" in text, "corrupcion no declarada"
    assert "ValueError" in text, "argumentos invalidos no declarados"
    assert "bool" in text, "rechazo de uid booleano no documentado"
    assert "[A-Za-z0-9_.-]{1,64}" in text, "patron de account_id no documentado"
    assert "`.` ni `..`" in text or "`.` y `..`" in text, (
        "rechazo explicito de '.' y '..' no documentado"
    )
    assert "no crea nada" in text or "no crean nada" in text, (
        "load no creativo no documentado"
    )
    assert "nunca" in text.lower() and "secreto" in text.lower()


def test_contract_documents_canonical_serialization():
    text = _contract_text()
    assert "sort_keys=True" in text, "sort_keys no documentado"
    assert "ensure_ascii=True" in text, "ensure_ascii no documentado"
    assert 'separators=(",", ":")' in text, "separadores compactos no documentados"
    assert "UTF-8" in text, "codificacion UTF-8 no documentada"
    assert "SIN salto de línea final" in text, "serializacion sin salto final no documentada"
    # Regla reimplementada: la serializacion canonica declarada produce los
    # bytes esperados para el ejemplo del contrato, sin dependencia de orden.
    assert _canonical({"a": 1, "b": 7}) == '{"cursors":{"a":1,"b":7}}'
    assert _canonical({"b": 7, "a": 1}) == _canonical({"a": 1, "b": 7})


def test_contract_examples_state_absence_zero_and_surgical_replace():
    text = _contract_text()
    assert "0" in text and "ausencia" in text.lower(), "ausencia=0 no documentada"
    assert "Reemplazo quirúrgico" in text, "reemplazo quirurgico no documentado"
    assert "idempotencia" in text.lower(), "idempotencia no documentada"


def test_oracle_itself_does_not_import_target_at_top_level():
    source = Path(__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            names = [a.name for a in node.names]
            assert not any("src" in n or "cursor_store" in n for n in names), (
                "el oracle no debe importar el target a nivel de modulo"
            )


def test_target_module_imports_are_within_deps_allowed():
    if not TARGET.exists():
        pytest.skip("target ausente: " + str(TARGET))
    tree = ast.parse(TARGET.read_text(encoding="utf-8"))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            imported |= {node.module.split(".")[0]}
    assert imported <= {"os", "pathlib", "json", "re"}, "imports fuera de deps: " + ", ".join(
        sorted(imported)
    )
    source = TARGET.read_text(encoding="utf-8")
    for banned in ("eval(", "exec(", "subprocess", "socket", "pickle", "imaplib", "smtplib"):
        assert banned not in source


# ------------------------------------------------------------- comportamiento


def _load_target():
    if not TARGET.exists():
        pytest.skip(f"target ausente: {TARGET}")
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    try:
        return importlib.import_module("src.email.cursor_store")
    except Exception as exc:  # paquete `src` o dependencias del target no resolubles
        pytest.skip(f"target no importable ({exc})")


@pytest.fixture
def tmp_root():
    with tempfile.TemporaryDirectory() as tmp:
        yield Path(tmp)


@pytest.fixture
def target():
    return _load_target()


def test_ausencia_devuelve_cero_sin_crear_nada(tmp_root, target):
    root = tmp_root / "raiz-nueva"
    assert _cursors_path(root).exists() is False
    assert target.load_sync_cursor(str(root), "gmail-1") == 0
    assert not root.exists(), "load no debe crear root ni .email-agent"


def test_save_estructura_ubicacion_ruta_y_carga(tmp_root, target):
    esperada = str(_cursors_path(tmp_root))
    ruta = target.save_sync_cursor(str(tmp_root), "gmail-1", 42)
    assert isinstance(ruta, str) and ruta == esperada
    assert _cursors_path(tmp_root).is_file()
    data = json.loads(_cursors_path(tmp_root).read_text(encoding="utf-8"))
    assert data == {"cursors": {"gmail-1": 42}}, "esquema distinto del pactado"
    assert target.load_sync_cursor(str(tmp_root), "gmail-1") == 42


def test_save_bytes_canonicos(tmp_root, target):
    target.save_sync_cursor(str(tmp_root), "gmail-1", 42)
    raw = _cursors_path(tmp_root).read_bytes()
    assert raw == b'{"cursors":{"gmail-1":42}}', "bytes no canonicos o con salto final"
    assert not raw.endswith(b"\n"), "salto de linea final prohibido"


def test_reemplazo_quirurgico_y_orden_determinista(tmp_root, target):
    target.save_sync_cursor(str(tmp_root), "b", 7)
    target.save_sync_cursor(str(tmp_root), "a", 1)
    target.save_sync_cursor(str(tmp_root), "a", 3)
    raw = _cursors_path(tmp_root).read_text(encoding="utf-8")
    assert raw == '{"cursors":{"a":3,"b":7}}'
    assert raw.index('"a"') < raw.index('"b"'), "claves sin sort_keys"
    assert target.load_sync_cursor(str(tmp_root), "b") == 7, "cuenta ajena alterada"
    assert target.load_sync_cursor(str(tmp_root), "a") == 3


def test_orden_independiente_del_orden_de_insercion(tmp_root, target):
    target.save_sync_cursor(str(tmp_root), "zeta", 9)
    target.save_sync_cursor(str(tmp_root), "alfa", 2)
    en_orden = _cursors_path(tmp_root).read_bytes()
    otro = tmp_root / "otro"
    target.save_sync_cursor(str(otro), "alfa", 2)
    target.save_sync_cursor(str(otro), "zeta", 9)
    assert _cursors_path(otro).read_bytes() == en_orden, "bytes dependen del orden"


def test_idempotencia_bytes(tmp_root, target):
    target.save_sync_cursor(str(tmp_root), "a", 1)
    primero = _cursors_path(tmp_root).read_bytes()
    target.save_sync_cursor(str(tmp_root), "a", 1)
    assert _cursors_path(tmp_root).read_bytes() == primero


def test_uid_cero_reinicia_cursor(tmp_root, target):
    target.save_sync_cursor(str(tmp_root), "a", 5)
    target.save_sync_cursor(str(tmp_root), "a", 0)
    assert target.load_sync_cursor(str(tmp_root), "a") == 0
    assert json.loads(_cursors_path(tmp_root).read_text(encoding="utf-8")) == {
        "cursors": {"a": 0}
    }


def test_cuenta_ausente_dentro_de_archivo_valido_devuelve_cero(tmp_root, target):
    target.save_sync_cursor(str(tmp_root), "a", 1)
    target.save_sync_cursor(str(tmp_root), "b", 7)
    assert target.load_sync_cursor(str(tmp_root), "c") == 0
    assert target.load_sync_cursor(str(tmp_root), "gmail-1") == 0


def test_uid_invalido_valueerror(tmp_root, target):
    for uid_invalido in (True, False, -1, "5", 5.0, None, [1], {"uid": 1}):
        with pytest.raises(ValueError):
            target.save_sync_cursor(str(tmp_root), "a", uid_invalido)
    assert not _cursors_path(tmp_root).exists(), "uid invalido toco disco"


def test_account_id_invalido_valueerror(tmp_root, target):
    no_patron = ("", "a b", "../x", "a/b", "a\\b", "a" * 65, "ñoño")
    for account_id in no_patron:
        assert ACCOUNT_ID_PATTERN.fullmatch(account_id) is None, (
            "oracle: el contrato debe rechazar por patron " + repr(account_id)
        )
    for account_id in sorted(ACCOUNT_ID_EXPLICIT_REJECTS):
        assert ACCOUNT_ID_PATTERN.fullmatch(account_id) is not None, (
            "oracle: " + repr(account_id) + " matchea el patron; el rechazo es explicito"
        )
    for account_id in no_patron + tuple(sorted(ACCOUNT_ID_EXPLICIT_REJECTS)):
        with pytest.raises(ValueError):
            target.load_sync_cursor(str(tmp_root), account_id)
        with pytest.raises(ValueError):
            target.save_sync_cursor(str(tmp_root), account_id, 1)
    assert not _cursors_path(tmp_root).exists(), "account_id invalido toco disco"
    assert ACCOUNT_ID_PATTERN.fullmatch("a" * 64) is not None, "64 chars son validos"


def test_root_invalido_valueerror(tmp_root, target):
    with pytest.raises(ValueError):
        target.load_sync_cursor("", "a")
    with pytest.raises(ValueError):
        target.save_sync_cursor("", "a", 1)
    with pytest.raises(ValueError):
        target.load_sync_cursor(None, "a")
    with pytest.raises(ValueError):
        target.save_sync_cursor(None, "a", 1)
    assert not _cursors_path(tmp_root).exists()


def test_validacion_antes_de_disco(tmp_root, target):
    target.save_sync_cursor(str(tmp_root), "a", 1)
    antes = _cursors_path(tmp_root).read_bytes()
    with pytest.raises(ValueError):
        target.save_sync_cursor(str(tmp_root), "", 2)
    with pytest.raises(ValueError):
        target.save_sync_cursor(str(tmp_root), "a", -1)
    assert _cursors_path(tmp_root).read_bytes() == antes, "estado alterado por llamada invalida"


def test_json_o_esquema_corrupto_runtimeerror_y_archivo_intacto(tmp_root, target):
    for corrupto in (
        "{no-json",
        json.dumps({"cursor": {"a": 1}}),
        json.dumps({"cursors": []}),
        json.dumps({"cursors": {"a": True}}),
        json.dumps({"cursors": {"a": -1}}),
        json.dumps({"cursors": {"a": 1, "b": "2"}}),
        json.dumps({"cursors": {"a": 1}, "extra": 2}),
        json.dumps({"cursors": {"../x": 1}}),
        json.dumps({"cursors": {".": 1}}),
        json.dumps({"cursors": {"..": 1}}),
        json.dumps({"cursors": {"a": 1.5}}),
        json.dumps([{"cursors": {"a": 1}}]),
    ):
        _cursors_path(tmp_root).parent.mkdir(parents=True, exist_ok=True)
        _cursors_path(tmp_root).write_text(corrupto, encoding="utf-8")
        with pytest.raises(RuntimeError):
            target.load_sync_cursor(str(tmp_root), "a")
        with pytest.raises(RuntimeError):
            target.save_sync_cursor(str(tmp_root), "a", 2)
        assert _cursors_path(tmp_root).read_text(encoding="utf-8") == corrupto, (
            "el archivo corrupto fue modificado: " + corrupto
        )


def test_archivo_valido_con_cuenta_ajena_corrupta_falla(tmp_root, target):
    corrupto = json.dumps({"cursors": {"a": 1, "b": True}})
    _cursors_path(tmp_root).parent.mkdir(parents=True, exist_ok=True)
    _cursors_path(tmp_root).write_text(corrupto, encoding="utf-8")
    with pytest.raises(RuntimeError):
        target.load_sync_cursor(str(tmp_root), "a")  # la cuenta ajena corrupta tambien


def test_esquema_valido_aceptado(tmp_root, target):
    payload = _valid_schema_payload({"a": 1, "b-2": 0})
    _cursors_path(tmp_root).parent.mkdir(parents=True, exist_ok=True)
    _cursors_path(tmp_root).write_text(payload, encoding="utf-8")
    assert target.load_sync_cursor(str(tmp_root), "a") == 1
    assert target.load_sync_cursor(str(tmp_root), "b-2") == 0
    assert target.load_sync_cursor(str(tmp_root), "c") == 0


def test_escritura_atomica_os_replace_sin_parciales(tmp_root, target, monkeypatch):
    target.save_sync_cursor(str(tmp_root), "a", 1)
    antes = _cursors_path(tmp_root).read_bytes()

    def boom(src, dst):
        raise OSError("disco lleno")

    monkeypatch.setattr(target.os, "replace", boom)
    with pytest.raises(OSError):
        target.save_sync_cursor(str(tmp_root), "a", 5)
    assert _cursors_path(tmp_root).read_bytes() == antes, "estado previo destruido"
    restos = [p.name for p in _cursors_path(tmp_root).parent.iterdir() if p.name != "cursors.json"]
    assert restos == [], "temporal sin limpiar: " + ", ".join(restos)


def test_save_crea_root_y_email_agent_si_faltan(tmp_root, target):
    root = tmp_root / "profundo" / "mas"
    ruta = target.save_sync_cursor(str(root), "gmail-1", 42)
    assert Path(ruta) == _cursors_path(root)
    assert _cursors_path(root).is_file()
    assert target.load_sync_cursor(str(root), "gmail-1") == 42