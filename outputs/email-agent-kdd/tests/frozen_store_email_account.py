"""Tests congelados del contrato store_email_account.

Oracle independiente: el modelo esperado (contrato, ejemplo frozen y
reglas reimplementadas) NO importa src.email ni account_store. El target
se importa SOLO dentro de las pruebas de comportamiento, contra un store
temporal. Sin red, sin secretos reales (solo referencias opacas falsas).
"""

import ast
import json
import os
import re
from pathlib import Path

CONTRACT = (
    Path(__file__).resolve().parents[1]
    / "knowledge"
    / "contracts"
    / "store-email-account.md"
)
TARGET = Path(__file__).resolve().parents[3] / "src" / "email" / "account_store.py"

RECORD_KEYS = ["account_id", "provider", "email", "credential_ref", "status"]


def _contract_text():
    return CONTRACT.read_text(encoding="utf-8")


def _frontmatter(text):
    return text.split("---\n", 2)[1]


def _fenced_block(text, label):
    match = re.search(r"```" + label + r"\n(.*?)\n```", text, re.DOTALL)
    assert match is not None, "bloque " + label + " ausente en el contrato"
    return match.group(1)


def _frozen_record():
    """Registro de ejemplo reconstruido de frozen-inputs, sin importar src."""
    account_id, provider, email, credential_ref, status = json.loads(
        _fenced_block(_contract_text(), "frozen-inputs")
    )
    return {
        "account_id": account_id,
        "provider": provider,
        "email": email,
        "credential_ref": credential_ref,
        "status": status,
    }


def _record(account_id, email="x@example.com", ref=None):
    if ref is None:
        ref = "keyring://prov/" + account_id
    return {
        "account_id": account_id,
        "provider": "gmail",
        "email": email,
        "credential_ref": ref,
        "status": "disconnected",
    }


# ---------------------------------------------------------------- estructura


def test_contract_frontmatter_budgets_deps_forbids():
    frontmatter = _frontmatter(_contract_text())
    assert "task: store_email_account" in frontmatter
    assert 'signature: "def save_email_account(root: str, account: dict) -> str"' in frontmatter
    assert "cyclomatic_max: 20" in frontmatter
    assert "nesting_max: 4" in frontmatter
    assert "lines_max: 80" in frontmatter
    assert "params_max: 5" in frontmatter
    assert "tests: tests/frozen_store_email_account.py" in frontmatter
    for allowed in ("json", "os", "pathlib"):
        assert allowed in frontmatter, "deps_allowed sin " + allowed
    for forbidden in (
        "eval",
        "exec",
        "subprocess",
        "network_access",
        "socket",
        "smtplib",
        "urllib",
        "requests",
    ):
        assert forbidden in frontmatter, "forbids sin " + forbidden


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


def test_contract_documents_exact_schema_and_atomic_write():
    text = _contract_text()
    assert "credential_ref" in text, "referencia opaca no documentada"
    assert "os.replace" in text, "escritura atomica no documentada"
    assert "ensure_ascii=False" in text
    assert "RuntimeError" in text, "corrupcion no declarada"
    assert "ValueError" in text, "rechazo de registro no declarado"
    assert "nunca" in text.lower() and "secreto" in text.lower()
    assert '"disconnected"' in text, "status inicial no documentado"
    assert "salto de linea" in text, "salto de linea final no documentado"


def test_frozen_example_is_deterministic_expected_bytes():
    """El modelo esperado: un solo objeto, lista ordenada, claves ordenadas."""
    example = _fenced_block(_contract_text(), "frozen-example")
    expected_line = example + "\n"
    data = json.loads(example)
    assert set(data) == {"accounts"}, "el store no es {accounts: [...]}"
    records = data["accounts"]
    assert len(records) == 1
    assert list(records[0]) == sorted(RECORD_KEYS), "claves sin ordenar en el ejemplo"
    assert records[0]["account_id"] == "personal"
    assert records[0]["status"] == "disconnected"
    # Regla reimplementada: json.dumps(sort_keys, ensure_ascii=False) del
    # registro debe reproducir la linea del contrato byte a byte.
    canonical = json.dumps(data, sort_keys=True, ensure_ascii=False)
    assert canonical == example, "el ejemplo frozen no es canonico"
    assert expected_line.endswith("\n") and expected_line.count("\n") == 1


def test_contract_requires_sorted_store_and_no_duplicates():
    text = _contract_text()
    assert "ordenada por `account_id`" in text or "ordenados por `account_id`" in text
    assert "REEMPLAZA" in text, "reemplazo por account_id no documentado"
    assert "archivo temporal" in text, "temporal previo al replace no documentado"
    assert "jamas incluyen el contenido" in text or "nunca" in text


def test_oracle_itself_does_not_import_target_at_top_level():
    source = Path(__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            names = [a.name for a in node.names]
            assert not any("src" in n or "account_store" in n for n in names), (
                "el oracle no debe importar el target a nivel de modulo"
            )


def test_target_module_imports_are_within_deps_allowed():
    tree = ast.parse(TARGET.read_text(encoding="utf-8"))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            imported |= {node.module.split(".")[0]}
    assert imported <= {"json", "os", "pathlib"}, "imports fuera de deps: " + ", ".join(
        sorted(imported)
    )
    source = TARGET.read_text(encoding="utf-8")
    for banned in ("smtplib", "socket", "urllib", "requests", "subprocess"):
        assert "import " + banned not in source


# ------------------------------------------------------------- comportamiento


def _target():
    from src.email import account_store

    return account_store


def _store(root):
    return Path(root) / ".email-agent" / "accounts.json"


def test_save_creates_dirs_and_returns_absolute_store_path(tmp_path):
    target = _target()
    root = tmp_path / "raiz"
    result = target.save_email_account(str(root), _record("personal"))
    assert isinstance(result, str) and Path(result).is_absolute()
    assert Path(result) == _store(root).resolve()
    assert _store(root).exists(), "accounts.json no fue escrito"


def test_save_writes_frozen_example_bytes(tmp_path):
    target = _target()
    root = tmp_path / "raiz"
    target.save_email_account(str(root), _frozen_record())
    expected = _fenced_block(_contract_text(), "frozen-example") + "\n"
    raw = _store(root).read_bytes()
    assert raw == expected.encode("utf-8"), "bytes del store no son los frozen"


def test_save_json_is_deterministic_and_utf8_ensure_ascii_false(tmp_path):
    target = _target()
    root_a = tmp_path / "a"
    root_b = tmp_path / "b"
    record = _record("uno", email="aña@example.com", ref="keyring://p/uno")
    target.save_email_account(str(root_a), record)
    target.save_email_account(str(root_b), record)
    raw_a = _store(root_a).read_bytes()
    assert raw_a == _store(root_b).read_bytes(), "JSON no determinista"
    assert "ñ".encode("utf-8") in raw_a, "ensure_ascii=False no respetado"
    assert "\\u00f1" not in raw_a.decode("utf-8"), "escape ascii inesperado"
    # Re-guardar el mismo registro no cambia los bytes (sin reloj ni azar).
    target.save_email_account(str(root_a), record)
    assert _store(root_a).read_bytes() == raw_a


def test_save_replaces_by_account_id_without_duplicates(tmp_path):
    target = _target()
    root = tmp_path / "raiz"
    target.save_email_account(str(root), _record("personal", ref="keyring://p/v1"))
    target.save_email_account(str(root), _record("personal", ref="keyring://p/v2"))
    loaded = target.load_email_accounts(str(root))
    assert len(loaded) == 1, "account_id duplicado en el store"
    assert loaded[0]["credential_ref"] == "keyring://p/v2", "reemplazo no aplicado"


def test_load_returns_sorted_by_account_id_regardless_of_save_order(tmp_path):
    target = _target()
    root = tmp_path / "raiz"
    target.save_email_account(str(root), _record("zulu"))
    target.save_email_account(str(root), _record("alpha"))
    target.save_email_account(str(root), _record("mike"))
    ids = [r["account_id"] for r in target.load_email_accounts(str(root))]
    assert ids == sorted(ids) == ["alpha", "mike", "zulu"], "orden incorrecto"
    on_disk = json.loads(_store(root).read_text(encoding="utf-8"))
    assert [r["account_id"] for r in on_disk["accounts"]] == ["alpha", "mike", "zulu"], (
        "orden en disco incorrecto"
    )


def test_load_round_trip_and_never_extra_keys(tmp_path):
    target = _target()
    root = tmp_path / "raiz"
    record = _record("personal")
    target.save_email_account(str(root), record)
    loaded = target.load_email_accounts(str(root))
    assert loaded == [record], "round-trip no es verbatim"
    for entry in loaded:
        assert list(entry) == RECORD_KEYS, "claves fuera del esquema devueltas"


def test_load_returns_empty_list_when_file_missing(tmp_path):
    target = _target()
    root = tmp_path / "no-existe"
    assert target.load_email_accounts(str(root)) == []
    assert not (root / ".email-agent").exists(), "load creo directorios"


def test_save_is_atomic_no_partial_or_temp_leftovers(tmp_path):
    target = _target()
    root = tmp_path / "raiz"
    target.save_email_account(str(root), _record("uno"))
    before = _store(root).read_bytes()
    # Un registro invalido NO debe tocar el store existente ni dejar .tmp.
    try:
        target.save_email_account(str(root), _record("dos", ref=""))
    except ValueError:
        pass
    else:  # pragma: no cover
        raise AssertionError("registro invalido aceptado")
    assert _store(root).read_bytes() == before, "store alterado por fallo previo"
    assert not list(_store(root).parent.glob("*.tmp")), "temporal remanente"
    target.save_email_account(str(root), _record("dos"))
    names = sorted(p.name for p in _store(root).parent.iterdir())
    assert names == ["accounts.json"], "escritura no atomica observable: " + str(names)
    assert len(json.loads(_store(root).read_text(encoding="utf-8"))["accounts"]) == 2


def test_save_rejects_invalid_root_with_valueerror():
    target = _target()
    for bad_root in ("", "   ", None, 123, b"raiz"):
        try:
            target.save_email_account(bad_root, _record("x"))
        except ValueError:
            continue
        except Exception as exc:  # pragma: no cover
            raise AssertionError("root invalido %r lanza %r" % (bad_root, exc))
        raise AssertionError("root invalido %r aceptado" % (bad_root,))


def test_save_rejects_invalid_records_with_valueerror(tmp_path):
    target = _target()
    root = tmp_path / "raiz"
    good = _record("personal")
    target.save_email_account(str(root), good)
    before = _store(root).read_bytes()
    cases = [
        None,
        "personal",
        [],
        {},
        {**good, "password": "NUNCA-GUARDAR"},
        {**good, "secret": "x"},
        {**good, "token": "x"},
        {k: v for k, v in good.items() if k != "status"},
        {k: v for k, v in good.items() if k != "email"},
        {**good, "status": "connected"},
        {**good, "account_id": ""},
        {**good, "email": "  "},
        {**good, "provider": None},
        {**good, "credential_ref": 7},
        {**good, "account_id": b"bytes"},
    ]
    for bad in cases:
        try:
            target.save_email_account(str(root), bad)
        except ValueError:
            continue
        except Exception as exc:  # pragma: no cover
            raise AssertionError("registro invalido %r lanza %r" % (bad, exc))
        raise AssertionError("registro invalido aceptado: %r" % (bad,))
    assert _store(root).read_bytes() == before, "store mutado por rechazos"


def test_load_raises_runtimeerror_on_corrupt_or_out_of_schema_store(tmp_path):
    target = _target()
    root = tmp_path / "raiz"
    path = _store(root)
    path.parent.mkdir(parents=True)
    fake_secret = "SECRETO-FALSO-xyz"
    cases = [
        "no es json {",
        "[]",
        '{"accounts": {}}',
        '{"accounts": "uno"}',
        '{"otra": []}',
        '{"accounts": [{"account_id": "x"}]}',
        json.dumps({"accounts": [{"account_id": "x", "provider": "p", "email": "e",
                                  "credential_ref": fake_secret, "status": "connected"}]}),
        json.dumps({"accounts": [{"account_id": "x", "provider": "p", "email": "e",
                                  "credential_ref": fake_secret, "status": "disconnected",
                                  "password": fake_secret}]}),
    ]
    for index, corrupt in enumerate(cases):
        path.write_text(corrupt, encoding="utf-8")
        try:
            target.load_email_accounts(str(root))
        except RuntimeError:
            continue
        except Exception as exc:  # pragma: no cover
            raise AssertionError("caso %d lanza %r" % (index, exc))
        raise AssertionError("store corrupto %d aceptado" % index)


def test_error_messages_never_leak_store_content(tmp_path):
    target = _target()
    root = tmp_path / "raiz"
    path = _store(root)
    path.parent.mkdir(parents=True)
    fake_secret = "SECRETO-FALSO-abc123"
    path.write_text(
        json.dumps(
            {
                "accounts": [
                    {
                        "account_id": "x",
                        "provider": "p",
                        "email": "x@example.com",
                        "credential_ref": fake_secret,
                        "status": "disconnected",
                        "extra": fake_secret,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    try:
        target.load_email_accounts(str(root))
    except RuntimeError as exc:
        message = str(exc)
        assert fake_secret not in message, "mensaje filtra el contenido de la entrada"
        assert "x@example.com" not in message
    else:  # pragma: no cover
        raise AssertionError("store fuera de esquema aceptado")
    # Rechazo de registros tambien sin filtrar contenido.
    try:
        target.save_email_account(str(root), {**_record("x"), "credential_ref": fake_secret,
                                              "status": "otro"})
    except ValueError as exc:
        assert fake_secret not in str(exc)
    else:  # pragma: no cover
        raise AssertionError("status invalido aceptado")


def test_store_never_contains_secrets_or_bytes(tmp_path):
    target = _target()
    root = tmp_path / "raiz"
    record = _record("personal", email="ana@example.com")
    target.save_email_account(str(root), record)
    on_disk = json.loads(_store(root).read_text(encoding="utf-8"))
    entry = on_disk["accounts"][0]
    assert set(entry) == set(RECORD_KEYS), "claves extra en disco"
    assert all(isinstance(v, str) for v in entry.values()), "valores no str en disco"
    assert entry["credential_ref"] == record["credential_ref"], "ref alterada"
    assert "password" not in _store(root).read_text(encoding="utf-8")