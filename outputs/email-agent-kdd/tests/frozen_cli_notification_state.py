"""Contrato congelado para pausar y reanudar reglas sin borrar su consulta."""

import json

from src.email import cli
from src.email.notifications import save_notification_rule


def _stored(path):
    return json.loads((path / ".email-agent" / "notification-rules.json").read_text())


def test_disable_requires_confirmation_without_mutating(tmp_path, capsys):
    save_notification_rule(str(tmp_path), "ventas", "para:ventas@example.test")
    assert cli._run_notification(["notification", "disable", str(tmp_path), "ventas"]) == 2
    assert _stored(tmp_path)["rules"][0]["enabled"] is True
    assert "CONFIRMAR REGLA" in capsys.readouterr().err


def test_disable_and_enable_preserve_query(tmp_path, capsys):
    save_notification_rule(str(tmp_path), "ventas", "para:ventas+cliente@example.test")
    args = ["notification", "disable", str(tmp_path), "ventas", "CONFIRMAR", "REGLA"]
    assert cli._run_notification(args) == 0
    assert json.loads(capsys.readouterr().out) == {"enabled": False, "name": "ventas"}
    assert _stored(tmp_path)["rules"][0] == {
        "enabled": False, "name": "ventas", "query": "para:ventas+cliente@example.test"
    }
    args[1] = "enable"
    assert cli._run_notification(args) == 0
    assert json.loads(capsys.readouterr().out) == {"enabled": True, "name": "ventas"}
    assert _stored(tmp_path)["rules"][0]["query"] == "para:ventas+cliente@example.test"
