"""Tests congelados del contrato email_provider_protocol.

Oracle independiente: NO importa el target ni src.email. Verifica la
estructura del contrato, la interfaz del modulo src/email/provider.py
parseada por AST (sin importarla ni ejecutarla) y que la frontera no
exige dependencias externas ni red.
"""

import ast
import json
import re
from pathlib import Path

CONTRACT = (
    Path(__file__).resolve().parents[1]
    / "knowledge"
    / "contracts"
    / "email-provider.md"
)
TARGET = Path(__file__).resolve().parents[3] / "src" / "email" / "provider.py"

FORBIDDEN_NAMES = [
    "smtplib",
    "socket",
    "urllib",
    "requests",
    "imaplib",
    "poplib",
    "subprocess",
    "eval",
    "exec",
]

METHOD_SIGNATURES = {
    "list_messages": ["self", "account", "query"],
    "send_message": ["self", "account", "message"],
}


def _contract_text():
    return CONTRACT.read_text(encoding="utf-8")


def _frontmatter(text):
    return text.split("---\n", 2)[1]


def _fenced_block(text, label):
    match = re.search(r"```" + label + r"\n(.*?)\n```", text, re.DOTALL)
    assert match is not None, "bloque " + label + " ausente en el contrato"
    return match.group(1)


def _parse_target():
    tree = ast.parse(TARGET.read_text(encoding="utf-8"))
    classes = [n for n in tree.body if isinstance(n, ast.ClassDef)]
    assert [c.name for c in classes] == ["EmailProvider"], (
        "el modulo debe definir solo la clase EmailProvider"
    )
    return tree, classes[0]


def test_contract_frontmatter_budgets_deps_forbids():
    frontmatter = _frontmatter(_contract_text())
    assert "task: email_provider_protocol" in frontmatter
    assert 'signature: "class EmailProvider(Protocol)"' in frontmatter
    assert "cyclomatic_max: 20" in frontmatter
    assert "nesting_max: 4" in frontmatter
    assert "lines_max: 80" in frontmatter
    assert "params_max: 5" in frontmatter
    assert "tests: tests/frozen_email_provider.py" in frontmatter
    assert "deps_allowed: [typing]" in frontmatter, "deps distintas de typing"
    for forbidden in FORBIDDEN_NAMES + ["network_access"]:
        assert forbidden in frontmatter, "forbids sin " + forbidden


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


def test_target_is_structural_protocol_only_stdlib():
    tree, klass = _parse_target()
    base_names = {b.id for b in klass.bases if isinstance(b, ast.Name)}
    assert base_names == {"Protocol"}, "la clase no hereda solo Protocol"
    decorators = {d.id for d in klass.decorator_list if isinstance(d, ast.Name)}
    assert "runtime_checkable" in decorators, "sin @runtime_checkable"
    imported = set()
    for node in tree.body:
        if isinstance(node, ast.ImportFrom):
            imported |= {a.name for a in node.names}
        elif isinstance(node, ast.Import):
            imported |= {a.name for a in node.names}
    assert imported == {"Protocol", "runtime_checkable"}, (
        "imports fuera de typing: " + ", ".join(sorted(imported))
    )
    assert not any(
        isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
        for n in tree.body
    ), "el modulo implementa funciones fuera de la clase"


def test_method_signatures_frozen_exactly():
    _, klass = _parse_target()
    methods = {
        n.name: n
        for n in klass.body
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    assert set(methods) == set(METHOD_SIGNATURES), (
        "metodos publicos distintos de los documentados"
    )
    assert not any(
        isinstance(n, ast.AsyncFunctionDef) for n in klass.body
    ), "metodos async no permitidos"
    for name, params in METHOD_SIGNATURES.items():
        node = methods[name]
        got = [a.arg for a in node.args.args]
        assert got == params, "firma de " + name + ": " + ", ".join(got)
        defaults = [ast.unparse(d) for d in node.args.defaults]
        expected = ["''"] if name == "list_messages" else []
        assert defaults == expected, "defaults de " + name + ": " + str(defaults)


def test_interface_no_dependencies_no_network():
    text = TARGET.read_text(encoding="utf-8")
    tree, _ = _parse_target()
    calls = [n.func for n in ast.walk(tree) if isinstance(n, ast.Call)]
    called = {
        n.attr if isinstance(n, ast.Attribute) else n.id
        for n in calls
        if isinstance(n, (ast.Attribute, ast.Name))
    }
    assert not (called & {"open", "print", "connect", "login", "send"}), (
        "la interfaz llama: " + ", ".join(sorted(called))
    )
    for forbidden in FORBIDDEN_NAMES:
        assert forbidden not in text, "el target usa " + forbidden
    assert "solo stdlib" in _contract_text(), "stdlib no documentada"


def test_bodies_declare_no_implementation():
    _, klass = _parse_target()
    for node in klass.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        body = list(node.body)
        if body and isinstance(body[0], ast.Expr) and isinstance(
            body[0].value, ast.Constant
        ) and isinstance(body[0].value.value, str):
            body = body[1:]
        assert body, "el cuerpo de " + node.name + " esta vacio"
        for statement in body:
            assert isinstance(statement, ast.Pass) or (
                isinstance(statement, ast.Expr)
                and isinstance(statement.value, ast.Constant)
                and statement.value.value is Ellipsis
            ), "el cuerpo de " + node.name + " implementa logica"


def test_message_and_account_dicts_serializable_and_confirmed():
    text = _contract_text()
    message = json.loads(_fenced_block(text, "frozen-message"))
    account = json.loads(_fenced_block(text, "frozen-account"))
    for label, payload in (("message", message), ("account", account)):
        json.dumps(payload)
        assert isinstance(payload, dict), label + " no es un dict"
    assert message["confirmed"] is True, "la orden frozen no esta confirmada"
    assert message["to"] and message["subject"] and message["body"]
    assert list(account.keys()) == [
        "account_id",
        "provider",
        "email",
        "credential_ref",
        "status",
    ], "account no es el registro de create_email_account"
    assert account["status"] == "disconnected"
    assert "serializable a JSON" in text


def test_send_message_is_confirmed_order_receipt_only():
    text = _contract_text()
    assert "YA confirmada" in text, "orden confirmada no documentada"
    assert "no debe saltarse la confirmacion" in text or (
        "NO ofrece ningun camino para saltarse la confirmacion" in text
    ), "regla de confirmacion ausente"
    assert "recibo" in text, "recibo de send_message no documentado"
    don_t = text.split("## Do / Don't", 1)[1].split("## Tests", 1)[0]
    assert "enviar sin confirmacion" in don_t, "don't de confirmacion ausente"
    assert "rechazar una orden sin `confirmed: true` con `ValueError`" in text, (
        "rechazo de orden sin confirmar no documentado"
    )


def test_account_stays_opaque_and_target_is_pure():
    text = _contract_text()
    assert "NUNCA el secreto mismo" in text, "credential_ref opaco ausente"
    assert "no lo abre, no lo resuelve ni lo loguea" in text
    assert "pura respecto a la red y al disco" in text
    assert "no escribe archivos" in text
    assert "no muta sus argumentos de entrada" in text
    assert "query" in text and 'query: str = ""' in text, (
        "query sin default documentado"
    )
    assert "vacio significa listar los mensajes recientes" in text