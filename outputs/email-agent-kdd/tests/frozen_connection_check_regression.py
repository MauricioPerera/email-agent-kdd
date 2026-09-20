"""Regression test for IMAP mailbox-selection verification."""

import pytest

from src.email.connection_check import verify_email_connection


class _Imap:
    def __init__(self):
        self.closed = False
        self.logged_out = False

    def login(self, user, password):
        return "OK", []

    def select(self, mailbox, readonly=False):
        assert mailbox == "INBOX"
        assert readonly is True
        return "NO", [b"INBOX unavailable"]

    def close(self):
        self.closed = True

    def logout(self):
        self.logged_out = True


class _Smtp:
    def login(self, user, password):
        raise AssertionError("SMTP no debe ejecutarse si INBOX no se puede abrir")

    def quit(self):
        pass


def test_imap_mailbox_selection_failure_is_rejected_before_save():
    imap = _Imap()
    with pytest.raises(RuntimeError, match="imap_authentication_failed"):
        verify_email_connection(
            {"email": "user@example.com"},
            {
                "imap_host": "imap.example.com",
                "imap_port": 993,
                "smtp_host": "smtp.example.com",
                "smtp_port": 587,
            },
            "secret-not-real",
            imap_factory=lambda host, port: imap,
            smtp_factory=lambda host, port: _Smtp(),
        )
    assert imap.closed and imap.logged_out
