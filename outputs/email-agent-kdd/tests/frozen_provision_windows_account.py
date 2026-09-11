"""Tests congelados del contrato provision_windows_email_account.

Oracle independiente: el modelo esperado (contrato, ejemplo frozen y
reglas reimplementadas) NO importa src.email ni el target, y JAMAS toca
el Windows Credential Manager real: el backend FALSO es obligatorio.
Solo escribe dentro de directorios temporales propios. Todo offline,
sin red, sin servidores y con secretos ficticios.
"""

import ast
import json
import os
import re
import tempfile
from pathlib import Path

CONTRACT = (
    Path(__file__).resolve().parents[1]
    / "knowledge"
    / "contracts"
    / "provision-windows-account.md"
)

SECTIONS = [
    "Intent",
    "Interface",
    "Invariants",
    "Examples",
    "Do / Don't",
    "Tests",
    "Constraints",
]

SIGNATURE = (
    "def provision_windows_email_account(root: str, account_id: str, "
    "provider: str, email: str, label: str, secret: str, backend=None) -> dict"
)

# Marcadores ficticios: jamas existen en el Credential Manager real.
FAKE_ACCOUNT_ID = "personal"
FAKE_PROVIDER = "  Gmail  "
FAKE_EMAIL = "  Ana @ Example.COM "
FAKE_LABEL = "email-personal"
FAKE_SECRET = "app-pass-fake-123"
REF_PREFIX = "wincred://"
LABEL_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
RECORD_KEYS = ("account_id", "provider", "email", "credential_ref", "status")
PUBLIC_KEYS = ("account_id", "provider", "email", "status")


class FakeBackend:
    """Backend falso en memoria con el protocolo write/read de wincred."""

    def __init__(self):
        self._vault = {}
        self.calls = []

    def write(self, label, secret):
        self.calls.append(("write", label))
        self._vault[label] = secret

    def read(self, label):
        self.calls.append(("read", label))
        if label not in self._vault:
            raise KeyError(label)
        return self._vault[label]


class FailingBackend:
    """Backend cuyo almacenamiento seguro falla (PARAR, sin fallback)."""

    def write(self, label, secret):
        raise RuntimeError("PARAR: el almacenamiento seguro fallo")

    def read(self, label):
        raise RuntimeError("PARAR: el almacenamiento seguro fallo")


def _contract_text():
    return CONTRACT.read_text(encoding="utf-8")


def _frontmatter(text):
    return text.split("---\n", 2)[1]


def _body(text):
    return text.split("---\n", 2)[2]


def _fenced_block(text, label):
    match = re.search(r"```" + label + r"\n(.*?)\n```", text, re.DOTALL)
    assert match is not None, "bloque " + label + " ausente en el contrato"
    return match.group(1)


def _accounts_path(root):
    return Path(root) / ".email-agent" / "accounts.json"


def _store_model(label, secret, backend=None):
    """Reglas EXACTAS de store_windows_credential (contrato wincred)."""
    if not isinstance(label, str) or LABEL_PATTERN.match(label) is None:
        raise ValueError("etiqueta invalida")
    if not isinstance(secret, str) or secret == "":
        raise ValueError("secreto invalido")
    if backend is None:
        raise RuntimeError("PARAR: backend real no disponible en pruebas")
    backend.write(label, secret)
    return REF_PREFIX + label


def _create_model(account_id, provider, email, credential_ref):
    """Reglas EXACTAS de create_email_account (normalizacion documentada)."""
    for value, name in (
        (account_id, "account_id"),
        (provider, "provider"),
        (email, "email"),
        (credential_ref, "credential_ref"),
    ):
        if not isinstance(value, str) or not value.strip():
            raise ValueError(name + " invalido")
    return {
        "account_id": account_id,
        "provider": provider.strip().lower(),
        "email": "".join(email.split()).lower(),
        "credential_ref": credential_ref,
        "status": "disconnected",
    }


def _save_model(root, record):
    """Reglas EXACTAS de save_email_account sobre un root temporal."""
    if not isinstance(root, str) or not root.strip():
        raise ValueError("root invalido")
    if not isinstance(record, dict) or set(record) != set(RECORD_KEYS):
        raise ValueError("registro invalido")
    path = _accounts_path(root)
    records = []
    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
        records = [
            r for r in data["accounts"] if r["account_id"] != record["account_id"]
        ]
    records.append({key: record[key] for key in RECORD_KEYS})
    records.sort(key=lambda r: r["account_id"])
    payload = json.dumps({"accounts": records}, sort_keys=True, ensure_ascii=False)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(payload + "\n", encoding="utf-8")
    os.replace(temporary, path)
    return str(path.resolve())


def _provision_model(root, account_id, provider, email, label, secret, backend=None, log=None):
    """Modelo de referencia con el orden EXACTO del contrato."""
    if log is not None:
        log.append("validate")
    for value, name in (
        (root, "root"),
        (account_id, "account_id"),
        (provider, "provider"),
        (email, "email"),
    ):
        if not isinstance(value, str) or not value.strip():
            raise ValueError(name + " invalido")
    if log is not None:
        log.append("store")
    ref = _store_model(label, secret, backend)
    if log is not None:
        log.append("create")
    record = _create_model(account_id, provider, email, ref)
    if log is not None:
        log.append("save")
    _save_model(root, record)
    return {key: record[key] for key in PUBLIC_KEYS}


def test_contract_structure():
    text = _contract_text()
    front = _frontmatter(text)
    assert "task: provision_windows_email_account" in front
    assert 'signature: "' + SIGNATURE + '"' in front
    assert "target: src/email/provision_account.py" in front
    assert "tests: tests/frozen_provision_windows_account.py" in front
    assert "params_max: 7" in front, "budget sin params_max: 7"
    assert "deps_allowed: []" in front, "deps_allowed no es vacia"
    for forbidden in ("subprocess", "cmdkey", "socket", "print", "open", "keyring", "getpass"):
        assert forbidden in front, "forbids sin declarar " + forbidden
    body = _body(text)
    for section in SECTIONS:
        assert "\n## " + section + "\n" in "\n" + body, "seccion " + section + " ausente"
    assert "PARAR y reportar si" in body, "Constraints sin regla de parada"
    assert "store_windows_credential" in body, "sin delegacion en store_windows_credential"
    assert "create_email_account" in body, "sin delegacion en create_email_account"
    assert "save_email_account" in body, "sin delegacion en save_email_account"
    assert "wincred://" in body, "el contrato no documenta la ref wincred://"
    assert "accounts.json" in body, "el contrato no documenta accounts.json"
    assert "credential_ref" in body, "el contrato no documenta credential_ref"
    assert "formulario" in body, "el contrato no menciona el formulario local"
    assert "fallback" in body, "el contrato sin prohibicion de fallback"
    assert "ValueError" in body and "RuntimeError" in body, "faltan los errores documentados"
    assert "no-Windows" in body, "el contrato sin la regla de no-Windows"


def test_contract_frozen_inputs():
    inputs = json.loads(_fenced_block(_contract_text(), "frozen-inputs"))
    assert inputs["secret"] == FAKE_SECRET, "secreto ficticio frozen inesperado"
    assert LABEL_PATTERN.match(inputs["label"]) is not None
    expected = json.loads(_fenced_block(_contract_text(), "frozen-example"))
    backend = FakeBackend()
    with tempfile.TemporaryDirectory() as root:
        result = _provision_model(
            root,
            inputs["account_id"],
            inputs["provider"],
            inputs["email"],
            inputs["label"],
            inputs["secret"],
            backend,
        )
        text = _accounts_path(root).read_text(encoding="utf-8")
    assert result == expected, "el modelo no reproduce el ejemplo frozen"
    assert REF_PREFIX + inputs["label"] in text, "accounts.json sin la ref wincred://"
    assert inputs["secret"] not in text, "accounts.json filtra el secreto"


def test_success_returns_public_record():
    backend = FakeBackend()
    with tempfile.TemporaryDirectory() as root:
        result = _provision_model(
            root, FAKE_ACCOUNT_ID, FAKE_PROVIDER, FAKE_EMAIL, FAKE_LABEL, FAKE_SECRET, backend
        )
        other = _provision_model(
            root, FAKE_ACCOUNT_ID, FAKE_PROVIDER, FAKE_EMAIL, FAKE_LABEL, FAKE_SECRET, backend
        )
    assert set(result) == set(PUBLIC_KEYS), "el retorno no es el registro publico"
    assert result == {
        "account_id": "personal",
        "provider": "gmail",
        "email": "ana@example.com",
        "status": "disconnected",
    }
    assert "credential_ref" not in result, "el retorno expone credential_ref"
    assert result == other and result is not other, "determinismo roto"


def test_persists_ref_without_secret():
    backend = FakeBackend()
    with tempfile.TemporaryDirectory() as root:
        _provision_model(
            root, FAKE_ACCOUNT_ID, FAKE_PROVIDER, FAKE_EMAIL, FAKE_LABEL, FAKE_SECRET, backend
        )
        text = _accounts_path(root).read_text(encoding="utf-8")
    data = json.loads(text)
    records = data["accounts"]
    assert len(records) == 1, "accounts.json no tiene una sola cuenta"
    record = records[0]
    assert set(record) == set(RECORD_KEYS), "esquema del registro inesperado"
    assert record["credential_ref"] == REF_PREFIX + FAKE_LABEL, "ref wincred:// ausente"
    assert FAKE_SECRET not in text, "accounts.json filtra el secreto"


def test_delegation_order_and_single_store_call():
    backend = FakeBackend()
    log = []
    with tempfile.TemporaryDirectory() as root:
        _provision_model(
            root, FAKE_ACCOUNT_ID, FAKE_PROVIDER, FAKE_EMAIL, FAKE_LABEL, FAKE_SECRET, backend, log
        )
    assert log == ["validate", "store", "create", "save"], "orden de delegacion roto"
    assert backend.calls == [("write", FAKE_LABEL)], "store se llamo de mas o de menos"


root_ok = "root-fake"


def test_invalid_public_inputs_reject_before_side_effects():
    backend = FakeBackend()
    bad_values = ["", "  ", "\t", None, 7, b"x"]
    cases = []
    for bad in bad_values:
        cases.append((bad, FAKE_ACCOUNT_ID, FAKE_PROVIDER, FAKE_EMAIL))
        cases.append((root_ok, bad, FAKE_PROVIDER, FAKE_EMAIL))
        cases.append((root_ok, FAKE_ACCOUNT_ID, bad, FAKE_EMAIL))
        cases.append((root_ok, FAKE_ACCOUNT_ID, FAKE_PROVIDER, bad))
    for case in cases:
        with tempfile.TemporaryDirectory() as root:
            try:
                _provision_model(
                    case[0], case[1], case[2], case[3], FAKE_LABEL, FAKE_SECRET, backend
                )
            except ValueError:
                pass
            else:  # pragma: no cover
                raise AssertionError("entrada publica invalida aceptada: %r" % (case,))
            assert not _accounts_path(root).exists(), "entrada invalida escribio accounts.json"
    assert backend.calls == [], "el backend fue tocado con entradas publicas invalidas"


def test_invalid_label_or_secret_reject_before_backend():
    with tempfile.TemporaryDirectory() as root:
        backend = FakeBackend()
        bad_labels = ["", " gmail", "gmail app", "-x", "ñ-app", "a" * 65, None, 123]
        bad_secrets = ["", None, 5, b"xyz"]
        for label in bad_labels:
            try:
                _provision_model(
                    root, FAKE_ACCOUNT_ID, FAKE_PROVIDER, FAKE_EMAIL, label, FAKE_SECRET, backend
                )
            except ValueError:
                pass
            else:  # pragma: no cover
                raise AssertionError("label invalido aceptado: %r" % (label,))
        for secret in bad_secrets:
            try:
                _provision_model(
                    root, FAKE_ACCOUNT_ID, FAKE_PROVIDER, FAKE_EMAIL, FAKE_LABEL, secret, backend
                )
            except ValueError:
                pass
            else:  # pragma: no cover
                raise AssertionError("secret invalido aceptado: %r" % (secret,))
        assert backend.calls == [], "el backend fue tocado con label/secret invalidos"
        assert not _accounts_path(root).exists(), "label/secret invalido escribio accounts.json"


def test_secret_never_leaks():
    backend = FakeBackend()
    with tempfile.TemporaryDirectory() as root:
        result = _provision_model(
            root, FAKE_ACCOUNT_ID, FAKE_PROVIDER, FAKE_EMAIL, FAKE_LABEL, FAKE_SECRET, backend
        )
        text = _accounts_path(root).read_text(encoding="utf-8")
    for surface in (repr(result), json.dumps(result), text):
        assert FAKE_SECRET not in surface, "el secreto filtra en una superficie"
        assert "app-pass-fake-123" not in surface
    # Errores genericos: jamas contienen el secreto.
    cases = [
        ("", FAKE_ACCOUNT_ID, FAKE_PROVIDER, FAKE_EMAIL, FAKE_LABEL, FAKE_SECRET),
        (root_ok, "", FAKE_PROVIDER, FAKE_EMAIL, FAKE_LABEL, FAKE_SECRET),
        (root_ok, FAKE_ACCOUNT_ID, FAKE_PROVIDER, FAKE_EMAIL, "e mail", FAKE_SECRET),
        (root_ok, FAKE_ACCOUNT_ID, FAKE_PROVIDER, FAKE_EMAIL, FAKE_LABEL, None),
    ]
    for case in cases:
        with tempfile.TemporaryDirectory() as root:
            try:
                _provision_model(case[0], case[1], case[2], case[3], case[4], case[5], FakeBackend())
            except ValueError as exc:
                assert FAKE_SECRET not in str(exc), "el error filtra el secreto"
            else:  # pragma: no cover
                raise AssertionError("entrada invalida aceptada: %r" % (case,))


def test_backend_failure_writes_nothing():
    with tempfile.TemporaryDirectory() as root:
        try:
            _provision_model(
                root, FAKE_ACCOUNT_ID, FAKE_PROVIDER, FAKE_EMAIL, FAKE_LABEL, FAKE_SECRET, FailingBackend()
            )
        except RuntimeError as exc:
            assert FAKE_SECRET not in str(exc), "el fallo del backend filtra el secreto"
        else:  # pragma: no cover
            raise AssertionError("fallo del almacenamiento seguro tragado")
        assert not _accounts_path(root).exists(), "fallo del backend escribio accounts.json"
        assert not (Path(root) / ".email-agent").exists(), "fallo del backend creo el store"


def test_backend_none_propagates_windows_limitation():
    with tempfile.TemporaryDirectory() as root:
        try:
            _provision_model(
                root, FAKE_ACCOUNT_ID, FAKE_PROVIDER, FAKE_EMAIL, FAKE_LABEL, FAKE_SECRET, None
            )
        except RuntimeError as exc:
            assert "PARAR" in str(exc), "la PARADA de no-Windows no es clara"
        else:  # pragma: no cover
            raise AssertionError("backend=None uso un fallback inseguro")
        assert not _accounts_path(root).exists(), "backend=None escribio accounts.json"


def test_reprovision_replaces_record():
    backend = FakeBackend()
    with tempfile.TemporaryDirectory() as root:
        first = _provision_model(
            root, FAKE_ACCOUNT_ID, FAKE_PROVIDER, FAKE_EMAIL, FAKE_LABEL, FAKE_SECRET, backend
        )
        second = _provision_model(
            root, FAKE_ACCOUNT_ID, "Outlook", "otra@example.com", FAKE_LABEL, FAKE_SECRET, backend
        )
        data = json.loads(_accounts_path(root).read_text(encoding="utf-8"))
    assert second == {
        "account_id": "personal",
        "provider": "outlook",
        "email": "otra@example.com",
        "status": "disconnected",
    }
    assert len(data["accounts"]) == 1, "reprovisionar duplico la cuenta"
    assert data["accounts"][0]["credential_ref"] == REF_PREFIX + FAKE_LABEL
    assert data["accounts"][0]["email"] == "otra@example.com"
    assert backend.calls == [("write", FAKE_LABEL), ("write", FAKE_LABEL)]


def test_models_have_no_side_channels():
    """El modelo de provision no imprime, abre archivos ni lanza procesos."""
    tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
    func = next(
        node for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == "_provision_model"
    )
    calls = [node.func for node in ast.walk(func) if isinstance(node, ast.Call)]
    names = {getattr(call, "id", getattr(call, "attr", "")) for call in calls}
    for banned in ("print", "open", "system", "Popen", "socket", "environ"):
        assert banned not in names, "el modelo usa un canal de escape: " + banned


def test_no_secret_in_process_environment():
    """El marcador ficticio jamas existe en el entorno real del proceso."""
    assert FAKE_SECRET not in os.environ.values()
    assert FAKE_LABEL not in os.environ