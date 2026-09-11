"""Contrato congelado para paginar resultados de search."""

from pathlib import Path

from src.email import cli


def _store(tmp_path):
    folder = Path(tmp_path) / "store" / "emails"
    folder.mkdir(parents=True)
    for index in range(4):
        (folder / f"m{index}.md").write_text("---\ntype: Email Message\n---\nfactura", encoding="utf-8")


def test_search_pagination_returns_stable_slices(tmp_path, capsys):
    _store(tmp_path)
    assert cli._run_search(["search", str(tmp_path), "factura", "--offset", "2", "--limit", "1"]) == 0
    assert capsys.readouterr().out.splitlines() == ["store/emails/m2.md"]


def test_search_pagination_rejects_invalid_limit(tmp_path, capsys):
    assert cli._run_search(["search", str(tmp_path), "factura", "--limit", "0"]) == 2
    assert "--limit" in capsys.readouterr().err
