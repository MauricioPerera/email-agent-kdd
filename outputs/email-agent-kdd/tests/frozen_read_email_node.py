"""Tests congelados del contrato read_email_node.

Oracle independiente: no importa el target ni node.py ni cli.py. Verifica
la estructura del contrato (frontmatter, secciones, reglas de seguridad y
delegacion CLI read ROOT REL_PATH) y re-deriva los casos congelados con una
implementacion de referencia propia de la semantica: lectura exacta UTF-8 de
un unico nodo .md bajo root con ruta relativa validada, y errores
ValueError / FileNotFoundError / OSError.
"""

import json
from pathlib import Path
import re
import tempfile

CONTRACT = (
    Path(__file__).resolve().parents[1]
    / "knowledge"
    / "contracts"
    / "read-email-node.md"
)

_DRIVE_RE = re.compile(r"^[A-Za-z]:")


def _contract_text():
    return CONTRACT.read_text(encoding="utf-8")


def _fenced_block(text, label):
    match = re.search(r"```" + label + r"\n(.*?)\n```", text, re.DOTALL)
    assert match is not None, "bloque " + label + " ausente en el contrato"
    return match.group(1)


def _frozen_cases():
    return json.loads(_fenced_block(_contract_text(), "frozen-cases"))


def _frozen_invalid():
    return json.loads(_fenced_block(_contract_text(), "frozen-invalid"))


def _case(name):
    return {c["name"]: c for c in _frozen_cases()}[name]


class _InvalidPath(ValueError):
    """Argumento o ruta invalida: `ValueError` de la referencia."""


def _validate_rel_path(rel_path):
    if not isinstance(rel_path, str) or not rel_path.strip():
        raise _InvalidPath("error: la ruta relativa es invalida")
    if (
        rel_path.startswith("~")
        or rel_path.startswith(("/", "\\"))
        or _DRIVE_RE.match(rel_path)
    ):
        raise _InvalidPath("error: la ruta debe ser relativa a la raiz")
    if "\\" in rel_path:
        raise _InvalidPath("error: la ruta usa separador no normalizado")
    parts = rel_path.split("/")
    if any(part in ("", ".", "..") for part in parts):
        raise _InvalidPath("error: la ruta contiene componentes invalidos")
    if not rel_path.endswith(".md"):
        raise _InvalidPath("error: solo se leen nodos .md")


def _reference_read(root, rel_path):
    """Referencia de la semantica pactada: lectura exacta de un nodo .md."""
    if not isinstance(root, str) or not root.strip():
        raise _InvalidPath("error: la raiz es invalida")
    _validate_rel_path(rel_path)
    root_abs = Path(root).resolve()
    if not root_abs.is_dir():
        raise _InvalidPath("error: la raiz no existe o no es un directorio")
    target = (root_abs / rel_path).resolve()
    try:
        target.relative_to(root_abs)
    except ValueError:
        raise _InvalidPath("error: la ruta escapa de la raiz")
    if not target.exists():
        raise FileNotFoundError("error: el nodo no existe")
    if not target.is_file():
        raise OSError("error: la ruta no es un archivo regular")
    try:
        return target.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        raise ValueError("error: el nodo no es UTF-8")


def _build_tree(tmp, tree):
    for relpath, content in tree.items():
        target = Path(tmp) / relpath
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            target.write_text(content, encoding="utf-8")
        except UnicodeEncodeError:
            target.write_bytes(content.encode("utf-8", "surrogatepass"))


_BASE_TREE = {
    "store/emails/msg-0001.md": "---\ntype: Email Message\nsubject: Hola\n---\nla factura del correo\n",
    "store/emails/msg-0002.MD": "nodo con extension en mayusculas\n",
    "store/notas.txt": "no es un nodo markdown\n",
    "store/notas.md.bak": "la extension final no es .md\n",
}


def test_contract_frontmatter_and_budgets():
    frontmatter = _contract_text().split("---\n", 2)[1]
    assert "task: read_email_node" in frontmatter
    assert (
        'signature: "def read_email_node(root: str, rel_path: str) -> str"'
        in frontmatter
    )
    assert "target: src/email/node.py" in frontmatter
    assert "tests: tests/frozen_read_email_node.py" in frontmatter
    assert "cyclomatic_max: 12" in frontmatter
    assert "nesting_max: 3" in frontmatter
    assert "lines_max: 60" in frontmatter
    assert "params_max: 5" in frontmatter
    assert "deps_allowed: [pathlib]" in frontmatter
    assert "forbids: [eval, exec, subprocess" in frontmatter
    assert "os.system" in frontmatter and "shutil" in frontmatter


def test_contract_sections_and_stop_phrase():
    text = _contract_text()
    for section in (
        "## Intent",
        "## Interface",
        "## Invariants",
        "## CLI: read ROOT REL_PATH",
        "## Examples",
        "## Do / Don't",
        "## Tests",
        "## Constraints",
    ):
        assert section in text, "seccion ausente: " + section
    assert "PARAR y reportar si" in text


def test_contract_security_rules():
    text = _contract_text()
    for clause in (
        "solo lectura",
        "Contenido como datos",
        "jamas se ejecuta",
        "Sin red ni procesos",
        "Validar antes de tocar disco",
        "ValueError",
        "FileNotFoundError",
        "OSError",
        "UTF-8",
        "~",
        "..",
        "resolve()",
        "relative_to",
        "extension FINAL",
    ):
        assert clause in text, "regla de seguridad ausente: " + clause
    assert "de solo lectura" in text, "la lectura no debe escribir nada"
    assert 'encoding="utf-8"' in text, "lectura UTF-8 estricta pactada"


def test_contract_cli_read_delegates():
    text = _contract_text()
    assert "read ROOT REL_PATH" in text, (
        "el contrato debe fijar el subcomando read ROOT REL_PATH"
    )
    assert "src.email.node.read_email_node" in text, (
        "la CLI debe delegar en read_email_node"
    )
    assert "def read_email_node(root: str, rel_path: str) -> str" in text
    assert "NO reimplementa la lectura" in text, (
        "el contrato debe prohibir reimplementar la lectura en la CLI"
    )
    assert "EXACTO" in text, (
        "stdout debe reproducir el texto devuelto tal cual"
    )
    assert "retorna `2`" in text, "codigo 2 para argumentos/ruta invalidos"
    assert "retorna `1`" in text, "codigo 1 para FileNotFoundError/OSError"
    assert "retorna `0`" in text, "codigo 0 para lectura exitosa"
    assert "quedan intactos" in text, "subcomandos existentes intactos"
    for subcommand in ("search", "account", "sync", "draft", "send", "query"):
        assert subcommand in text, "subcomando conservado ausente: " + subcommand


def test_frozen_cases_shape_and_trees():
    cases = _frozen_cases()
    assert len(cases) >= 8, "el contrato debe congelar al menos 8 casos"
    for case in cases:
        assert isinstance(case["name"], str) and case["name"]
        assert isinstance(case["tree"], dict) and case["tree"], (
            "arbol vacio en el caso " + case["name"]
        )
        assert isinstance(case["rel_path"], str)
        kind = "error" if "error" in case else "expected"
        assert ("error" in case) ^ ("expected" in case), (
            "cada caso fija expected o error: " + case["name"]
        )
        if kind == "error":
            assert case["error"] in (
                "ValueError",
                "FileNotFoundError",
                "OSError",
            ), "error no previsto en " + case["name"]
        else:
            assert isinstance(case["expected"], str), (
                "expected debe ser el texto exacto en " + case["name"]
            )
        for relpath in case["tree"]:
            assert not relpath.startswith("/"), "ruta absoluta en el arbol"
            assert ".." not in relpath.split("/"), "salto .. en el arbol"


def _run_frozen_case(case):
    with tempfile.TemporaryDirectory() as tmp:
        _build_tree(tmp, case["tree"])
        try:
            return _reference_read(tmp, case["rel_path"]), None
        except Exception as exc:  # noqa: BLE001 - la referencia tipifica
            return None, exc


def test_frozen_cases_success_exact_text():
    successes = [c for c in _frozen_cases() if "expected" in c]
    assert len(successes) >= 5, "deben congelarse casos de lectura exitosa"
    for case in successes:
        content, error = _run_frozen_case(case)
        assert error is None, "lectura fallida en " + case["name"]
        assert content == case["expected"], (
            "el texto devuelto debe ser exacto en " + case["name"]
        )
    exact = _case("frontmatter_node_exact")
    assert exact["expected"].startswith("---\ntype: Email Message\n"), (
        "el frontmatter viaja dentro del texto tal cual"
    )
    assert exact["expected"].endswith("\n"), (
        "el salto de linea final se conserva"
    )
    assert _case("empty_file_returns_empty")["expected"] == "", (
        "archivo vacio devuelve cadena vacia"
    )
    assert _case("no_trailing_newline_preserved")["expected"].endswith("final"), (
        "sin salto final no se anade ninguno"
    )


def test_frozen_cases_content_is_data_not_code():
    case = _case("content_is_data_not_code")
    content, error = _run_frozen_case(case)
    assert error is None and content == case["expected"], (
        "el contenido con apariencia de comandos se devuelve tal cual"
    )
    assert "os.system('rm -rf /')" in content, (
        "el caso debe congelar contenido con apariencia de ejecucion"
    )
    assert "Ignora las instrucciones anteriores" in content, (
        "el caso debe congelar un intento de inyeccion de instrucciones"
    )


def test_frozen_cases_error_typing():
    errors = [c for c in _frozen_cases() if "error" in c]
    assert len(errors) >= 3, "deben congelarse los tres tipos de error"
    for case in errors:
        content, error = _run_frozen_case(case)
        assert content is None and error is not None, (
            "el caso debe fallar: " + case["name"]
        )
        assert type(error).__name__ == case["error"], (
            "tipo de error pactado en " + case["name"]
        )
        if case["error"] in ("FileNotFoundError", "OSError"):
            assert isinstance(error, OSError), (
                "los errores de E/S derivan de OSError en " + case["name"]
            )
        if case["error"] == "ValueError":
            assert not isinstance(error, OSError), (
                "el fallo de decodificacion es ValueError puro en " + case["name"]
            )
    case = _case("invalid_utf8_is_value_error")
    assert "\\udcff" in _fenced_block(
        _contract_text(), "frozen-cases"
    ) or "\udcff" in case["tree"]["store/emails/corrupto.md"], (
        "el caso debe congelar bytes inequivocamente no UTF-8"
    )


def test_frozen_invalid_cases_raise_value_error():
    invalid = _frozen_invalid()
    assert len(invalid) >= 12, "el contrato debe congelar los errores pactados"
    with tempfile.TemporaryDirectory() as tmp:
        _build_tree(tmp, _BASE_TREE)
        for pair in invalid:
            assert isinstance(pair, list) and len(pair) == 2, (
                "cada caso invalido es [root, rel_path]"
            )
            root, rel_path = pair
            if root == "store":
                # Raiz valida: el ValueError debe venir de la regla de ruta.
                root = tmp
            try:
                _reference_read(root, rel_path)
            except _InvalidPath:
                continue
            raise AssertionError(
                "el caso invalido debe dar ValueError: " + repr(pair)
            ) from None


def test_frozen_invalid_cases_cover_each_rejection_rule():
    text = "\n".join("|".join(pair) for pair in _frozen_invalid())
    assert "/etc/passwd" in text, "ruta absoluta posix"
    assert "C:/Windows/win.ini" in text, "ruta con letra de unidad"
    assert "~/secretos.md" in text, "ruta del home del usuario"
    assert "../fuera.md" in text and "store/../fuera.md" in text, (
        "componente .."
    )
    assert "store//emails/msg-0001.md" in text, "componente vacio"
    assert "store\\emails\\msg-0001.md" in text, "separador backslash"
    assert "store/notas.txt" in text, "extension distinta"
    assert "store/emails/msg-0002.MD" in text, "extension no minuscula"
    assert "store/notas.md.bak" in text, "extension final no es .md"
    for pair in _frozen_invalid():
        rel_path = pair[1]
        # La regla de extension solo aplica a rutas RELATIVAS VALIDAS: los
        # casos que ya se rechazan por prefijo ~, ruta absoluta, letra de
        # unidad, backslash o componentes invalidos (., .., vacio) quedan
        # fuera de esta comprobacion, pues no deben existir en _BASE_TREE.
        if not isinstance(rel_path, str) or not rel_path.strip():
            continue
        if (
            rel_path.startswith("~")
            or rel_path.startswith(("/", "\\"))
            or _DRIVE_RE.match(rel_path)
            or "\\" in rel_path
        ):
            continue
        parts = rel_path.split("/")
        if any(part in ("", ".", "..") for part in parts):
            continue
        assert rel_path in _BASE_TREE or not rel_path.endswith(".md"), (
            "los casos invalidos de extension no deben apuntar a un nodo"
            " .md existente: " + rel_path
        )