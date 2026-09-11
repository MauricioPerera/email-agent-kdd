"""Capa local minima de borrado reversible para nodos `.md` del store.

`soft_delete` mueve UN archivo `.md` a `root/.trash/<rel_path>` y escribe un
manifiesto JSON atomico (escritura temporal + `os.replace`); `restore`
devuelve el archivo a su ubicacion original y retira el manifiesto;
`list_trash` lista los manifiestos; `purge` elimina definitivamente un
elemento YA dentro de `.trash` SOLO con la confirmacion literal exacta
`CONFIRMAR BORRADO PERMANENTE`. Ninguna ruta resuelta escapa de `root` y
`soft_delete` NUNCA elimina contenido: solo mueve.

Integracion con `src.email.index_lifecycle`: `soft_delete` identifica los
indices Markdown de `store/conversations` y `store/topics` que contienen
EXACTAMENTE la ruta original, guarda en el manifiesto un snapshot JSON (el
texto integro de cada indice afectado) y retira la ruta con
`remove_path_from_markdown_index`. Cualquier indice corrupto bajo esos
directorios aborta `soft_delete` ANTES de mover el mensaje. `restore`
reconstruye desde el snapshot los indices que faltan (o anade la ruta de
forma compatible a los que existen) y los manifiestos antiguos sin
snapshots siguen funcionando sin tocar indices.

Integracion con `src.email.contact_store`: `soft_delete` guarda en el
manifiesto una copia integro de `contacts.json` SOLO si existe
(`contacts_snapshot`) y, DESPUES de mover el mensaje, reconstruye
`contacts.json` recorriendo UNICAMENTE los nodos activos de
`store/emails` (nunca `.trash`), extrayendo From/To/Cc del frontmatter
OKF de cada mensaje y escribiendo de forma atomica con el mismo formato
que `contact_store`. `restore` restaura el archivo y reconstruye
`contacts.json` incluyendo el mensaje restaurado. Un frontmatter
corrupto en un nodo activo o un fallo de escritura deja el error claro
SIN borrar datos activos: `contacts.json` conserva su contenido previo
(el manifiesto guarda la copia para recuperarlo) y el mensaje queda en
`.trash`. Los manifiestos antiguos sin `contacts_snapshot` siguen
funcionando.

Ambas operaciones son TRANSACCIONALES: `soft_delete` valida indices y
contactos (todos los nodos activos, incluido el objetivo) ANTES de mover;
si la escritura del manifiesto, de cualquier indice o de `contacts.json`
falla, hace rollback COMPLETO usando los snapshots: indices y
`contacts.json` vuelven a su texto previo y el mensaje vuelve a su
ubicacion original sin dejar estado parcial. `restore` valida los
snapshots, el destino y el frontmatter del elemento antes de tocar nada;
si reconstruir un indice, mover el mensaje o reconstruir
`contacts.json` falla, devuelve todo al estado previo (mensaje en
`.trash`, indices previos, `contacts.json` previo) y el manifiesto
sobrevive para reintentar.
"""

import json
import os
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from src.email.contact_store import _validate_contact
from src.email.contacts import extract_contacts
from src.email.index_lifecycle import (
    _parse,
    add_path_to_markdown_index,
    remove_path_from_markdown_index,
)
from src.email.node import _check_rel_path, _check_root

TRASH_DIRNAME = ".trash"
MANIFEST_SUFFIX = ".json"
PURGE_CONFIRMATION = "CONFIRMAR BORRADO PERMANENTE"
MANIFEST_KEYS = (
    "rel_path",
    "trash_rel_path",
    "manifest_rel_path",
    "deleted_at",
    "size_bytes",
)
CONVERSATION_INDEX_DIRNAME = "store/conversations"
TOPIC_INDEX_DIRNAME = "store/topics"
INDEX_SNAPSHOT_KEY = "index_snapshots"
INDEX_DIRS = (CONVERSATION_INDEX_DIRNAME, TOPIC_INDEX_DIRNAME)
MESSAGES_DIRNAME = "store/emails"
CONTACTS_SNAPSHOT_KEY = "contacts_snapshot"


def _check_any_rel_path(rel_path) -> None:
    """Rechaza cualquier ruta relativa insegura, con o sin extension .md."""
    if not isinstance(rel_path, str) or not rel_path.strip():
        raise ValueError("rel_path debe ser str no vacio")
    if (
        rel_path.startswith("~")
        or rel_path.startswith(("/", "\\"))
        or "\\" in rel_path
        or (rel_path[:1].isalpha() and rel_path[1:2] == ":")
    ):
        raise ValueError(
            "rel_path insegura (absoluta, ~, \\ o unidad): " + repr(rel_path)
        )
    if any(p in ("", ".", "..") for p in rel_path.split("/")):
        raise ValueError(
            "rel_path con componente vacio, . o ..: " + repr(rel_path)
        )


def _check_trash_rel_path(root_path, trash_rel_path):
    """Valida que `trash_rel_path` sea relativa segura y caiga en .trash.

    Acepta la extension final `.md` (elemento) o `.json` (manifiesto).
    """
    _check_any_rel_path(trash_rel_path)
    candidate = (root_path / trash_rel_path).resolve()
    try:
        candidate.relative_to((root_path / TRASH_DIRNAME).resolve())
    except ValueError as exc:
        raise ValueError(
            "la ruta no pertenece a .trash: " + repr(trash_rel_path)
        ) from exc
    return candidate


def _inside_trash(candidate, root_path):
    """Devuelve True solo si `candidate` (resuelto) esta bajo root/.trash."""
    try:
        candidate.relative_to((root_path / TRASH_DIRNAME).resolve())
    except ValueError:
        return False
    return True


def _write_json_atomic(path, payload):
    """Escribe `payload` JSON en `path` de forma atomica (temp + os.replace)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    handle_fd, tmp_name = tempfile.mkstemp(
        dir=str(path.parent), prefix=".manifest-", suffix=".tmp"
    )
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(handle_fd, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(payload, stream, sort_keys=True, indent=2, ensure_ascii=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp_path, path)
    except BaseException:
        try:
            tmp_path.unlink()
        except OSError:
            pass
        raise


def _write_text_atomic(path, text) -> None:
    """Reescribe `path` con `text` de forma atomica (temp + os.replace).

    Rollback ONLY: distinta de `_write_contacts_atomic` para que un fallo
    simulado en la escritura de la libreta no impida devolver el contenido
    previo durante el rollback.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    handle_fd, tmp_name = tempfile.mkstemp(
        dir=str(path.parent), prefix=".rollback-", suffix=".tmp"
    )
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(handle_fd, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp_path, path)
    except BaseException:
        try:
            tmp_path.unlink()
        except OSError:
            pass
        raise


def _snapshot_affected_indices(root_path, rel_path) -> dict:
    """Indices de store/conversations y store/topics con EXACTAMENTE rel_path.

    Devuelve `{ruta relativa del indice: texto integro}`. Analiza cada indice
    con `index_lifecycle._parse`: cualquier indice corrupto bajo esos dos
    directorios lanza `ValueError` aqui, ANTES de mover el mensaje.
    """
    snapshots = {}
    for dirname in INDEX_DIRS:
        directory = root_path / dirname
        if not directory.is_dir():
            continue
        for index_path in sorted(directory.rglob("*.md")):
            if not index_path.is_file():
                continue
            _, _, paths = _parse(index_path)
            if rel_path in paths:
                snapshots[index_path.relative_to(root_path).as_posix()] = (
                    index_path.read_text(encoding="utf-8")
                )
    return snapshots


def _contacts_path(root_path):
    """Ruta de la libreta de contactos del store: <root>/contacts.json."""
    return root_path / "contacts.json"


def _read_contacts_snapshot(root_path):
    """Texto integro de contacts.json, o None si no existe.

    Copia literal (sin interpretar): sirve para recuperar la libreta si la
    reconstruccion posterior falla o la deja en mal estado.
    """
    contacts_path = _contacts_path(root_path)
    if not contacts_path.is_file():
        return None
    try:
        return contacts_path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError(
            "contacts.json no es UTF-8 valido: " + str(contacts_path)
        ) from exc


def _frontmatter_fields(text) -> dict:
    """Campos escalares del frontmatter OKF; `{}` si el nodo no trae.

    Un nodo sin frontmatter contribuye sin contactos; un frontmatter
    abierto (sin `---` de cierre) o con una linea propia (sin sangria y
    sin `clave: valor`) es corrupto y lanza `ValueError`. Las lineas
    sangradas (listas como `attachments:`) se ignoran.
    """
    lines = text.split("\n")
    if not lines or lines[0].rstrip("\r") != "---":
        return {}
    fields = {}
    closed = False
    for line in lines[1:]:
        if line[:1] in (" ", "\t"):
            continue
        stripped = line.rstrip("\r")
        if stripped in ("---", "..."):
            closed = True
            break
        if not stripped:
            continue
        key, sep, value = stripped.partition(":")
        if not sep or not key.strip():
            raise ValueError(
                "frontmatter corrupto (linea sin 'clave: valor'): "
                + repr(stripped)
            )
        fields[key.strip().lower()] = value.strip()
    if not closed:
        raise ValueError("frontmatter corrupto (sin '---' de cierre)")
    return fields


def _contacts_from_node(node_path) -> list:
    """Contactos From/To/Cc validados extraidos del frontmatter OKF del nodo.

    Un nodo sin frontmatter o sin cabeceras de contacto devuelve `[]`.
    Un contacto que no cumpla el esquema de `contact_store` lanza
    `ValueError` con la ruta del nodo (no se escribe nada).
    """
    try:
        text = node_path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError(
            "el nodo no es UTF-8 valido: " + str(node_path)
        ) from exc
    fields = _frontmatter_fields(text)
    if not fields:
        return []
    extracted = extract_contacts({
        "from": fields.get("from", ""),
        "to": fields.get("to", ""),
        "cc": fields.get("cc", ""),
    })
    validated = []
    for contact in extracted:
        try:
            validated.append(_validate_contact(contact))
        except ValueError as exc:
            raise ValueError(
                "contacto invalido en " + str(node_path) + ": " + str(exc)
            ) from exc
    return validated


def _is_active_node(node_path, root_path) -> bool:
    """True si el nodo no cae bajo NINGUN directorio `.trash` del store."""
    return TRASH_DIRNAME not in node_path.relative_to(root_path).parts


def _collect_active_contacts(root_path) -> list:
    """Contactos ordenados de los nodos activos de store/emails, SIN escribir.

    Computo puro de la reconstruccion: recorre cada `.md` activo bajo
    `store/emails` (nunca bajo un directorio `.trash`), extrae From/To/Cc del
    frontmatter OKF y deduplica por email. Ante frontmatter corrupto o
    contacto invalido lanza el error claro de `_contacts_from_node`.
    """
    messages_dir = root_path / MESSAGES_DIRNAME
    merged = {}
    if messages_dir.is_dir():
        for node_path in sorted(messages_dir.rglob("*.md")):
            if not node_path.is_file() or not _is_active_node(
                node_path, root_path
            ):
                continue
            for contact in _contacts_from_node(node_path):
                merged.setdefault(contact["email"], contact)
    return [merged[email] for email in sorted(merged)]


def _rebuild_contacts(root_path) -> None:
    """Reconstruye contacts.json desde SOLO los nodos activos de store/emails.

    Usa `_collect_active_contacts` (nunca `.trash`, nunca indices) y escribe
    la libreta de forma atomica con el mismo formato compacto que
    `contact_store`. Si la libreta no existe y no hay contactos, no crea
    nada. Ante frontmatter corrupto o contacto invalido lanza el error
    claro SIN tocar contacts.json.
    """
    ordered = _collect_active_contacts(root_path)
    contacts_path = _contacts_path(root_path)
    if not ordered and not contacts_path.exists():
        return
    _write_contacts_atomic(contacts_path, ordered)


def _write_contacts_atomic(contacts_path, ordered) -> None:
    """Escribe la libreta de forma atomica con el formato de contact_store."""
    payload = (
        json.dumps({"contacts": ordered}, sort_keys=True, ensure_ascii=False)
        + "\n"
    )
    contacts_path.parent.mkdir(parents=True, exist_ok=True)
    handle_fd, tmp_name = tempfile.mkstemp(
        dir=str(contacts_path.parent), prefix=".contacts-", suffix=".tmp"
    )
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(handle_fd, "w", encoding="utf-8", newline="") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp_path, contacts_path)
    except BaseException:
        try:
            tmp_path.unlink()
        except OSError:
            pass
        raise


def _check_index_rel_path(root_path, index_rel_path) -> Path:
    """Valida la ruta de un indice del snapshot y la devuelve resuelta.

    Debe ser relativa segura, terminar en `.md` y caer bajo
    store/conversations o store/topics.
    """
    _check_any_rel_path(index_rel_path)
    if not index_rel_path.endswith(".md"):
        raise ValueError(
            "la ruta del indice no termina en .md: " + repr(index_rel_path)
        )
    candidate = (root_path / index_rel_path).resolve()
    for dirname in INDEX_DIRS:
        try:
            candidate.relative_to((root_path / dirname).resolve())
        except ValueError:
            continue
        return candidate
    raise ValueError(
        "la ruta del indice no pertenece a store/conversations ni a "
        "store/topics: " + repr(index_rel_path)
    )


def _validated_snapshots(root_path, manifest) -> dict:
    """Snapshots del manifiesto validados; `{}` si es un manifiesto antiguo.

    Lanza `ValueError` si el campo existe y no es un dict de str -> str, o si
    una ruta de indice es insegura.
    """
    snapshots = manifest.get(INDEX_SNAPSHOT_KEY)
    if snapshots is None:
        return {}
    if not isinstance(snapshots, dict):
        raise ValueError(
            "index_snapshots debe ser un dict: " + str(manifest["manifest_rel_path"])
        )
    validated = {}
    for index_rel_path, text in sorted(snapshots.items()):
        if not isinstance(text, str) or not text:
            raise ValueError(
                "el snapshot del indice debe ser un str no vacio: "
                + repr(index_rel_path)
            )
        validated[index_rel_path] = text
    if validated:
        # Valida TODAS las rutas de indice (y los indices existentes) antes
        # de tocar nada, para no dejar estado parcial si algo falla.
        for index_rel_path in validated:
            index_path = _check_index_rel_path(root_path, index_rel_path)
            if index_path.exists():
                _parse(index_path)
    return validated


def _apply_snapshot(root_path, index_rel_path, text, rel_path) -> None:
    """Reconstruye el indice desde el snapshot o anade la ruta de forma compatible.

    Si el indice falta se reescribe el texto del snapshot (validado con
    `_parse` antes del reemplazo atomico); si existe, se anade `rel_path` con
    `add_path_to_markdown_index` sin sobrescribir nada.
    """
    index_path = _check_index_rel_path(root_path, index_rel_path)
    if index_path.exists():
        add_path_to_markdown_index(index_path, rel_path)
        return
    tmp = index_path.with_name(index_path.name + ".restore-tmp")
    try:
        with open(tmp, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
        _parse(tmp)
        os.replace(tmp, index_path)
    finally:
        if tmp.exists():
            os.remove(tmp)


def _restore_index_texts(root_path, index_texts) -> None:
    """Devuelve cada indice a su texto previo del rollback.

    `index_texts` mapea ruta relativa del indice a su texto previo, o a
    `None` si el indice NO existia antes (en ese caso se elimina la copia
    reconstruida). Cada escritura es atomica con `_write_text_atomic`.
    """
    for index_rel_path, text in sorted(index_texts.items()):
        index_path = _check_index_rel_path(root_path, index_rel_path)
        if text is None:
            if index_path.exists():
                index_path.unlink()
        else:
            _write_text_atomic(index_path, text)


def _manifest_rel_path(rel_path):
    """Ruta del manifiesto dentro de .trash para el elemento `rel_path`."""
    return rel_path + MANIFEST_SUFFIX


def _load_manifest(manifest_path):
    """Lee un manifiesto JSON y rechaza el que no tenga las claves fijadas."""
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError(
            "el manifiesto es ilegible o invalido: " + str(manifest_path)
        ) from exc
    if not isinstance(payload, dict) or any(
        key not in payload for key in MANIFEST_KEYS
    ):
        raise ValueError(
            "el manifiesto es ilegible o invalido: " + str(manifest_path)
        )
    return payload


def _resolve_trash_entry(root_path, trash_rel_path):
    """Acepta la ruta del elemento .md o la del manifiesto y devuelve ambos."""
    _check_any_rel_path(trash_rel_path)
    item_path = _check_trash_rel_path(root_path, trash_rel_path)
    if trash_rel_path.endswith(MANIFEST_SUFFIX):
        manifest_path = item_path
        item_path = _check_trash_rel_path(
            root_path, trash_rel_path[: -len(MANIFEST_SUFFIX)]
        )
    else:
        manifest_path = _check_trash_rel_path(
            root_path, _manifest_rel_path(trash_rel_path)
        )
    return item_path, manifest_path


def soft_delete(root: str, rel_path: str) -> dict:
    """Mueve el nodo `rel_path` a root/.trash y escribe su manifiesto atomico.

    El manifiesto incluye `index_snapshots`: el texto integro de cada indice
    de store/conversations y store/topics que contiene `rel_path` (la ruta se
    retira de ellos con `remove_path_from_markdown_index`). El manifiesto
    incluye `contacts_snapshot`: una copia integro de `contacts.json` si
    existe (None si no). Valida indices y contactos (TODOS los nodos activos,
    incluido el objetivo: un frontmatter corrupto o un contacto invalido
    aborta con `ValueError` sin mover nada) ANTES de mover el mensaje. Si la
    escritura del manifiesto, de cualquier indice o de `contacts.json` falla,
    hace rollback COMPLETO usando los snapshots: indices y `contacts.json`
    vuelven a su texto previo y el mensaje vuelve a su ubicacion original,
    sin dejar estado parcial. Un indice corrupto bajo esos directorios aborta
    con `ValueError` antes de mover el mensaje. Nunca elimina contenido: si
    el destino ya existe en .trash falla sin tocar nada.
    """
    root_path = _check_root(root)
    _check_rel_path(rel_path)
    source = (root_path / rel_path).resolve()
    try:
        source.relative_to(root_path)
    except ValueError as exc:
        raise ValueError("la ruta resuelta escapa de root: " + repr(rel_path)) from exc
    if not source.is_file():
        raise FileNotFoundError("el nodo no existe: " + str(source))
    trash_rel_path = TRASH_DIRNAME + "/" + rel_path
    destination = _check_trash_rel_path(root_path, trash_rel_path)
    manifest_rel_path = TRASH_DIRNAME + "/" + _manifest_rel_path(rel_path)
    manifest_path = _check_trash_rel_path(root_path, manifest_rel_path)
    if destination.exists() or manifest_path.exists():
        raise ValueError(
            "el elemento ya esta en .trash (o su manifiesto existe): "
            + repr(rel_path)
        )
    size_bytes = source.stat().st_size
    snapshots = _snapshot_affected_indices(root_path, rel_path)
    contacts_snapshot = _read_contacts_snapshot(root_path)
    # Valida los contactos de TODOS los nodos activos (incluido el objetivo)
    # ANTES de mover: un frontmatter corrupto o un contacto invalido aborta
    # SIN tocar nada (los mensajes corruptos no se mueven).
    _collect_active_contacts(root_path)
    os.makedirs(destination.parent, exist_ok=True)
    shutil.move(str(source), str(destination))
    manifest = {
        "rel_path": rel_path,
        "trash_rel_path": trash_rel_path,
        "manifest_rel_path": manifest_rel_path,
        "deleted_at": datetime.now(timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z"),
        "size_bytes": size_bytes,
        INDEX_SNAPSHOT_KEY: snapshots,
        CONTACTS_SNAPSHOT_KEY: contacts_snapshot,
    }
    try:
        _write_json_atomic(manifest_path, manifest)
        # Retira la ruta de cada indice afectado DESPUES del manifiesto: si
        # una escritura falla, el snapshot permite reconstruirlo.
        index_errors = []
        for index_rel_path in sorted(snapshots):
            try:
                remove_path_from_markdown_index(
                    root_path / index_rel_path, rel_path
                )
            except OSError as error:
                index_errors.append((index_rel_path, error))
        if index_errors:
            raise OSError(
                "no se pudo actualizar el indice "
                + repr(index_errors[0][0])
                + ": "
                + str(index_errors[0][1])
            )
        # Reconstruye contacts.json desde SOLO los nodos activos (el mensaje
        # movido ya no cuenta): el snapshot conserva la copia previa para el
        # rollback si la reconstruccion falla.
        _rebuild_contacts(root_path)
    except BaseException:
        # Rollback COMPLETO con los snapshots: indices y contacts.json a su
        # texto previo, mensaje de vuelta en su ubicacion original y sin
        # manifiesto. Nunca queda estado parcial.
        _rollback_soft_delete(
            root_path,
            source,
            destination,
            manifest_path,
            snapshots,
            contacts_snapshot,
        )
        raise
    return manifest


def _rollback_soft_delete(
    root_path, source, destination, manifest_path, snapshots, contacts_snapshot
) -> None:
    """Deshace un soft_delete a medias usando los snapshots ya tomados.

    Restaura el texto integro de cada indice afectado, devuelve
    `contacts.json` a su contenido previo (o lo elimina si no existia) y
    devuelve el mensaje a su ubicacion original. El manifiesto se retira al
    final: si el rollback falla a mitad, sigue describiendo el elemento.
    """
    _restore_index_texts(root_path, snapshots)
    contacts_path = _contacts_path(root_path)
    if contacts_snapshot is None:
        if contacts_path.exists():
            contacts_path.unlink()
    else:
        _write_text_atomic(contacts_path, contacts_snapshot)
    if destination.exists():
        shutil.move(str(destination), str(source))
    if manifest_path.exists():
        manifest_path.unlink()


def restore(root: str, trash_rel_path: str) -> dict:
    """Devuelve el elemento en .trash a su ubicacion original y retira el manifiesto.

    Acepta `trash_rel_path` como la ruta del `.md` en .trash o la del
    manifiesto. No sobrescribe un archivo ya existente en el destino. Si el
    manifiesto trae `index_snapshots`, reconstruye cada indice ausente desde
    su snapshot (o anade la ruta de forma compatible al indice existente);
    despues de devolver el archivo reconstruye `contacts.json` desde SOLO los
    nodos activos de store/emails, ya incluyendo el mensaje restaurado (con
    validacion previa del frontmatter del elemento, ANTES de moverlo). Si
    reconstruir un indice, mover el mensaje o reconstruir `contacts.json`
    falla, hace rollback al estado previo: el mensaje vuelve a `.trash`, los
    indices y `contacts.json` recuperan su texto previo y el manifiesto
    sobrevive para reintentar. Los manifiestos antiguos sin snapshots ni
    `contacts_snapshot` siguen funcionando.
    """
    root_path = _check_root(root)
    item_path, manifest_path = _resolve_trash_entry(root_path, trash_rel_path)
    if not manifest_path.is_file():
        raise FileNotFoundError("el manifiesto no existe: " + str(manifest_path))
    manifest = _load_manifest(manifest_path)
    if not item_path.is_file():
        item_path = _check_trash_rel_path(root_path, manifest["trash_rel_path"])
    if not item_path.is_file():
        raise FileNotFoundError("el elemento no esta en .trash: " + str(item_path))
    _check_rel_path(manifest["rel_path"])
    destination = (root_path / manifest["rel_path"]).resolve()
    try:
        destination.relative_to(root_path)
    except ValueError as exc:
        raise ValueError(
            "la ruta original escapa de root: " + repr(manifest["rel_path"])
        ) from exc
    if destination.exists():
        raise ValueError(
            "el destino ya existe y no sera sobrescrito: "
            + repr(manifest["rel_path"])
        )
    # Los snapshots, el destino y el frontmatter del elemento se validan
    # ANTES de tocar nada: cualquier error aqui no deja mutaciones.
    snapshots = _validated_snapshots(root_path, manifest)
    _contacts_from_node(item_path)
    # Captura el estado previo para el rollback: texto integro de cada indice
    # afectado (o None si no existia) y de contacts.json.
    previous_indices = {}
    for index_rel_path in sorted(snapshots):
        index_path = _check_index_rel_path(root_path, index_rel_path)
        previous_indices[index_rel_path] = (
            index_path.read_text(encoding="utf-8") if index_path.exists() else None
        )
    contacts_path = _contacts_path(root_path)
    contacts_snapshot = _read_contacts_snapshot(root_path)
    moved = False
    try:
        # Los snapshots se aplican ANTES de mover y de retirar el manifiesto:
        # si una escritura falla aqui, el rollback devuelve cada indice a su
        # estado previo y el elemento sigue en .trash.
        for index_rel_path in sorted(snapshots):
            _apply_snapshot(
                root_path,
                index_rel_path,
                snapshots[index_rel_path],
                manifest["rel_path"],
            )
        os.makedirs(destination.parent, exist_ok=True)
        shutil.move(str(item_path), str(destination))
        moved = True
        # Reconstruye contacts.json ya incluyendo el mensaje restaurado.
        _rebuild_contacts(root_path)
        os.remove(manifest_path)
        return manifest
    except BaseException:
        # Rollback al estado previo: indices previos, contacts.json previo y
        # el mensaje de vuelta en .trash con su manifiesto intacto.
        _rollback_restore(
            root_path,
            previous_indices,
            contacts_snapshot,
            destination,
            item_path,
            moved,
        )
        raise


def _rollback_restore(
    root_path, previous_indices, contacts_snapshot, destination, item_path, moved
) -> None:
    """Deshace un restore a medias devolviendo todo al estado previo.

    Restaura el texto previo de cada indice afectado (o elimina el recreado),
    devuelve `contacts.json` a su contenido previo (o lo elimina si no
    existia) y devuelve el mensaje a `.trash`. El manifiesto NO se retira:
    conserva los snapshots para reintentar.
    """
    _restore_index_texts(root_path, previous_indices)
    contacts_path = _contacts_path(root_path)
    if contacts_snapshot is None:
        if contacts_path.exists():
            contacts_path.unlink()
    else:
        _write_text_atomic(contacts_path, contacts_snapshot)
    if moved and destination.exists():
        shutil.move(str(destination), str(item_path))


def list_trash(root: str) -> list:
    """Lista los manifiestos de root/.trash ordenados por trash_rel_path."""
    root_path = _check_root(root)
    trash_root = (root_path / TRASH_DIRNAME).resolve()
    if not trash_root.is_dir():
        return []
    manifests = []
    for path in sorted(trash_root.rglob("*" + MANIFEST_SUFFIX)):
        if not _inside_trash(path, root_path) or not path.is_file():
            continue
        manifests.append(_load_manifest(path))
    manifests.sort(key=lambda manifest: manifest["trash_rel_path"])
    return manifests


def purge(root: str, trash_rel_path: str, confirmation: str) -> dict:
    """Elimina definitivamente un elemento YA en .trash, solo con confirmacion exacta.

    La confirmacion literal debe ser exactamente `CONFIRMAR BORRADO
    PERMANENTE`; cualquier otra cosa aborta sin tocar el disco. La ruta
    debe resolver dentro de root/.trash.
    """
    root_path = _check_root(root)
    if confirmation != PURGE_CONFIRMATION:
        raise ValueError(
            "confirmacion explicita requerida para el borrado permanente"
        )
    item_path, manifest_path = _resolve_trash_entry(root_path, trash_rel_path)
    if not item_path.is_file():
        raise FileNotFoundError("el elemento no esta en .trash: " + str(item_path))
    manifest = _load_manifest(manifest_path) if manifest_path.is_file() else None
    os.remove(item_path)
    if manifest_path.is_file():
        os.remove(manifest_path)
    removed = dict(manifest) if manifest is not None else {}
    removed["purged"] = _trash_display(root_path, trash_rel_path)
    return removed


def _trash_display(root_path, trash_rel_path):
    """Normaliza la entrada aceptada a la ruta del elemento dentro de .trash."""
    if trash_rel_path.endswith(MANIFEST_SUFFIX):
        return trash_rel_path[: -len(MANIFEST_SUFFIX)]
    return trash_rel_path