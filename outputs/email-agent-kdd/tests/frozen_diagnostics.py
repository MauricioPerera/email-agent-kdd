import json
from pathlib import Path

from src.email.cli import cli_main
from src.email.diagnostics import run_diagnostics


def test_diagnostics_is_local_and_has_safe_checks():
    result = run_diagnostics()
    assert result["status"] in {"ready", "needs_attention"}
    assert {item["name"] for item in result["checks"]} >= {"platform", "python", "pip"}
    assert all("secret" not in json.dumps(item).lower() for item in result["checks"])


def test_doctor_help_is_documented_and_accepts_optional_root(capsys, tmp_path):
    assert cli_main(["--help"]) == 0
    assert "doctor [ROOT]" in capsys.readouterr().out
    assert cli_main(["doctor", str(tmp_path)]) in {0, 1}
    payload = json.loads(capsys.readouterr().out)
    assert payload["checks"]
    assert payload["status"] in {"ready", "needs_attention"}
