"""Transport policy checks; integration TLS evidence is tracked separately."""

import ssl
import pytest
from src.email import transport


@pytest.mark.parametrize("protocol,port", [("imap", 993), ("smtp", 465)])
def test_implicit_tls_verifies_certificate_hostname_and_timeout(monkeypatch, protocol, port):
    calls = []
    def factory(host, port, **kwargs):
        calls.append(kwargs)
        return object()
    if protocol == "imap":
        monkeypatch.setattr(transport.imaplib, "IMAP4_SSL", factory)
        transport.open_imap("mail.example.test", port)
        context = calls[0]["ssl_context"]
    else:
        monkeypatch.setattr(transport.smtplib, "SMTP_SSL", factory)
        transport.open_smtp("mail.example.test", port)
        context = calls[0]["context"]
    assert context.verify_mode == ssl.CERT_REQUIRED
    assert context.check_hostname is True
    assert calls[0]["timeout"] == 30


def test_starttls_requires_verified_context():
    class Connection:
        def starttls(self, *, context):
            assert context.verify_mode == ssl.CERT_REQUIRED
            assert context.check_hostname
    transport.secure_smtp(Connection(), 587)


def test_missing_starttls_is_rejected():
    with pytest.raises(AttributeError):
        transport.secure_smtp(object(), 587)


def test_quit_failure_does_not_turn_accepted_delivery_into_failure():
    from src.email.smtp_send import send_smtp_message
    events = []
    class Connection:
        def login(self, *args):
            events.append('login')
        def send_message(self, message):
            events.append('accepted')
            return {}
        def quit(self):
            raise OSError('connection lost after acceptance')
        def close(self):
            events.append('closed')
    receipt = send_smtp_message(
        {'account_id': 'test', 'email': 'sender@example.test'},
        {'host': 'smtp.example.test', 'port': 465,
         'username': 'test', 'password': 'synthetic'},
        {'confirmed': True, 'to': ['recipient@example.test'],
         'subject': 'test', 'body': 'test'},
        connection_factory=lambda host, port: Connection(),
    )
    assert receipt['sent'] is True
    assert events == ['login', 'accepted', 'closed']
