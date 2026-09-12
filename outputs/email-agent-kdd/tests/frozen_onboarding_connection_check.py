"""Tests congelados de la comprobacion de conexion (Sprint 8).

Ejercita el codigo REAL de `src/email/connection_check.py` con fabricas de
IMAP/SMTP falsas inyectadas (sin sockets): exito IMAP+SMTP, eleccion de
fabrica por puerto (SMTP_SSL para 465, STARTTLS para 587), fallos de
autenticacion con mensajes fijos que jamas contienen la contrasena, y
validacion fail-closed de los datos antes de conectar. Todo offline, sin
red real y sin credenciales.

Congela ademas la garantia del formulario: la comprobacion solo autentica
(IMAP readonly, SMTP sin mensajes) y jamas envia correo.
"""

import pytest

import src.email.connection_check as connection_check
from src.email.connection_check import verify_email_connection

EMAIL = "ana@example.com"
SECRET = "app-pass-fake-123"
IMAP_SERVERS = {
    "imap_host": "imap.midominio.test",
    "imap_port": 1993,
    "smtp_host": "smtp.midominio.com",
    "smtp_port": 1587,
}


class _World:
    """Estado capturado por las conexiones falsas."""

    def __init__(self, imap_fail=False):
        self.imap_fail = imap_fail
        self.imap_login = None
        self.imap_select = None
        self.imap_closed = False
        self.imap_logged_out = False
        self.smtp_login = None
        self.smtp_quit = False


class _FakeImap:
    def __init__(self, world, host, port):
        self.world = world
        self.host, self.port = host, port

    def login(self, user, password):
        self.world.imap_login = (user, password)
        if self.world.imap_fail:
            raise RuntimeError("LOGIN roto")

    def select(self, mailbox, readonly=False):
        self.world.imap_select = (mailbox, readonly)
        if not readonly:
            raise AssertionError("INBOX debe abrirse readonly")

    def close(self):
        self.world.imap_closed = True

    def logout(self):
        self.world.imap_logged_out = True


class _FakeSmtp:
    def __init__(self, world, host, port):
        self.world = world
        self.host, self.port = host, port
        self.tls = False

    def starttls(self, *, context):
        assert context.check_hostname
        self.tls = True

    def login(self, user, password):
        self.world.smtp_login = (user, password)

    def sendmail(self, *args):
        raise AssertionError("la comprobacion jamas envia un mensaje")

    def quit(self):
        self.world.smtp_quit = True


def _fake_factories(world):
    def imap_factory(host, port):
        return _FakeImap(world, host, port)

    def smtp_factory(host, port):
        return _FakeSmtp(world, host, port)

    return imap_factory, smtp_factory


def test_success_authenticates_readonly_and_never_sends():
    world = _World()
    imap_factory, smtp_factory = _fake_factories(world)
    result = verify_email_connection(
        {"email": EMAIL}, IMAP_SERVERS, SECRET,
        imap_factory=imap_factory, smtp_factory=smtp_factory,
    )
    assert result == {"imap_verified": True, "smtp_verified": True}
    assert world.imap_login == (EMAIL, SECRET)
    assert world.imap_select == ("INBOX", True), "INBOX en solo lectura"
    assert world.imap_closed and world.imap_logged_out
    assert world.smtp_login == (EMAIL, SECRET)
    assert world.smtp_quit


def test_imap_failure_stops_before_smtp_and_releases():
    world = _World(imap_fail=True)
    imap_factory, smtp_factory = _fake_factories(world)
    with pytest.raises(RuntimeError) as excinfo:
        verify_email_connection(
            {"email": EMAIL}, IMAP_SERVERS, SECRET,
            imap_factory=imap_factory, smtp_factory=smtp_factory,
        )
    assert str(excinfo.value) == "imap_authentication_failed"
    assert SECRET not in str(excinfo.value)
    assert world.imap_closed and world.imap_logged_out
    assert world.smtp_login is None, "SMTP no debe intentarse tras fallo IMAP"


def test_smtp_failure_releases_imap_and_hides_secret():
    world = _World()
    imap_factory, _ = _fake_factories(world)

    class _LeakySmtp(_FakeSmtp):
        def login(self, user, password):
            raise RuntimeError("login con " + password)

    def smtp_factory(host, port):
        return _LeakySmtp(world, host, port)

    with pytest.raises(RuntimeError) as excinfo:
        verify_email_connection(
            {"email": EMAIL}, IMAP_SERVERS, SECRET,
            imap_factory=imap_factory, smtp_factory=smtp_factory,
        )
    assert str(excinfo.value) == "smtp_authentication_failed"
    assert SECRET not in str(excinfo.value), (
        "el mensaje de error jamas filtra la contrasena"
    )
    assert world.imap_closed, "IMAP queda liberado aunque SMTP falle"


def test_default_factories_ssl_for_465_and_starttls_for_587(monkeypatch):
    created = []

    class _StubImap:
        def __init__(self, host, port, *, ssl_context, timeout):
            assert ssl_context.check_hostname and timeout == 30
            created.append(("IMAP4_SSL", host, port))

        def login(self, user, password):
            pass

        def select(self, mailbox, readonly=False):
            pass

        def close(self):
            pass

        def logout(self):
            pass

    class _StubSmtpSsl(_StubImap):
        def __init__(self, host, port, *, context, timeout):
            assert context.check_hostname and timeout == 30
            created.append(("SMTP_SSL", host, port))

        def login(self, user, password):
            pass

        def quit(self):
            pass

    monkeypatch.setattr(connection_check.imaplib, "IMAP4_SSL", _StubImap)
    monkeypatch.setattr(connection_check.smtplib, "SMTP_SSL", _StubSmtpSsl)
    verify_email_connection(
        {"email": EMAIL}, dict(IMAP_SERVERS, smtp_port=465), SECRET
    )
    assert created == [
        ("IMAP4_SSL", "imap.midominio.test", 1993),
        ("SMTP_SSL", "smtp.midominio.com", 465),
    ], "el puerto 465 exige SSL directo"

    created.clear()

    class _StubSmtpTls(_StubImap):
        def __init__(self, host, port, *, timeout):
            assert timeout == 30
            created.append(("SMTP", host, port))
            self.tls = False

        def starttls(self, *, context):
            assert context.check_hostname
            self.tls = True

        def login(self, user, password):
            assert self.tls, "el puerto 587 exige STARTTLS antes de login"

        def quit(self):
            pass

    monkeypatch.setattr(connection_check.smtplib, "SMTP", _StubSmtpTls)
    verify_email_connection(
        {"email": EMAIL}, dict(IMAP_SERVERS, smtp_port=587), SECRET
    )
    # El stub de IMAP4_SSL sigue parcheado en esta prueba, por lo que la
    # segunda comprobacion tambien lo construye.
    assert created == [
        ("IMAP4_SSL", "imap.midominio.test", 1993),
        ("SMTP", "smtp.midominio.com", 587),
    ], "el puerto 587 usa la fabrica STARTTLS"


def test_input_validation_is_fail_closed():
    imap_factory, smtp_factory = _fake_factories(_World())
    with pytest.raises(ValueError):
        verify_email_connection({"email": EMAIL}, IMAP_SERVERS, "")
    with pytest.raises(ValueError):
        verify_email_connection({}, IMAP_SERVERS, SECRET)
    with pytest.raises(ValueError):
        verify_email_connection({"email": ""}, IMAP_SERVERS, SECRET)
    with pytest.raises(ValueError):
        verify_email_connection({"email": EMAIL}, "no-dict", SECRET)
    with pytest.raises(ValueError):
        verify_email_connection(
            {"email": EMAIL}, dict(IMAP_SERVERS, imap_port="993"), SECRET
        )
    with pytest.raises(ValueError):
        verify_email_connection(
            {"email": EMAIL}, dict(IMAP_SERVERS, smtp_port=0), SECRET
        )
