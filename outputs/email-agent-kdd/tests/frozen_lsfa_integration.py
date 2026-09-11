"""Pruebas del puente declarativo email-agent-kdd ↔ LSFA."""

from src.email.lsfa_bridge import connect_email_request, send_email_request


def test_connect_request_declares_secret_without_value():
    request = connect_email_request()
    assert request["operation"] == "connect_email"
    assert request["validation"]["preflight"] == "imap_auth_and_smtp_auth"
    secret_fields = [field for field in request["fields"] if field["sensitivity"] == "secret"]
    assert [field["name"] for field in secret_fields] == ["password"]
    assert all("value" not in field for field in request["fields"])


def test_send_request_requires_high_risk_confirmation():
    request = send_email_request()
    assert request["operation"] == "send_email"
    assert request["risk"] == "high"
    assert request["confirmation"] == {"method": "pin", "required": True, "summary": ["to", "subject"]}
    assert all("value" not in field for field in request["fields"])
