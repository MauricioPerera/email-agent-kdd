"""SMTP integration on loopback only, with synthetic credentials."""

import socket
import threading

import pytest

from src.email.smtp_send import send_smtp_message


def test_server_without_starttls_never_receives_auth_or_message():
    commands = []
    errors = []
    listener = socket.socket()
    listener.bind(('127.0.0.1', 0))
    listener.listen(1)
    listener.settimeout(5)
    port = listener.getsockname()[1]

    def serve():
        try:
            with listener.accept()[0] as connection:
                connection.settimeout(5)
                with connection.makefile('rwb') as stream:
                    stream.write(b'220 localhost test server\r\n')
                    stream.flush()
                    while True:
                        line = stream.readline(4096)
                        if not line:
                            break
                        command = line.split()[0].upper()
                        commands.append(command)
                        if command == b'EHLO':
                            # AUTH is advertised deliberately; STARTTLS is absent.
                            stream.write(b'250-localhost\r\n250 AUTH PLAIN LOGIN\r\n')
                        elif command == b'QUIT':
                            stream.write(b'221 bye\r\n')
                            stream.flush()
                            break
                        else:
                            stream.write(b'500 unexpected command\r\n')
                        stream.flush()
        except Exception as exc:
            errors.append(exc)

    thread = threading.Thread(target=serve, daemon=True)
    thread.start()
    try:
        with pytest.raises(RuntimeError, match='SMTPNotSupportedError'):
            send_smtp_message(
                {'account_id': 'test', 'email': 'sender@example.test'},
                {'host': '127.0.0.1', 'port': port, 'username': 'synthetic',
                 'password': 'synthetic-secret'},
                {'confirmed': True, 'to': ['recipient@example.test'],
                 'subject': 'synthetic', 'body': 'synthetic'},
            )
    finally:
        thread.join(timeout=6)
        listener.close()
    assert not thread.is_alive()
    assert errors == []
    assert commands == [b'EHLO', b'QUIT']
