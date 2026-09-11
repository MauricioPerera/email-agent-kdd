"""Tests congelados del contrato store_windows_credential.

Oracle independiente: el modelo esperado (contrato, ejemplo frozen y
reglas reimplementadas) NO importa src.email ni wincred.py, y JAMAS
toca el Windows Credential Manager real. El comportamiento se verifica
contra un modelo de referencia local con un backend FALSO en memoria.
Todo offline: sin red, sin disco, sin os.environ, con secretos ficticios.
"""

import ast
import json
import re
from pathlib import Path

CONTRACT = (
    Path(__file__).resolve().parents[1]
    / "knowledge"
    / "contracts"
    / "store-windows-credential.md"
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

SIGNATURE = "def store_windows_credential(label: str, secret: str, backend=None) -> str"
SIGNATURE_RESOLVE = "def resolve_windows_credential(ref: str, backend=None) -> str"

# Marcadores ficticios: nunca existen en el Credential Manager real.
FAKE_LABEL = "gmail-app"
FAKE_SECRET = "app-pass-fake-123"
OTHER_SECRET = "otro-secreto-falso-456"
REF_PREFIX = "wincred://"
LABEL_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")


class FakeBackend:
    """Backend falso en memoria con el protocolo write/read del contrato."""

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


def _store_model(label, secret, backend=None):
    """Modelo de referencia de store con las reglas EXACTAS del contrato."""
    if not isinstance(label, str) or LABEL_PATTERN.match(label) is None:
        raise ValueError("etiqueta invalida")
    if not isinstance(secret, str) or secret == "":
        raise ValueError("secreto invalido")
    if backend is None:
        raise RuntimeError("PARAR: backend real no disponible en pruebas")
    backend.write(label, secret)
    return REF_PREFIX + label


def _resolve_model(ref, backend=None):
    """Modelo de referencia de resolve con las reglas EXACTAS del contrato."""
    if not isinstance(ref, str) or not ref.startswith(REF_PREFIX):
        raise ValueError("referencia invalida")
    label = ref[len(REF_PREFIX):]
    if LABEL_PATTERN.match(label) is None:
        raise ValueError("referencia invalida")
    if backend is None:
        raise RuntimeError("PARAR: backend real no disponible en pruebas")
    try:
        value = backend.read(label)
    except LookupError:
        raise ValueError("credencial ausente")
    if not isinstance(value, str) or value == "":
        raise ValueError("credencial ausente o vacia")
    return value


def test_contract_structure():
    text = _contract_text()
    front = _frontmatter(text)
    assert "task: store_windows_credential" in front
    assert 'signature: "' + SIGNATURE + '"' in front
    assert 'signature: "' + SIGNATURE_RESOLVE + '"' in front or SIGNATURE_RESOLVE in text
    assert "target: src/email/wincred.py" in front
    assert "tests: tests/frozen_store_windows_credential.py" in front
    assert "deps_allowed: [ctypes, re]" in front, "deps_allowed sin ctypes/re"
    for forbidden in ("print", "open", "logging", "subprocess", "socket", "cmdkey"):
        assert forbidden in front, "forbids sin declarar " + forbidden
    body = _body(text)
    for section in SECTIONS:
        assert "\n## " + section + "\n" in "\n" + body, "seccion " + section + " ausente"
    assert "PARAR y reportar si" in body, "Constraints sin regla de parada"
    assert "wincred://" in body, "el contrato no documenta la forma wincred://"
    assert "ctypes" in body, "el contrato no documenta el backend real via ctypes"
    assert "cmdkey" in body and "subprocess" in body, "el contrato no prohibe subprocess/cmdkey"
    assert "no Windows" in body, "el contrato sin la regla de sistemas no Windows"
    assert "fallback inseguro" in body, "el contrato sin prohibicion de fallback inseguro"
    assert "ValueError" in body, "el contrato no documenta el rechazo con ValueError"
    assert "### Integracion" in body, "falta la seccion de integracion con el formulario"
    assert "accounts.json" in body, "el contrato no documenta el trato de accounts.json"
    assert "formulario" in body, "el contrato no menciona el formulario local"


def test_contract_frozen_inputs():
    label, secret = json.loads(_fenced_block(_contract_text(), "frozen-inputs"))
    assert label == FAKE_LABEL, "etiqueta frozen inesperada"
    assert secret == FAKE_SECRET, "secreto ficticio frozen inesperado"
    assert LABEL_PATTERN.match(label) is not None
    backend = FakeBackend()
    ref = _store_model(label, secret, backend)
    assert ref == REF_PREFIX + label, "la ref no es wincred://<label>"
    assert secret not in ref, "la ref devuelta contiene el secreto"
    assert _resolve_model(ref, backend) == secret, "modelo no resuelve verbatim"


def test_store_returns_ref_not_secret():
    backend = FakeBackend()
    ref = _store_model(FAKE_LABEL, FAKE_SECRET, backend)
    assert ref == "wincred://" + FAKE_LABEL
    assert isinstance(ref, str) and FAKE_SECRET not in ref
    assert ref not in (FAKE_SECRET,), "store devolvio el secreto"


def test_store_rejects_invalid_labels():
    backend = FakeBackend()
    bad = [
        "",
        " gmail",
        "gmail app",
        "gmail/app",
        "gmail\\app",
        "gmail;drop",
        "-gmail",
        ".gmail",
        "gmail-app ",
        "ñ-app",
        "a" * 65,
        None,
        123,
        b"gmail-app",
    ]
    for label in bad:
        try:
            _store_model(label, FAKE_SECRET, backend)
        except ValueError:
            pass
        else:  # pragma: no cover
            raise AssertionError("etiqueta invalida aceptada: %r" % (label,))
    assert backend.calls == [], "el backend fue tocado con etiquetas invalidas"


def test_store_rejects_invalid_secrets():
    backend = FakeBackend()
    for secret in ["", None, 5, b"xyz"]:
        try:
            _store_model(FAKE_LABEL, secret, backend)
        except ValueError:
            pass
        else:  # pragma: no cover
            raise AssertionError("secreto invalido aceptado: %r" % (secret,))
    assert backend.calls == [], "el backend fue tocado con secretos invalidos"


def test_store_requires_backend_and_stops_without_fallback():
    for call in (
        lambda: _store_model(FAKE_LABEL, FAKE_SECRET),
        lambda: _resolve_model(REF_PREFIX + FAKE_LABEL),
    ):
        try:
            call()
        except RuntimeError as exc:
            assert "PARAR" in str(exc), "el mensaje de parada no es claro"
        else:  # pragma: no cover
            raise AssertionError("sin backend se uso un fallback inseguro")


def test_resolve_returns_verbatim():
    backend = FakeBackend()
    for secret in [
        FAKE_SECRET,
        "con espacios  y   tabulados",
        "signos !@#$%^&*()",
        "linea1\nlinea2",
        "unicode-fake-ñ-✓",
        "x",
    ]:
        ref = _store_model("etiqueta.con-puntos_y-guiones", secret, backend)
        assert ref == REF_PREFIX + "etiqueta.con-puntos_y-guiones"
        assert _resolve_model(ref, backend) == secret, "secreto no verbatim"
    assert backend.calls == [
        ("write", "etiqueta.con-puntos_y-guiones"),
        ("read", "etiqueta.con-puntos_y-guiones"),
    ] * 6


def test_resolve_rejects_malformed_refs():
    backend = FakeBackend()
    _store_model(FAKE_LABEL, FAKE_SECRET, backend)
    bad = [
        "env://" + FAKE_LABEL,
        "keyring://" + FAKE_LABEL,
        "file:///tmp/secret",
        "wincred:/gmail-app",
        "wincred://",
        "wincred://gmail-app/extra",
        "wincred://gmail app",
        "wincred://gmail-app ",
        "wincred://ñ-app",
        "WINCRED://" + FAKE_LABEL,
        "wincred//missing",
        "",
        None,
        123,
    ]
    for ref in bad:
        try:
            _resolve_model(ref, backend)
        except ValueError:
            pass
        else:  # pragma: no cover
            raise AssertionError("referencia malformada aceptada: %r" % (ref,))


def test_resolve_missing_label_generic_error():
    backend = FakeBackend()
    try:
        _resolve_model("wincred://no-existe-fake", backend)
    except ValueError:
        pass
    else:  # pragma: no cover
        raise AssertionError("credencial ausente aceptada")
    for bad_value in ["", 5, None]:
        vault = FakeBackend()
        vault._vault[FAKE_LABEL] = bad_value
        try:
            _resolve_model(REF_PREFIX + FAKE_LABEL, vault)
        except ValueError:
            continue
        else:  # pragma: no cover
            raise AssertionError("valor vacio o no str aceptado: %r" % (bad_value,))


def test_idempotent_store_overwrites():
    backend = FakeBackend()
    ref1 = _store_model(FAKE_LABEL, FAKE_SECRET, backend)
    ref2 = _store_model(FAKE_LABEL, OTHER_SECRET, backend)
    assert ref1 == ref2, "la ref cambio al re-guardar la misma etiqueta"
    assert ref1 == "wincred://" + FAKE_LABEL
    assert _resolve_model(ref2, backend) == OTHER_SECRET, "no gana el ultimo secreto"
    assert FAKE_SECRET not in str(backend.calls)


def test_errors_never_contain_the_secret():
    backend = FakeBackend()
    backend._vault["etiqueta.con-puntos_y-guiones"] = "sk-super-secreto-ficticio-987"
    cases = [
        ("store", ("gmail app", "sk-super-secreto-ficticio-987", backend)),
        ("store", ("gmail-app", None, backend)),
        ("resolve", ("env://GMAIL_APP_PASSWORD", backend)),
        ("resolve", ("wincred://", backend)),
        ("resolve", ("wincred://gmail-app/extra", backend)),
        ("resolve", ("wincred://no-existe-fake", backend)),
    ]
    for kind, args in cases:
        func = _store_model if kind == "store" else _resolve_model
        try:
            func(*args)
        except ValueError as exc:
            message = str(exc)
            assert "sk-super-secreto-ficticio-987" not in message, "el mensaje filtra el secreto"
            assert FAKE_SECRET not in message, "el mensaje filtra el secreto frozen"
        else:  # pragma: no cover
            raise AssertionError("entrada invalida aceptada: %r" % (args,))


def test_backend_only_used_via_write_and_read():
    backend = FakeBackend()
    ref = _store_model(FAKE_LABEL, FAKE_SECRET, backend)
    assert backend.calls == [("write", FAKE_LABEL)], "store toco el backend de mas"
    _resolve_model(ref, backend)
    assert backend.calls == [("write", FAKE_LABEL), ("read", FAKE_LABEL)]
    assert backend._vault == {FAKE_LABEL: FAKE_SECRET}


def test_models_have_no_side_channels():
    """Los modelos de referencia no imprimen, abren archivos ni lanzan procesos."""
    tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
    for name in ("_store_model", "_resolve_model"):
        func = next(
            node for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef) and node.name == name
        )
        calls = [node.func for node in ast.walk(func) if isinstance(node, ast.Call)]
        names = {getattr(call, "id", getattr(call, "attr", "")) for call in calls}
        # "write"/"read" estan permitidos: son los metodos contractuales del backend.
        for banned in ("print", "open", "system", "Popen", "socket", "dump", "environ"):
            assert banned not in names, "el modelo usa un canal de escape: " + banned


def test_no_real_credential_manager_or_env_access():
    """El marcador ficticio jamas existe en el entorno real del proceso."""
    assert FAKE_LABEL not in __import__("os").environ
    assert FAKE_SECRET not in __import__("os").environ.values()