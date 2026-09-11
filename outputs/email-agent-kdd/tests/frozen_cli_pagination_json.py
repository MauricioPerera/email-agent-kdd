"""Contrato congelado para recibos JSON de paginacion."""

import json
from pathlib import Path

from src.email import cli


def _store(tmp_path):
    folder = Path(tmp_path) / "store" / "emails"
    folder.mkdir(parents=True)
    for index in range(3):
        (folder / f"m{index}.md").write_text("factura", encoding="utf-8")


def test_query_json_reports_total_and_next_offset(tmp_path, capsys):
    _store(tmp_path)
    assert cli._run_query(["query", str(tmp_path), "factura", "--offset", "1", "--limit", "1", "--json"]) == 0
    assert json.loads(capsys.readouterr().out) == {
        "limit": 1, "next_offset": 2, "offset": 1,
        "results": ["store/emails/m1.md"], "total": 3,
    }


def test_search_json_ends_with_null_next_offset(tmp_path, capsys):
    _store(tmp_path)
    assert cli._run_search(["search", str(tmp_path), "factura", "--limit", "5", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["next_offset"] is None
