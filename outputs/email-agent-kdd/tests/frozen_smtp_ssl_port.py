"""Prueba de regresion del contrato send_smtp_message: clase de transporte por puerto.

Sustituye smtplib.SMTP y smtplib.SMTP_SSL por fakes, de modo que no se abre
ningun socket y no se envia nada real. Verifica que la fabrica por defecto sea
SMTP_SSL solo con puerto 465 y SMTP en los demas puertos (587 incluido), que
una fabrica inyectada gana siempre, que la confirmacion estricta se mantiene
(sin confirmed is True no se instancia ninguna conexion) y que el error de
transporte no expone la password ni el cuerpo.
"""

import json
import smtplib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.email import smtp_send  # noqa: E402

ACCOUNT = {"account_id": "personal", "email": "yo@inbox.test"}
PASSWORD = "frozen-secret-ssl"


class _FakeConnection:
    def __init__(self, record, host, port):
        self.host = host
        self.port = port
        self.login_calls = []
        self.sent = []
        self.quit_calls = 0
        record.append(self)

    def login(self, username, password):
        self.login_calls.append((username, password))

    def send_message(self, msg):
        self.sent.append(msg)

    def quit(self):
        self.quit_calls += 1


def _install_fakes(monkeypatch):
    ssl_connections, plain_connections = [], []

    class FakeSSL(_FakeConnection):
        def __init__(self, host, port):
            super().__init__(ssl_connections, host, port)

    class FakePlain(_FakeConnection):
        def __init__(self, host, port):
            super().__init__(plain_connections, host, port)

    monkeypatch.setattr(smtplib, "SMTP", FakePlain)
    monkeypatch.setattr(smtplib, "SMTP_SSL", FakeSSL)
    return plain_connections, ssl_connections


def _message(confirmed=True):
    return {
        "confirmed": confirmed,
        "to": ["ana@example.com"],
        "subject": "Hola",
        "body": "Cuerpo privado.",
    }


def test_port_465_uses_smtp_ssl(monkeypatch):
    plain, ssl_connections = _install_fakes(monkeypatch)
    receipt = smtp_send.send_smtp_message(
        ACCOUNT,
        {"host": "smtp.example.test", "username": "usuario", "password": PASSWORD, "port": 465},
        _message(),
    )
    assert plain == [], "puerto 465 no debe usar smtplib.SMTP"
    assert len(ssl_connections) == 1, "puerto 465 debe usar SMTP_SSL"
    conn = ssl_connections[0]
    assert (conn.host, conn.port) == ("smtp.example.test", 465)
    assert conn.login_calls == [("usuario", PASSWORD)]
    assert len(conn.sent) == 1 and conn.quit_calls == 1
    assert receipt["sent"] is True
    assert list(receipt) == ["account_id", "from_email", "to", "subject", "sent"]
    assert "password" not in json.dumps(receipt)
    assert "Cuerpo privado." not in json.dumps(receipt)


def test_port_587_uses_smtp_plain(monkeypatch):
    plain, ssl_connections = _install_fakes(monkeypatch)
    smtp_send.send_smtp_message(
        ACCOUNT,
        {"host": "smtp.example.test", "username": "usuario", "password": PASSWORD, "port": 587},
        _message(),
    )
    assert len(plain) == 1, "puerto 587 debe usar smtplib.SMTP"
    assert (plain[0].host, plain[0].port) == ("smtp.example.test", 587)
    assert plain[0].quit_calls == 1
    assert ssl_connections == [], "puerto 587 no debe usar SMTP_SSL"


def test_default_port_587_uses_smtp_plain(monkeypatch):
    plain, ssl_connections = _install_fakes(monkeypatch)
    smtp_send.send_smtp_message(
        ACCOUNT,
        {"host": "smtp.example.test", "username": "usuario", "password": PASSWORD},
        _message(),
    )
    assert len(plain) == 1 and ssl_connections == []


def test_other_port_uses_smtp_plain(monkeypatch):
    plain, ssl_connections = _install_fakes(monkeypatch)
    smtp_send.send_smtp_message(
        ACCOUNT,
        {"host": "smtp.example.test", "username": "usuario", "password": PASSWORD, "port": 2525},
        _message(),
    )
    assert len(plain) == 1 and ssl_connections == []


def test_injected_factory_wins_even_on_465(monkeypatch):
    plain, ssl_connections = _install_fakes(monkeypatch)
    injected = []

    def factory(host, port):
        conn = _FakeConnection(injected, host, port)
        return conn

    receipt = smtp_send.send_smtp_message(
        ACCOUNT,
        {"host": "smtp.example.test", "username": "usuario", "password": PASSWORD, "port": 465},
        _message(),
        connection_factory=factory,
    )
    assert [(c.host, c.port) for c in injected] == [("smtp.example.test", 465)]
    assert injected[0].quit_calls == 1
    assert receipt["sent"] is True
    assert plain == [] and ssl_connections == [], "la fabrica inyectada debe usarse tal cual"


def test_unconfirmed_message_never_instantiates_transport(monkeypatch):
    plain, ssl_connections = _install_fakes(monkeypatch)
    try:
        smtp_send.send_smtp_message(
            ACCOUNT,
            {"host": "smtp.example.test", "username": "usuario", "password": PASSWORD, "port": 465},
            _message(confirmed=False),
        )
    except ValueError:
        pass
    else:
        raise AssertionError("confirmed=False debe rechazarse")
    assert plain == [] and ssl_connections == [], "sin confirmacion no debe haber conexion"


def test_transport_error_wraps_without_leaking_secrets(monkeypatch):
    plain, _ = _install_fakes(monkeypatch)

    class Broken(_FakeConnection):
        def __init__(self, host, port):
            super().__init__(plain, host, port)

        def send_message(self, msg):
            raise RuntimeError("fallo con password=" + PASSWORD)

    monkeypatch.setattr(smtplib, "SMTP", Broken)
    try:
        smtp_send.send_smtp_message(
            ACCOUNT,
            {"host": "smtp.example.test", "username": "usuario", "password": PASSWORD},
            _message(),
        )
    except RuntimeError as exc:
        message = str(exc)
        assert "smtp.example.test" in message and "personal" in message
        assert PASSWORD not in message and "Cuerpo privado." not in message
    else:
        raise AssertionError("el fallo de transporte debe relanzarse como RuntimeError")
    assert plain[0].quit_calls == 1, "quit en finally"
    assert plain[0].sent == []