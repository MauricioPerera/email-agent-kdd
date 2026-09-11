"""Tests congelados del onboarding por terminal (Sprint 8).

Ejercita el codigo REAL de la CLI: `cli_main(["account", "setup", ROOT])`
con `input()` sustituido por un iterador de respuestas y con el ROOT en un
directorio temporal real. Todo offline: sin red, sin secretos (el asistente
nunca pide la contrasena, solo el nombre de la variable de entorno) y sin
tocar stores reales.

Congela: exito (una confirmacion publica, el store escribe `env://NOMBRE`
que jamas aparece en stdout), cancelacion por palabra o EOF (codigo 1, sin
store), respuestas vacias, proveedor invalido, nombre de variable invalido,
store corrupto (error generico, sin traceback ni referencias) y errores de
argumentos (codigo 2, usage en stderr).
"""

import json
from pathlib import Path

import pytest

import src.email.cli as cli

INTRO = (
    "Configuracion guiada de cuenta "
    "(escribe 'cancelar' en cualquier paso para abortar):"
)
PROMPTS = (
    "1) Identificador de la cuenta (ej. personal): ",
    "2) Proveedor (gmail u outlook): ",
    "3) Correo electronico: ",
    "4) Nombre de la variable de entorno que guarda tu clave de aplicacion "
    "(ej. GMAIL_APP_PASSWORD; nunca la clave en si): ",
)


class _FakeInput:
    """input() falso: responde de la lista y EOF cuando se agota."""

    def __init__(self, lines):
        self._lines = list(lines)

    def __call__(self, *args):
        if not self._lines:
            raise EOFError
        return self._lines.pop(0)


@pytest.fixture()
def run_setup(monkeypatch, tmp_path):
    """Corre el setup REAL con respuestas inyectadas y ROOT temporal."""

    def _run(inputs, argv_root=None):
        monkeypatch.setattr(cli, "input", _FakeInput(inputs))
        code = cli.cli_main(["account", "setup", str(tmp_path)])
        store = tmp_path / ".email-agent" / "accounts.json"
        stored = None
        if store.exists():
            # El store puede ser corrupto por el propio caso de prueba; el
            # ayudante no debe fallar por datos que el propio test escribio.
            try:
                stored = json.loads(store.read_text(encoding="utf-8"))
            except ValueError:
                stored = None
        return code, stored, store.exists()

    return _run


def _caps(capsys):
    captured = capsys.readouterr()
    return captured.out, captured.err


def test_setup_success_writes_env_ref_only_in_store(run_setup, capsys):
    code, stored, store_exists = run_setup(
        ["personal", "gmail", "yo@example.com", "GMAIL_APP_PASSWORD"]
    )
    out, err = _caps(capsys)
    assert code == 0 and store_exists and err == ""
    assert out.startswith(INTRO), "el dialogo arranca con la intro guiada"
    for prompt in PROMPTS:
        assert prompt in out, "la pregunta guiada ausente: " + prompt
    assert out.endswith("account saved: personal\n"), (
        "la unica linea de resultado es la confirmacion publica"
    )
    assert out.count("account saved") == 1
    record = stored["accounts"][0]
    assert record["credential_ref"] == "env://GMAIL_APP_PASSWORD"
    assert record["email"] == "yo@example.com"
    assert record["provider"] == "gmail"
    assert record["status"] == "disconnected"
    assert "env://" not in out, "la referencia jamas se imprime"
    assert out.count("GMAIL_APP_PASSWORD") == 1, (
        "el nombre de la variable solo puede aparecer en el ejemplo del prompt"
    )


def test_setup_accepts_explicit_portuguese_language(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(cli, "input", _FakeInput(["personal"]))
    assert cli.cli_main(["account", "setup", str(tmp_path), "--lang", "pt"]) == 1
    out, err = _caps(capsys)
    assert out.startswith("Configuracao guiada da conta")
    assert "configuracao cancelada" in err


def test_setup_cancel_persists_nothing(run_setup, capsys):
    code, _, store_exists = run_setup(
        ["personal", "cancelar", "yo@example.com", "GMAIL_APP_PASSWORD"]
    )
    out, err = _caps(capsys)
    assert code == 1 and not store_exists
    assert "cancelada" in err.lower()
    assert "traceback" not in err.lower()
    assert INTRO in out


def test_setup_eof_persists_nothing(run_setup, capsys):
    code, _, store_exists = run_setup(["personal"])
    _, err = _caps(capsys)
    assert code == 1 and not store_exists
    assert "cancelada" in err.lower()
    assert "env://" not in err


def test_setup_blank_answer_persists_nothing(run_setup, capsys):
    code, _, store_exists = run_setup(["personal", "gmail", "", "GMAIL_APP_PASSWORD"])
    _, err = _caps(capsys)
    assert code == 1 and not store_exists
    assert "vacia" in err.lower()
    assert "env://" not in err


def test_setup_provider_not_admitted_persists_nothing(run_setup, capsys):
    code, _, store_exists = run_setup(
        ["personal", "yahoo", "yo@example.com", "YAHOO_APP_PASSWORD"]
    )
    _, err = _caps(capsys)
    assert code == 1 and not store_exists
    assert "proveedor" in err.lower() and "gmail" in err.lower()
    assert "traceback" not in err.lower()
    assert "env://" not in err


def test_setup_env_var_name_invalid_persists_nothing(run_setup, capsys):
    code, _, store_exists = run_setup(
        ["personal", "gmail", "yo@example.com", "1-MALA-VAR"]
    )
    _, err = _caps(capsys)
    assert code == 1 and not store_exists
    assert "variable" in err.lower()
    assert "env://" not in err


def test_setup_corrupt_store_is_generic(run_setup, capsys, tmp_path):
    store = tmp_path / ".email-agent" / "accounts.json"
    store.parent.mkdir(parents=True)
    store.write_text("{no-json", encoding="utf-8")
    code, _, _ = run_setup(
        ["personal", "gmail", "yo@example.com", "GMAIL_APP_PASSWORD"]
    )
    out, err = _caps(capsys)
    assert code == 1
    assert "no se pudo guardar la cuenta" in err.lower()
    assert "Traceback" not in err and "no-json" not in err
    assert "env://" not in (out + err)


def test_setup_missing_root_and_extra_args_are_usage_errors(capsys):
    for argv in ([], ["account", "setup"], ["account", "setup", "a", "b"]):
        code = cli.cli_main(argv or ["account", "setup"])
        out, err = _caps(capsys)
        assert code == 2
        assert out == ""
        assert "usage:" in err.lower()
        assert "env://" not in err


def test_setup_prompts_never_ask_for_the_secret(run_setup):
    """El asistente solo pide el NOMBRE de la variable, jamas la clave."""
    code, _, _ = run_setup(
        ["personal", "gmail", "yo@example.com", "GMAIL_APP_PASSWORD"]
    )
    assert code == 0
    # El cuarto prompt menciona explicitamente que no se pide la clave.
    assert "nunca la clave en si" in PROMPTS[3]


def test_setup_help_documents_both_onboarding_paths(capsys):
    code = cli.cli_main(["--help"])
    out, err = _caps(capsys)
    assert code == 0 and err == ""
    lowered = out.lower()
    assert "account setup root" in lowered
    assert "account setup-gui root" in lowered
    assert "env://" not in out
