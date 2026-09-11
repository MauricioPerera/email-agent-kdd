"""Regresión de salida Unicode de `email-agent read` en Windows."""

import io

from src.email import cli


def test_write_stdout_emite_utf8_en_windows(monkeypatch):
    raw = io.BytesIO()
    stream = io.TextIOWrapper(raw, encoding="cp1252")
    monkeypatch.setattr(cli.sys, "stdout", stream)
    monkeypatch.setattr(cli.sys, "platform", "win32")

    cli._write_stdout("mañana — revisión\n")
    stream.flush()

    assert raw.getvalue().decode("utf-8") == "mañana — revisión\n"
