"""Tests congelados del contrato fetch_imap_messages.

Oracle independiente: no importa el target ni src.email, no abre sockets y
no escribe disco. Verifica el frontmatter del contrato (budgets, deps,
forbids), las 7 secciones, la frase `PARAR y reportar si` y los casos
congelados recomputando con un modelo de referencia propio las reglas
documentadas: defaults de mailbox/limit, limit 1..100 (bool rechazado),
cursor opcional since_uid (int no bool >= 0, filtro estricto antes de
ordenar y truncar), campos obligatorios de account/config, orden
ascendente de ids, metadato transitorio imap_uid (int) de cada registro
igual al id solicitado, en orden y tambien bajo since_uid y limit,
secuencia IMAP fija con select readonly, envoltura de errores en
RuntimeError sin password, y cierre/logout en finally incluso ante
fallos.
"""

import json
from pathlib import Path
import re

CONTRACT = (
    Path(__file__).resolve().parents[1]
    / "knowledge"
    / "contracts"
    / "fetch-imap-messages.md"
)

DEFAULT_MAILBOX = "INBOX"
DEFAULT_LIMIT = 50
LIMIT_MIN = 1
LIMIT_MAX = 100
REQUIRED_ACCOUNT = ("account_id", "email")
REQUIRED_CONFIG = ("host", "username", "password")
FIXED_SEQUENCE = ["login", "select", "search", "fetch", "close", "logout"]


def _contract_text():
    return CONTRACT.read_text(encoding="utf-8")


def _fenced_block(text, label):
    match = re.search(r"```" + label + r"\n(.*?)\n```", text, re.DOTALL)
    assert match is not None, "bloque " + label + " ausente en el contrato"
    return match.group(1)


def _frozen_cases():
    return json.loads(_fenced_block(_contract_text(), "frozen-cases"))


def _field_ok(mapping, key):
    value = mapping.get(key) if isinstance(mapping, dict) else None
    return isinstance(value, str) and value != ""


def _limit_valid(limit):
    return (
        isinstance(limit, int)
        and not isinstance(limit, bool)
        and LIMIT_MIN <= limit <= LIMIT_MAX
    )


def _since_uid_valid(since_uid):
    return (
        isinstance(since_uid, int)
        and not isinstance(since_uid, bool)
        and since_uid >= 0
    )


def _filter_ids(search_ids, since_uid):
    """Orden ascendente tras el filtro estricto del cursor (sin filtro si
    since_uid es None)."""
    ids = sorted(int(value) for value in search_ids)
    if since_uid is None:
        return ids
    return [value for value in ids if value > since_uid]


def _records_from(ids):
    """Registro esperado por id: el metadato transitorio imap_uid (int)
    igual al id solicitado; los demas campos vienen de parse_raw_email y
    este oracle no los modela."""
    return [{"imap_uid": value} for value in ids]


def _recompute(case):
    """Modelo de referencia: aplica las reglas documentadas a un caso."""
    account = case["account"]
    config = case["config"]
    required_ok = all(
        _field_ok(account, key) for key in REQUIRED_ACCOUNT
    ) and all(_field_ok(config, key) for key in REQUIRED_CONFIG)
    limit = config.get("limit", DEFAULT_LIMIT)
    since_uid = config.get("since_uid")
    if not required_ok or not _limit_valid(limit) or (
        since_uid is not None and not _since_uid_valid(since_uid)
    ):
        return {
            "error": "ValueError",
            "result_ids": None,
            "result_uids": None,
            "records": None,
            "sequence": [],
            "message_contains": None,
        }
    ids = _filter_ids(case["search_ids"], since_uid)[:limit]
    if case.get("fetch_error"):
        # Mensaje documentado: host + account_id, jamas la password.
        message = (
            "IMAP fetch fallo para "
            + account["account_id"]
            + " en "
            + config["host"]
            + ": "
            + case["fetch_error"]
        )
        assert config["password"] not in message, (
            "el mensaje documentado no debe contener la password"
        )
        return {
            "error": "RuntimeError",
            "result_ids": None,
            "result_uids": None,
            "records": None,
            "sequence": FIXED_SEQUENCE,
            "message_contains": [config["host"], account["account_id"]],
        }
    return {
        "error": None,
        "result_ids": ids,
        "result_uids": ids,
        "records": _records_from(ids),
        "sequence": FIXED_SEQUENCE,
        "message_contains": None,
    }


def _case(name):
    return {c["name"]: c for c in _frozen_cases()}[name]


def test_contract_frontmatter_and_budgets():
    frontmatter = _contract_text().split("---\n", 2)[1]
    assert "task: fetch-imap-messages" in frontmatter
    assert "target: src/email/imap_reader.py" in frontmatter
    assert (
        "signature: \"def fetch_imap_messages(account: dict, config: dict, "
        "connection_factory=None) -> list\"" in frontmatter
    )
    assert "cyclomatic_max: 20" in frontmatter
    assert "nesting_max: 4" in frontmatter
    assert "lines_max: 120" in frontmatter
    assert "params_max: 3" in frontmatter
    assert "deps_allowed: [imaplib, email, typing]" in frontmatter
    assert (
        "forbids: [eval, exec, subprocess, filesystem_write, print]"
        in frontmatter
    )
    assert "tests: tests/frozen_fetch_imap.py" in frontmatter


def test_contract_has_seven_sections_and_stop_phrase():
    text = _contract_text()
    for section in (
        "## Intent",
        "## Interface",
        "## Invariants",
        "## Examples",
        "## Do / Don't",
        "## Tests",
        "## Constraints",
    ):
        assert section in text, "seccion ausente: " + section
    assert "PARAR y reportar si" in text


def test_contract_documents_required_behaviors():
    text = _contract_text()
    for phrase in (
        "parse_raw_email",
        "connection_factory",
        "readonly=True",
        "(RFC822)",
        "finally",
        "imaplib.IMAP4_SSL",
        "RuntimeError",
        "search(None, \"ALL\")",
        "bool` se rechaza",
        "since_uid",
        "orden ascendente",
        "imap_uid",
        "metadato transitorio de transporte",
        "persist_email_okf` no lo serializa en OKF",
        "parse_raw_email` permanece sin ese campo",
    ):
        assert phrase in text, "frase ausente en el contrato: " + phrase
    assert "password" in text and "logout()" in text


def test_frozen_defaults_are_applied():
    case = _case("defaults_mailbox_and_limit")
    config = case["config"]
    assert "mailbox" not in config and "limit" not in config, (
        "el caso de defaults no debe fijar mailbox ni limit"
    )
    assert "since_uid" not in config, (
        "el caso de defaults no debe fijar since_uid"
    )
    recomputed = _recompute(case)
    assert case["expected"]["mailbox"] == DEFAULT_MAILBOX
    assert case["expected"]["limit"] == DEFAULT_LIMIT
    assert recomputed == {
        "error": case["expected"]["error"],
        "result_ids": case["expected"]["result_ids"],
        "result_uids": case["expected"]["result_uids"],
        "records": case["expected"]["records"],
        "sequence": case["expected"]["sequence"],
        "message_contains": case["expected"]["message_contains"],
    }
    assert case["expected"]["select_readonly"] is True


def test_frozen_explicit_values_and_deterministic_order():
    case = _case("explicit_mailbox_limit_and_order")
    config = case["config"]
    assert config["mailbox"] == "Archive"
    assert _limit_valid(config["limit"])
    recomputed = _recompute(case)
    assert recomputed["result_ids"] == case["expected"]["result_ids"]
    assert case["expected"]["result_ids"] == sorted(
        case["expected"]["result_ids"]
    ), "el orden debe ser ascendente"
    assert case["expected"]["result_ids"] != case["search_ids"], (
        "el caso debe congelar una entrada desordenada"
    )
    assert recomputed == {
        "error": case["expected"]["error"],
        "result_ids": case["expected"]["result_ids"],
        "result_uids": case["expected"]["result_uids"],
        "records": case["expected"]["records"],
        "sequence": case["expected"]["sequence"],
        "message_contains": case["expected"]["message_contains"],
    }


def test_frozen_limit_out_of_range_rejected():
    for name in ("limit_above_range_rejected", "limit_not_int_rejected"):
        case = _case(name)
        limit = case["config"]["limit"]
        assert not _limit_valid(limit), (
            "el limite congelado debe estar fuera de 1..100 o no ser int"
        )
        recomputed = _recompute(case)
        assert recomputed["error"] == "ValueError"
        assert recomputed["error"] == case["expected"]["error"]
        assert recomputed["sequence"] == [], (
            "la validacion debe fallar antes de abrir conexion"
        )


def test_frozen_limit_bool_is_rejected():
    case = _case("limit_bool_rejected")
    limit = case["config"]["limit"]
    assert limit is True, "el caso debe congelar un bool"
    assert not _limit_valid(limit), "bool no cuenta como limit valido"
    assert _recompute(case)["error"] == "ValueError"


def test_frozen_missing_required_field_rejected():
    case = _case("missing_required_field_rejected")
    assert "email" not in case["account"], "el caso debe omitir email"
    for key in REQUIRED_CONFIG:
        assert _field_ok(case["config"], key), (
            "config debe estar completa para aislar el fallo de account"
        )
    recomputed = _recompute(case)
    assert recomputed["error"] == "ValueError"
    assert recomputed["sequence"] == []


def test_frozen_transport_error_wrapped_without_password():
    case = _case("transport_error_wrapped_without_password")
    recomputed = _recompute(case)
    expected = case["expected"]
    assert recomputed["error"] == "RuntimeError" == expected["error"]
    assert expected["result_ids"] is None
    assert expected["result_uids"] is None and expected["records"] is None, (
        "ante error de transporte no hay uids ni registros devueltos"
    )
    assert expected["sequence"] == FIXED_SEQUENCE, (
        "close y logout deben ejecutarse en finally tambien ante fallos"
    )
    assert "close" in expected["sequence"] and "logout" in expected["sequence"]
    for needle in expected["message_contains"]:
        assert needle in (case["config"]["host"], case["account"]["account_id"])
    assert case["config"]["password"] not in case["fetch_error"], (
        "el error de transporte congelado no debe contener la password"
    )


def test_frozen_since_uid_selects_only_new():
    case = _case("since_uid_selects_only_new")
    since_uid = case["config"]["since_uid"]
    assert _since_uid_valid(since_uid), (
        "el cursor congelado debe ser int no bool >= 0"
    )
    assert any(value <= since_uid for value in case["search_ids"]), (
        "el caso debe congelar mensajes viejos descartados por el cursor"
    )
    assert all(
        value > since_uid for value in case["expected"]["result_ids"]
    ), "el filtro debe ser estrictamente mayor que since_uid"
    recomputed = _recompute(case)
    assert recomputed == {
        "error": case["expected"]["error"],
        "result_ids": case["expected"]["result_ids"],
        "result_uids": case["expected"]["result_uids"],
        "records": case["expected"]["records"],
        "sequence": case["expected"]["sequence"],
        "message_contains": case["expected"]["message_contains"],
    }


def test_frozen_since_uid_at_or_above_all_returns_empty():
    case = _case("since_uid_at_or_above_all_returns_empty")
    since_uid = case["config"]["since_uid"]
    assert _since_uid_valid(since_uid)
    assert since_uid >= max(case["search_ids"]), (
        "el caso debe congelar un cursor mayor o igual que todos los ids"
    )
    assert case["expected"]["result_ids"] == [], (
        "cursor que cubre todo el buzon debe devolver lista vacia, no error"
    )
    recomputed = _recompute(case)
    assert recomputed["error"] is None
    assert recomputed["result_ids"] == []
    assert recomputed["sequence"] == FIXED_SEQUENCE


def test_frozen_since_uid_zero_processes_all():
    case = _case("since_uid_zero_processes_all")
    assert case["config"]["since_uid"] == 0
    assert case["expected"]["result_ids"] == sorted(
        int(v) for v in case["search_ids"]
    ), "cursor 0 debe procesar todos los mensajes como sin cursor"


def test_frozen_since_uid_with_limit_truncates_after_filter():
    case = _case("since_uid_with_limit_truncates_after_filter")
    config = case["config"]
    since_uid = config["since_uid"]
    limit = config["limit"]
    assert _since_uid_valid(since_uid) and _limit_valid(limit)
    filtered = [
        value for value in sorted(int(v) for v in case["search_ids"])
        if value > since_uid
    ]
    assert len(filtered) > limit, (
        "el caso debe congelar mas ids filtrados que el limit"
    )
    assert case["expected"]["result_ids"] == filtered[:limit], (
        "el limit debe truncar despues del filtro y del orden ascendente"
    )
    assert _recompute(case)["result_ids"] == filtered[:limit]


def test_frozen_since_uid_invalid_values_rejected():
    for name in (
        "since_uid_bool_rejected",
        "since_uid_negative_rejected",
        "since_uid_not_int_rejected",
    ):
        case = _case(name)
        since_uid = case["config"]["since_uid"]
        assert not _since_uid_valid(since_uid), (
            "el valor congelado debe ser bool, negativo o no int"
        )
        recomputed = _recompute(case)
        assert recomputed["error"] == "ValueError" == case["expected"]["error"]
        assert recomputed["result_ids"] is None
        assert recomputed["sequence"] == [], (
            "la validacion del cursor debe fallar antes de abrir conexion"
        )


def test_frozen_records_carry_imap_uid_in_order():
    """El oracle verifica los UIDs en orden, tambien con since_uid y limit."""
    cases = _frozen_cases()
    connected = [
        c for c in cases if c["expected"]["sequence"] == FIXED_SEQUENCE
    ]
    successful = [c for c in connected if c["expected"]["error"] is None]
    assert successful, "debe haber casos exitosos que congelar imap_uid"
    for case in connected:
        expected = case["expected"]
        if expected["error"] is None:
            ids = expected["result_ids"]
            assert expected["result_uids"] == ids, (
                "result_uids debe ser la secuencia de imap_uid devuelta"
            )
            assert expected["records"] == _records_from(ids), (
                "cada registro debe llevar imap_uid (int) igual al id "
                "solicitado, en el mismo orden"
            )
            since_uid = case["config"].get("since_uid")
            assert ids == _filter_ids(case["search_ids"], since_uid)[
                : expected["limit"]
            ], "los uids deben respetar filtro since_uid, orden y limit"
        else:
            assert expected["result_uids"] is None and expected[
                "records"
            ] is None, "sin mensajes procesados no hay uids ni records"
    covered_since = any(
        "since_uid" in c["config"] for c in successful
    )
    covered_limit = any(
        "limit" in c["config"]
        and c["config"]["limit"] < len(_filter_ids(c["search_ids"], None))
        for c in successful
    )
    assert covered_since and covered_limit, (
        "el orden de imap_uid debe congelarse bajo since_uid y bajo limit"
    )


def test_frozen_cases_shape_and_no_real_credentials():
    cases = _frozen_cases()
    assert len(cases) >= 6, "el contrato debe congelar al menos 6 casos"
    seen = set()
    for case in cases:
        assert case["name"] not in seen, "caso duplicado: " + case["name"]
        seen.add(case["name"])
        assert isinstance(case["search_ids"], list)
        since_uid = case["config"].get("since_uid")
        assert since_uid is None or isinstance(since_uid, (int, str)), (
            "since_uid congelado debe ser int o el valor invalido congelado"
        )
        expected = case["expected"]
        assert expected["mailbox"] in (DEFAULT_MAILBOX,) or isinstance(
            expected["mailbox"], str
        )
        assert expected["select_readonly"] is True
        assert expected["sequence"] in ([], FIXED_SEQUENCE)
        assert expected["error"] in (None, "ValueError", "RuntimeError")
        if expected["error"] is None:
            assert expected["result_ids"] == _filter_ids(
                case["search_ids"], case["config"].get("since_uid")
            )[: expected["limit"]], (
                "caso exitoso debe reflejar filtro since_uid + orden ascendente + limit"
            )
            assert expected["result_uids"] == expected["result_ids"]
            assert expected["records"] == _records_from(
                expected["result_ids"]
            )
        else:
            assert expected["result_uids"] is None
            assert expected["records"] is None
        assert expected["message_contains"] is None or isinstance(
            expected["message_contains"], list
        )
        # Sin credenciales ni hosts reales: placeholders congelados.
        assert case["config"]["password"].startswith("frozen-"), (
            "la password congelada debe ser un placeholder, no credencial real"
        )
        assert case["config"]["host"].endswith(".test"), (
            "el host congelado debe ser un dominio reservado para pruebas"
        )
        assert case["config"]["username"] == "usuario" or case["config"][
            "username"
        ] == "u"
        if "email" in case["account"]:
            assert case["account"]["email"].endswith(".test"), (
                "el email congelado debe ser un dominio reservado"
            )


def test_frozen_cases_cover_sequence_and_error_matrix():
    cases = {c["name"]: c for c in _frozen_cases()}
    ok = [
        c
        for c in cases.values()
        if c["expected"]["error"] is None
        and c["expected"]["sequence"] == FIXED_SEQUENCE
    ]
    rejected = [c for c in cases.values() if c["expected"]["error"] == "ValueError"]
    wrapped = [
        c for c in cases.values() if c["expected"]["error"] == "RuntimeError"
    ]
    assert ok and rejected and wrapped, (
        "la matriz debe cubrir exito, ValueError y RuntimeError"
    )
    for case in ok + wrapped:
        assert case["expected"]["sequence"] == FIXED_SEQUENCE, (
            "la secuencia IMAP debe ser la documentada en todo caso conectado"
        )
        assert case["expected"]["select_readonly"] is True