"""Contrato congelado para la confirmacion de borrado de reglas."""

import json

from src.email import cli
from src.email.notifications import save_notification_rule


def test_delete_requires_exact_confirmation_without_mutating(tmp_path, capsys):
    root = str(tmp_path)
    save_notification_rule(root, "ventas", "para:ventas@example.test")

    assert cli._run_notification(["notification", "delete", root, "ventas"]) == 2
    assert json.loads((tmp_path / ".email-agent" / "notification-rules.json").read_text()) == {
        "rules": [{"enabled": True, "name": "ventas", "query": "para:ventas@example.test"}]
    }
    assert "CONFIRMAR REGLA" in capsys.readouterr().err


def test_delete_with_exact_confirmation_removes_rule(tmp_path, capsys):
    root = str(tmp_path)
    save_notification_rule(root, "ventas", "para:ventas@example.test")

    assert cli._run_notification(
        ["notification", "delete", root, "ventas", "CONFIRMAR", "REGLA"]
    ) == 0
    assert json.loads(capsys.readouterr().out) == {"deleted": True}
    assert json.loads((tmp_path / ".email-agent" / "notification-rules.json").read_text()) == {"rules": []}


def test_list_remains_read_only(tmp_path, capsys):
    root = str(tmp_path)
    save_notification_rule(root, "ventas", "para:ventas@example.test")

    assert cli._run_notification(["notification", "list", root]) == 0
    assert json.loads(capsys.readouterr().out) == {
        "enabled": True,
        "name": "ventas",
        "query": "para:ventas@example.test",
    }
