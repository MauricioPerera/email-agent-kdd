"""Contrato congelado para inspeccionar una regla sin mutarla."""

import json

from src.email import cli
from src.email.notifications import save_notification_rule


def test_show_returns_exact_rule(tmp_path, capsys):
    save_notification_rule(str(tmp_path), "ventas", "para:ventas+cliente@example.test")

    assert cli._run_notification(["notification", "show", str(tmp_path), "ventas"]) == 0
    assert json.loads(capsys.readouterr().out) == {
        "enabled": True,
        "name": "ventas",
        "query": "para:ventas+cliente@example.test",
    }


def test_show_missing_rule_is_read_only_error(tmp_path, capsys):
    assert cli._run_notification(["notification", "show", str(tmp_path), "ventas"]) == 1
    assert not (tmp_path / ".email-agent" / "notification-rules.json").exists()
    assert "no encontrada" in capsys.readouterr().err
