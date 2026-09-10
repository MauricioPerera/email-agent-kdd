"""Tests congelados del contrato persist_email_okf.

Oracle independiente: no importa el target ni normalize.py. Verifica la
estructura del contrato y su ejemplo frozen-example (nodo OKF escrito).
"""

from pathlib import Path
import re

CONTRACT = (
    Path(__file__).resolve().parents[1]
    / "knowledge"
    / "contracts"
    / "persist-email-okf.md"
)


def _contract_text():
    return CONTRACT.read_text(encoding="utf-8")


def _fenced_block(text, label):
    match = re.search(
        r"```" + label + r"\n(.*?)\n```", text, re.DOTALL
    )
    assert match is not None, "bloque " + label + " ausente en el contrato"
    return match.group(1)


def test_contract_frontmatter_and_budgets():
    text = _contract_text()
    frontmatter = text.split("---\n", 2)[1]
    assert "task: persist_email_okf" in frontmatter
    assert "signature: \"def persist_email_okf(record: dict, path: str) -> str\"" in frontmatter
    assert "cyclomatic_max: 20" in frontmatter
    assert "nesting_max: 4" in frontmatter
    assert "lines_max: 80" in frontmatter
    assert "params_max: 5" in frontmatter
    assert "deps_allowed:" in frontmatter
    assert "forbids:" in frontmatter


def test_contract_has_seven_sections_and_stop_phrase():
    text = _contract_text()
    for section in (
        "## Intent",
        "## Interface",
        "## Invariants",
        "## Examples",
        "## Do / Don't",
        "## Tests",
        "## Constraints",
    ):
        assert section in text, "seccion ausente: " + section
    assert "PARAR y reportar si" in text


def test_frozen_example_frontmatter_type():
    node = _fenced_block(_contract_text(), "frozen-example")
    node_frontmatter = node.split("---\n", 2)[1]
    assert "type: Email Message" in node_frontmatter


def test_frozen_example_account_and_hash_and_body():
    node = _fenced_block(_contract_text(), "frozen-example")
    node_frontmatter = node.split("---\n", 2)[1]
    assert "account_id: personal" in node_frontmatter
    assert (
        "raw_sha256: 33399744d24298f2a37e46f7a04758ee47549ecf83f36310278583703d483337"
        in node_frontmatter
    )
    assert node.split("---\n", 2)[2] == "Hola desde el MVP.\n"


def test_frozen_example_rejects_unsafe_paths():
    text = _contract_text()
    unsafe = eval(  # noqa: S307 - contenido propio del contrato congelado
        _fenced_block(text, "frozen-unsafe-paths")
    )
    assert unsafe, "lista de rutas inseguras vacia"
    for path in unsafe:
        assert (
            ".." in path.replace("\\", "/").split("/") or path.startswith(("/", "C:\\", "~"))
        ), "ruta insegura mal catalogada: " + path
    assert "ValueError" in text, "el contrato no declara rechazo con ValueError"