"""Real TLS handshakes using ephemeral synthetic certificates on loopback."""

import datetime
import socket
import ssl
import threading

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from src.email import transport


@pytest.mark.parametrize('trust', [False, True])
@pytest.mark.parametrize('protocol', ['imap', 'smtp'])
def test_rejects_untrusted_or_wrong_hostname_before_auth(tmp_path, monkeypatch, trust, protocol):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, 'wrong.example.test')])
    now = datetime.datetime.now(datetime.timezone.utc)
    certificate = (x509.CertificateBuilder().subject_name(name).issuer_name(name)
                   .public_key(key.public_key()).serial_number(x509.random_serial_number())
                   .not_valid_before(now - datetime.timedelta(minutes=1))
                   .not_valid_after(now + datetime.timedelta(days=1))
                   .add_extension(x509.SubjectAlternativeName([x509.DNSName('wrong.example.test')]), False)
                   .sign(key, hashes.SHA256()))
    cert = tmp_path / 'synthetic.pem'
    private = tmp_path / 'synthetic-key.pem'
    cert.write_bytes(certificate.public_bytes(serialization.Encoding.PEM))
    private.write_bytes(key.private_bytes(serialization.Encoding.PEM,
                        serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    server_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    server_context.load_cert_chain(cert, private)
    if trust:
        original = ssl.create_default_context
        monkeypatch.setattr(transport.ssl, 'create_default_context',
                            lambda: original(cafile=str(cert)))
    received = []
    errors = []
    listener = socket.socket()
    listener.bind(('127.0.0.1', 0))
    listener.listen(1)
    listener.settimeout(5)
    port = listener.getsockname()[1]
    def serve():
        try:
            with listener.accept()[0] as raw:
                raw.settimeout(5)
                if protocol == 'smtp':
                    raw.sendall(b'220 localhost\r\n')
                    with raw.makefile('rb') as commands:
                        assert commands.readline().startswith(b'ehlo')
                        raw.sendall(b'250-localhost\r\n250 STARTTLS\r\n')
                        assert commands.readline().strip().upper() == b'STARTTLS'
                        raw.sendall(b'220 ready\r\n')
                try:
                    with server_context.wrap_socket(raw, server_side=True) as secure:
                        received.append(secure.recv(4096))
                except (ssl.SSLError, ConnectionResetError):
                    pass  # Expected client rejection during handshake.
        except Exception as exc:
            errors.append(exc)
    thread = threading.Thread(target=serve, daemon=True)
    thread.start()
    try:
        with pytest.raises(ssl.SSLCertVerificationError) as caught:
            if protocol == 'imap':
                transport.open_imap('127.0.0.1', port)
            else:
                connection = transport.open_smtp('127.0.0.1', port)
                try:
                    transport.secure_smtp(connection, port)
                finally:
                    connection.close()
        if trust:
            assert 'IP address mismatch' in str(caught.value)
        else:
            assert 'self-signed' in str(caught.value)
    finally:
        thread.join(6)
        listener.close()
    assert not thread.is_alive()
    assert errors == []
    assert received == []
