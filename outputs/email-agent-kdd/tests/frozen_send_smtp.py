"""Tests congelados del contrato send_smtp_message.

Oracle independiente: no importa el target ni src.email, no abre sockets,
no toca la red y no escribe disco. Recompone las reglas documentadas con
un modelo de referencia propio y un fake SMTP inyectable, y las contrasta
con los casos congelados del contrato. Valida ademas que sin confirmacion
no se abre ninguna conexion y que el fake captura una sola entrega.
"""

import json
import re
from email.message import EmailMessage
from pathlib import Path

CONTRACT = (
    Path(__file__).resolve().parents[1]
    / "knowledge"
    / "contracts"
    / "send-smtp-message.md"
)


def _contract_text():
    return CONTRACT.read_text(encoding="utf-8")


def _frontmatter(text):
    return text.split("---\n", 2)[1]


def _fenced_block(text, label):
    match = re.search(r"```" + label + r"\n(.*?)\n```", text, re.DOTALL)
    assert match is not None, "bloque " + label + " ausente en el contrato"
    return match.group(1)


def _frozen_cases():
    return json.loads(_fenced_block(_contract_text(), "frozen-cases"))


# ---------------------------------------------------------------------------
# Fake SMTP (oraculo): conexion de mentira con fabrica inyectable.
# ---------------------------------------------------------------------------


class FakeSMTPConnection:
    def __init__(self, send_error=None):
        self.login_calls = []
        self.sent_messages = []
        self.quit_calls = 0
        self.send_error = send_error

    def login(self, username, password):
        self.login_calls.append((username, password))

    def send_message(self, msg):
        if self.send_error is not None:
            raise RuntimeError(self.send_error)
        self.sent_messages.append(msg)
        return {}

    def quit(self):
        self.quit_calls += 1


def _fake_factory(record, send_error=None):
    def factory(host, port):
        record["factory_calls"] += 1
        record["host_port"] = (host, port)
        connection = FakeSMTPConnection(send_error=send_error)
        record["connections"].append(connection)
        return connection

    return factory


# ---------------------------------------------------------------------------
# Modelo de referencia del contrato, reimplementado por el oracle.
# ---------------------------------------------------------------------------


def _nonempty_str(value):
    return isinstance(value, str) and value != ""


def run_reference(account, config, message, factory, record=None):
    if record is None:
        record = {"factory_calls": 0, "connections": [], "host_port": None}
    try:
        receipt = _reference_body(account, config, message, factory, record)
    except ValueError as exc:
        return {
            "error": "ValueError",
            "error_message": str(exc),
            "receipt": None,
            "record": record,
        }
    except RuntimeError as exc:
        return {
            "error": "RuntimeError",
            "error_message": str(exc),
            "receipt": None,
            "record": record,
        }
    return {
        "error": None,
        "error_message": None,
        "receipt": receipt,
        "record": record,
    }


def _reference_body(account, config, message, factory, record):
    # Orden fijo de validacion documentado en Invariants, previo a conectar.
    if (
        not isinstance(account, dict)
        or not _nonempty_str(account.get("account_id"))
        or not _nonempty_str(account.get("email"))
    ):
        raise ValueError("account invalido")
    if (
        not isinstance(config, dict)
        or not _nonempty_str(config.get("host"))
        or not _nonempty_str(config.get("username"))
        or not _nonempty_str(config.get("password"))
    ):
        raise ValueError("config invalido")
    port = 587
    if "port" in config:
        value = config["port"]
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError("port no es int")
        if not 1 <= value <= 65535:
            raise ValueError("port fuera de 1..65535")
        port = value
    from_email = account["email"]
    if "from_email" in config:
        if not _nonempty_str(config.get("from_email")):
            raise ValueError("from_email invalido")
        from_email = config["from_email"]
    if not isinstance(message, dict):
        raise ValueError("message invalido")
    # Confirmacion estricta por identidad: 1, "true", None o False no confirman.
    if message.get("confirmed") is not True:
        raise ValueError("confirmacion ausente")
    to = message.get("to")
    if not isinstance(to, list) or not to or not all(_nonempty_str(x) for x in to):
        raise ValueError("to invalido")
    subject = message.get("subject")
    body = message.get("body")
    if not _nonempty_str(subject) or not _nonempty_str(body):
        raise ValueError("subject o body invalido")

    host = config["host"]
    record["host_port"] = (host, port)
    msg = EmailMessage()
    msg["From"] = from_email
    msg["To"] = ", ".join(to)
    msg["Subject"] = subject
    msg.set_content(body)
    record["message"] = msg

    connection = None
    try:
        try:
            connection = factory(host, port)
            connection.login(config["username"], config["password"])
            connection.send_message(msg)
        finally:
            if connection is not None:
                connection.quit()
    except Exception as exc:  # error de transporte: se envuelve sin password
        detail = type(exc).__name__ + ": " + str(exc)
        raise RuntimeError(
            "smtp send failed for "
            + account["account_id"]
            + " via "
            + host
            + ": "
            + detail
        ) from exc
    return {
        "account_id": account["account_id"],
        "from_email": from_email,
        "to": list(to),
        "subject": subject,
        "sent": True,
    }


def _actual(outcome):
    record = outcome["record"]
    sent_messages = [
        msg for conn in record["connections"] for msg in conn.sent_messages
    ]
    built = record.get("message")
    actual = {
        "error": outcome["error"],
        "factory_calls": record["factory_calls"],
        "port": record["host_port"][1] if record["host_port"] else None,
        "from_email": str(built["From"]) if built is not None else None,
        "to_header": str(built["To"]) if built is not None else None,
        "deliveries": len(sent_messages),
        "quit_calls": sum(conn.quit_calls for conn in record["connections"]),
        "receipt": outcome["receipt"],
    }
    return actual


# ---------------------------------------------------------------------------
# Tests del contrato congelado.
# ---------------------------------------------------------------------------


def test_contract_frontmatter_budgets_deps_forbids():
    frontmatter = _frontmatter(_contract_text())
    assert "task: send_smtp_message" in frontmatter
    assert (
        'signature: "def send_smtp_message(account: dict, config: dict, '
        'message: dict, connection_factory=None) -> dict"' in frontmatter
    )
    assert "cyclomatic_max: 20" in frontmatter
    assert "nesting_max: 4" in frontmatter
    assert "lines_max: 80" in frontmatter
    assert "params_max: 4" in frontmatter
    assert "test_command: python -m pytest tests/frozen_send_smtp.py -q" in frontmatter
    assert "deps_allowed: [smtplib, email, typing]" in frontmatter
    for forbidden in ("eval", "exec", "subprocess", "filesystem_write", "print"):
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
        assert section in text, "seccion ausente en el contrato: " + section
    assert "PARAR y reportar si" in text, "sin regla de parada en Constraints"
    assert "PARAR y reportar si" in text.split("## Constraints")[1]


def test_frozen_cases_parse_and_cover_contract():
    cases = _frozen_cases()
    names = [case["name"] for case in cases]
    assert len(cases) >= 8, "casos congelados insuficientes"
    for expected_name in (
        "success_default_port_and_from",
        "success_explicit_port_and_from",
        "missing_confirmation_no_connection",
        "unconfirmed_flag_false_no_connection",
        "invalid_subject_no_connection",
        "invalid_account_no_connection",
        "port_out_of_range_no_connection",
        "transport_error_wrapped_without_password",
    ):
        assert expected_name in names, "caso congelado ausente: " + expected_name


def test_frozen_cases_match_reference_model():
    text = _contract_text()
    for case in _frozen_cases():
        send_error = case["send_error"]
        record = {"factory_calls": 0, "connections": [], "host_port": None}
        factory = _fake_factory(record, send_error=send_error)
        outcome = run_reference(
            case["account"], case["config"], case["message"], factory, record
        )
        expected = dict(case["expected"])
        actual = _actual(outcome)
        assert actual["error"] == expected["error"], case["name"]
        assert actual["factory_calls"] == expected["factory_calls"], case["name"]
        assert actual["port"] == expected["port"], case["name"]
        assert actual["from_email"] == expected["from_email"], case["name"]
        assert actual["to_header"] == expected["to_header"], case["name"]
        assert actual["deliveries"] == expected["deliveries"], case["name"]
        assert actual["quit_calls"] == expected["quit_calls"], case["name"]
        assert actual["receipt"] == expected["receipt"], case["name"]
        if expected["message_contains"] is not None:
            for fragment in expected["message_contains"]:
                assert fragment in outcome["error_message"], case["name"]
        if expected["message_not_contains"] is not None:
            for fragment in expected["message_not_contains"]:
                assert fragment not in outcome["error_message"], case["name"]
        assert "ValueError" in text, "el contrato no declara rechazo con ValueError"


def test_missing_confirmation_never_connects():
    base = {"to": ["ana@example.com"], "subject": "Hola", "body": "Texto."}
    account = {"account_id": "personal", "email": "yo@inbox.test"}
    config = {"host": "smtp.example.test", "username": "usuario", "password": "s"}
    for confirmed in (None, False, 1, "true", "yes", 0, "True", []):
        record = {"factory_calls": 0, "connections": [], "host_port": None}
        message = dict(base, confirmed=confirmed)
        outcome = run_reference(
            account, config, message, _fake_factory(record), record
        )
        assert outcome["error"] == "ValueError", "confirmed=" + repr(confirmed)
        assert outcome["receipt"] is None
        assert record["factory_calls"] == 0, "conecto sin confirmacion"
        assert record["connections"] == []
        assert record["host_port"] is None


def test_fake_captures_single_delivery_on_success():
    account = {"account_id": "personal", "email": "yo@inbox.test"}
    config = {"host": "smtp.example.test", "username": "usuario", "password": "s"}
    message = {"confirmed": True, "to": ["ana@example.com"], "subject": "Hola", "body": "Texto."}
    record = {"factory_calls": 0, "connections": [], "host_port": None}
    outcome = run_reference(account, config, message, _fake_factory(record), record)
    assert outcome["error"] is None
    assert record["factory_calls"] == 1, "el fake debe capturar una sola conexion"
    assert record["host_port"] == ("smtp.example.test", 587)
    connections = record["connections"]
    assert len(connections) == 1
    fake = connections[0]
    assert fake.login_calls == [("usuario", "s")]
    assert len(fake.sent_messages) == 1, "el fake debe capturar una sola entrega"
    assert fake.quit_calls == 1, "la sesion debe cerrarse una vez"
    receipt = outcome["receipt"]
    assert list(receipt) == ["account_id", "from_email", "to", "subject", "sent"]
    assert receipt["sent"] is True
    assert json.dumps(receipt) == json.dumps(
        {
            "account_id": "personal",
            "from_email": "yo@inbox.test",
            "to": ["ana@example.com"],
            "subject": "Hola",
            "sent": True,
        }
    )
    assert "password" not in json.dumps(receipt)
    assert "Texto." not in json.dumps(receipt)
    # El fake es la unica red: sin fabrica no hay conexion posible aqui.


def test_transport_error_wraps_without_leaking_password():
    account = {"account_id": "personal", "email": "yo@inbox.test"}
    config = {
        "host": "smtp.example.test",
        "username": "usuario",
        "password": "frozen-secret-x",
    }
    message = {"confirmed": True, "to": ["ana@example.com"], "subject": "Hola", "body": "Cuerpo privado."}
    record = {"factory_calls": 0, "connections": [], "host_port": None}
    factory = _fake_factory(
        record, send_error="smtplib.SMTPAuthenticationError: boom"
    )
    outcome = run_reference(account, config, message, factory, record)
    assert outcome["error"] == "RuntimeError"
    assert outcome["receipt"] is None
    error_message = outcome["error_message"]
    assert "smtp.example.test" in error_message
    assert "personal" in error_message
    assert "frozen-secret-x" not in error_message
    assert "Cuerpo privado." not in error_message
    assert record["connections"][0].quit_calls == 1, "quit en finally"
    assert record["connections"][0].sent_messages == []


def test_contract_documents_exact_rules():
    text = _contract_text()
    assert "message[\"confirmed\"] is True" in text, "confirmacion no estricta"
    assert '"true"' in text and "1" in text, "sin variantes no booleanas rechazadas"
    assert "smtplib.SMTP(host, port)" in text, "fabrica por defecto no documentada"
    assert "smtplib.SMTP_SSL" in text, "fabrica por defecto 465 no documentada"
    assert "puerto `465`" in text, "seleccion por puerto no documentada"
    assert "quit()` se ejecuta en un `finally" in text, "cierre no en finally"
    assert "email.message.EmailMessage()" in text, "EmailMessage no documentado"
    assert "`sent` (`True`)" in text, "recibo sin sent True documentado"
    assert "nunca la password" in text, "password en errores no prohibida"
    assert "sin logs" in text and "no escribe disco" in text, "sin prohibicion de disco/log"
    assert "RuntimeError" in text, "envoltura de transporte no documentada"


def test_oracle_is_independent_and_offline():
    source = Path(__file__).read_text(encoding="utf-8")
    prefix_import = "import "
    prefix_from = "from "
    for forbidden in ("src", "smtplib", "socket"):
        assert prefix_import + forbidden not in source, (
            "el oracle no debe importar " + forbidden
        )
        assert prefix_from + forbidden not in source, (
            "el oracle no debe importar " + forbidden
        )
    assert "ope" + "n(" not in source, "el oracle no debe leer/escribir archivos"