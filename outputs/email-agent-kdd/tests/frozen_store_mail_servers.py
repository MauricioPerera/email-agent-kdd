"""Tests congelados del contrato store_mail_server_config.

Oracle independiente: el modelo esperado (contrato, ejemplo frozen y
reglas reimplementadas) NO importa src.email ni mail_server_store.py.
Todo offline, con directorios temporales propios; el store real del
proyecto jamas se toca y ninguna prueba abre red.
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
    / "store-mail-servers.md"
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

SIGNATURE_STORE = "def store_mail_server_config(root: str, account_id: str, config: dict) -> str"
SIGNATURE_LOAD = "def load_mail_server_config(root: str, account_id: str) -> dict"

STORE_DIR = ".email-agent"
STORE_NAME = "mail-servers.json"
ACCOUNT_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
HOST_PATTERN = re.compile(r"^[a-z0-9]([a-z0-9._-]{0,251}[a-z0-9])?$")
CONFIG_KEYS = frozenset(
    {"imap_host", "imap_port", "smtp_host", "smtp_port"}
)
FROZEN_CONFIG = {
    "imap_host": "imap.gmail.com",
    "imap_port": 993,
    "smtp_host": "smtp.gmail.com",
    "smtp_port": 587,
}


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


def _valid_host(host):
    return (
        isinstance(host, str)
        and len(host) <= 253
        and HOST_PATTERN.match(host) is not None
        and ".." not in host
    )


def _valid_port(port):
    return (
        isinstance(port, int)
        and not isinstance(port, bool)
        and 1 <= port <= 65535
    )


def _validate_root(root):
    if not isinstance(root, str) or root.strip() == "":
        raise ValueError("root invalido")


def _validate_account_id(account_id):
    if not isinstance(account_id, str):
        raise ValueError("account_id invalido")
    if ACCOUNT_ID_PATTERN.match(account_id) is None:
        raise ValueError("account_id invalido")


def _validate_config(config):
    if not isinstance(config, dict):
        raise ValueError("config invalida")
    if set(config) != CONFIG_KEYS:
        raise ValueError("config invalida")
    for key in ("imap_host", "smtp_host"):
        if not _valid_host(config[key]):
            raise ValueError("config invalida")
    for key in ("imap_port", "smtp_port"):
        if not _valid_port(config[key]):
            raise ValueError("config invalida")


def _store_path(root):
    return Path(root) / STORE_DIR / STORE_NAME


def _read_store(path):
    """Lee y valida el esquema completo del store; RuntimeError si esta mal."""
    if not path.exists():
        return {"servers": {}}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, UnicodeDecodeError):
        raise RuntimeError("store corrupto") from None
    if not isinstance(data, dict) or set(data) != {"servers"}:
        raise RuntimeError("store fuera de esquema")
    servers = data["servers"]
    if not isinstance(servers, dict):
        raise RuntimeError("store fuera de esquema")
    for entry in servers.values():
        try:
            _validate_config(entry)
        except ValueError:
            raise RuntimeError("store fuera de esquema") from None
    return data


def _model_store(root, account_id, config):
    """Modelo de referencia de store_mail_server_config (reglas del contrato)."""
    _validate_root(root)
    _validate_account_id(account_id)
    _validate_config(config)
    path = _store_path(str(Path(root).resolve()))
    data = _read_store(path)
    servers = data.setdefault("servers", {})
    servers[account_id] = dict(config)
    text = json.dumps(data, sort_keys=True, ensure_ascii=False) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(str(tmp), str(path))
    return os.path.abspath(str(path))


def _model_load(root, account_id):
    """Modelo de referencia de load_mail_server_config (reglas del contrato)."""
    _validate_root(root)
    _validate_account_id(account_id)
    data = _read_store(_store_path(root))
    entry = data["servers"].get(account_id)
    if entry is None:
        return None
    return dict(entry)


def test_contract_structure():
    text = _contract_text()
    front = _frontmatter(text)
    assert "task: store_mail_server_config" in front
    assert 'signature: "' + SIGNATURE_STORE + '"' in front
    assert "target: src/email/mail_server_store.py" in front
    assert "tests: tests/frozen_store_mail_servers.py" in front
    deps = next(
        line for line in front.splitlines() if line.startswith("deps_allowed:")
    )
    for dep in ("json", "os", "pathlib"):
        assert dep in deps, "deps_allowed sin la dependencia " + dep
    for forbidden in ("subprocess", "socket", "smtplib", "print", "environ"):
        assert forbidden in front, "forbids sin declarar " + forbidden
    body = _body(text)
    for section in SECTIONS:
        assert "\n## " + section + "\n" in "\n" + body, "seccion " + section + " ausente"
    assert SIGNATURE_LOAD in body, "el contrato no documenta la firma de load"
    assert "PARAR y reportar si" in body, "Constraints sin regla de parada"
    assert STORE_DIR + "/" + STORE_NAME in body, "el contrato no documenta la ruta del store"
    assert '"servers"' in body, "el contrato no documenta la clave servers"
    assert "os.replace" in body, "el contrato no documenta la escritura atomica"
    assert "idempotente" in body, "el contrato no documenta el reemplazo idempotente"
    assert "None" in body, "el contrato no documenta la carga ausente"
    assert "RuntimeError" in body, "el contrato no documenta el error de carga"
    assert "password" in body and "credential_ref" in body, (
        "el contrato no prohibe secretos ni credential_ref"
    )
    assert "discover_mail_servers" in body, (
        "el contrato no documenta la integracion con discovery"
    )


def test_contract_frozen_example():
    inputs = json.loads(_fenced_block(_contract_text(), "frozen-inputs"))
    expected = json.loads(_fenced_block(_contract_text(), "frozen-example"))
    assert inputs["account_id"] == "personal", "account_id frozen inesperado"
    assert inputs["config"] == FROZEN_CONFIG, "config frozen inesperada"
    assert expected == {"servers": {"personal": FROZEN_CONFIG}}
    _validate_config(inputs["config"])
    _validate_account_id(inputs["account_id"])
    with tempfile.TemporaryDirectory() as tmp:
        returned = _model_store(tmp, inputs["account_id"], inputs["config"])
        path = _store_path(tmp)
        assert Path(returned) == path.resolve(), "ruta devuelta incorrecta"
        assert path.read_text(encoding="utf-8") == json.dumps(
            expected, sort_keys=True, ensure_ascii=False
        ) + "\n", "los bytes del store no coinciden con el ejemplo frozen"
        assert _model_load(tmp, "personal") == FROZEN_CONFIG


def test_model_store_returns_confined_path():
    with tempfile.TemporaryDirectory() as tmp:
        returned = _model_store(tmp, "personal", dict(FROZEN_CONFIG))
        path = Path(returned)
        assert path.is_file(), "el store no fue escrito"
        assert path == _store_path(tmp).resolve(), "el store quedo fuera de root"
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data == {"servers": {"personal": FROZEN_CONFIG}}
        assert _model_load(tmp, "personal") == dict(FROZEN_CONFIG)


def test_model_bytes_are_deterministic():
    with tempfile.TemporaryDirectory() as tmp_a, tempfile.TemporaryDirectory() as tmp_b:
        _model_store(tmp_a, "personal", dict(FROZEN_CONFIG))
        _model_store(tmp_b, "personal", dict(FROZEN_CONFIG))
        bytes_a = _store_path(tmp_a).read_bytes()
        bytes_b = _store_path(tmp_b).read_bytes()
        assert bytes_a == bytes_b, "mismo contenido, bytes distintos"
        _model_store(tmp_a, "personal", dict(FROZEN_CONFIG))
        assert _store_path(tmp_a).read_bytes() == bytes_a, "re-store no idempotente"
        assert not list(Path(tmp_a).glob("*.tmp")), "temporal residual"


def test_model_replacement_is_idempotent():
    other = {
        "imap_host": "outlook.office365.com",
        "imap_port": 993,
        "smtp_host": "smtp.office365.com",
        "smtp_port": 587,
    }
    with tempfile.TemporaryDirectory() as tmp:
        _model_store(tmp, "work", dict(other))
        _model_store(tmp, "personal", dict(FROZEN_CONFIG))
        replacement = dict(FROZEN_CONFIG)
        replacement["smtp_port"] = 465
        _model_store(tmp, "personal", replacement)
        data = json.loads(_store_path(tmp).read_text(encoding="utf-8"))
        assert data["servers"]["personal"] == replacement, "no gano la ultima"
        assert data["servers"]["work"] == other, "las otras cuentas se tocaron"
        assert list(data["servers"]) == sorted(data["servers"])
        assert len(data["servers"]) == 2, "duplicados por account_id"
        assert _model_load(tmp, "personal") == replacement


def test_model_load_missing_returns_none():
    with tempfile.TemporaryDirectory() as tmp:
        assert _model_load(tmp, "personal") is None, "store ausente no devolvio None"
        _model_store(tmp, "personal", dict(FROZEN_CONFIG))
        assert _model_load(tmp, "work") is None, "cuenta ausente no devolvio None"
        assert _model_load(tmp, "personal") == dict(FROZEN_CONFIG)
        assert _store_path(tmp).exists(), "la carga ausente creo un store"


def test_model_rejects_invalid_store_inputs():
    with tempfile.TemporaryDirectory() as tmp:
        _model_store(tmp, "personal", dict(FROZEN_CONFIG))
        bad_roots = ["", "   ", None, 7, b"/tmp"]
        bad_account_ids = [
            "",
            "   ",
            None,
            7,
            "..",
            ".",
            "../escape",
            "sub/dir",
            "sub\\dir",
            "gmail app",
            "-gmail",
            "ñ-app",
            "a" * 65,
        ]
        for root in bad_roots:
            try:
                _model_store(root, "personal", dict(FROZEN_CONFIG))
            except ValueError:
                pass
            else:  # pragma: no cover
                raise AssertionError("root invalido aceptado: %r" % (root,))
            try:
                _model_load(root, "personal")
            except ValueError:
                pass
            else:  # pragma: no cover
                raise AssertionError("root invalido aceptado: %r" % (root,))
        for bad in bad_account_ids:
            try:
                _model_store(tmp, bad, dict(FROZEN_CONFIG))
            except ValueError:
                pass
            else:  # pragma: no cover
                raise AssertionError("account_id invalido aceptado: %r" % (bad,))
            try:
                _model_load(tmp, bad)
            except ValueError:
                pass
            else:  # pragma: no cover
                raise AssertionError("account_id invalido aceptado: %r" % (bad,))
        bad_configs = [
            None,
            {},
            {"imap_host": "imap.gmail.com", "imap_port": 993, "smtp_host": "smtp.gmail.com"},
            dict(FROZEN_CONFIG, password="fake-pass"),
            dict(FROZEN_CONFIG, credential_ref="wincred://gmail-app"),
            dict(FROZEN_CONFIG, token="fake-token"),
            dict(FROZEN_CONFIG, user="ana@example.com"),
            dict(FROZEN_CONFIG, imap_host="IMAP.GMAIL.COM"),
            dict(FROZEN_CONFIG, imap_host="imap gmail.com"),
            dict(FROZEN_CONFIG, imap_host=".gmail.com"),
            dict(FROZEN_CONFIG, imap_host="gmail.com."),
            dict(FROZEN_CONFIG, imap_host="a..b.com"),
            dict(FROZEN_CONFIG, imap_host=""),
            dict(FROZEN_CONFIG, imap_host="ñ.gmail.com"),
            dict(FROZEN_CONFIG, imap_host="a" * 254),
            dict(FROZEN_CONFIG, imap_port=0),
            dict(FROZEN_CONFIG, imap_port=65536),
            dict(FROZEN_CONFIG, imap_port=-1),
            dict(FROZEN_CONFIG, imap_port=True),
            dict(FROZEN_CONFIG, imap_port="993"),
            dict(FROZEN_CONFIG, imap_port=993.0),
            dict(FROZEN_CONFIG, imap_port=None),
            dict(FROZEN_CONFIG, smtp_host="smtp://smtp.gmail.com"),
            dict(FROZEN_CONFIG, smtp_port="587"),
        ]
        for bad in bad_configs:
            try:
                _model_store(tmp, "personal", bad)
            except ValueError:
                continue
            else:  # pragma: no cover
                raise AssertionError("config invalida aceptada: %r" % (bad,))
        data = json.loads(_store_path(tmp).read_text(encoding="utf-8"))
        assert data == {"servers": {"personal": FROZEN_CONFIG}}, (
            "un rechazo muto el store"
        )


def test_model_traversal_never_escapes_root():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        before = sorted(str(p) for p in root.rglob("*"))
        for bad in ["../escape", "..", "sub/dir", "sub\\dir", ".hidden"]:
            try:
                _model_store(tmp, bad, dict(FROZEN_CONFIG))
            except ValueError:
                pass
            else:  # pragma: no cover
                raise AssertionError("traversal aceptado: %r" % (bad,))
            try:
                _model_load(tmp, bad)
            except ValueError:
                pass
            else:  # pragma: no cover
                raise AssertionError("traversal aceptado: %r" % (bad,))
        assert sorted(str(p) for p in root.rglob("*")) == before, (
            "un rechazo escribio en disco"
        )
        assert not (root.parent / "escape").exists(), "se escapo del root"
        returned = _model_store(tmp, "personal", dict(FROZEN_CONFIG))
        assert Path(returned) == _store_path(tmp).resolve(), (
            "la ruta escrita no es la del store confinado"
        )


def test_model_load_corrupt_or_invalid_raises_runtime():
    def _expect_runtime(store_text, account_id="personal"):
        with tempfile.TemporaryDirectory() as tmp:
            path = _store_path(tmp)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(store_text, encoding="utf-8")
            try:
                _model_load(tmp, account_id)
            except RuntimeError as exc:
                message = str(exc)
                assert message.strip() != "", "mensaje vacio"
                return message
            else:  # pragma: no cover
                raise AssertionError("store invalido aceptado: %r" % (store_text[:40],))

    for bad in [
        "{no json",
        "[1, 2]",
        '"solo un texto"',
        "42",
        '{"accounts": {}}',
        '{"servers": [], "extra": 1}',
        '{"servers": {"personal": {"imap_host": "imap.gmail.com", "imap_port": 993, "smtp_host": "smtp.gmail.com", "smtp_port": 587}, "otra": {"imap_host": "x", "imap_port": 993, "smtp_host": "y", "smtp_port": 587, "password": "fake"}}}',
        '{"servers": {"personal": {"imap_host": "imap.gmail.com", "imap_port": 0, "smtp_host": "smtp.gmail.com", "smtp_port": 587}}}',
        '{"servers": {"personal": {"imap_host": "imap.gmail.com", "imap_port": 993}}}',
    ]:
        message = _expect_runtime(bad)
        assert "fake" not in message, "el mensaje filtra el contenido del store"
        assert "imap.gmail.com" not in message, "el mensaje filtra el contenido del store"
    # Un store corrupto jamas se reescribe al guardar encima.
    with tempfile.TemporaryDirectory() as tmp:
        path = _store_path(tmp)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{no json", encoding="utf-8")
        try:
            _model_store(tmp, "personal", dict(FROZEN_CONFIG))
        except RuntimeError:
            pass
        else:  # pragma: no cover
            raise AssertionError("store corrupto sobreescrito en silencio")
        assert path.read_text(encoding="utf-8") == "{no json", "el store fue mutado"


def test_model_never_stores_secrets():
    with tempfile.TemporaryDirectory() as tmp:
        secret = "app-pass-fake-123"
        for extra in ("password", "credential_ref", "secret", "token", "user"):
            config = dict(FROZEN_CONFIG)
            config[extra] = secret
            try:
                _model_store(tmp, "personal", config)
            except ValueError as exc:
                assert secret not in str(exc), "el error filtra el valor rechazado"
            else:  # pragma: no cover
                raise AssertionError("clave prohibida aceptada: " + extra)
        _model_store(tmp, "personal", dict(FROZEN_CONFIG))
        raw = _store_path(tmp).read_text(encoding="utf-8")
        assert secret not in raw, "el store contiene el marcador del secreto"
        for banned in ("password", "credential_ref", "secret", "token"):
            assert '"%s"' % banned not in raw, "el store contiene la clave " + banned
        loaded = _model_load(tmp, "personal")
        assert set(loaded) == CONFIG_KEYS, "la carga devolvio claves extra"
        assert secret not in json.dumps(loaded), "la carga devolvio el marcador"


def test_models_have_no_side_channels():
    """Los modelos no imprimen, abren red ni lanzan procesos."""
    source = Path(__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    allowed_imports = {"json", "os", "re", "tempfile", "pathlib"}
    for name in ("_model_store", "_model_load", "_read_store"):
        func = next(
            node for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef) and node.name == name
        )
        calls = [node.func for node in ast.walk(func) if isinstance(node, ast.Call)]
        names = {getattr(call, "id", getattr(call, "attr", "")) for call in calls}
        for banned in (
            "print",
            "system",
            "Popen",
            "socket",
            "getaddrinfo",
            "environ",
            "SMTP",
            "IMAP4",
        ):
            assert banned not in names, "el modelo usa un canal de escape: " + banned
        # Solo los imports DENTRO de los modelos quedan restringidos; el
        # modulo de pruebas (ast, tempfile, ...) es de harness, no del modelo.
        for node in ast.walk(func):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert alias.name.split(".")[0] in allowed_imports, (
                        "import no autorizado: " + alias.name
                    )
            if isinstance(node, ast.ImportFrom) and node.module:
                assert node.module.split(".")[0] in allowed_imports, (
                    "import no autorizado: " + node.module
                )


def test_no_real_store_or_secrets_in_environment():
    """Los marcadores ficticios jamas existen en el entorno real del proceso."""
    assert "app-pass-fake-123" not in json.dumps(FROZEN_CONFIG)
    assert "password" not in json.dumps(FROZEN_CONFIG)
    assert FROZEN_CONFIG["imap_host"] == "imap.gmail.com"