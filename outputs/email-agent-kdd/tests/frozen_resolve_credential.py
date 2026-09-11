"""Tests congelados del contrato resolve_credential.

Oracle independiente: el modelo esperado (contrato, ejemplos frozen y
reglas reimplementadas) NO importa src.email ni credentials.py, y JAMAS
toca el Windows Credential Manager real. Para wincred:// usa un DOBLE
explicito: backend falso en memoria con read(label) (backend=None PARA,
sin fallback). Todo offline: mapping ficticio inyectado, marcadores
falsos y jamas se toca os.environ.
"""

import ast
import json
import re
from pathlib import Path

CONTRACT = (
    Path(__file__).resolve().parents[1]
    / "knowledge"
    / "contracts"
    / "resolve-credential.md"
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

SIGNATURE = "def resolve_credential(credential_ref: str, environ=None) -> str"

# Marcadores ficticios: nunca son variables reales de entorno ni
# entradas reales del Credential Manager.
FAKE_NAME = "TEST_EMAIL_AGENT_API_KEY"
FAKE_SECRET = "sk-fake-123"
WINCRED_FAKE_LABEL = "gmail-app"
WINCRED_FAKE_SECRET = "app-pass-fake-123"
REF_PATTERN = re.compile(r"^env://([A-Za-z0-9_]+)$")
WINCRED_PREFIX = "wincred://"
WINCRED_LABEL_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")


class FakeBackend:
    """Doble del backend Windows: vault en memoria con read(label)."""

    def __init__(self):
        self._vault = {}
        self.calls = []

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


def _wincred_model(ref, backend=None):
    """Modelo de referencia del esquema wincred:// (reglas del contrato)."""
    if not isinstance(ref, str) or not ref.startswith(WINCRED_PREFIX):
        raise ValueError("referencia invalida")
    label = ref[len(WINCRED_PREFIX):]
    if WINCRED_LABEL_PATTERN.match(label) is None:
        raise ValueError("referencia invalida")
    if backend is None:
        raise RuntimeError("PARAR: backend real no disponible en pruebas")
    try:
        value = backend.read(label)
    except LookupError:
        raise ValueError("credencial ausente") from None
    if not isinstance(value, str) or value == "":
        raise ValueError("credencial ausente o vacia")
    return value


def _model(credential_ref, environ=None, wincred_backend=None):
    """Modelo de referencia con las reglas EXACTAS del contrato."""
    if not isinstance(credential_ref, str):
        raise ValueError("credential_ref invalida")
    if credential_ref.startswith(WINCRED_PREFIX):
        return _wincred_model(credential_ref, wincred_backend)
    match = REF_PATTERN.match(credential_ref)
    if match is None:
        raise ValueError("referencia invalida: esquemas env://NAME y wincred://LABEL")
    source = environ if environ is not None else None
    if source is None:
        import os

        source = os.environ
    value = source.get(match.group(1))
    if not isinstance(value, str) or value.strip() == "":
        raise ValueError("credencial ausente o vacia")
    return value


def test_contract_structure():
    text = _contract_text()
    front = _frontmatter(text)
    assert "task: resolve_credential" in front
    assert 'signature: "' + SIGNATURE + '"' in front
    assert "target: src/email/credentials.py" in front
    assert "tests: tests/frozen_resolve_credential.py" in front
    deps = next(
        line for line in front.splitlines() if line.startswith("deps_allowed:")
    )
    for dep in ("os", "re", "src.email.wincred"):
        assert dep in deps, "deps_allowed sin la dependencia " + dep
    for forbidden in ("print", "open", "logging", "subprocess", "socket", "urllib"):
        assert forbidden in front, "forbids sin declarar " + forbidden
    body = _body(text)
    for section in SECTIONS:
        assert "\n## " + section + "\n" in "\n" + body, "seccion " + section + " ausente"
    assert "PARAR y reportar si" in body, "Constraints sin regla de parada"
    assert "env://" in body, "el contrato no documenta la forma env://NAME"
    assert "wincred://" in body, "el contrato no documenta la forma wincred://LABEL"
    assert "Windows Credential Manager" in body, "el contrato no documenta el requisito wincred"
    assert "fallback inseguro" in body, "el contrato sin prohibicion de fallback inseguro"
    assert "resolve_windows_credential" in body, "el contrato no documenta el delegado"
    assert "monkeypatch" in body, "el contrato no documenta el doble de prueba"
    assert "JAMAS se pasa al backend Windows" in body, "el contrato no prohibe pasar environ al backend"
    assert "ValueError" in body, "el contrato no documenta el rechazo con ValueError"
    assert "os.environ" in body, "el contrato no documenta el fallback a os.environ"


def test_contract_frozen_inputs():
    ref, secret = json.loads(_fenced_block(_contract_text(), "frozen-inputs"))
    assert ref == "env://" + FAKE_NAME, "referencia frozen inesperada"
    assert secret == FAKE_SECRET, "secreto ficticio frozen inesperado"
    assert REF_PATTERN.match(ref) is not None
    assert _model(ref, {FAKE_NAME: secret}) == secret, "modelo no resuelve verbatim"


def test_contract_frozen_wincred_inputs():
    label, secret = json.loads(
        _fenced_block(_contract_text(), "frozen-inputs-wincred")
    )
    assert label == WINCRED_FAKE_LABEL, "etiqueta frozen inesperada"
    assert secret == WINCRED_FAKE_SECRET, "secreto ficticio frozen inesperado"
    assert WINCRED_LABEL_PATTERN.match(label) is not None
    backend = FakeBackend()
    backend._vault[label] = secret
    assert _model(WINCRED_PREFIX + label, wincred_backend=backend) == secret


def test_model_accepts_valid_refs():
    environ = {FAKE_NAME: FAKE_SECRET, "OTRO_FAKE_2": "v  con espacios"}
    assert _model("env://" + FAKE_NAME, environ) == FAKE_SECRET
    assert _model("env://OTRO_FAKE_2", environ) == "v  con espacios", "valor no verbatim"
    assert _model("env://" + FAKE_NAME, environ) == environ.get(FAKE_NAME)
    assert environ == {FAKE_NAME: FAKE_SECRET, "OTRO_FAKE_2": "v  con espacios"}


def test_model_accepts_valid_wincred_refs():
    backend = FakeBackend()
    for secret in [
        WINCRED_FAKE_SECRET,
        "con espacios  y   tabulados",
        "signos !@#$%^&*()",
        "unicode-fake-ñ-✓",
        "x",
    ]:
        backend._vault[WINCRED_FAKE_LABEL] = secret
        assert (
            _model(WINCRED_PREFIX + WINCRED_FAKE_LABEL, wincred_backend=backend)
            == secret
        ), "secreto no verbatim"
        assert backend.calls == [("read", WINCRED_FAKE_LABEL)], "mas de una lectura"
        backend.calls.clear()
    environ = {FAKE_NAME: FAKE_SECRET}
    _model(WINCRED_PREFIX + WINCRED_FAKE_LABEL, environ, backend)
    assert environ == {FAKE_NAME: FAKE_SECRET}, "el backend recibio environ"


def test_model_rejects_invalid_refs():
    environ = {FAKE_NAME: FAKE_SECRET}
    bad = [
        "keyring://gmail/personal",
        "file:///tmp/secret",
        "plain:" + FAKE_NAME,
        "env://",
        "env://MAL NOMBRE",
        "env://con-guion",
        "env://" + FAKE_NAME + " ",
        "ENV://" + FAKE_NAME,
        "env//missing",
        "",
        None,
        123,
    ]
    for ref in bad:
        try:
            _model(ref, environ)
        except ValueError:
            pass
        else:  # pragma: no cover
            raise AssertionError("referencia invalida aceptada: %r" % (ref,))


def test_model_rejects_malformed_wincred_refs():
    backend = FakeBackend()
    backend._vault[WINCRED_FAKE_LABEL] = WINCRED_FAKE_SECRET
    bad = [
        "wincred://",
        "wincred://gmail app",
        "wincred://gmail-app/extra",
        "wincred://gmail-app ",
        "wincred://-gmail",
        "wincred://ñ-app",
        "wincred://" + "a" * 65,
        "WINCRED://" + WINCRED_FAKE_LABEL,
        "wincred:/gmail-app",
        "wincred//missing",
        "",
        None,
        123,
    ]
    for ref in bad:
        try:
            _model(ref, wincred_backend=backend)
        except ValueError:
            pass
        else:  # pragma: no cover
            raise AssertionError("referencia malformada aceptada: %r" % (ref,))
    assert backend.calls == [], "el backend fue tocado con refs malformadas"


def test_model_rejects_missing_or_empty_values():
    try:
        _model("env://NO_EXISTE_FAKE", {})
    except ValueError:
        pass
    else:  # pragma: no cover
        raise AssertionError("variable ausente aceptada")
    for bad_value in ["", "   ", None, 5]:
        environ = {FAKE_NAME: bad_value}
        try:
            _model("env://" + FAKE_NAME, environ)
        except ValueError:
            continue
        else:  # pragma: no cover
            raise AssertionError("valor vacio o no str aceptado: %r" % (bad_value,))


def test_model_rejects_missing_wincred_values():
    backend = FakeBackend()
    try:
        _model("wincred://no-existe-fake", wincred_backend=backend)
    except ValueError:
        pass
    else:  # pragma: no cover
        raise AssertionError("credencial ausente aceptada")
    for bad_value in ["", None, 5]:
        vault = FakeBackend()
        vault._vault[WINCRED_FAKE_LABEL] = bad_value
        try:
            _model(WINCRED_PREFIX + WINCRED_FAKE_LABEL, wincred_backend=vault)
        except ValueError:
            continue
        else:  # pragma: no cover
            raise AssertionError("valor vacio o no str aceptado: %r" % (bad_value,))


def test_model_wincred_requires_backend_and_stops_without_fallback():
    try:
        _model(WINCRED_PREFIX + WINCRED_FAKE_LABEL)
    except RuntimeError as exc:
        assert "PARAR" in str(exc), "el mensaje de parada no es claro"
    else:  # pragma: no cover
        raise AssertionError("sin backend se uso un fallback inseguro")


def test_model_wincred_does_not_read_env():
    """wincred:// jamas consulta environ ni muta el mapping inyectado."""
    backend = FakeBackend()
    backend._vault[WINCRED_FAKE_LABEL] = WINCRED_FAKE_SECRET
    environ = {FAKE_NAME: FAKE_SECRET}
    assert (
        _model(WINCRED_PREFIX + WINCRED_FAKE_LABEL, environ, backend)
        == WINCRED_FAKE_SECRET
    )
    assert environ == {FAKE_NAME: FAKE_SECRET}, "el mapping inyectado fue mutado"
    assert backend.calls == [("read", WINCRED_FAKE_LABEL)]


def test_errors_never_contain_the_secret():
    fake_secret = "sk-super-secreto-ficticio-987"
    environ = {FAKE_NAME: fake_secret}
    wincred_backend = FakeBackend()
    wincred_backend._vault[WINCRED_FAKE_LABEL] = fake_secret
    cases = [
        ("keyring://gmail/personal", environ, None),
        ("env://", environ, None),
        ("env://MAL NOMBRE", environ, None),
        ("env://NO_EXISTE_FAKE", {}, None),
        ("env://" + FAKE_NAME, {FAKE_NAME: ""}, None),
        ("wincred://", environ, wincred_backend),
        ("wincred://gmail app", environ, wincred_backend),
        ("wincred://gmail-app/extra", environ, wincred_backend),
        ("wincred://no-existe-fake", environ, wincred_backend),
        (WINCRED_PREFIX + WINCRED_FAKE_LABEL, environ, FakeBackend()),
    ]
    for ref, source, backend in cases:
        try:
            _model(ref, source, backend)
        except ValueError as exc:
            message = str(exc)
            assert fake_secret not in message, "el mensaje filtra el secreto"
            assert FAKE_SECRET not in message, "el mensaje filtra el secreto frozen"
            assert WINCRED_FAKE_SECRET not in message, "el mensaje filtra el secreto wincred"
        else:  # pragma: no cover
            raise AssertionError("referencia invalida aceptada: %r" % (ref,))


def test_model_only_reads_the_injected_mapping():
    environ = {FAKE_NAME: FAKE_SECRET}
    _model("env://" + FAKE_NAME, environ)
    assert environ == {FAKE_NAME: FAKE_SECRET}, "el mapping inyectado fue mutado"
    assert FAKE_NAME not in __import__("os").environ, "el marcador ficticio existe de verdad"


def test_models_have_no_side_channels():
    """Los modelos de referencia no imprimen, abren archivos ni lanzan procesos."""
    tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
    for name in ("_model", "_wincred_model"):
        func = next(
            node for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef) and node.name == name
        )
        calls = [node.func for node in ast.walk(func) if isinstance(node, ast.Call)]
        names = {getattr(call, "id", getattr(call, "attr", "")) for call in calls}
        # "read" esta permitido: es el metodo contractual del doble (backend falso).
        for banned in ("print", "open", "write", "system", "Popen", "socket", "dump", "environ"):
            assert banned not in names, "el modelo usa un canal de escape: " + banned


def test_no_real_credential_manager_or_env_access():
    """Los marcadores ficticios jamas existen en el entorno real del proceso."""
    assert FAKE_NAME not in __import__("os").environ
    assert FAKE_SECRET not in __import__("os").environ.values()
    assert WINCRED_FAKE_LABEL not in __import__("os").environ
    assert WINCRED_FAKE_SECRET not in __import__("os").environ.values()