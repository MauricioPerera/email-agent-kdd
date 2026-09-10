"""Tests congelados del contrato query_email.

Oracle independiente: no importa el target ni query.py. Verifica la
estructura del contrato y los casos congelados (AND de terminos libres,
filtros contact:/conversation:/topic:/account:/date:, combinacion de
criterios, orden de rutas relativas y errores) definidos en frozen-cases
y frozen-invalid.
"""

import re
from pathlib import Path

import pytest

CONTRACT = (
    Path(__file__).resolve().parents[1]
    / "knowledge"
    / "contracts"
    / "query-email.md"
)

_CASE_RE = re.compile(
    r'\{\s*"name":\s*"(?P<name>[^"]+)",\s*'
    r'"tree":\s*\{(?P<tree>.*?)\}\s*,\s*'
    r'"instruction":\s*"(?P<instruction>[^"]*)",\s*'
    r'"expected":\s*\[(?P<expected>[^\]]*)\]\s*\}',
    re.DOTALL,
)

_TREE_ENTRY_RE = re.compile(r'"([^"\\]+)":\s*"((?:[^"\\]|\\.)*)"')

_UNESCAPES = {"n": "\n", "t": "\t", '"': '"', "\\": "\\"}


def _contract_text():
    return CONTRACT.read_text(encoding="utf-8")


def _fenced_block(text, label):
    match = re.search(r"```" + label + r"\n(.*?)\n```", text, re.DOTALL)
    assert match is not None, "bloque " + label + " ausente en el contrato"
    return match.group(1)


def _unescape(value):
    out = []
    index = 0
    while index < len(value):
        char = value[index]
        if char == "\\" and index + 1 < len(value):
            nxt = value[index + 1]
            out.append(_UNESCAPES.get(nxt, "\\" + nxt))
            index += 2
        else:
            out.append(char)
            index += 1
    return "".join(out)


def _frozen_cases():
    block = _fenced_block(_contract_text(), "frozen-cases")
    cases = []
    for match in _CASE_RE.finditer(block):
        tree = {
            _unescape(entry.group(1)): _unescape(entry.group(2))
            for entry in _TREE_ENTRY_RE.finditer(match.group("tree"))
        }
        cases.append(
            {
                "name": match.group("name"),
                "tree": tree,
                "instruction": _unescape(match.group("instruction")),
                "expected": re.findall(r'"([^"]+)"', match.group("expected")),
            }
        )
    return cases


def _case(name):
    return {c["name"]: c for c in _frozen_cases()}[name]


def _frozen_invalid():
    block = _fenced_block(_contract_text(), "frozen-invalid")
    groups = re.findall(r'\[((?:"[^"]*"(?:\s*,\s*)?)+)\]', block)
    return [re.findall(r'"([^"]*)"', group) for group in groups]


def _index_listing(tree, directory, key):
    wanted = directory + key.lower() + ".md"
    for path, content in tree.items():
        if path.lower() == wanted:
            return re.findall(r"(?m)^-\s+(\S+)\s*$", content)
    raise AssertionError("indice ausente en el arbol: " + wanted)


def test_contract_frontmatter_and_budgets():
    frontmatter = _contract_text().split("---\n", 2)[1]
    assert "task: query_email" in frontmatter
    assert (
        'signature: "def query_email(root: str, instruction: str) -> list"'
        in frontmatter
    )
    assert "target: src/email/query.py" in frontmatter
    assert "tests: tests/frozen_query_email.py" in frontmatter
    assert "cyclomatic_max: 20" in frontmatter
    assert "nesting_max: 4" in frontmatter
    assert "lines_max: 100" in frontmatter
    assert "params_max: 5" in frontmatter
    assert "deps_allowed: [json, pathlib, re]" in frontmatter
    assert "forbids: [eval, exec, subprocess" in frontmatter


def test_contract_has_sections_filters_and_stop_phrase():
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
    for filter_decl in (
        "contact:EMAIL",
        "conversation:KEY",
        "topic:TOPIC",
        "account:ACCOUNT_ID",
        "date:DATE",
    ):
        assert filter_decl in text, "filtro ausente: " + filter_decl
    assert "^[0-9a-f]{64}$" in text, "invariante hex-64 del KEY ausente"
    assert "^\\w{1,64}$" in text, "invariante de TOPIC seguro ausente"
    assert "^[A-Za-z0-9_.-]{1,64}$" in text, "invariante de ACCOUNT_ID seguro ausente"
    assert "^\\d{4}-\\d{2}-\\d{2}$" in text, "invariante de formato estricto de DATE ausente"


def test_frozen_cases_shape_order_and_relative_paths():
    cases = _frozen_cases()
    assert len(cases) >= 4, "el contrato debe congelar al menos 4 casos"
    for case in cases:
        assert isinstance(case["instruction"], str)
        assert case["tree"], "arbol vacio en el caso " + case["name"]
        assert isinstance(case["expected"], list)
        for path in case["expected"]:
            assert "\\" not in path, "separador no normalizado en " + path
            assert not path.startswith("/"), "ruta absoluta en " + path
            assert ".." not in path.split("/"), "salto .. en " + path
            assert path.endswith(".md"), "solo .md puede listarse: " + path
            assert path in case["tree"], "nodo ausente del arbol: " + path
        assert case["expected"] == sorted(case["expected"]), (
            "orden lexicografico esperado en " + case["name"]
        )


def test_frozen_cases_free_terms_and():
    case = _case("free_terms_and")
    terms = case["instruction"].split()
    assert len(terms) > 1, "el caso AND debe usar varios terminos"
    partial = {
        p for p in case["tree"] if p.endswith(".md")
    } - set(case["expected"])
    assert partial, "el caso AND debe incluir archivos con solo parte de los terminos"
    for path, content in case["tree"].items():
        if not path.endswith(".md"):
            continue
        complete = all(term in content.lower() for term in terms)
        assert complete == (path in case["expected"]), "AND inconsistente en " + path
    assert case["expected"] == ["store/emails/msg-0002.md"]


def test_frozen_cases_topic_filter():
    case = _case("topic_filter")
    topic = case["instruction"][len("topic:"):]
    assert re.fullmatch(r"\w{1,64}", topic), "TOPIC congelado debe ser seguro"
    listing = _index_listing(case["tree"], "store/topics/", topic)
    assert sorted(listing) == case["expected"]
    assert len(listing) == len(set(listing)), "sin duplicados en el indice"
    for path in case["expected"]:
        assert path in case["tree"], "nodo listado ausente: " + path
    assert case["expected"] == [
        "store/emails/msg-0001.md",
        "store/emails/msg-0007.md",
    ]


def test_frozen_cases_conversation_filter():
    case = _case("conversation_filter")
    key = case["instruction"][len("conversation:"):]
    assert re.fullmatch(r"[0-9a-f]{64}", key.lower()), "KEY debe ser hex-64"
    assert key == key.upper() and key != key.lower(), (
        "el caso debe congelar KEY en mayusculas frente al indice en minusculas"
    )
    listing = _index_listing(case["tree"], "store/conversations/", key)
    assert sorted(listing) == case["expected"]
    assert case["expected"] == ["store/emails/msg-0001.md"]


def test_frozen_cases_contact_filter():
    case = _case("contact_filter")
    email = case["instruction"][len("contact:"):].strip().lower()
    assert "@" in email, "EMAIL congelado debe llevar @"
    matches = [
        path
        for path, content in case["tree"].items()
        if path.endswith(".md") and email in content.lower()
    ]
    assert sorted(matches) == case["expected"]
    node = case["tree"][case["expected"][0]]
    assert "ANA@example.com" in node, (
        "el caso debe congelar la insensibilidad a mayusculas del email"
    )
    assert case["expected"] == ["store/emails/msg-0001.md"]


def test_frozen_cases_combined_and_intersection():
    case = _case("combined_and")
    email = "ana@example.com"
    listing = _index_listing(case["tree"], "store/topics/", "factura")
    nodes = case["tree"]
    assert email not in nodes["store/emails/msg-0002.md"].lower(), (
        "msg-0002 (from: Bob) debe quedar excluido por contact:"
    )
    assert "store/emails/msg-0002.md" not in case["expected"]
    for path in ("store/emails/msg-0001.md", "store/emails/msg-0003.md"):
        node = nodes[path]
        assert email in node.lower(), "criterio contact falla en " + path
        assert "factura" in node.lower(), "termino libre falla en " + path
        assert path in listing, "criterio topic falla en " + path
    assert case["expected"] == [
        "store/emails/msg-0001.md",
        "store/emails/msg-0003.md",
    ]


def test_frozen_cases_combined_and_full_intersection():
    case = _case("combined_and")
    email = "ana@example.com"
    terms = [
        token.lower()
        for token in case["instruction"].split()
        if ":" not in token
    ]
    topics = [
        token[len("topic:"):]
        for token in case["instruction"].split()
        if token.lower().startswith("topic:")
    ]
    contacts = [
        token[len("contact:"):].strip().lower()
        for token in case["instruction"].split()
        if token.lower().startswith("contact:")
    ]
    nodes = {
        path: content.lower()
        for path, content in case["tree"].items()
        if path.endswith(".md")
    }
    sets = [
        {p for p, c in nodes.items() if all(t in c for t in terms) or not terms}
    ]
    for contact in contacts:
        sets.append({p for p, c in nodes.items() if contact in c})
    for topic in topics:
        listing = _index_listing(case["tree"], "store/topics/", topic)
        sets.append(set(listing) & set(nodes))
    result = set.intersection(*sets)
    assert sorted(result) == case["expected"] == [
        "store/emails/msg-0001.md",
        "store/emails/msg-0003.md",
    ]


def test_frozen_cases_account_filter():
    case = _case("account_filter")
    instruction = case["instruction"]
    assert instruction.startswith("ACCOUNT:"), (
        "el caso debe congelar el prefijo insensible a mayusculas"
    )
    account = instruction[len("account:"):]
    assert re.fullmatch(r"[A-Za-z0-9_.-]{1,64}", account), (
        "ACCOUNT_ID congelado debe ser seguro"
    )
    matches = [
        path
        for path, content in case["tree"].items()
        if path.endswith(".md") and account.casefold() in content.casefold()
    ]
    assert sorted(matches) == case["expected"]
    node = case["tree"][case["expected"][0]]
    assert "Workspace-A1" in node and "workspace-a1" not in node, (
        "el caso debe congelar la insensibilidad a mayusculas del valor"
    )
    assert case["expected"] == ["store/emails/msg-0001.md"]


def test_frozen_cases_date_filter():
    case = _case("date_filter")
    date = case["instruction"][len("date:"):]
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", date), (
        "DATE congelado debe tener formato estricto YYYY-MM-DD"
    )
    matches = [
        path
        for path, content in case["tree"].items()
        if path.endswith(".md") and date in content.casefold()
    ]
    assert sorted(matches) == case["expected"]
    for path, content in case["tree"].items():
        if path not in case["expected"]:
            assert date not in content, "falso positivo congelado en " + path
    assert case["expected"] == ["store/emails/msg-0001.md"]


def test_frozen_cases_account_date_combined_and():
    case = _case("account_date_combined")
    tokens = case["instruction"].split()
    accounts = [
        token[len("account:"):].casefold()
        for token in tokens
        if token.lower().startswith("account:")
    ]
    dates = [
        token[len("date:"):]
        for token in tokens
        if token.lower().startswith("date:")
    ]
    terms = [token.casefold() for token in tokens if ":" not in token]
    assert accounts and dates and terms, (
        "el caso debe congelar cuenta + fecha + termino libre combinados"
    )
    nodes = {
        path: content.casefold()
        for path, content in case["tree"].items()
        if path.endswith(".md")
    }
    sets = [{p for p, c in nodes.items() if all(t in c for t in terms)}]
    for account in accounts:
        solo = {p for p, c in nodes.items() if account in c}
        assert len(solo) > 1, "el criterio account aislado no debe bastar"
        sets.append(solo)
    for date in dates:
        solo = {p for p, c in nodes.items() if date in c}
        assert len(solo) > 1, "el criterio date aislado no debe bastar"
        sets.append(solo)
    assert sorted(set.intersection(*sets)) == case["expected"] == [
        "store/emails/msg-0001.md"
    ]


def test_frozen_cases_no_match_returns_empty():
    case = _case("no_match_empty")
    term = case["instruction"].lower()
    assert term not in case["tree"]["store/emails/msg-0001.md"].lower()
    assert case["expected"] == []


def test_frozen_invalid_cases_shape_and_values():
    invalid = _frozen_invalid()
    assert len(invalid) >= 15, "el contrato debe congelar los errores pactados"
    for pair in invalid:
        assert len(pair) == 2, "cada caso invalido es [root, instruction]"
        root, instruction = pair
        assert isinstance(root, str) and root, "root siempre presente"
        assert isinstance(instruction, str)
    assert ["no-existe", "hola"] in invalid, "raiz inexistente"
    assert ["store", ""] in invalid, "instruccion vacia"
    assert ["store", "   "] in invalid, "instruccion solo espacios"
    assert ["store", "conversation:1234"] in invalid, "KEY corto"
    bad_key = "conversation:" + "z" * 64
    assert ["store", bad_key] in invalid, "KEY no hex"
    assert not re.fullmatch(r"[0-9a-f]{64}", bad_key[len("conversation:"):])
    assert ["store", "topic:../etc"] in invalid, "TOPIC inseguro"
    assert ["store", "topic:"] in invalid, "TOPIC sin valor"
    assert ["store", "contact:"] in invalid, "EMAIL sin valor"
    bad_email = "contact:example.com"
    assert ["store", bad_email] in invalid, "EMAIL malformado"
    assert "@" not in bad_email[len("contact:"):], (
        "el EMAIL congelado debe ser inequivocamente malformado (sin @)"
    )
    assert ["store", "account:"] in invalid, "ACCOUNT sin valor"
    bad_account = "account:mal!cido"
    assert ["store", bad_account] in invalid, "ACCOUNT_ID inseguro"
    assert not re.fullmatch(r"[A-Za-z0-9_.-]{1,64}", bad_account[len("account:"):])
    long_account = "account:" + "a" * 65
    assert ["store", long_account] in invalid, "ACCOUNT_ID demasiado largo"
    assert len(long_account) - len("account:") == 65, (
        "el ACCOUNT_ID congelado debe exceder el maximo de 64 caracteres"
    )
    assert ["store", "date:"] in invalid, "DATE sin valor"
    bad_dates = ("date:2026-9-10", "date:20260910", "date:2026-09-1")
    for bad_date in bad_dates:
        assert ["store", bad_date] in invalid, (
            "DATE fuera del formato estricto: " + bad_date
        )
        assert not re.fullmatch(r"\d{4}-\d{2}-\d{2}", bad_date[len("date:"):])