"""Tests congelados del contrato sync-email-account.

Oracle independiente: no importa el target ni src.email. Verifica la
estructura del contrato (frontmatter, presupuestos, 7 secciones, frase de
parada) y recomputa cada caso congelado con un modelo de referencia propio
sobre dobles inyectados simulados (sin red, sin disco).
"""

import json
from pathlib import Path
import re

CONTRACT = (
    Path(__file__).resolve().parents[1]
    / "knowledge"
    / "contracts"
    / "sync-email-account.md"
)

SIGNATURE = (
    "def sync_email_account(account: dict, fetch_messages, persist_message, "
    "update_contacts=None) -> dict"
)
RESULT_KEYS = {
    "account_id",
    "fetched",
    "persisted",
    "persisted_paths",
    "contacts_updated",
}


def _contract_text():
    return CONTRACT.read_text(encoding="utf-8")


def _frozen_cases():
    text = _contract_text()
    match = re.search(r"```frozen-cases\n(.*?)\n```", text, re.DOTALL)
    assert match is not None, "bloque frozen-cases ausente en el contrato"
    return json.loads(match.group(1))


def test_contract_frontmatter_and_budgets():
    frontmatter = _contract_text().split("---\n", 2)[1]
    assert "task: sync-email-account" in frontmatter
    assert "src/email/sync.py" in frontmatter
    assert "target:" in frontmatter
    assert 'signature: "' + SIGNATURE + '"' in frontmatter
    assert "cyclomatic_max: 15" in frontmatter
    assert "nesting_max: 4" in frontmatter
    assert "lines_max: 80" in frontmatter
    assert "params_max: 5" in frontmatter
    assert "deps_allowed:" in frontmatter
    assert "forbids:" in frontmatter
    assert "network_access" in frontmatter
    assert "filesystem_write" in frontmatter


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


def test_contract_fixes_call_semantics_and_result_shape():
    text = _contract_text()
    assert "EXACTAMENTE una vez" in text, "la semantica de llamadas debe fijarse"
    assert "RuntimeError" in text, "los errores deben envolverse en RuntimeError"
    assert "copia" in text, "los contactos deben recibir una copia"
    for key in sorted(RESULT_KEYS):
        assert key in text, "clave del resultado ausente: " + key


# ---------------------------------------------------------------------------
# Modelo de referencia (independiente del target): reproduce las reglas
# documentadas en el contrato sobre dobles simulados.
# ---------------------------------------------------------------------------


class _Failure(Exception):
    pass


class _Simulator:
    """Ejecuta las reglas del contrato con dobles simulados y observa las
    llamadas: fetch_calls, persist_calls, contacts_calls, contacts_arg."""

    def __init__(self, case):
        self.case = case
        self.fetch_calls = 0
        self.persist_calls = 0
        self.contacts_calls = 0
        self.contacts_arg = None
        self.persist_order = []

    # -- dobles ------------------------------------------------------------
    def fetch(self, account):
        self.fetch_calls += 1
        if self.case["fetch_error"]:
            raise _Failure(self.case["fetch_error"])
        return self.case["messages"]

    def persist(self, message):
        index = self.persist_calls + 1
        self.persist_calls += 1
        if self.case["persist_error_index"] == index:
            raise _Failure("persist failure at %d" % index)
        path = self.case["persist_paths"][self.persist_calls - 1]
        self.persist_order.append(path)
        return path

    def contacts(self, values):
        self.contacts_calls += 1
        self.contacts_arg = list(values)
        if self.case["contacts_error"]:
            raise _Failure(self.case["contacts_error"])

    # -- reglas del contrato -------------------------------------------------
    def run(self):
        error = None
        fetched = 0
        persisted = 0
        persisted_paths = []
        contacts_updated = False
        try:
            account = self.case["account"]
            account_id = account.get("account_id")
            if not isinstance(account_id, str) or not account_id:
                raise _Failure("account_id invalido")
            messages = self.fetch(account)
            if not isinstance(messages, list):
                raise _Failure("fetch no devolvio una lista")
            for message in messages:
                if not isinstance(message, dict):
                    raise _Failure("mensaje no dict")
            fetched = len(messages)
            for message in messages:
                persisted_paths.append(self.persist(message))
            persisted = len(persisted_paths)
            if self.case["with_contacts"]:
                self.contacts(list(messages))
                contacts_updated = True
        except _Failure:
            # El resultado no se emite en error: el resumen queda vacio
            # (el contrato devuelve solo por la via del exito).
            error = "RuntimeError"
            persisted = 0
            persisted_paths = []
        return {
            "error": error,
            "fetched": fetched,
            "persisted": persisted,
            "persisted_paths": persisted_paths,
            "contacts_updated": contacts_updated,
            "fetch_calls": self.fetch_calls,
            "persist_calls": self.persist_calls,
            "contacts_calls": self.contacts_calls,
            "contacts_receives_copy": (
                self.contacts_calls == 1
                and self.contacts_arg is not self.case["messages"]
                and list(self.contacts_arg) == list(self.case["messages"])
            ),
        }


def test_frozen_cases_match_reference_model():
    cases = _frozen_cases()
    assert len(cases) >= 7, "el contrato debe congelar al menos 7 casos"
    for case in cases:
        observed = _Simulator(case).run()
        assert observed == case["expected"], "desviacion en caso: " + case["name"]


def test_frozen_calls_exactly_once_on_success():
    for case in _frozen_cases():
        if case["expected"]["error"] is not None:
            continue
        assert case["expected"]["fetch_calls"] == 1, "fetch debe llamarse 1 vez"
        assert case["expected"]["persist_calls"] == len(
            case["expected"]["persisted_paths"]
        ), "una persistencia por mensaje"
        if case["with_contacts"]:
            assert case["expected"]["contacts_calls"] == 1
            assert case["expected"]["contacts_receives_copy"] is True


def test_frozen_errors_are_runtimeerror_and_stop_the_pipeline():
    for case in _frozen_cases():
        expected = case["expected"]
        if expected["error"] is None:
            continue
        assert expected["error"] == "RuntimeError", case["name"]
        if expected["error"] == "RuntimeError":
            assert expected["persisted"] == 0
            assert expected["persisted_paths"] == []
            if not case["contacts_error"]:
                # Solo el caso contacts_error_wrapped llega a contacts.
                assert expected["contacts_calls"] == 0
            assert expected["contacts_updated"] is False
    midway = {c["name"]: c for c in _frozen_cases()}["persist_error_midway"]
    assert midway["expected"]["persist_calls"] == 2, "se aborta en la falla"
    missing = {c["name"]: c for c in _frozen_cases()}["account_id_missing"]
    assert missing["expected"]["fetch_calls"] == 0, "validar antes de fetch"


def test_frozen_result_shape_exact_keys():
    for case in _frozen_cases():
        expected = case["expected"]
        assert set(expected) == {
            "error",
            "fetched",
            "persisted",
            "persisted_paths",
            "contacts_updated",
            "fetch_calls",
            "persist_calls",
            "contacts_calls",
            "contacts_receives_copy",
        }
        if expected["error"] is None:
            assert expected["fetched"] == len(case["messages"])
            assert expected["persisted"] == len(expected["persisted_paths"])
            assert isinstance(expected["contacts_updated"], bool)


def test_frozen_order_is_preserved():
    happy = {c["name"]: c for c in _frozen_cases()}["happy_path_contacts_updated"]
    assert happy["expected"]["persisted_paths"] == happy["persist_paths"]
    assert happy["persist_paths"] == [
        "store/emails/m1.md",
        "store/emails/m2.md",
        "store/emails/m3.md",
    ]


def test_contract_has_no_secrets_or_real_hosts():
    text = _contract_text()
    for forbidden in ("password", "api_key", "token"):
        assert forbidden not in text.lower(), "posible secreto en el contrato"
    assert "example.com" in text, "solo dominios de ejemplo permitidos"