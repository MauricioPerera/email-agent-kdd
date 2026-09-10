"""Oracle congelado e independiente para normalize_email.

NO importa src.email.normalize ni ningún otro target: el contrato esperado
vive aquí como casos y errores congelados (hashes literales) y como una
referencia stdlib propia. La implementación real en src/email/normalize.py
debe reproducir exactamente los registros congelados de este archivo.
"""

import email
import hashlib
import json
import re
from pathlib import Path

import pytest

CONTRACT_PATH = (
    Path(__file__).resolve().parents[1]
    / "knowledge"
    / "contracts"
    / "normalize-email.md"
)

PLAIN_RAW = (
    b"From: Ana Garcia <ana@example.com>\n"
    b"To: user@example.com\n"
    b"Subject: Hola\n"
    b"\n"
    b"Hola desde el MVP."
)

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

HTML_ONLY_RAW = (
    b"From: a@example.com\n"
    b"To: user@example.com\n"
    b"Subject: Html\n"
    b"Content-Type: text/html; charset=utf-8\n"
    b"\n"
    b"<p>Solo html</p>"
)

MULTIPART_NO_PLAIN_RAW = (
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

BAD_UTF8_RAW = (
    b"From: a@example.com\n"
    b"Subject: Roto\n"
    b"Content-Type: text/plain; charset=utf-8\n"
    b"\n"
    b"A\xffB"
)

HEADERS_ONLY_RAW = b"Subject: solo\n\n"

PLAIN_SHA256 = "33399744d24298f2a37e46f7a04758ee47549ecf83f36310278583703d483337"
MULTIPART_SHA256 = "192abb0c62dc118bc832122a0ca909b9d4b38dfcce79721fed6071cfc7a06383"
HTML_ONLY_SHA256 = "99b1fc11a9beea112d9065decb5d922b10900959d8a5a6a1c628661f59daa6ac"
MULTIPART_NO_PLAIN_SHA256 = (
    "87dabfb3df16ba298c58af88e435c30253be53b0a6af7db1455bc2f52f26ba17"
)
BAD_UTF8_SHA256 = "100a75965a21d31ed07accc524f6a99b2be0cd2aa2ff7a6ca7a8376c1b47343a"
HEADERS_ONLY_SHA256 = "b4ea8c6717a7cc2c9259cc1e69e9b14b3ed9531898002db53d1783d6fa5db0df"
PDF_CONTENT_SHA256 = (
    "38523c087796e5d5dd1cf9bad1fb026781a838dd9dd2cf8af58b9f6502a46778"
)

PDF_CONTENT = b"%PDF-"


def _frozen_record(account_id, headers, body, attachments, raw, raw_sha256):
    return {
        "account_id": account_id,
        "headers": headers,
        "body": body,
        "attachments": attachments,
        "raw": raw,
        "raw_sha256": raw_sha256,
    }


FROZEN_CASES = {
    "plain": (
        PLAIN_RAW,
        "personal",
        _frozen_record(
            "personal",
            {
                "from": "Ana Garcia <ana@example.com>",
                "to": "user@example.com",
                "subject": "Hola",
            },
            "Hola desde el MVP.",
            [],
            PLAIN_RAW,
            PLAIN_SHA256,
        ),
    ),
    "multipart_with_body_and_attachment": (
        MULTIPART_RAW,
        "work",
        _frozen_record(
            "work",
            {
                "from": "a@example.com",
                "to": "user@example.com",
                "subject": "Reporte",
                "mime-version": "1.0",
                "content-type": 'multipart/mixed; boundary="BOUND"',
            },
            "Cuerpo en texto.",
            [
                {
                    "name": "informe.pdf",
                    "mime_type": "application/pdf",
                    "size": len(PDF_CONTENT),
                    "content": PDF_CONTENT,
                    "sha256": PDF_CONTENT_SHA256,
                }
            ],
            MULTIPART_RAW,
            MULTIPART_SHA256,
        ),
    ),
    "html_only_has_empty_body": (
        HTML_ONLY_RAW,
        "personal",
        _frozen_record(
            "personal",
            {
                "from": "a@example.com",
                "to": "user@example.com",
                "subject": "Html",
                "content-type": "text/html; charset=utf-8",
            },
            "",
            [],
            HTML_ONLY_RAW,
            HTML_ONLY_SHA256,
        ),
    ),
    "multipart_without_plain_has_empty_body": (
        MULTIPART_NO_PLAIN_RAW,
        "work",
        _frozen_record(
            "work",
            {
                "from": "a@example.com",
                "subject": "Fallback",
                "mime-version": "1.0",
                "content-type": 'multipart/alternative; boundary="ALT"',
            },
            "",
            [],
            MULTIPART_NO_PLAIN_RAW,
            MULTIPART_NO_PLAIN_SHA256,
        ),
    ),
    "bad_utf8_replaced": (
        BAD_UTF8_RAW,
        "personal",
        _frozen_record(
            "personal",
            {
                "from": "a@example.com",
                "subject": "Roto",
                "content-type": "text/plain; charset=utf-8",
            },
            "A\uFFFDB",
            [],
            BAD_UTF8_RAW,
            BAD_UTF8_SHA256,
        ),
    ),
    "headers_only_empty_body": (
        HEADERS_ONLY_RAW,
        "personal",
        _frozen_record(
            "personal",
            {"subject": "solo"},
            "",
            [],
            HEADERS_ONLY_RAW,
            HEADERS_ONLY_SHA256,
        ),
    ),
}

FROZEN_INVALID_RAW = [
    ("bytearray", bytearray(PLAIN_RAW)),
    ("str", "From: a@example.com\n\ntexto"),
    ("list", [1, 2, 3]),
    ("memoryview", memoryview(PLAIN_RAW)),
    ("none", None),
    ("int", 7),
]

FROZEN_INVALID_ACCOUNT = [
    ("empty", ""),
    ("whitespace", "   "),
    ("tabs", "\t\n"),
    ("none", None),
    ("int", 7),
    ("bytes", b"personal"),
]


def _ref_decoded(part):
    return part.get_payload(decode=True) or b""


def _ref_attachment(part):
    content = _ref_decoded(part)
    return {
        "name": part.get_filename() or "",
        "mime_type": part.get_content_type(),
        "size": len(content),
        "content": content,
        "sha256": hashlib.sha256(content).hexdigest(),
    }


def _ref_scan(raw):
    body = None
    attachments = []
    for part in email.message_from_bytes(raw).walk():
        if part.is_multipart():
            continue
        if "attachment" in (part.get("Content-Disposition") or "").lower():
            attachments.append(_ref_attachment(part))
        elif body is None and part.get_content_type() == "text/plain":
            body = _ref_decoded(part).decode("utf-8", errors="replace")
    return body if body is not None else "", attachments


def _reference_normalize(raw_message, account_id):
    """Referencia stdlib del contrato; NO es el target bajo prueba."""
    if not isinstance(raw_message, bytes):
        raise ValueError("raw_message debe ser bytes")
    if not isinstance(account_id, str) or not account_id.strip():
        raise ValueError("account_id debe ser str no vacío")
    body, attachments = _ref_scan(raw_message)
    message = email.message_from_bytes(raw_message)
    return {
        "account_id": account_id,
        "headers": {
            name.lower(): value for name, value in message.items()
        },
        "body": body,
        "attachments": attachments,
        "raw": raw_message,
        "raw_sha256": hashlib.sha256(raw_message).hexdigest(),
    }


def _contract_text():
    return CONTRACT_PATH.read_text(encoding="utf-8")


def _frontmatter():
    match = re.match(r"^---\n(.*?)\n---\n", _contract_text(), re.DOTALL)
    assert match, "el contrato debe tener front-matter YAML delimitado por ---"
    return match.group(1)


def test_contract_declares_strengthened_front_matter():
    fm = _frontmatter()
    assert "task: normalize_email" in fm
    assert "target: src/email/normalize.py" in fm
    assert (
        'signature: "def normalize_email(raw_message: bytes, account_id: str) -> dict"'
        in fm
    )
    assert "tests: tests/frozen_normalize_email.py" in fm
    assert (
        "test_command: python -m pytest tests/frozen_normalize_email.py -q" in fm
    )
    assert "deps_allowed: [email, hashlib]" in fm
    assert "cyclomatic_max: 12" in fm
    assert "nesting_max: 4" in fm
    assert "lines_max: 80" in fm
    assert "params_max: 3" in fm
    for forbidden in ("eval", "exec", "subprocess", "network_access", "file_write"):
        assert forbidden in fm


def test_contract_declares_explicit_decisions():
    body = _contract_text()
    for marker in (
        "bytearray",
        "whitespace",
        "raw_sha256",
        "lower-case",
        'errors="replace"',
        "U+FFFD",
        # Decisión de body vacio, en ASCII: no depender del caracter acentuado
        # (el contrato lo declara como "`body` vac" + accento).
        "body` vac",
        '"content"',
        "## KDD",
        "## PARAR",
    ):
        assert marker in body, marker


def test_oracle_is_independent_of_target():
    source = Path(__file__).read_text(encoding="utf-8")
    # Tokens separados: el propio texto de esta aserción no debe disparar
    # el detector (ninguna línea importa del target).
    assert ("from" + " src") not in source
    assert ("import" + " src") not in source


def test_frozen_cases_match_reference():
    for name, (raw, account_id, expected) in FROZEN_CASES.items():
        assert _reference_normalize(raw, account_id) == expected, name


def test_reference_is_deterministic():
    for raw, account_id, expected in FROZEN_CASES.values():
        first = _reference_normalize(raw, account_id)
        assert first == _reference_normalize(raw, account_id)
        assert first == expected


def test_hash_is_sha256_of_exact_original_bytes():
    for raw, _account_id, expected in FROZEN_CASES.values():
        assert expected["raw"] == raw
        assert expected["raw_sha256"] == hashlib.sha256(raw).hexdigest()
        record = _reference_normalize(raw, "acc")
        assert record["raw_sha256"] == hashlib.sha256(raw).hexdigest()


def test_headers_are_lower_case_and_json_serializable():
    for _raw, _account_id, expected in FROZEN_CASES.values():
        json.dumps(expected["headers"])
        for key in expected["headers"]:
            assert key == key.lower()


def test_attachment_carries_name_mime_size_content_and_sha256():
    record = _reference_normalize(MULTIPART_RAW, "work")
    assert record["attachments"] == [
        {
            "name": "informe.pdf",
            "mime_type": "application/pdf",
            "size": len(PDF_CONTENT),
            "content": PDF_CONTENT,
            "sha256": PDF_CONTENT_SHA256,
        }
    ]


def test_html_only_and_multipart_without_plain_have_empty_body():
    assert _reference_normalize(HTML_ONLY_RAW, "personal")["body"] == ""
    assert _reference_normalize(MULTIPART_NO_PLAIN_RAW, "work")["body"] == ""


def test_bad_utf8_body_is_replaced_not_raised():
    record = _reference_normalize(BAD_UTF8_RAW, "personal")
    assert record["body"] == "A\uFFFDB"


@pytest.mark.parametrize("name,bad", FROZEN_INVALID_RAW)
def test_rejects_invalid_raw_message(name, bad):
    with pytest.raises(ValueError):
        _reference_normalize(bad, "personal")


@pytest.mark.parametrize("name,bad", FROZEN_INVALID_ACCOUNT)
def test_rejects_invalid_account_id(name, bad):
    with pytest.raises(ValueError):
        _reference_normalize(PLAIN_RAW, bad)