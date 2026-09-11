import json
from pathlib import Path

from src.email.cli import cli_main
from src.email.diagnostics import run_diagnostics, write_diagnostic_report


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
    assert "doctor [ROOT] [--fix] [--report FILE]" in capsys.readouterr().out
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
