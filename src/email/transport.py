"""Verified mail transports; authentication belongs to the caller."""

import imaplib
import smtplib
import ssl

TIMEOUT_SECONDS = 30


def open_imap(host, port):
    return imaplib.IMAP4_SSL(
        host, port, ssl_context=ssl.create_default_context(),
        timeout=TIMEOUT_SECONDS,
    )


def open_smtp(host, port):
    if port == 465:
        return smtplib.SMTP_SSL(
            host, port, context=ssl.create_default_context(),
            timeout=TIMEOUT_SECONDS,
        )
    return smtplib.SMTP(host, port, timeout=TIMEOUT_SECONDS)


def secure_smtp(connection, port):
    if port != 465:
        connection.starttls(context=ssl.create_default_context())
