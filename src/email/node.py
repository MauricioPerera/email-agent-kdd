"""Primitiva de lectura puntual de nodos Markdown del store local.

`read_email_node` lee UN unico archivo `.md` dentro de `root` desde una ruta
relativa segura y devuelve EXACTAMENTE su texto UTF-8, sin recortar ni
normalizar nada. Solo lectura: no escribe, no crea y no toca la red.
"""

from pathlib import Path


def _check_root(root) -> Path:
    """Valida `root` y devuelve su ruta absoluta canonica."""
    if not isinstance(root, str) or not root.strip():
        raise ValueError("root debe ser str no vacio")
    root_path = Path(root).resolve()
    if not root_path.is_dir():
        raise ValueError("root no existe o no es directorio: " + repr(root))
    return root_path


def _check_rel_path(rel_path) -> None:
    """Rechaza cualquier ruta relativa insegura o sin extension final .md."""
    if not isinstance(rel_path, str) or not rel_path.strip():
        raise ValueError("rel_path debe ser str no vacio")
    if (
        rel_path.startswith("~")
        or rel_path.startswith(("/", "\\"))
        or "\\" in rel_path
        or (rel_path[:1].isalpha() and rel_path[1:2] == ":")
    ):
        raise ValueError("rel_path insegura (absoluta, ~, \\ o unidad): " + repr(rel_path))
    if any(p in ("", ".", "..") for p in rel_path.split("/")):
        raise ValueError("rel_path con componente vacio, . o ..: " + repr(rel_path))
    if not rel_path.endswith(".md"):
        raise ValueError("la extension final no es .md: " + repr(rel_path))


def read_email_node(root: str, rel_path: str) -> str:
    """Lee el texto UTF-8 integro del nodo `rel_path` dentro de `root`."""
    root_path = _check_root(root)
    _check_rel_path(rel_path)
    candidate = root_path.joinpath(*rel_path.split("/"))
    # La ruta ya es relativa y no admite `..`. No se resuelve antes de leer:
    # Windows puede virtualizar un subdirectorio de una raíz lógica (por
    # ejemplo `store`) y devolver una ruta física distinta aunque siga dentro
    # del almacenamiento autorizado. Un archivo enlace se rechaza de todos
    # modos para no seguir destinos arbitrarios.
    if candidate.is_symlink():
        raise ValueError("nodo enlace no permitido: " + repr(rel_path))
    if not candidate.exists():
        raise FileNotFoundError("el nodo no existe: " + str(candidate))
    if not candidate.is_file():
        raise OSError("la ruta no es un archivo regular: " + str(candidate))
    return candidate.read_text(encoding="utf-8")
