import json

from src.email import cli
from src.email.sync_status import read_sync_status, record_sync_status


def test_sync_status_persists_public_summary(tmp_path):
    record_sync_status(str(tmp_path), {
        "account_id": "personal",
        "fetched": 3,
        "persisted": 3,
        "contacts_updated": True,
    })
    result = read_sync_status(str(tmp_path), "personal")
    assert result["fetched"] == 3
    assert result["persisted"] == 3
    assert result["contacts_updated"] is True
    assert "at" in result
    payload = json.loads((tmp_path / ".email-agent" / "sync-status.json").read_text())
    assert set(payload["accounts"]["personal"]) == {"at", "fetched", "persisted", "contacts_updated"}


def test_startup_status_details_is_opt_in(tmp_path, monkeypatch, capsys):
    record_sync_status(str(tmp_path), {"account_id": "personal", "fetched": 1, "persisted": 1})
    monkeypatch.setattr(cli, "startup_status", lambda account_id: True)
    assert cli._run_startup(["startup", "status", str(tmp_path), "personal", "--details"]) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["enabled"] is True
    assert output["last_sync"]["fetched"] == 1
