"""Oracle congelado e independiente del empaquetado del plugin (Sprint 6).

Valida, SIN ejecutar la CLI ni conectar a red, que un agente no tecnico
pueda descubrir e instalar email-agent:

- Manifiesto del plugin (.codex-plugin/plugin.json) presente, valido y
  con rutas que resuelven dentro del plugin.
- SKILL.md con frontmatter (name/description) y comandos que existen
  en la superficie de la CLI.
- marketplace.json apuntando a un directorio de plugin existente.
- Frases de confirmacion literales presentes y exactas en la CLI.
- Instaladores con verificacion posterior al instalar.
- pyproject con el entry point `email-agent`.

Puede ejecutarse con pytest o de forma directa:
`python outputs/email-agent-kdd/tests/frozen_plugin_manifest.py`
"""

import json
import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
PLUGIN_ROOT = REPO / "plugins" / "email-agent"
MANIFEST = PLUGIN_ROOT / ".codex-plugin" / "plugin.json"
SKILL = PLUGIN_ROOT / "skills" / "email-agent" / "SKILL.md"
MARKETPLACE = REPO / ".agents" / "plugins" / "marketplace.json"
CLI_SOURCE = REPO / "src" / "email" / "cli.py"
PYPROJECT = REPO / "pyproject.toml"

CONFIRMATION_PHRASES = [
    "CONFIRMAR ENVIO",
    "CONFIRMAR DESVINCULAR",
    "CONFIRMAR BORRADO PERMANENTE",
    "CONFIRMAR BORRADO ADJUNTOS",
    "CONFIRMAR EXTRACCION",
]

# Comandos que SKILL.md documenta y que la CLI debe exponer (tokens
# distintivos que deben aparecer en src/email/cli.py).
CLI_COMMAND_TOKENS = [
    "attachment list",
    "attachment download",
    "attachment gc",
    "message delete",
    "message trash",
    "message restore",
    "message purge",
    "message remote-delete",
    "message remote-restore",
    "message remote-purge",
    "sync",
    "watch",
    "notification add",
    "notification list",
    "notification delete",
    "startup install|status|remove",
    "draft",
    "send",
    "account setup-gui",
    "account setup",
    "onboard",
    "account list",
    "account remove",
    "query",
    "search",
    "read",
]


def _load_manifest():
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def _cli_source():
    return CLI_SOURCE.read_text(encoding="utf-8")


def test_manifest_exists_and_is_valid_json():
    assert MANIFEST.is_file(), "falta .codex-plugin/plugin.json"
    data = _load_manifest()
    assert data["name"] == "email-agent"
    assert re.fullmatch(r"\d+\.\d+\.\d+", data["version"])
    assert data["description"].strip() != ""
    assert data["license"] == "MIT"


def test_manifest_component_paths_are_relative_and_resolve():
    data = _load_manifest()
    for key in ("skills", "mcpServers", "apps", "hooks"):
        if key not in data:
            continue
        entries = data[key] if isinstance(data[key], list) else [data[key]]
        for entry in entries:
            path = entry if isinstance(entry, str) else entry.get("path", "")
            assert path.startswith("./"), f"{key}: {path} debe ser relativo con ./"
            assert ".." not in Path(path).parts
            resolved = (PLUGIN_ROOT / path).resolve()
            assert resolved.is_file() or resolved.is_dir()
            assert PLUGIN_ROOT.resolve() in resolved.parents


def test_optional_components_declared_only_if_file_exists():
    data = _load_manifest()
    if "apps" in data:
        assert any(f.is_file() for f in PLUGIN_ROOT.glob("*.app.json"))
    if "mcpServers" in data:
        assert (PLUGIN_ROOT / ".mcp.json").is_file()


def test_skill_frontmatter_present():
    text = SKILL.read_text(encoding="utf-8")
    assert text.startswith("---")
    front = text.split("---")[1]
    assert "name: email-agent" in front
    assert "description:" in front


def test_marketplace_entry_points_to_plugin():
    data = json.loads(MARKETPLACE.read_text(encoding="utf-8"))
    entry = next(p for p in data["plugins"] if p["name"] == "email-agent")
    path = entry["source"]["path"]
    assert (REPO / path.lstrip("./")).is_dir()


def test_documented_commands_exist_in_cli():
    cli = _cli_source()
    for token in CLI_COMMAND_TOKENS:
        assert token in cli, f"comando documentado ausente en la CLI: {token}"


def test_usage_prefix_is_email_agent():
    cli = _cli_source()
    assert "email-cli" not in cli
    assert "usage: email-agent" in cli


def test_confirmation_phrases_literal_in_cli():
    cli = _cli_source()
    for phrase in CONFIRMATION_PHRASES:
        assert phrase in cli, f"falta frase literal: {phrase}"


def test_skill_mentions_every_confirmation_phrase():
    text = SKILL.read_text(encoding="utf-8")
    for phrase in CONFIRMATION_PHRASES:
        assert phrase in text, f"SKILL.md no documenta: {phrase}"


def test_skill_documents_onboarding_options():
    text = SKILL.read_text(encoding="utf-8")
    for phrase in ("onboard ROOT", "--gui", "--terminal", "--lang es|en|pt", "account setup ROOT --lang es|en|pt", "email-agent sync ROOT ACCOUNT_ID --limit 50", "--unread", "watch ROOT ACCOUNT_ID --every 300 --limit 50", "runs only while the process remains alive"):
        assert phrase in text, f"SKILL.md no documenta onboarding: {phrase}"


def test_skill_documents_startup_confirmation_boundary():
    text = SKILL.read_text(encoding="utf-8")
    assert "startup install ROOT ACCOUNT_ID --every 300 --limit 50" in text
    assert "only after the user confirms immediately before enabling it" in text
    assert "startup remove ROOT ACCOUNT_ID" in text
    assert "receiving confirmation immediately before removal" in text


def test_skill_documents_delivery_filter_notifications():
    text = SKILL.read_text(encoding="utf-8")
    assert 'notification add ROOT ventas "para:ventas+cliente@example.com"' in text
    assert "Rules are evaluated only after `sync`" in text


def test_skill_documents_notification_payload_safety():
    text = SKILL.read_text(encoding="utf-8")
    assert "never interpolated into a script" in text
    assert "never through a shell" in text
    assert "`$()`" in text


def test_installers_verify_command_after_install():
    for name in ("install.ps1", "install.sh"):
        text = (REPO / "installers" / name).read_text(encoding="utf-8")
        assert "email-agent --help" in text


def test_installers_check_python_and_pip_before_installing():
    ps1 = (REPO / "installers" / "install.ps1").read_text(encoding="utf-8")
    sh = (REPO / "installers" / "install.sh").read_text(encoding="utf-8")
    assert "3.10" in ps1 and "python -m pip --version" in ps1
    assert "3, 10" in ps1
    assert "python3" in sh and "-m pip --version" in sh
    assert "3, 10" in sh


def test_installers_point_to_origin_repository():
    text = (REPO / "installers" / "install.ps1").read_text(encoding="utf-8")
    sh = (REPO / "installers" / "install.sh").read_text(encoding="utf-8")
    for content in (text, sh):
        assert "github.com/MauricioPerera/email-agent-kdd" in content


def test_pyproject_declares_entry_point():
    data = PYPROJECT.read_text(encoding="utf-8")
    assert 'email-agent = "src.email.cli:main"' in data
    assert 'requires-python = ">=3.10"' in data
    assert "dependencies = []" in data


def main() -> int:
    """Modo directo: ejecuta cada check y devuelve 0 si todo pasa."""
    checks = [value for name, value in sorted(globals().items()) if name.startswith("test_")]
    failures = []
    for check in checks:
        try:
            check()
        except AssertionError as exc:
            failures.append(f"{check.__name__}: {exc}")
    if failures:
        for line in failures:
            print(f"FAIL {line}")
        return 1
    print(f"OK frozen_plugin_manifest ({len(checks)} checks)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
