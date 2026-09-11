"""Oracle congelado e independiente para parse_raw_email.

Los valores esperados (hashes, cuerpos, metadatos) se calculan inline con
stdlib, sin helpers del target bajo prueba. La lista `delivered_to` esperada
se deriva del modelo de referencia del oraculo de delivery-recipient
(getaddresses sobre los headers de envelope, dedup exacta, orden estable),
reimplementada aqui; jamas se canonicaliza (puntos/+tag/minusculas).
"""

import email.utils
import hashlib

import pytest

from src.email.parse import parse_raw_email


def _sha256(data):
    return hashlib.sha256(data).hexdigest()


def _model_delivered_to(raw_message):
    import email

    message = email.message_from_bytes(raw_message)
    collected = []
    for name in ("Delivered-To", "X-Original-To", "Envelope-To"):
        for value in message.get_all(name, []):
            for _display, addr_spec in email.utils.getaddresses([str(value)]):
                addr = addr_spec.strip()
                if addr and "@" in addr:
                    collected.append(addr)
    return sorted(set(collected))


SIMPLE_RAW = (
    b"From: Ana Garcia <ana@example.com>\n"
    b"To: user@example.com\n"
    b"Cc: bob@example.com\n"
    b"Subject: Hola\n"
    b"Date: Wed, 10 Sep 2026 10:00:00 +0000\n"
    b"Message-ID: <msg-1@example.com>\n"
    b"\n"
    b"Hola desde el MVP."
)

PDF_CONTENT = b"%PDF-"

MULTIPART_RAW = (
    b"From: a@example.com\n"
    b"To: user@example.com\n"
    b"Subject: Reporte\n"
    b"MIME-Version: 1.0\n"
    b'Content-Type: multipart/mixed; boundary="BOUND"\n'
    b"\n"
    b"--BOUND\n"
    b"Content-Type: text/plain; charset=utf-8\n"
    b"\n"
    b"Cuerpo en texto.\n"
    b"--BOUND\n"
    b"Content-Type: application/pdf; name=informe.pdf\n"
    b"Content-Disposition: attachment; filename=informe.pdf\n"
    b"Content-Transfer-Encoding: base64\n"
    b"\n"
    b"JVBERi0=\n"
    b"--BOUND--\n"
)

HTML_RAW = (
    b"From: a@example.com\n"
    b"To: user@example.com\n"
    b"Subject: Html\n"
    b"Content-Type: text/html; charset=utf-8\n"
    b"\n"
    b"<p>Solo html</p>"
)

MULTIPART_HTML_RAW = (
    b"From: a@example.com\n"
    b"Subject: Fallback\n"
    b"MIME-Version: 1.0\n"
    b'Content-Type: multipart/alternative; boundary="ALT"\n'
    b"\n"
    b"--ALT\n"
    b"Content-Type: text/html; charset=utf-8\n"
    b"\n"
    b"<p>Fallback html</p>\n"
    b"--ALT--\n"
)

THREAD_RAW = (
    b"From: a@example.com\n"
    b"To: user@example.com\n"
    b"Subject: Re: Hola\n"
    b"In-Reply-To: <msg-1@example.com>\n"
    b"References: <msg-1@example.com> <msg-0@example.com>\n"
    b"\n"
    b"Respuesta."
)

LATIN1_RAW = (
    b"From: a@example.com\n"
    b"Subject: Codificacion\n"
    b"Content-Type: text/plain; charset=iso-8859-1\n"
    b"\n"
    b"Calend\xe1rio"
)

REPLACEMENT_RAW = (
    b"From: a@example.com\n"
    b"Subject: Roto\n"
    b"Content-Type: text/plain; charset=utf-8\n"
    b"\n"
    b"A\xffB"
)

DELIVERY_RAW = (
    b"From: Ana Garcia <ana@example.com>\n"
    b"To: user@example.com\n"
    b"Subject: Entrega\n"
    b"Delivered-To: user+newsletters@example.com\n"
    b"X-Original-To: user@example.com\n"
    b"\n"
    b"Entregado al buzon real."
)

DELIVERY_NAME_BRACKETS_RAW = (
    b"From: a@example.com\n"
    b"To: user@example.com\n"
    b"Subject: Envelope\n"
    b"Envelope-To: <U.SER@example.com>\n"
    b"\n"
    b"Cuerpo."
)

NO_DELIVERY_RAW = SIMPLE_RAW


def test_rejects_non_bytes_raw_message():
    with pytest.raises(ValueError):
        parse_raw_email("no-bytes", "personal")
    with pytest.raises(ValueError):
        parse_raw_email(None, "personal")


def test_rejects_empty_account_id():
    with pytest.raises(ValueError):
        parse_raw_email(SIMPLE_RAW, "")
    with pytest.raises(ValueError):
        parse_raw_email(SIMPLE_RAW, None)


def test_simple_message_full_record():
    record = parse_raw_email(SIMPLE_RAW, "personal")
    assert record == {
        "type": "email",
        "account_id": "personal",
        "subject": "Hola",
        "from": "Ana Garcia <ana@example.com>",
        "to": "user@example.com",
        "cc": "bob@example.com",
        "date": "Thu, 10 Sep 2026 10:00:00 +0000",
        "message_id": "<msg-1@example.com>",
        "in_reply_to": "",
        "references": "",
        "body": "Hola desde el MVP.",
        "raw_sha256": _sha256(SIMPLE_RAW),
        "attachments": [],
    }


def test_parse_is_deterministic():
    assert parse_raw_email(SIMPLE_RAW, "personal") == parse_raw_email(
        SIMPLE_RAW, "personal"
    )


def test_multipart_prefers_plain_and_attachment_metadata_only():
    record = parse_raw_email(MULTIPART_RAW, "work")
    # La newline previa al boundary pertenece al delimitador MIME (RFC 2046).
    assert record["body"] == "Cuerpo en texto."
    assert record["attachments"] == [
        {
            "filename": "informe.pdf",
            "content_type": "application/pdf",
            "size": len(PDF_CONTENT),
            "sha256": _sha256(PDF_CONTENT),
        }
    ]
    assert "content" not in record["attachments"][0]


def test_html_body_when_no_plain():
    record = parse_raw_email(HTML_RAW, "personal")
    assert record["body"] == "<p>Solo html</p>"


def test_multipart_html_fallback():
    record = parse_raw_email(MULTIPART_HTML_RAW, "personal")
    assert record["body"] == "<p>Fallback html</p>"


def test_threading_headers_are_captured():
    record = parse_raw_email(THREAD_RAW, "personal")
    assert record["in_reply_to"] == "<msg-1@example.com>"
    assert record["references"] == "<msg-1@example.com> <msg-0@example.com>"


def test_charset_decoded_safely():
    record = parse_raw_email(LATIN1_RAW, "personal")
    assert record["body"] == "Calend\xe1rio"


def test_invalid_bytes_replaced():
    record = parse_raw_email(REPLACEMENT_RAW, "personal")
    assert record["body"] == "A�B"


def test_missing_headers_are_empty_and_serializable():
    record = parse_raw_email(b"Subject: solo\n\nx", "personal")
    import json

    json.dumps(record)
    assert record["from"] == ""
    assert record["message_id"] == ""


def test_delivery_recipient_captured_verbatim_no_canonicalization():
    record = parse_raw_email(DELIVERY_RAW, "personal")
    assert record["delivered_to"] == _model_delivered_to(DELIVERY_RAW)
    # Las variantes con puntos y +tag NO se colapsan: verbatim cada una.
    assert record["delivered_to"] == ["user+newsletters@example.com", "user@example.com"]
    import json

    json.dumps(record)


def test_delivery_recipient_from_bracketed_envelope_to():
    record = parse_raw_email(DELIVERY_NAME_BRACKETS_RAW, "personal")
    # Verbatim: sin minusculas ni colapso de puntos del local part.
    assert record["delivered_to"] == ["U.SER@example.com"]
    assert record["delivered_to"] == _model_delivered_to(DELIVERY_NAME_BRACKETS_RAW)


def test_no_delivery_headers_omits_key_for_backward_compat():
    record = parse_raw_email(NO_DELIVERY_RAW, "personal")
    assert "delivered_to" not in record, (
        "la clave debe ausentarse sin headers de entrega (compat de nodos ya persistidos)"
    )


def test_delivery_key_matches_oracle_model():
    for raw in (DELIVERY_RAW, DELIVERY_NAME_BRACKETS_RAW, THREAD_RAW):
        record = parse_raw_email(raw, "personal")
        expected = _model_delivered_to(raw)
        if expected:
            assert record["delivered_to"] == expected
        else:
            assert "delivered_to" not in record