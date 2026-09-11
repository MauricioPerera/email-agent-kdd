"""Tests congelados del contrato cli_account_setup_gui.

Oracle independiente: el modelo esperado (contrato, ejemplo frozen y
reglas reimplementadas) NO importa src.email, NO importa tkinter,
JAMAS abre ventanas reales, JAMAS hace DNS y JAMAS usa Credential
Manager ni secretos reales. El comportamiento se verifica contra un
modelo de referencia local con una ventana FALSA en memoria, un
discovery FALSO, una provision FALSA y un almacen de servidores FALSO.
Todo offline: sin red, sin disco, sin os.environ, con secretos
ficticios.
"""

import ast
import json
import re
from pathlib import Path

CONTRACT = (
    Path(__file__).resolve().parents[1]
    / "knowledge"
    / "contracts"
    / "cli-account-setup-gui.md"
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

SIGNATURE = "def run_account_setup_gui(root: str) -> int"

# Marcadores ficticios: nunca existen en Credential Manager ni en DNS real.
FAKE_ROOT = "<temp-oracle>"
FAKE_EMAIL = "Ana@Example.COM"
FAKE_SECRET = "app-pass-fake-123"
DERIVED_ID = "ana-example.com"
FAKE_LABEL = "email-" + DERIVED_ID
PROVIDER = "custom"
DISCOVERED = {
    "imap_host": "imap.gmail.com",
    "imap_port": 993,
    "smtp_host": "smtp.gmail.com",
    "smtp_port": 587,
}
MANUAL_SERVERS = {
    "imap_host": "imap.midominio.test",
    "imap_port": 1993,
    "smtp_host": "smtp.midominio.com",
    "smtp_port": 1587,
}
CONFIG_KEYS = ("imap_host", "imap_port", "smtp_host", "smtp_port")
LABEL_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
HOST_PATTERN = re.compile(r"^[a-z0-9]([a-z0-9._-]{0,251}[a-z0-9])?$")
PASSWORD_MASK = 'show="*"'
COMMAND = "account setup-gui ROOT"

def _stop_message(platform=None):
    """Modelo del mensaje de PARAR: el almacen nativo, nombrado por OS."""
    import sys

    system = sys.platform if platform is None else platform
    if system.startswith("win"):
        name = "Windows (Credential Manager)"
    elif system == "darwin":
        name = "macOS (Keychain)"
    elif system.startswith("linux"):
        name = "Linux (Secret Service)"
    else:
        name = "de este sistema"
    return (
        "PARAR: el almacenamiento seguro de " + name + " no esta "
        "disponible en este sistema; no existe alternativa segura"
    )
GENERIC_ERROR = "error generico: no se pudo guardar la cuenta"
EMPTY_FIELDS = "error generico: escriba su correo y su contrasena"
INCOMPLETE = "error generico: faltan datos del servidor de correo"


def derive_account_id(email: str) -> str:
    """Modelo de la derivacion congelada del account_id desde el correo."""
    local, _, domain = email.partition("@")
    safe = re.sub(r"[^a-z0-9._-]+", "-", (local + "-" + domain).lower())
    safe = re.sub(r"-{2,}", "-", safe).strip("-._")[:57].strip("-._")
    return safe or "cuenta"


class FakeWindow:
    """Ventana falsa en memoria: estado, mensajes y seccion avanzada."""

    def __init__(self):
        self.email_text = ""
        self.password_value = ""
        self.advanced_values = {
            "imap_host": "",
            "imap_port": "",
            "smtp_host": "",
            "smtp_port": "",
        }
        self.advanced_visible = False
        self.notes = []
        self.dialogs = []
        self.cleared = 0
        self.destroyed = None

    def open_advanced(self):
        self.advanced_visible = True

    def note(self, message):
        self.notes.append(message)

    def dialog(self, kind, message):
        self.dialogs.append((kind, message))

    def clear_password(self):
        self.cleared += 1
        self.password_value = ""

    def close(self, code):
        self.clear_password()
        self.destroyed = code


class FakeDiscovery:
    """Discovery falso: registra el email pedido y simula el resultado."""

    def __init__(self, result=None, exc=None):
        self.calls = []
        self.result = result
        self.exc = exc

    def __call__(self, email):
        self.calls.append(email)
        if self.exc is not None:
            raise self.exc
        return dict(self.result)


class FakeProvision:
    """Provision falsa: registra llamadas y simula exito o fallo."""

    def __init__(self, exc=None):
        self.calls = []
        self.exc = exc

    def __call__(self, root, account_id, provider, email, label, secret):
        self.calls.append(
            {
                "root": root,
                "account_id": account_id,
                "provider": provider,
                "email": email,
                "label": label,
                "secret": secret,
            }
        )
        if self.exc is not None:
            raise self.exc
        return {
            "account_id": account_id,
            "provider": provider,
            "email": email,
            "status": "disconnected",
        }


class FakeStore:
    """Almacen de servidores falso: registra llamadas o lanza."""

    def __init__(self, exc=None):
        self.calls = []
        self.exc = exc

    def __call__(self, root, account_id, config):
        self.calls.append(
            {"root": root, "account_id": account_id, "config": dict(config)}
        )
        if self.exc is not None:
            raise self.exc
        return root + "/.email-agent/mail-servers.json"


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
        host != ""
        and len(host) <= 253
        and ".." not in host
        and HOST_PATTERN.match(host) is not None
    )


def _parse_port(text):
    try:
        port = int(text.strip())
    except ValueError:
        return None
    return port if 1 <= port <= 65535 else None


class SetupModel:
    """Modelo de referencia del formulario con las reglas EXACTAS del contrato.

    La ventana, el discovery, la provision y el almacen son falsos. El
    pipeline sigue el orden congelado: campos, discovery UNA vez sin
    password, seccion avanzada como unico fallback, derivacion del id,
    UNA provision y despues UN almacen; mensajes genericos y password
    limpio en todo cierre terminal.
    """

    def __init__(self, window, discovery, provision, store, root=FAKE_ROOT):
        self.window = window
        self.discovery = discovery
        self.provision = provision
        self.store = store
        self.root = root
        self.servers = None
        self.discovery_done = False

    def _terminal(self, kind, message, code=1):
        self.window.clear_password()
        self.window.dialog(kind, message)
        self.window.close(code)

    def _read_advanced(self):
        raw = {
            "imap_host": self.window.advanced_values["imap_host"],
            "smtp_host": self.window.advanced_values["smtp_host"],
            "imap_port": self.window.advanced_values["imap_port"],
            "smtp_port": self.window.advanced_values["smtp_port"],
        }
        imap_host = raw["imap_host"].strip().lower()
        smtp_host = raw["smtp_host"].strip().lower()
        imap_port = _parse_port(raw["imap_port"])
        smtp_port = _parse_port(raw["smtp_port"])
        if (
            imap_host == ""
            or smtp_host == ""
            or imap_port is None
            or smtp_port is None
            or not _valid_host(imap_host)
            or not _valid_host(smtp_host)
        ):
            return None
        return {
            "imap_host": imap_host,
            "imap_port": imap_port,
            "smtp_host": smtp_host,
            "smtp_port": smtp_port,
        }

    def save(self):
        email = self.window.email_text.strip()
        password = self.window.password_value
        if email == "" or password == "":
            self.window.note(EMPTY_FIELDS)
            return
        if self.servers is None:
            if not self.discovery_done:
                self.discovery_done = True
                try:
                    self.servers = self.discovery(email)
                except ValueError:
                    self.window.open_advanced()
                    self.window.note(
                        "No pudimos detectar los servidores de tu correo "
                        "automaticamente; completa la seccion avanzada y "
                        "vuelve a pulsar Guardar."
                    )
                    return
                except Exception:
                    self._terminal("error", GENERIC_ERROR)
                    return
                self.window.note(
                    "Detectamos los servidores de tu correo; guardando "
                    "la cuenta..."
                )
            else:
                self.servers = self._read_advanced()
                if self.servers is None:
                    self.window.note(INCOMPLETE)
                    return
        self._provision(email)

    def _provision(self, email):
        account_id = derive_account_id(email)
        label = "email-" + account_id
        if LABEL_PATTERN.match(label) is None:
            self._terminal("error", GENERIC_ERROR)
            return
        try:
            record = self.provision(
                self.root,
                account_id,
                PROVIDER,
                email,
                label,
                self.window.password_value,
            )
        except RuntimeError:
            self._terminal("warning", _stop_message())
            return
        except Exception:
            self._terminal("error", GENERIC_ERROR)
            return
        try:
            self.store(self.root, account_id, dict(self.servers))
        except Exception:
            self._terminal("error", GENERIC_ERROR)
            return
        self._terminal(
            "info", "cuenta guardada: " + record["account_id"], code=0
        )

    def cancel(self):
        self.window.clear_password()
        self.window.close(1)


# --------------------------------------------------------------------------
# Estructura del contrato
# --------------------------------------------------------------------------


def test_contract_structure():
    text = _contract_text()
    front = _frontmatter(text)
    assert "task: cli_account_setup_gui" in front
    assert 'signature: "' + SIGNATURE + '"' in front
    assert "target: src/email/gui_setup.py" in front
    assert "tests: tests/frozen_cli_account_setup_gui.py" in front
    assert "tkinter" in front, "deps_allowed sin tkinter"
    assert "src.email.provision_account" in front, "deps sin provision_account"
    assert "src.email.discover_mail_servers" in front, "deps sin discovery"
    assert "src.email.mail_server_store" in front, "deps sin store servidores"
    for forbidden in (
        "input", "getpass", "os.environ", "print", "open", "logging",
        "socket", "urllib", "requests", "smtplib", "subprocess", "eval",
        "exec", "cmdkey", "keyring",
    ):
        assert forbidden in front, "forbids sin declarar " + forbidden
    body = _body(text)
    for section in SECTIONS:
        assert "\n## " + section + "\n" in "\n" + body, "seccion " + section + " ausente"
    assert "PARAR y reportar si" in body, "Constraints sin regla de parada"
    assert COMMAND in body, "el contrato no documenta el subcomando"
    assert "python -m src.email account setup-gui" in body, "falta la forma de invocacion"
    assert PASSWORD_MASK in body, "el contrato no exige show=\"*\" en el password"
    assert "discover_mail_servers" in body, "falta el discovery congelado"
    assert "store_mail_server_config" in body, "falta la persistencia de servidores"
    assert "provision_email_account" in body, "falta la delegacion conceptual"
    assert '"custom"' in body, "falta la etiqueta publica del proveedor"
    assert "email-" in body, "falta la derivacion determinista del label"
    assert "57" in body, "falta la truncacion que mantiene el label <= 64"
    assert "seccion avanzada" in body, "falta el fallback manual amigable"
    assert "tkinter" in body, "el contrato no declara tkinter"
    assert "navegador" in body and "servidor" in body, "faltan las prohibiciones de red/ventana"
    assert "input()" in body and "getpass" in body, "faltan prohibiciones input/getpass"
    assert "variables de entorno" in body or "os.environ" in body, "falta prohibicion de env"
    assert "fallback inseguro" in body, "falta prohibicion de fallback inseguro"
    assert "accounts.json" in body and "wincred://" in body, "falta el trato de accounts.json"
    assert "mail-servers.json" in body, "falta el trato de mail-servers.json"
    assert "credential_ref" in body, "falta el trato de credential_ref"
    assert "JAMAS" in body and "sin contrasena" in body.lower(), (
        "el contrato no congela discovery sin contrasena"
    )
    for code in ("0", "1", "2"):
        assert "`" + code + "`" in body, "falta el codigo de salida " + code
    for sub in ("search", "account add", "account list", "account setup",
                "query", "sync", "draft", "send"):
        assert sub in body, "el contrato no declara intacto el subcomando " + sub


def test_contract_frozen_inputs():
    values = json.loads(_fenced_block(_contract_text(), "frozen-inputs"))
    assert values["root"] == FAKE_ROOT
    assert values["email"] == FAKE_EMAIL
    assert values["password"] == FAKE_SECRET
    assert values["discovered"] == DISCOVERED
    window = FakeWindow()
    window.email_text = FAKE_EMAIL
    window.password_value = FAKE_SECRET
    discovery = FakeDiscovery(result=DISCOVERED)
    provision = FakeProvision()
    store = FakeStore()
    model = SetupModel(window, discovery, provision, store, root=FAKE_ROOT)
    model.save()
    assert window.destroyed == 0, "el flujo frozen debe ser exitoso"
    assert discovery.calls == [FAKE_EMAIL], "discovery debe recibir solo el email"
    assert provision.calls == [
        {
            "root": FAKE_ROOT,
            "account_id": DERIVED_ID,
            "provider": PROVIDER,
            "email": FAKE_EMAIL,
            "label": FAKE_LABEL,
            "secret": FAKE_SECRET,
        }
    ]
    assert store.calls == [
        {
            "root": FAKE_ROOT,
            "account_id": DERIVED_ID,
            "config": dict(DISCOVERED),
        }
    ]
    assert ("info", "cuenta guardada: " + DERIVED_ID) in window.dialogs
    assert window.password_value == "", "el password debe limpiarse tambien en exito"
    assert window.cleared >= 1


def test_discovery_never_receives_password():
    window = FakeWindow()
    window.email_text = FAKE_EMAIL
    window.password_value = FAKE_SECRET
    discovery = FakeDiscovery(result=DISCOVERED)
    provision = FakeProvision()
    store = FakeStore()
    SetupModel(window, discovery, provision, store).save()
    assert discovery.calls == [FAKE_EMAIL], (
        "el discovery solo recibe el email, jamas el password"
    )


def test_advanced_fallback_after_discovery_value_error():
    window = FakeWindow()
    window.email_text = FAKE_EMAIL
    window.password_value = FAKE_SECRET
    discovery = FakeDiscovery(exc=ValueError("no confirmado"))
    provision = FakeProvision()
    store = FakeStore()
    model = SetupModel(window, discovery, provision, store)
    model.save()
    assert window.advanced_visible, "la seccion avanzada debe abrirse"
    assert provision.calls == [], "no se debe provisionar sin servidores"
    assert store.calls == [], "no se debe escribir el almacen"
    assert window.destroyed is None, "la ventana debe permanecer abierta"
    # Segundo Guardar con datos avanzados completos y validos.
    window.advanced_values = {
        "imap_host": "  IMAP.Midominio.TEST ",
        "imap_port": " 1993 ",
        "smtp_host": "smtp.midominio.com",
        "smtp_port": "1587",
    }
    model.save()
    assert window.destroyed == 0
    assert len(provision.calls) == 1
    assert provision.calls[0]["account_id"] == DERIVED_ID
    assert provision.calls[0]["provider"] == PROVIDER
    assert provision.calls[0]["secret"] == FAKE_SECRET
    assert store.calls == [
        {"root": FAKE_ROOT, "account_id": DERIVED_ID, "config": MANUAL_SERVERS}
    ], "los hosts manuales deben normalizarse a minusculas y recortarse"
    assert discovery.calls == [FAKE_EMAIL], "el discovery no debe reintentarse"


def test_discovery_unexpected_error_is_terminal():
    window = FakeWindow()
    window.email_text = FAKE_EMAIL
    window.password_value = FAKE_SECRET
    discovery = FakeDiscovery(exc=OSError("dns roto"))
    provision = FakeProvision()
    store = FakeStore()
    SetupModel(window, discovery, provision, store).save()
    assert window.destroyed == 1
    assert ("error", GENERIC_ERROR) in window.dialogs
    assert provision.calls == [] and store.calls == []
    assert window.password_value == ""


def test_incomplete_advanced_data_never_provisions():
    window = FakeWindow()
    window.email_text = FAKE_EMAIL
    window.password_value = FAKE_SECRET
    discovery = FakeDiscovery(exc=ValueError("no confirmado"))
    provision = FakeProvision()
    store = FakeStore()
    model = SetupModel(window, discovery, provision, store)
    model.save()
    # Datos incompletos: falta el puerto de salida.
    window.advanced_values = {
        "imap_host": "imap.midominio.test",
        "imap_port": "1993",
        "smtp_host": "smtp.midominio.com",
        "smtp_port": "",
    }
    model.save()
    assert window.destroyed is None, "la ventana debe permanecer abierta"
    assert provision.calls == [] and store.calls == []
    assert INCOMPLETE in window.notes


def test_invalid_advanced_values_never_provision():
    bad_values = [
        {"imap_host": "mi servidor", "imap_port": "993",
         "smtp_host": "smtp.midominio.com", "smtp_port": "587"},
        {"imap_host": "imap..midominio", "imap_port": "993",
         "smtp_host": "smtp.midominio.com", "smtp_port": "587"},
        {"imap_host": "imap.midominio.test", "imap_port": "0",
         "smtp_host": "smtp.midominio.com", "smtp_port": "587"},
        {"imap_host": "imap.midominio.test", "imap_port": "70000",
         "smtp_host": "smtp.midominio.com", "smtp_port": "587"},
        {"imap_host": "imap.midominio.test", "imap_port": "abc",
         "smtp_host": "smtp.midominio.com", "smtp_port": "587"},
        {"imap_host": "", "imap_port": "993",
         "smtp_host": "smtp.midominio.com", "smtp_port": "587"},
    ]
    for values in bad_values:
        window = FakeWindow()
        window.email_text = FAKE_EMAIL
        window.password_value = FAKE_SECRET
        discovery = FakeDiscovery(exc=ValueError("no confirmado"))
        provision = FakeProvision()
        store = FakeStore()
        model = SetupModel(window, discovery, provision, store)
        model.save()
        window.advanced_values = dict(values)
        model.save()
        assert provision.calls == [], "provision con datos invalidos: %r" % (values,)
        assert store.calls == [] and window.destroyed is None


def test_cancel_writes_nothing():
    window = FakeWindow()
    window.email_text = FAKE_EMAIL
    window.password_value = FAKE_SECRET
    discovery = FakeDiscovery(result=DISCOVERED)
    provision = FakeProvision()
    store = FakeStore()
    SetupModel(window, discovery, provision, store).cancel()
    assert window.destroyed == 1
    assert discovery.calls == [], "cancelar llamo al discovery"
    assert provision.calls == [], "cancelar llamo a provision"
    assert store.calls == [], "cancelar llamo al almacen"
    assert window.dialogs == [] and window.notes == []
    assert window.password_value == ""


def test_empty_fields_keep_window_open_without_calls():
    for email, password in (("", FAKE_SECRET), (FAKE_EMAIL, "")):
        window = FakeWindow()
        window.email_text = email
        window.password_value = password
        discovery = FakeDiscovery(result=DISCOVERED)
        provision = FakeProvision()
        store = FakeStore()
        SetupModel(window, discovery, provision, store).save()
        assert window.destroyed is None
        assert discovery.calls == [] and provision.calls == []
        assert EMPTY_FIELDS in window.notes


def test_credential_manager_stop_without_fallback_nor_store():
    window = FakeWindow()
    window.email_text = FAKE_EMAIL
    window.password_value = FAKE_SECRET
    discovery = FakeDiscovery(result=DISCOVERED)
    provision = FakeProvision(exc=RuntimeError("PARAR: Credential Manager no disponible"))
    store = FakeStore()
    SetupModel(window, discovery, provision, store).save()
    assert window.destroyed == 1
    kind, message = window.dialogs[0]
    assert kind == "warning", "la parada no se mostro como tal"
    assert "PARAR" in message, "el mensaje de parada no es claro"
    assert "no existe alternativa" in message or "no esta disponible" in message
    assert store.calls == [], "con provision fallida el almacen no se llama"
    assert FAKE_SECRET not in message
    assert window.password_value == ""


def test_provision_value_error_is_generic_without_store():
    window = FakeWindow()
    window.email_text = FAKE_EMAIL
    window.password_value = FAKE_SECRET
    discovery = FakeDiscovery(result=DISCOVERED)
    provision = FakeProvision(exc=ValueError("detalle interno del store"))
    store = FakeStore()
    SetupModel(window, discovery, provision, store).save()
    assert window.destroyed == 1
    kind, message = window.dialogs[0]
    assert kind == "error" and message == GENERIC_ERROR
    assert "detalle interno" not in message, "el mensaje filtra la excepcion"
    assert store.calls == []


def test_store_failure_is_generic():
    window = FakeWindow()
    window.email_text = FAKE_EMAIL
    window.password_value = FAKE_SECRET
    discovery = FakeDiscovery(result=DISCOVERED)
    provision = FakeProvision()
    store = FakeStore(exc=RuntimeError("store corrupto"))
    SetupModel(window, discovery, provision, store).save()
    assert window.destroyed == 1
    assert len(provision.calls) == 1, "la provision si ocurrio"
    kind, message = window.dialogs[-1]
    assert kind == "error" and message == GENERIC_ERROR
    assert "store corrupto" not in message, "el mensaje filtra la excepcion"
    assert window.password_value == ""


def test_fake_secret_never_reaches_outputs():
    """El secreto ficticio jamas aparece en mensajes ni en retornos del modelo."""
    scenarios = [
        ("ok", FakeDiscovery(result=DISCOVERED), FakeProvision(), FakeStore()),
        ("discovery_falla", FakeDiscovery(exc=ValueError("x")), FakeProvision(), FakeStore()),
        ("stop", FakeDiscovery(result=DISCOVERED),
         FakeProvision(exc=RuntimeError("PARAR: sin Credential Manager")), FakeStore()),
    ]
    for name, discovery, provision, store in scenarios:
        window = FakeWindow()
        window.email_text = FAKE_EMAIL
        window.password_value = FAKE_SECRET
        SetupModel(window, discovery, provision, store).save()
        outputs = window.notes + [m for _, m in window.dialogs] + [str(window.destroyed)]
        assert FAKE_SECRET not in " ".join(outputs), name + ": el secreto llego a la salida"
        assert FAKE_SECRET not in json.dumps(store.calls), (
            name + ": el secreto llego al almacen de servidores"
        )
        if window.destroyed is not None:
            assert window.password_value == ""


def test_account_id_derivation_is_deterministic_and_safe():
    assert derive_account_id(FAKE_EMAIL) == DERIVED_ID
    assert derive_account_id("Ana@Example.COM") == derive_account_id("ana@example.com")
    assert derive_account_id("Mi Cuenta@X.COM") == "mi-cuenta-x.com"
    assert derive_account_id("a.b-c_d@x.co") == "a.b-c_d-x.co"
    long_id = derive_account_id("a" * 80 + "@example.com")
    assert long_id == "a" * 57, "la derivacion debe truncar a 57"
    assert derive_account_id("weird!!email@example.com") == "weird-email-example.com"
    for email in ("x@example.com", "no.se@sub.domino.test", "a+b@gmail.com"):
        account_id = derive_account_id(email)
        assert LABEL_PATTERN.match(account_id) is not None, email
        assert LABEL_PATTERN.match("email-" + account_id) is not None, email


def test_models_have_no_side_channels():
    """El modelo de referencia no imprime, abre archivos ni lanza procesos."""
    tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
    model = next(
        node for node in ast.walk(tree)
        if isinstance(node, ast.ClassDef) and node.name == "SetupModel"
    )
    calls = [node.func for node in ast.walk(model) if isinstance(node, ast.Call)]
    names = {getattr(call, "id", getattr(call, "attr", "")) for call in calls}
    for banned in ("print", "open", "system", "Popen", "socket", "environ",
                   "getpass", "input", "dump"):
        assert banned not in names, "el modelo usa un canal de escape: " + banned


def test_no_real_credential_manager_or_env_access():
    """El marcador ficticio jamas existe en el entorno real del proceso."""
    assert FAKE_SECRET not in __import__("os").environ
    assert FAKE_LABEL not in __import__("os").environ.values()