"""Pruebas del puente declarativo email-agent-kdd ↔ LSFA."""

import pytest

from src.email.lsfa_bridge import (
    connect_email_request,
    send_email_request,
    validate_lsfa_request,
)


def test_connect_request_declares_secret_without_value():
    request = connect_email_request()
    assert request["operation"] == "connect_email"
    assert request["validation"]["preflight"] == "imap_auth_and_smtp_auth"
    secret_fields = [field for field in request["fields"] if field["sensitivity"] == "secret"]
    assert [field["name"] for field in secret_fields] == ["password"]
    assert all("value" not in field for field in request["fields"])
    assert validate_lsfa_request(request) is True
    assert request["confirmation"]["single_use"] is True


def test_send_request_requires_high_risk_confirmation():
    request = send_email_request()
    assert request["operation"] == "send_email"
    assert request["risk"] == "high"
    assert request["confirmation"] == {
        "method": "pin",
        "required": True,
        "summary": ["to", "subject"],
        "single_use": True,
    }
    assert all("value" not in field for field in request["fields"])
    assert validate_lsfa_request(request) is True


def test_validator_rejects_secret_values_and_reusable_confirmation():
    request = connect_email_request()
    request["fields"][0]["value"] = "should-not-be-here"
    with pytest.raises(ValueError, match="must not include field values"):
        validate_lsfa_request(request)

    request = send_email_request()
    request["confirmation"]["single_use"] = False
    with pytest.raises(ValueError, match="single-use"):
        validate_lsfa_request(request)
