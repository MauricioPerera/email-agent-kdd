"""Contrato congelado para paginar resultados de query."""

from pathlib import Path

from src.email import cli


def _store(tmp_path):
    folder = Path(tmp_path) / "store" / "emails"
    folder.mkdir(parents=True)
    for index in range(5):
        (folder / f"m{index}.md").write_text("---\ntype: Email Message\n---\nfactura", encoding="utf-8")


def test_query_pagination_returns_stable_slices(tmp_path, capsys):
    _store(tmp_path)
    assert cli._run_query(["query", str(tmp_path), "factura", "--offset", "1", "--limit", "2"]) == 0
    assert capsys.readouterr().out.splitlines() == ["store/emails/m1.md", "store/emails/m2.md"]


def test_query_pagination_rejects_unsafe_values_without_reading(tmp_path, capsys):
    assert cli._run_query(["query", str(tmp_path), "factura", "--offset", "-1"]) == 2
    assert "offset" in capsys.readouterr().err
    assert cli._run_query(["query", str(tmp_path), "factura", "--limit", "101"]) == 2
