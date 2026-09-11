"""Contrato congelado para reemplazar reglas de notificacion."""

import json

from src.email import cli
from src.email.notifications import save_notification_rule


def _stored(path):
    return json.loads((path / ".email-agent" / "notification-rules.json").read_text())


def test_new_rule_does_not_need_replacement_confirmation(tmp_path, capsys):
    assert cli._run_notification(
        ["notification", "add", str(tmp_path), "ventas", "para:ventas@example.test"]
    ) == 0
    assert json.loads(capsys.readouterr().out) == {"saved": "ventas"}


def test_existing_rule_cannot_be_replaced_without_confirmation(tmp_path, capsys):
    save_notification_rule(str(tmp_path), "ventas", "para:ventas@example.test")
    assert cli._run_notification(
        ["notification", "add", str(tmp_path), "ventas", "para:nueva@example.test"]
    ) == 2
    assert _stored(tmp_path)["rules"][0]["query"] == "para:ventas@example.test"
    assert "CONFIRMAR REGLA" in capsys.readouterr().err


def test_existing_rule_replacement_requires_exact_confirmation(tmp_path, capsys):
    save_notification_rule(str(tmp_path), "ventas", "para:ventas@example.test")
    assert cli._run_notification([
        "notification", "add", str(tmp_path), "ventas",
        "para:nueva@example.test", "CONFIRMAR", "REGLA",
    ]) == 0
    assert json.loads(capsys.readouterr().out) == {"saved": "ventas"}
    assert _stored(tmp_path)["rules"][0]["query"] == "para:nueva@example.test"
