"""Contrato congelado para consulta exacta de un contacto."""

import json

from src.email import cli
from src.email.contact_store import store_email_contacts


def test_contact_show_matches_email_case_insensitively(tmp_path, capsys):
    store_email_contacts(str(tmp_path), [{"name": "Ana", "email": "ana+ventas@Example.test"}])
    assert cli._run_contact(["contact", "show", str(tmp_path), " ANA+VENTAS@example.test "]) == 0
    assert json.loads(capsys.readouterr().out) == {"email": "ana+ventas@example.test", "name": "Ana"}


def test_contact_show_missing_is_read_only_error(tmp_path, capsys):
    assert cli._run_contact(["contact", "show", str(tmp_path), "nadie@example.test"]) == 1
    assert not (tmp_path / "contacts.json").exists()
    assert "no encontrado" in capsys.readouterr().err
