import json
from pathlib import Path

from src.email.cli import cli_main
from src.email.diagnostics import run_diagnostics, write_diagnostic_report, _write_diagnostic_report
from src.email.language import load_language, save_language


def test_diagnostics_is_local_and_has_safe_checks():
    result = run_diagnostics()
    assert result["status"] in {"ready", "needs_attention"}
    assert {item["name"] for item in result["checks"]} >= {"platform", "python", "pip"}
    serialized = json.dumps(result["checks"]).lower()
    assert "password" not in serialized
    assert "credential_ref" not in serialized
    assert "secreto-frozen" not in serialized


def test_doctor_help_is_documented_and_accepts_optional_root(capsys, tmp_path):
    assert cli_main(["--help"]) == 0
    assert "doctor [ROOT] [--fix] [--lang es|en|pt] [--format json|text] [--report FILE]" in capsys.readouterr().out
    assert cli_main(["doctor", str(tmp_path)]) in {0, 1}
    payload = json.loads(capsys.readouterr().out)
    assert payload["checks"]
    assert payload["status"] in {"ready", "needs_attention"}


def test_doctor_fix_only_proposes_actions():
    result = run_diagnostics(repair=True)
    assert result["repair"]["performed"] is False
    assert result["repair"]["actions"]


def test_diagnostic_report_excludes_root_and_is_atomic(tmp_path):
    report = tmp_path / "diagnostic.json"
    result = run_diagnostics(str(tmp_path), repair=True)
    assert write_diagnostic_report(str(report), result) is True
    text = report.read_text(encoding="utf-8")
    assert str(tmp_path) not in text
    assert "password" not in text.lower()
    assert "credential_ref" not in text.lower()
    assert not (tmp_path / "diagnostic.json.tmp").exists()


def test_diagnostic_report_supports_english_and_portuguese_text(tmp_path):
    result = run_diagnostics()
    english = tmp_path / "doctor-en.txt"
    portuguese = tmp_path / "doctor-pt.json"
    assert _write_diagnostic_report(str(english), result, "en", "text") is True
    assert _write_diagnostic_report(str(portuguese), result, "pt", "json") is True
    assert "Email Agent diagnostics" in english.read_text(encoding="utf-8")
    assert json.loads(portuguese.read_text(encoding="utf-8"))["language"] == "pt"


def test_language_preference_is_local_and_used_by_doctor(tmp_path, capsys):
    assert save_language(str(tmp_path), "en") == "en"
    assert load_language(str(tmp_path)) == "en"
    # El almacén nativo de credenciales es dependiente del runner; el reporte
    # debe generarse tanto si el diagnóstico queda listo como si requiere atención.
    assert cli_main(["doctor", str(tmp_path), "--format", "text", "--report", str(tmp_path / "report.txt")]) in {0, 1}
    assert "Status:" in (tmp_path / "report.txt").read_text(encoding="utf-8")


def test_onboard_runs_diagnostics_before_selecting_setup(monkeypatch, tmp_path):
    import src.email.cli as cli

    calls = []
    monkeypatch.setattr(cli, "run_diagnostics", lambda root: {"status": "ready", "checks": [{"name": "gui", "status": "ok"}], "next": "ok"})
    monkeypatch.setattr(cli, "_account_setup_gui", lambda argv: calls.append(argv) or 0)
    assert cli.cli_main(["onboard", str(tmp_path)]) == 0
    assert calls == [["account", "setup-gui", str(tmp_path)]]


def test_onboard_explains_cancelled_setup(monkeypatch, tmp_path, capsys):
    import src.email.cli as cli

    save_language(str(tmp_path), "es")
    monkeypatch.setattr(cli, "run_diagnostics", lambda root: {"status": "ready", "checks": [{"name": "gui", "status": "ok"}], "next": "ok"})
    monkeypatch.setattr(cli, "_account_setup_gui", lambda argv: 1)
    assert cli.cli_main(["onboard", str(tmp_path)]) == 1
    assert "configuracion cancelada" in capsys.readouterr().err


def test_onboard_reports_required_diagnostic_action(monkeypatch, tmp_path, capsys):
    import src.email.cli as cli

    monkeypatch.setattr(cli, "run_diagnostics", lambda root: {"status": "needs_attention", "checks": [], "next": "fix"})
    assert cli.cli_main(["onboard", str(tmp_path)]) == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["action"] == "email-agent doctor --fix"


def test_onboard_localizes_blocked_result(monkeypatch, tmp_path, capsys):
    import src.email.cli as cli

    save_language(str(tmp_path), "en")
    monkeypatch.setattr(cli, "run_diagnostics", lambda root: {"status": "needs_attention", "checks": [], "next": "irrelevant"})
    assert cli.cli_main(["onboard", str(tmp_path)]) == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["language"] == "en"
    assert payload["next"] == "Fix the checks marked as errors and run doctor again"


def test_onboard_localizes_cancelled_setup(monkeypatch, tmp_path, capsys):
    import src.email.cli as cli

    save_language(str(tmp_path), "pt")
    monkeypatch.setattr(cli, "run_diagnostics", lambda root: {"status": "ready", "checks": [{"name": "gui", "status": "ok"}], "next": "ok"})
    monkeypatch.setattr(cli, "_account_setup_gui", lambda argv: 1)
    assert cli.cli_main(["onboard", str(tmp_path)]) == 1
    assert "cancelada" in capsys.readouterr().err


def test_onboard_reports_safe_public_account_summary(monkeypatch, tmp_path, capsys):
    import src.email.cli as cli

    save_language(str(tmp_path), "es")
    account = {
        "account_id": "personal",
        "provider": "gmail",
        "email": "user@example.test",
        "credential_ref": "wincred://private-label",
        "status": "disconnected",
    }
    monkeypatch.setattr(cli, "run_diagnostics", lambda root: {"status": "ready", "checks": [{"name": "gui", "status": "ok"}], "next": "ok"})
    monkeypatch.setattr(cli, "_account_setup_gui", lambda argv: 0)
    monkeypatch.setattr(cli, "load_email_accounts", lambda root: [account])
    assert cli.cli_main(["onboard", str(tmp_path)]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload == {
        "account": {"account_id": "personal", "email": "user@example.test", "provider": "gmail"},
        "language": "es",
        "status": "configured",
    }
    assert "credential_ref" not in payload
