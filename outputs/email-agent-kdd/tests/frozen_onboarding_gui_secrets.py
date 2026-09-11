"""Tests congelados del onboarding seguro GUI (Sprint 8).

Ejercita el codigo REAL de `src/email/gui_setup.py` (no un modelo espejo)
sin abrir ventanas: el modulo se importa (sin efectos) y se sustituyen
unicamente los widgets por falsos en memoria y las cuatro dependencias con
efecto externo (discovery, verificacion IMAP/SMTP, provision y almacen de
servidores) por dobles en memoria. Todo offline: sin red real, sin tkinter,
sin Credential Manager, sin disco y sin secretos reales.

Congela: exito (una llamada por dependencia, discovery solo con el email,
password limpio), validacion (descubrimiento fallido -> seccion avanzada,
datos incompletos/invalidos -> sin provision), verificacion de conexion
fallida (sin provision ni escritura), cancelacion (cero llamadas, cero
escrituras, password limpio), provision sin Credential Manager (PARAR sin
fallback ni almacen), fallo del almacen (generico) y el invariante de
secreto: la contrasena ficticia jamas aparece en ninguna salida.
"""

import ast
from pathlib import Path

import pytest

import src.email.gui_setup as gui

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


class _FakeEntry:
    """Campo falso: get() y delete() suficientes para el flujo real."""

    def __init__(self, text=""):
        self.text = text

    def get(self):
        return self.text

    def delete(self, first, last):
        self.text = ""


class _FakeStatus:
    """Etiqueta falsa que registra los mensajes no terminales."""

    def __init__(self):
        self.notes = []

    def config(self, **kwargs):
        if "text" in kwargs:
            self.notes.append(kwargs["text"])


class _FakeAdvanced:
    """Seccion avanzada falsa: solo recuerda si se hizo visible."""

    def __init__(self):
        self.visible = False

    def grid(self):
        self.visible = True

    def grid_remove(self):
        self.visible = False


class _FakeWindow:
    """Ventana falsa: destroy y codigo de salida capturados."""

    def __init__(self):
        self.destroyed = False

    def destroy(self):
        self.destroyed = True


class _FakeDialog:
    """Sustituto de _show: registra (kind, message) sin abrir dialogos."""

    def __init__(self):
        self.dialogs = []


class _FakeDiscovery:
    def __init__(self, result=None, exc=None):
        self.calls = []
        self.result = result
        self.exc = exc

    def __call__(self, email):
        self.calls.append(email)
        if self.exc is not None:
            raise self.exc
        return dict(self.result)


class _FakeVerify:
    def __init__(self, exc=None):
        self.calls = []
        self.exc = exc

    def __call__(self, account, servers, password):
        self.calls.append((dict(account), dict(servers), password))
        if self.exc is not None:
            raise self.exc
        return {"imap_verified": True, "smtp_verified": True}


class _FakeProvision:
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


class _FakeStore:
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


def _form(monkeypatch, *, discovery=None, verify=None, provision=None,
          store=None, email=FAKE_EMAIL, password=FAKE_SECRET):
    """Formulario REAL con widgets falsos y dependencias inyectadas."""
    window = _FakeWindow()
    recorder = _FakeDialog()
    form = gui._SetupForm(window, FAKE_ROOT)
    form.email = _FakeEntry(email)
    form.password = _FakeEntry(password)
    form.status = _FakeStatus()
    form.advanced = _FakeAdvanced()
    form.imap_host = _FakeEntry()
    form.imap_port = _FakeEntry()
    form.smtp_host = _FakeEntry()
    form.smtp_port = _FakeEntry()
    if discovery is not None:
        monkeypatch.setattr(gui, "discover_mail_servers", discovery)
        # Los casos que cuentan llamadas leen el doble desde el formulario,
        # igual que con provision y almacen.
        form.discovery = discovery
    if verify is not None:
        monkeypatch.setattr(gui, "verify_email_connection", verify)
    if provision is not None:
        monkeypatch.setattr(gui, "provision_email_account", provision)
    store = store or _FakeStore()
    monkeypatch.setattr(gui, "store_mail_server_config", store)
    # Se sustituye SOLO el dialogo terminal (tkinter.messagebox); el resto
    # del formulario es el codigo real.
    monkeypatch.setattr(
        form, "_show",
        lambda message, kind: recorder.dialogs.append((kind, message)),
    )
    form.recorder = recorder
    form.provision = provision
    form.store = store
    return form


def _outputs(form):
    return (
        form.status.notes
        + [message for _, message in form.recorder.dialogs]
    )


# --------------------------------------------------------------------------
# Estructura estatica del modulo real
# --------------------------------------------------------------------------


def test_form_never_prints_nor_logs():
    """El formulario real no imprime ni registra: solo widgets y dialogos."""
    tree = ast.parse(
        Path("src/email/gui_setup.py").read_text(encoding="utf-8")
    )
    form = next(
        node for node in ast.walk(tree)
        if isinstance(node, ast.ClassDef) and node.name == "_SetupForm"
    )
    calls = [node.func for node in ast.walk(form) if isinstance(node, ast.Call)]
    names = {getattr(call, "id", getattr(call, "attr", "")) for call in calls}
    for banned in ("print", "logging", "system", "Popen", "socket",
                   "environ", "getpass", "input"):
        assert banned not in names, (
            "el formulario usa un canal de escape: " + banned
        )


def test_discovery_is_called_without_password():
    """El discovery jamas toca self.password en el codigo real."""
    tree = ast.parse(
        Path("src/email/gui_setup.py").read_text(encoding="utf-8")
    )
    discover = next(
        node for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == "_discover"
    )
    for node in ast.walk(discover):
        if isinstance(node, ast.Attribute):
            assert node.attr != "password", (
                "el discovery lee el password en el codigo real"
            )


# --------------------------------------------------------------------------
# Exito
# --------------------------------------------------------------------------


def test_success_pipeline_is_single_call_per_dependency(monkeypatch):
    discovery = _FakeDiscovery(result=DISCOVERED)
    verify = _FakeVerify()
    provision = _FakeProvision()
    store = _FakeStore()
    form = _form(monkeypatch, discovery=discovery, verify=verify,
                 provision=provision, store=store)
    form._on_save()
    assert discovery.calls == [FAKE_EMAIL], "discovery solo recibe el email"
    assert len(verify.calls) == 1
    account, servers, password = verify.calls[0]
    assert account == {"email": FAKE_EMAIL}
    assert servers == dict(DISCOVERED)
    assert password == FAKE_SECRET, "la verificacion recibe el secreto en memoria"
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
        {"root": FAKE_ROOT, "account_id": DERIVED_ID, "config": dict(DISCOVERED)}
    ]
    assert form.code == 0
    assert ("info", "cuenta guardada: " + DERIVED_ID) in form.recorder.dialogs
    assert form.password.get() == "", "el password debe limpiarse en exito"
    assert FAKE_SECRET not in " ".join(_outputs(form))


def test_discovery_confirmed_note_is_generic(monkeypatch):
    form = _form(
        monkeypatch,
        discovery=_FakeDiscovery(result=DISCOVERED),
        verify=_FakeVerify(),
        provision=_FakeProvision(),
        store=_FakeStore(),
    )
    form._on_save()
    assert gui._DISCOVERY_CONFIRMED in form.status.notes


# --------------------------------------------------------------------------
# Validacion
# --------------------------------------------------------------------------


def test_discovery_value_error_opens_advanced_without_provision(monkeypatch):
    form = _form(
        monkeypatch,
        discovery=_FakeDiscovery(exc=ValueError("no confirmado")),
        verify=_FakeVerify(),
        provision=_FakeProvision(),
        store=_FakeStore(),
    )
    form._on_save()
    assert form.advanced.visible, "la seccion avanzada debe abrirse"
    assert gui._DISCOVERY_GUIDE in form.status.notes
    assert form.recorder.dialogs == []
    assert form.code == 1 and form.window.destroyed is False
    assert form.provision.calls == [] and form.store.calls == []
    # Segundo Guardar con datos avanzados validos y completos.
    form.imap_host = _FakeEntry("  IMAP.Midominio.TEST ")
    form.imap_port = _FakeEntry(" 1993 ")
    form.smtp_host = _FakeEntry("smtp.midominio.com")
    form.smtp_port = _FakeEntry("1587")
    form._on_save()
    assert form.code == 0
    assert form.provision.calls[0]["account_id"] == DERIVED_ID
    assert form.recorder.dialogs[-1] == (
        "info", "cuenta guardada: " + DERIVED_ID
    )
    assert form.store.calls == [
        {"root": FAKE_ROOT, "account_id": DERIVED_ID, "config": MANUAL_SERVERS}
    ]
    assert form.discovery.calls == [FAKE_EMAIL], "el discovery no debe reintentarse"


def test_incomplete_advanced_data_never_provisions(monkeypatch):
    form = _form(
        monkeypatch,
        discovery=_FakeDiscovery(exc=ValueError("no confirmado")),
        verify=_FakeVerify(),
        provision=_FakeProvision(),
        store=_FakeStore(),
    )
    form._on_save()
    form.smtp_port = _FakeEntry("")
    form._on_save()
    assert gui._INCOMPLETE in form.status.notes
    assert form.code == 1 and form.window.destroyed is False
    assert form.provision.calls == [] and form.store.calls == []


@pytest.mark.parametrize(
    "values",
    (
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
    ),
)
def test_invalid_advanced_values_never_provision(monkeypatch, values):
    form = _form(
        monkeypatch,
        discovery=_FakeDiscovery(exc=ValueError("no confirmado")),
        verify=_FakeVerify(),
        provision=_FakeProvision(),
        store=_FakeStore(),
    )
    form._on_save()
    for key, value in values.items():
        setattr(form, key, _FakeEntry(value))
    form._on_save()
    assert form.provision.calls == [] and form.store.calls == []
    assert form.code == 1 and form.window.destroyed is False


def test_empty_fields_keep_window_open_without_calls(monkeypatch):
    for email, password in (("", FAKE_SECRET), (FAKE_EMAIL, "")):
        form = _form(monkeypatch, email=email, password=password,
                     discovery=_FakeDiscovery(result=DISCOVERED),
                     verify=_FakeVerify(), provision=_FakeProvision(),
                     store=_FakeStore())
        form._on_save()
        assert gui._EMPTY_FIELDS in form.status.notes
        assert form.code == 1 and form.window.destroyed is False
        assert form.discovery.calls == [] and form.provision.calls == []


# --------------------------------------------------------------------------
# Verificacion de conexion (validacion antes de persistir)
# --------------------------------------------------------------------------


def test_verify_failure_persists_nothing(monkeypatch):
    form = _form(
        monkeypatch,
        discovery=_FakeDiscovery(result=DISCOVERED),
        verify=_FakeVerify(exc=RuntimeError("smtp_authentication_failed")),
        provision=_FakeProvision(),
        store=_FakeStore(),
    )
    form._on_save()
    assert gui._VERIFY_FAILED in form.status.notes
    assert form.provision.calls == [] and form.store.calls == []
    assert form.code == 1 and form.window.destroyed is False


def test_verify_error_message_is_generic_without_secrets(monkeypatch):
    form = _form(
        monkeypatch,
        discovery=_FakeDiscovery(result=DISCOVERED),
        verify=_FakeVerify(exc=RuntimeError("imap_authentication_failed")),
        provision=_FakeProvision(),
        store=_FakeStore(),
    )
    form._on_save()
    for output in _outputs(form):
        assert FAKE_SECRET not in output
        assert "imap_authentication_failed" not in output, (
            "el detalle interno no debe mostrarse al usuario"
        )


# --------------------------------------------------------------------------
# Cancelacion
# --------------------------------------------------------------------------


def test_cancel_writes_nothing_and_clears_password(monkeypatch):
    discovery = _FakeDiscovery(result=DISCOVERED)
    verify = _FakeVerify()
    provision = _FakeProvision()
    store = _FakeStore()
    form = _form(monkeypatch, discovery=discovery, verify=verify,
                 provision=provision, store=store)
    form._on_cancel()
    assert form.code == 1
    assert form.window.destroyed is True
    assert discovery.calls == [] and verify.calls == []
    assert provision.calls == [] and store.calls == []
    assert form.recorder.dialogs == [] and form.status.notes == []
    assert form.password.get() == ""


# --------------------------------------------------------------------------
# Errores de provision y almacen
# --------------------------------------------------------------------------


def test_credential_manager_stop_without_fallback_nor_store(monkeypatch):
    form = _form(
        monkeypatch,
        discovery=_FakeDiscovery(result=DISCOVERED),
        verify=_FakeVerify(),
        provision=_FakeProvision(exc=RuntimeError("PARAR: sin wincred")),
        store=_FakeStore(),
    )
    form._on_save()
    assert form.code == 1
    kind, message = form.recorder.dialogs[0]
    assert kind == "warning" and "PARAR" in message
    assert "no existe alternativa" in message
    assert form.store.calls == [], "sin provision el almacen no se llama"
    assert FAKE_SECRET not in message and form.password.get() == ""


def test_provision_value_error_is_generic_without_store(monkeypatch):
    form = _form(
        monkeypatch,
        discovery=_FakeDiscovery(result=DISCOVERED),
        verify=_FakeVerify(),
        provision=_FakeProvision(exc=ValueError("detalle interno del store")),
        store=_FakeStore(),
    )
    form._on_save()
    assert form.code == 1
    kind, message = form.recorder.dialogs[0]
    assert kind == "error" and message == gui._GENERIC_ERROR
    assert "detalle interno" not in message
    assert form.store.calls == []


def test_store_failure_is_generic(monkeypatch):
    provision = _FakeProvision()
    form = _form(
        monkeypatch,
        discovery=_FakeDiscovery(result=DISCOVERED),
        verify=_FakeVerify(),
        provision=provision,
        store=_FakeStore(exc=RuntimeError("store corrupto")),
    )
    form._on_save()
    assert form.code == 1
    assert len(provision.calls) == 1, "la provision si ocurrio"
    kind, message = form.recorder.dialogs[-1]
    assert kind == "error" and message == gui._GENERIC_ERROR
    assert "store corrupto" not in message
    assert form.password.get() == ""


def test_fake_secret_never_reaches_outputs(monkeypatch):
    scenarios = (
        ("ok", _FakeDiscovery(result=DISCOVERED), _FakeVerify(),
         _FakeProvision(), _FakeStore()),
        ("verificacion_falla", _FakeDiscovery(result=DISCOVERED),
         _FakeVerify(exc=RuntimeError("x")), _FakeProvision(), _FakeStore()),
        ("stop", _FakeDiscovery(result=DISCOVERED), _FakeVerify(),
         _FakeProvision(exc=RuntimeError("PARAR")), _FakeStore()),
        ("store_falla", _FakeDiscovery(result=DISCOVERED), _FakeVerify(),
         _FakeProvision(), _FakeStore(exc=OSError("io"))),
    )
    for name, discovery, verify, provision, store in scenarios:
        form = _form(monkeypatch, discovery=discovery, verify=verify,
                     provision=provision, store=store)
        form._on_save()
        assert FAKE_SECRET not in " ".join(_outputs(form)), (
            name + ": el secreto llego a la salida"
        )
        assert FAKE_SECRET not in repr(store.calls), (
            name + ": el secreto llego al almacen de servidores"
        )


# --------------------------------------------------------------------------
# Helpers puros reales
# --------------------------------------------------------------------------


def test_derive_account_id_is_deterministic_and_safe():
    assert gui._derive_account_id(FAKE_EMAIL) == DERIVED_ID
    assert gui._derive_account_id("ana@example.com") == DERIVED_ID
    assert gui._derive_account_id("Mi Cuenta@X.COM") == "mi-cuenta-x.com"
    assert gui._derive_account_id("a" * 80 + "@example.com") == "a" * 57
    assert gui._derive_account_id("a.b-c_d@x.co") == "a.b-c_d-x.co"
    assert gui._derive_account_id("weird!!email@example.com") == (
        "weird-email-example.com"
    )


def test_parse_port_bounds():
    assert gui._parse_port("993") == 993
    assert gui._parse_port(" 1993 ") == 1993
    assert gui._parse_port("0") is None
    assert gui._parse_port("70000") is None
    assert gui._parse_port("abc") is None
    assert gui._parse_port("") is None


def test_valid_host_rules():
    assert gui._valid_host("imap.midominio.test")
    assert not gui._valid_host("")
    assert not gui._valid_host("mi servidor")
    assert not gui._valid_host("imap..midominio")
    assert not gui._valid_host("a" * 260 + ".test")