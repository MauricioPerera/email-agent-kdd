"""Busqueda de nodos Markdown bajo una raiz (contrato search_email_nodes).

Determinista: recorre `root`, considera solo archivos con extension final
`.md`, y devuelve las rutas relativas cuyo contenido contiene TODOS los
terminos del query (insensible a mayusculas), ordenadas lexicograficamente
con separador `/`. Los archivos bajo `root/.trash` (papelera de soft_delete)
se excluyen y nunca se leen.
"""

from pathlib import Path

TRASH_DIRNAME = ".trash"


def search_email_nodes(root: str, query: str) -> list:
    root_path = Path(root)
    if not root_path.is_dir():
        raise ValueError("root no existe o no es un directorio: " + str(root))

    terms = query.split()
    if not terms:
        raise ValueError("query sin terminos tras normalizar espacios")

    lowered_terms = [term.lower() for term in terms]
    matches = []
    for path in root_path.rglob("*"):
        if not path.is_file() or path.suffix.lower() != ".md":
            continue
        if path.relative_to(root_path).parts[0] == TRASH_DIRNAME:
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            raise ValueError(
                "archivo .md no leible como UTF-8: " + str(path)
            )
        lowered = content.lower()
        if all(term in lowered for term in lowered_terms):
            matches.append(path.relative_to(root_path).as_posix())
    return sorted(matches)