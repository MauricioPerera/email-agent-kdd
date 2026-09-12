"""Comprobaciones de conexion de correo sin descargar ni enviar mensajes."""

import imaplib
import smtplib
from src.email.transport import open_imap, open_smtp, secure_smtp


def verify_email_connection(account: dict, servers: dict, password: str,
                            imap_factory=None, smtp_factory=None) -> dict:
    """Verificar IMAP y SMTP antes de persistir una cuenta.

    La contrasena solo vive durante esta llamada. SMTP autentica, pero nunca
    construye ni envia un mensaje.
    """
    email = account.get("email") if isinstance(account, dict) else None
    if not isinstance(email, str) or not email or not isinstance(servers, dict):
        raise ValueError("datos de conexion invalidos")
    if not isinstance(password, str) or not password:
        raise ValueError("password invalida")
    imap_host = servers.get("imap_host")
    imap_port = servers.get("imap_port")
    smtp_host = servers.get("smtp_host")
    smtp_port = servers.get("smtp_port")
    if not all(isinstance(value, str) and value for value in (imap_host, smtp_host)):
        raise ValueError("host invalido")
    if not all(isinstance(value, int) and 1 <= value <= 65535 for value in (imap_port, smtp_port)):
        raise ValueError("puerto invalido")

    imap_factory = imap_factory or open_imap
    smtp_factory = smtp_factory or open_smtp
    imap = None
    smtp = None
    try:
        imap = imap_factory(imap_host, imap_port)
        imap.login(email, password)
        imap.select("INBOX", readonly=True)
    except Exception as exc:
        raise RuntimeError("imap_authentication_failed") from exc
    finally:
        if imap is not None:
            for action in ("close", "logout"):
                try:
                    getattr(imap, action)()
                except Exception:
                    pass
    try:
        smtp = smtp_factory(smtp_host, smtp_port)
        secure_smtp(smtp, smtp_port)
        smtp.login(email, password)
    except Exception as exc:
        raise RuntimeError("smtp_authentication_failed") from exc
    finally:
        if smtp is not None:
            try:
                smtp.quit()
            except Exception:
                pass
    return {"imap_verified": True, "smtp_verified": True}
