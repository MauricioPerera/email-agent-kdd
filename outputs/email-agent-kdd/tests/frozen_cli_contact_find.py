"""Contrato congelado para candidatos de contacto."""

import json

from src.email import cli
from src.email.contact_store import store_email_contacts


def test_contact_find_returns_name_and_email_matches(tmp_path, capsys):
    store_email_contacts(str(tmp_path), [
        {"name": "Ana García", "email": "ana@example.test"},
        {"name": "Ana Ventas", "email": "ventas@example.test"},
        {"name": "Bob", "email": "bob@example.test"},
    ])
    assert cli._run_contact(["contact", "find", str(tmp_path), " ANA "]) == 0
    assert [json.loads(line) for line in capsys.readouterr().out.splitlines()] == [
        {"email": "ana@example.test", "name": "Ana García"},
        {"email": "ventas@example.test", "name": "Ana Ventas"},
    ]


def test_contact_find_empty_text_is_argument_error(tmp_path, capsys):
    assert cli._run_contact(["contact", "find", str(tmp_path), "   "]) == 2
    assert "TEXT no vacio" in capsys.readouterr().err


def test_contact_find_json_returns_candidates_and_total(tmp_path, capsys):
    store_email_contacts(str(tmp_path), [
        {"name": "Ana García", "email": "ana@example.test"},
        {"name": "Bob", "email": "bob@example.test"},
    ])
    assert cli._run_contact(["contact", "find", str(tmp_path), "ana", "--json"]) == 0
    assert json.loads(capsys.readouterr().out) == {
        "limit": None, "next_offset": None, "offset": 0,
        "results": [{"email": "ana@example.test", "name": "Ana García"}], "total": 1,
    }


def test_contact_find_json_paginates_candidates(tmp_path, capsys):
    store_email_contacts(str(tmp_path), [
        {"name": "Ana Uno", "email": "ana1@example.test"},
        {"name": "Ana Dos", "email": "ana2@example.test"},
    ])
    assert cli._run_contact([
        "contact", "find", str(tmp_path), "ana", "--offset", "1", "--limit", "1", "--json"
    ]) == 0
    assert json.loads(capsys.readouterr().out) == {
        "limit": 1, "next_offset": None, "offset": 1,
        "results": [{"email": "ana2@example.test", "name": "Ana Dos"}], "total": 2,
    }
