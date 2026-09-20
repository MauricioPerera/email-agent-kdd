from src.email.notifications import (
    notification_matches,
    notify_new_records,
    save_notification_rule,
    preview_notification_rule,
)
from src.email import cli
from src.email.conversation import conversation_key
from src.email.query import query_email


def _record(**overrides):
    record = {
        "account_id": "account-1",
        "from": "Mauricio Perera <mauricio.perera@gmail.com>",
        "to": "user@example.com",
        "cc": "copy@example.com",
        "delivered_to": ["user@example.com"],
        "subject": "Re: Prueba de Email Agent",
        "body": "contenido",
        "date": "Thu, 10 Sep 2026 17:43:55 -0600",
        "message_id": "<reply@example.com>",
        "in_reply_to": "<original@example.com>",
        "references": ["<original@example.com>"],
        "attachments": [{"filename": "report.txt"}],
    }
    record.update(overrides)
    return record


def test_header_and_account_filters():
    record = _record()
    assert notification_matches(record, "from:mauricio.perera@gmail.com")
    assert notification_matches(record, "to:user@example.com cc:copy@example.com")
    assert notification_matches(record, "contact:mauricio.perera@gmail.com account:account-1")
    assert notification_matches(record, "subject:prueba date:2026-09-10")


def test_reply_attachment_conversation_and_topic_filters():
    record = _record()
    conversation = conversation_key(record)
    assert notification_matches(record, "is:reply")
    assert notification_matches(record, "has:attachment")
    assert notification_matches(record, f"conversation:{conversation}")
    assert notification_matches(record, "topic:prueba")


def test_extended_filters_fail_closed():
    record = _record(in_reply_to="", references=[], attachments=[], subject="Consulta nueva")
    assert not notification_matches(record, "is:reply")
    assert not notification_matches(record, "has:attachment")
    assert not notification_matches(record, "from:other@example.com")


def test_legacy_re_subject_is_a_reply_without_thread_headers():
    legacy = _record(in_reply_to="", references=[], subject=" Re: conversación anterior")
    assert notification_matches(legacy, "is:reply")
    assert not notification_matches(_record(in_reply_to="", references=[], subject="Respuesta"), "is:reply")


def test_summary_rule_emits_one_count_notification(tmp_path):
    save_notification_rule(str(tmp_path), "mauricio", "from:mauricio.perera@gmail.com", summary=True)
    seen = []
    records = [_record(raw_sha256="one"), _record(raw_sha256="two")]
    assert notify_new_records(str(tmp_path), records, lambda title, body: seen.append((title, body))) == 1
    assert seen == [("Email Agent", "2 correos nuevos coinciden con la regla mauricio")]


def test_rule_test_is_read_only_and_returns_only_headers(tmp_path):
    store = tmp_path / "store" / "emails"
    store.mkdir(parents=True)
    (store / "sample.md").write_text(
        "---\nfrom: Mauricio <mauricio@example.com>\nsubject: Prueba\ndate: 2026-09-20\n---\ncuerpo\n",
        encoding="utf-8",
    )
    save_notification_rule(str(tmp_path), "mauricio", "from:mauricio@example.com")
    result = preview_notification_rule(str(tmp_path), "mauricio")
    assert result == {
        "name": "mauricio",
        "total": 1,
        "truncated": False,
        "results": [{
            "path": "store/emails/sample.md",
            "from": "Mauricio <mauricio@example.com>",
            "subject": "Prueba",
            "date": "2026-09-20",
        }],
    }
    assert not (tmp_path / ".email-agent" / "notification-state.json").exists()


def test_query_uses_the_same_header_and_reply_grammar(tmp_path):
    store = tmp_path / "store" / "emails"
    store.mkdir(parents=True)
    (store / "reply.md").write_text(
        "---\nfrom: Mauricio <mauricio@example.com>\nsubject: Re: Prueba\nin_reply_to: <original@example.com>\n---\ncuerpo\n",
        encoding="utf-8",
    )
    assert query_email(str(tmp_path), "from:mauricio@example.com is:reply") == ["store/emails/reply.md"]


def test_query_path_is_accepted_by_read_and_attachment_list(tmp_path, capsys):
    store = tmp_path / "store" / "emails"
    store.mkdir(parents=True)
    (store / "message.md").write_text("---\nsubject: Prueba\n---\ncuerpo\n", encoding="utf-8")
    path = query_email(str(tmp_path), "subject:Prueba")[0]
    assert cli._run_read(["read", str(tmp_path), path]) == 0
    assert "cuerpo" in capsys.readouterr().out
    assert cli._run_attachment(["attachment", "list", str(tmp_path), path]) == 0


def test_query_recognizes_legacy_re_subject_without_thread_headers(tmp_path):
    store = tmp_path / "store" / "emails"
    store.mkdir(parents=True)
    (store / "legacy.md").write_text("---\nsubject: Re: Prueba\n---\ncuerpo\n", encoding="utf-8")
    assert query_email(str(tmp_path), "is:reply") == ["store/emails/legacy.md"]
