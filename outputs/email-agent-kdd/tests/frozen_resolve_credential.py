"""Tests congelados del contrato resolve_credential.

Oracle independiente: el modelo esperado (contrato, ejemplo frozen y
reglas reimplementadas) NO importa src.email ni credentials.py. El target
aun no existe; el comportamiento se verifica contra un modelo de
referencia local construido con las reglas del contrato. Todo offline:
mapping ficticio inyectado, marcadores falsos y jamas se toca os.environ.
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

# Marcadores ficticios: nunca son variables reales de entorno.
FAKE_NAME = "TEST_EMAIL_AGENT_API_KEY"
FAKE_SECRET = "sk-fake-123"
REF_PATTERN = re.compile(r"^env://([A-Za-z0-9_]+)$")


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


def _model(credential_ref, environ=None):
    """Modelo de referencia con las reglas EXACTAS del contrato."""
    if not isinstance(credential_ref, str):
        raise ValueError("credential_ref invalida")
    match = REF_PATTERN.match(credential_ref)
    if match is None:
        raise ValueError("credencial invalida")
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
    for dep in ("deps_allowed: [os, re]",):
        assert dep in front, "deps_allowed sin las dependencias declaradas"
    for forbidden in ("print", "open", "logging", "subprocess", "socket", "urllib"):
        assert forbidden in front, "forbids sin declarar " + forbidden
    body = _body(text)
    for section in SECTIONS:
        assert "\n## " + section + "\n" in "\n" + body, "seccion " + section + " ausente"
    assert "PARAR y reportar si" in body, "Constraints sin regla de parada"
    assert "env://" in body, "el contrato no documenta la forma env://NAME"
    assert "ValueError" in body, "el contrato no documenta el rechazo con ValueError"
    assert "os.environ" in body, "el contrato no documenta el fallback a os.environ"


def test_contract_frozen_inputs():
    ref, secret = json.loads(_fenced_block(_contract_text(), "frozen-inputs"))
    assert ref == "env://" + FAKE_NAME, "referencia frozen inesperada"
    assert secret == FAKE_SECRET, "secreto ficticio frozen inesperado"
    assert REF_PATTERN.match(ref) is not None
    assert _model(ref, {FAKE_NAME: secret}) == secret, "modelo no resuelve verbatim"


def test_model_accepts_valid_refs():
    environ = {FAKE_NAME: FAKE_SECRET, "OTRO_FAKE_2": "v  con espacios"}
    assert _model("env://" + FAKE_NAME, environ) == FAKE_SECRET
    assert _model("env://OTRO_FAKE_2", environ) == "v  con espacios", "valor no verbatim"
    assert _model("env://" + FAKE_NAME, environ) == environ.get(FAKE_NAME)
    assert environ == {FAKE_NAME: FAKE_SECRET, "OTRO_FAKE_2": "v  con espacios"}


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


def test_errors_never_contain_the_secret():
    fake_secret = "sk-super-secreto-ficticio-987"
    environ = {FAKE_NAME: fake_secret}
    cases = [
        ("keyring://gmail/personal", environ),
        ("env://", environ),
        ("env://MAL NOMBRE", environ),
        ("env://NO_EXISTE_FAKE", {}),
        ("env://" + FAKE_NAME, {FAKE_NAME: ""}),
    ]
    for ref, source in cases:
        try:
            _model(ref, source)
        except ValueError as exc:
            message = str(exc)
            assert fake_secret not in message, "el mensaje filtra el secreto"
        else:  # pragma: no cover
            raise AssertionError("referencia invalida aceptada: %r" % (ref,))


def test_model_only_reads_the_injected_mapping():
    environ = {FAKE_NAME: FAKE_SECRET}
    _model("env://" + FAKE_NAME, environ)
    assert environ == {FAKE_NAME: FAKE_SECRET}, "el mapping inyectado fue mutado"
    assert FAKE_NAME not in __import__("os").environ, "el marcador ficticio existe de verdad"


def test_model_has_no_side_channels():
    """El modelo de referencia no imprime, abre archivos ni lanza procesos."""
    tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
    func = next(
        node for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == "_model"
    )
    calls = [node.func for node in ast.walk(func) if isinstance(node, ast.Call)]
    names = {getattr(call, "id", getattr(call, "attr", "")) for call in calls}
    for banned in ("print", "open", "write", "system", "Popen", "socket", "dump"):
        assert banned not in names, "el modelo usa un canal de escape: " + banned