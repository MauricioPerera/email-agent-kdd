"""Nucleo de adjuntos: metadatos siempre, contenido solo con autorizacion.

El filename del correo es dato no confiable: nunca compone rutas. La ruta del
blob se deriva UNICAMENTE del sha256 (64 hex validados) bajo
`ROOT/attachments/ab/cd/<sha256>`; los bytes se guardan solo mediante
`store_attachment_bytes` con `authorize=True` (extraccion autorizada
explicitamente). Los errores nominales no exponen rutas absolutas ni secretos.
"""

import hashlib
import json
import os
import re
from datetime import datetime, timezone
from email import policy
from email.parser import BytesParser
from pathlib import Path

from src.email.node import read_email_node

MAX_ATTACHMENT_BYTES = 25 * 1024 * 1024
MAX_EXTRACTED_TEXT_BYTES = 2 * 1024 * 1024
_TEXT_TYPES = frozenset(
    {"text/plain", "text/csv", "text/markdown", "application/json"}
)

_BLOCKED_TYPES = frozenset(
    {"application/x-msdownload", "application/x-sh"}
)
_BLOCKED_EXTS = frozenset({".exe", ".scr", ".lnk", ".bat", ".cmd", ".js"})

_DISPLAY_MAX = 80
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class AttachmentError(Exception):
    """Error nominal de adjuntos: `code` estable, mensaje ya saneado."""

    def __init__(self, code, message=""):
        self.code = code
        self.message = message or code
        super().__init__(self.message)


def _front_text(value):
    """Texto de frontmatter: sin saltos ni caracteres de control."""
    text = str(value if value is not None else "")
    return "".join(
        "?" if (ord(char) < 0x20 or ord(char) == 0x7F) else char for char in text
    )


def _scalar_text(value):
    text = _front_text(value)
    return '""' if text == "" else text


def sanitize_display_name(filename, part_index=0):
    """Nombre SOLO para display: base, sin separadores, ni control, acotado."""
    base = str(filename or "").replace("\\", "/").split("/")[-1]
    cleaned = "".join(
        "?"
        if (ord(char) < 0x20 or ord(char) == 0x7F)
        else ("_" if char in ':*?"<>|' else char)
        for char in base
    )
    cleaned = cleaned.lstrip(".").strip()
    if len(cleaned) > _DISPLAY_MAX:
        cleaned = cleaned[:_DISPLAY_MAX]
    return cleaned or "attachment-" + str(int(part_index))


def _normalize_sha256(sha256):
    text = str(sha256 or "").strip().lower()
    if not _SHA256_RE.fullmatch(text):
        raise AttachmentError(
            "hash-mismatch", "sha256 invalido (se esperaban 64 caracteres hex)"
        )
    return text


def blob_path(root, sha256):
    """Ruta del blob bajo ROOT, derivada solo del sha256 validado."""
    hex_sha = _normalize_sha256(sha256)
    return (
        Path(root)
        / "attachments"
        / hex_sha[:2]
        / hex_sha[2:4]
        / hex_sha
    )


def meta_path(root, sha256):
    """Ruta del registro de metadatos `.meta` junto al blob."""
    return Path(root) / "attachments" / (_normalize_sha256(sha256) + ".meta")


def blob_rel_path(sha256):
    """Ruta relativa a ROOT (para mensajes de error sin rutas absolutas)."""
    hex_sha = _normalize_sha256(sha256)
    return "attachments/" + hex_sha[:2] + "/" + hex_sha[2:4] + "/" + hex_sha


def is_type_allowed(content_type, filename, allowed_types=None):
    """False para tipos/extensiones de alto riesgo salvo lista explicita."""
    ctype = str(content_type or "application/octet-stream").split(";")[0].strip().lower()
    base = str(filename or "").replace("\\", "/").split("/")[-1].lower()
    ext = "." + base.rsplit(".", 1)[-1] if "." in base else ""
    if allowed_types is not None:
        return ctype in {str(item).strip().lower() for item in allowed_types}
    return ctype not in _BLOCKED_TYPES and ext not in _BLOCKED_EXTS


def _normalize_metadata(metadata):
    data = dict(metadata or {})
    return {
        "filename": str(data.get("filename") or ""),
        "content_type": str(
            data.get("content_type") or "application/octet-stream"
        ),
        "part_index": int(data.get("part_index") or 0),
    }


def _skipped_entry(sha256, reason):
    return {
        "sha256": sha256,
        "stored": False,
        "skipped": reason,
        "path": blob_rel_path(sha256),
    }


def _write_meta_if_missing(root, sha256, metadata, size):
    target = meta_path(root, sha256)
    if target.exists():
        return
    record = {
        "sha256": sha256,
        "filename_display": sanitize_display_name(
            metadata["filename"], metadata["part_index"]
        ),
        "content_type": metadata["content_type"],
        "size": size,
        "refs": 0,
        "extracted_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def store_attachment_bytes(
    root,
    sha256,
    content,
    metadata=None,
    *,
    authorize=False,
    max_bytes=MAX_ATTACHMENT_BYTES,
    allowed_types=None,
):
    """Guarda el blob de un adjunto (content-addressed) tras validar todo.

    Sin `authorize=True` no se escribe NINGUN byte en disco. Devuelve la
    entrada de frontmatter resultante: `{stored: True, ...}` o
    `{stored: False, skipped: <motivo>}`. Idempotente: si el blob ya existe
    con el mismo hash verificado es un no-op; si existe con otro contenido
    se trata como colision/corrupcion y se aborta sin sobrescribir.
    """
    if not authorize:
        raise AttachmentError(
            "confirmation-required",
            "extraccion de adjuntos no autorizada (se requiere confirmacion explicita)",
        )
    hex_sha = _normalize_sha256(sha256)
    if not isinstance(content, (bytes, bytearray)):
        raise AttachmentError("hash-mismatch", "el contenido no es binario")
    content = bytes(content)
    if hashlib.sha256(content).hexdigest() != hex_sha:
        raise AttachmentError(
            "hash-mismatch", "el contenido no coincide con el sha256 declarado"
        )
    data = _normalize_metadata(metadata)
    size = len(content)
    if max_bytes is not None and size > max_bytes:
        return _skipped_entry(hex_sha, "size-limit-exceeded")
    if not is_type_allowed(data["content_type"], data["filename"], allowed_types):
        return _skipped_entry(hex_sha, "type-not-allowed")
    blob = blob_path(root, hex_sha)
    relative = blob_rel_path(hex_sha)
    if blob.exists():
        existing = blob.read_bytes()
        if len(existing) == size and hashlib.sha256(existing).hexdigest() == hex_sha:
            _write_meta_if_missing(root, hex_sha, data, size)
            return {
                "sha256": hex_sha,
                "stored": True,
                "path": relative,
                "size": size,
                "idempotent": True,
            }
        raise AttachmentError(
            "hash-mismatch",
            "blob existente no coincide con el sha256 declarado (no se sobreescribe): "
            + relative,
        )
    blob.parent.mkdir(parents=True, exist_ok=True)
    tmp = blob.with_name(blob.name + ".tmp")
    try:
        with open(tmp, "wb") as handle:
            handle.write(content)
        os.replace(tmp, blob)
    except Exception:
        # Rollback: un fallo de E/S no deja blobs temporales residuales.
        try:
            tmp.unlink()
        except FileNotFoundError:
            pass
        raise
    if hashlib.sha256(blob.read_bytes()).hexdigest() != hex_sha:
        raise AttachmentError(
            "hash-mismatch", "verificacion post-escritura fallo (blob corrupto)"
        )
    _write_meta_if_missing(root, hex_sha, data, size)
    return {
        "sha256": hex_sha,
        "stored": True,
        "path": relative,
        "size": size,
        "idempotent": False,
    }


def store_record_attachments(root, record, budget_bytes=None):
    """Extrae y guarda los adjuntos permitidos de UN record de sync.

    Reutiliza el RFC822 ya obtenido durante esa sincronizacion
    (`record["raw_message"]`, bytes): no hay re-fetch ni conexion nueva. Sin
    `raw_message` los adjuntos quedan como solo metadatos (stored false).
    Devuelve `(entries, stats)`: `entries` son las entradas completas para el
    frontmatter (`stored: true` o `stored: false` con `skipped: <motivo>`;
    tipos bloqueados y tamanos excedidos nunca se truncan) y `stats` un dict
    `{stored, skipped, errors, remaining}` con el presupuesto restante en
    bytes. Cada fallo por entrada se degrada a `skipped`: nunca aborta la
    sincronizacion, nunca rompe el cursor y nunca deja blobs `.tmp`.
    """
    entries = full_entries(record.get("attachments") or [])
    stats = {"stored": 0, "skipped": 0, "errors": 0, "remaining": budget_bytes}
    raw = record.get("raw_message")
    if not isinstance(raw, (bytes, bytearray)):
        return entries, stats
    for entry in entries:
        size = int(entry.get("size") or 0)
        if stats["remaining"] is not None and size > stats["remaining"]:
            entry["skipped"] = "budget-exhausted"
            stats["skipped"] += 1
            continue
        part_index = entry["part_index"]
        try:
            extracted = extract_attachment_bytes(raw, part_index)
            if extracted is None:
                entry["skipped"] = "part-not-found"
                stats["errors"] += 1
                continue
            content, filename, content_type = extracted
            result = store_attachment_bytes(
                root,
                entry["sha256"],
                content,
                {
                    "filename": filename,
                    "content_type": content_type,
                    "part_index": part_index,
                },
                authorize=True,
                max_bytes=MAX_ATTACHMENT_BYTES,
            )
            if result.get("stored"):
                entry["stored"] = True
                stats["stored"] += 1
                if stats["remaining"] is not None:
                    stats["remaining"] -= int(result.get("size") or size)
            else:
                entry["skipped"] = str(result.get("skipped") or "skipped")
                stats["skipped"] += 1
        except AttachmentError as exc:
            entry["skipped"] = exc.code
            stats["errors"] += 1
        except Exception:
            entry["skipped"] = "storage-error"
            stats["errors"] += 1
    return entries, stats


def full_entries(attachments):
    """Entradas completas de frontmatter a partir de los metadatos del parse.

    Agrega `part_index` (orden de aparicion en el MIME, determinista) y
    `stored: False`; el registro del parse queda intacto.
    """
    entries = []
    for index, attachment in enumerate(attachments or []):
        source = dict(attachment) if isinstance(attachment, dict) else {"sha256": attachment}
        entry = {
            "filename": str(source.get("filename") or ""),
            "content_type": str(source.get("content_type") or "application/octet-stream"),
            "size": int(source.get("size") or 0),
            "sha256": str(source.get("sha256") or ""),
        }
        entry["part_index"] = int(source.get("part_index") if source.get("part_index") is not None else index)
        entry["stored"] = bool(source.get("stored", False))
        if source.get("skipped"):
            entry["skipped"] = str(source["skipped"])
        entries.append(entry)
    return entries


def _front_value(text):
    stripped = text.strip()
    if stripped.startswith('"') and stripped.endswith('"') and len(stripped) >= 2:
        return stripped[1:-1]
    if stripped.lower() in ("true", "false"):
        return stripped.lower() == "true"
    return stripped


def _frontmatter_text(node_text):
    if not isinstance(node_text, str):
        raise ValueError("node_text debe ser str")
    parts = node_text.split("---\n", 2)
    return parts[1] if len(parts) == 3 else ""


def read_attachment_entries(node_text):
    """Lee las entradas de `attachments:` del frontmatter de un nodo.

    Acepta el formato antiguo (lista de hashes) y el nuevo (mapas con
    filename/content_type/size/part_index/stored), sin abrir blobs.
    """
    stored_flag = None
    raw_entries = []
    current = None
    in_block = False
    for line in _frontmatter_text(node_text).splitlines():
        stripped = line.strip()
        if stripped.startswith("attachments_stored:"):
            stored_flag = _front_value(stripped.split(":", 1)[1]) is True
            continue
        if not line.startswith((" ", "\t")):
            in_block = stripped == "attachments:"
            if not in_block:
                current = None
            continue
        if not in_block:
            continue
        if stripped.startswith("- "):
            item = stripped[2:].strip()
            if item.startswith("sha256:"):
                current = {"sha256": _front_value(item.split(":", 1)[1])}
                raw_entries.append(current)
            elif item and item != '""':
                current = {"sha256": _front_value(item)}
                raw_entries.append(current)
        elif current is not None and ":" in stripped:
            key, _, value = stripped.partition(":")
            current[key.strip()] = _front_value(value.strip())
    entries = []
    for index, raw in enumerate(raw_entries):
        entry = {
            "sha256": str(raw.get("sha256") or ""),
            "filename": str(raw.get("filename") or ""),
            "content_type": str(raw.get("content_type") or ""),
            "size": int(raw.get("size") or 0),
            "part_index": int(
                raw.get("part_index") if raw.get("part_index") is not None else index
            ),
            "stored": bool(raw["stored"]) if "stored" in raw else bool(stored_flag),
            "skipped": raw.get("skipped") or None,
        }
        entries.append(entry)
    return entries


def list_attachments(entries):
    """Filas de display a partir de entradas de frontmatter (sin leer blobs)."""
    rows = []
    for index, entry in enumerate(entries or []):
        sha256 = str((entry or {}).get("sha256") or "")
        part_index = int((entry or {}).get("part_index") if (entry or {}).get("part_index") is not None else index)
        rows.append(
            {
                "index": part_index,
                "display": sanitize_display_name(
                    (entry or {}).get("filename"), part_index
                ),
                "content_type": str(
                    (entry or {}).get("content_type") or "application/octet-stream"
                ),
                "size": int((entry or {}).get("size") or 0),
                "sha256": sha256,
                "sha256_short": sha256[:12],
                "status": "stored" if (entry or {}).get("stored") else "not-stored",
                "skipped": (entry or {}).get("skipped") or None,
            }
        )
    return rows


def list_node_attachments(root, rel_path):
    """Lista los adjuntos de un nodo del store: lee el nodo, nunca los blobs."""
    rows = list_attachments(read_attachment_entries(read_email_node(root, rel_path)))
    return rows


def extract_text_from_blob(root, entry, max_bytes=MAX_EXTRACTED_TEXT_BYTES):
    """Lee solo blobs almacenados y los convierte con parsers de texto inertes.

    No interpreta HTML, PDF, documentos ofimaticos ni formatos ejecutables:
    esos formatos requieren una etapa futura con sandbox y antivirus externo.
    """
    data = dict(entry or {})
    content_type = str(data.get("content_type") or "").split(";", 1)[0].lower()
    filename = str(data.get("filename") or "")
    if content_type not in _TEXT_TYPES or not is_type_allowed(content_type, filename):
        raise AttachmentError("type-not-supported", "tipo no soportado para texto")
    sha256 = _normalize_sha256(data.get("sha256"))
    blob = blob_path(root, sha256)
    if not blob.is_file():
        raise AttachmentError("not-stored", "el adjunto no esta almacenado")
    content = blob.read_bytes()
    if len(content) > int(max_bytes):
        raise AttachmentError("size-limit-exceeded", "texto extraido demasiado grande")
    if hashlib.sha256(content).hexdigest() != sha256:
        raise AttachmentError("hash-mismatch", "blob corrupto")
    if b"\x00" in content:
        raise AttachmentError("unsafe-content", "contenido no textual")
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise AttachmentError("decode-error", "texto no UTF-8 valido") from exc
    return {"sha256": sha256, "content_type": content_type, "text": text}


def extract_attachment_bytes(raw_message, part_index):
    """Extrae UNA parte hoja con filename de un RFC822 por indice.

    Mismo orden determinista que `parse._attachments`: hojas con filename en
    orden `walk()`. Devuelve `(bytes, filename_crudo, content_type)` o `None`
    si el indice excede las partes con filename.
    """
    if not isinstance(raw_message, (bytes, bytearray)):
        raise ValueError("raw_message debe ser bytes")
    message = BytesParser(policy=policy.default).parsebytes(bytes(raw_message))
    index = 0
    for part in message.walk():
        if part.is_multipart() or part.get_filename() is None:
            continue
        if index == int(part_index):
            content = part.get_payload(decode=True) or b""
            return bytes(content), str(part.get_filename()), part.get_content_type()
        index += 1
    return None


def read_download_target(node_text):
    """Identidad del mensaje para el re-fetch por UID: (account_id, imap_uid, mailbox).

    Lee el frontmatter del nodo; `imap_uid` es int >= 1 solo si el frontmatter
    lo trae, y `account_id`/`mailbox` son str no vacios o None. Los nodos
    legacy (sin `imap_uid`) no son descargables por diseño.
    """
    fields = {"account_id": None, "imap_uid": None, "mailbox": None}
    for line in _frontmatter_text(node_text).splitlines():
        stripped = line.strip()
        for label in fields:
            if not stripped.startswith(label + ":"):
                continue
            value = _front_value(stripped.split(":", 1)[1].strip())
            if isinstance(value, str) and value.strip() and value != '""':
                fields[label] = value.strip()
            break
    raw_uid = fields["imap_uid"]
    if raw_uid is not None:
        fields["imap_uid"] = int(raw_uid) if raw_uid.isdigit() else None
    if fields["imap_uid"] is not None and fields["imap_uid"] < 1:
        fields["imap_uid"] = None
    return fields["account_id"], fields["imap_uid"], fields["mailbox"]


def legacy_attachment_block(node_text):
    """True si alguna entrada de `attachments:` es un hash suelto (formato antiguo).

    Deteccion de solo lectura: una entrada legacy se reconoce por ser un item
    de lista que NO empieza por `sha256:` (los nodos del formato nuevo siempre
    escriben el mapa completo con `part_index` y `stored`).
    """
    in_block = False
    for line in _frontmatter_text(node_text).splitlines():
        stripped = line.strip()
        if not line.startswith((" ", "\t")):
            in_block = stripped == "attachments:"
            continue
        if not in_block or not stripped.startswith("- "):
            continue
        item = stripped[2:].strip()
        if item and item != '""' and not item.startswith("sha256:"):
            return True
    return False


def mark_attachment_stored(node_text, part_index):
    """Texto del nodo con `stored: true` SOLO en la entrada `part_index`.

    Reescribe unicamente la linea `stored:` de esa entrada y conserva TODO lo
    demas byte a byte (metadatos, otras entradas, cuerpo y delimitadores). Un
    nodo con entradas legacy (hashes sueltos) se rechaza con
    `legacy-node-format` para no reescribirlo silenciosamente; un indice
    ausente, con `no-such-attachment`.
    """
    if not isinstance(node_text, str):
        raise ValueError("node_text debe ser str")
    lines = _frontmatter_text(node_text).splitlines(keepends=True)
    in_block = False
    entries = []
    current = None
    for index, line in enumerate(lines):
        stripped = line.strip()
        if not line.startswith((" ", "\t")):
            in_block = stripped == "attachments:"
            if not in_block:
                current = None
            continue
        if not in_block:
            continue
        if stripped.startswith("- "):
            current = [index]
            entries.append(current)
        elif current is not None:
            current.append(index)
    target = None
    for entry in entries:
        body = [lines[item].strip() for item in entry]
        fields = {}
        for field in body[1:]:
            if ":" not in field:
                continue
            key, _, value = field.partition(":")
            fields[key.strip()] = value.strip()
        if "part_index" not in fields and "stored" not in fields:
            raise AttachmentError(
                "legacy-node-format",
                "el nodo usa el formato antiguo de adjuntos (hashes sueltos): "
                "no se marca stored sin reescribir el formato",
            )
        raw = _front_value(fields.get("part_index", ""))
        entry_index = int(raw) if isinstance(raw, str) and raw.isdigit() else -1
        if target is None and entry_index == int(part_index):
            target = entry
    if target is None:
        raise AttachmentError(
            "no-such-attachment", "part_index no presente en el nodo"
        )
    updated = list(lines)
    for item in target:
        stripped = lines[item].strip()
        if not stripped.startswith("stored:"):
            continue
        indent = lines[item][: len(lines[item]) - len(lines[item].lstrip())]
        eol = "\n" if lines[item].endswith("\n") else ""
        updated[item] = indent + "stored: true" + eol
    parts = node_text.split("---\n", 2)
    return parts[0] + "---\n" + "".join(updated) + "---\n" + parts[2]


def _resolve_node_rel_path(root_path, rel_path):
    """Ruta relativa segura del nodo (misma politica de lectura) bajo ROOT."""
    if not isinstance(rel_path, str) or not rel_path.strip():
        raise ValueError("rel_path debe ser str no vacio")
    portable = rel_path.replace("\\", "/")
    if (
        portable.startswith("~")
        or Path(portable).is_absolute()
        or (len(portable) >= 3 and portable[1:3] == ":/")
    ):
        raise ValueError("rel_path insegura (absoluta, ~ o unidad): " + repr(rel_path))
    if any(part in ("", ".", "..") for part in portable.split("/")):
        raise ValueError("rel_path con componente vacio, . o ..: " + repr(rel_path))
    if not portable.endswith(".md"):
        raise ValueError("la extension final no es .md: " + repr(rel_path))
    target = (root_path / Path(portable)).resolve()
    if target != root_path and root_path not in target.parents:
        raise ValueError("rel_path resuelve fuera de la raiz: " + repr(rel_path))
    return target


def write_node_text_atomic(root, rel_path, node_text):
    """Reescritura atomica de un nodo existente bajo ROOT (tmp + replace).

    La ruta se valida con la misma politica relativa de `read_email_node` y
    resuelve dentro de ROOT; el contenido viaja completo via `.tmp` y
    `os.replace`, asi que ante cualquier fallo el nodo queda intacto y no
    queda residual `.tmp`. Nunca compone rutas con datos del correo.
    """
    if not isinstance(node_text, str):
        raise ValueError("node_text debe ser str")
    if not isinstance(root, str) or not root.strip():
        raise ValueError("root debe ser str no vacio")
    root_path = Path(root).resolve()
    if not root_path.is_dir():
        raise ValueError("root no existe o no es directorio")
    target = _resolve_node_rel_path(root_path, rel_path)
    tmp = target.with_name(target.name + ".tmp")
    try:
        tmp.write_bytes(node_text.encode("utf-8"))
        os.replace(tmp, target)
    except Exception:
        try:
            tmp.unlink()
        except FileNotFoundError:
            pass
        raise
    return target


def render_attachment_front_lines(entry):
    """Lineas de frontmatter de una entrada de adjunto.

    Formato antiguo (string, o dict sin part_index/stored): solo el hash, tal
    como se escribia antes, para no alterar nodos ya persistidos. Formato
    nuevo (dict con part_index o stored): mapa completo, sin bytes.
    """
    if isinstance(entry, str):
        return ["  - " + _scalar_text(entry)]
    data = entry if isinstance(entry, dict) else {}
    if "part_index" not in data and "stored" not in data:
        return ["  - " + _scalar_text(data.get("sha256", ""))]
    lines = [
        "  - sha256: " + _scalar_text(data.get("sha256", "")),
        "    filename: " + _scalar_text(data.get("filename", "")),
        "    content_type: " + _scalar_text(data.get("content_type", "")),
        "    size: " + str(int(data.get("size") or 0)),
        "    part_index: " + str(int(data.get("part_index") or 0)),
        "    stored: " + ("true" if data.get("stored") else "false"),
    ]
    if data.get("skipped"):
        lines.append("    skipped: " + _scalar_text(data["skipped"]))
    return lines


# ---------------------------------------------------------------------------
# GC de blobs sin referencia: escaneo de solo lectura, borrado solo con la
# frase literal exacta. La ruta de CADA blob se valida contra el layout del
# hash (`attachments/ab/cd/<sha256>`); NUNCA se sigue una ruta derivada del
# filename, NUNCA se borra un blob referenciado, corrupto o no reconocido.
# ---------------------------------------------------------------------------

GC_CONFIRMATION = "CONFIRMAR BORRADO ADJUNTOS"
_STORE_DIRNAME = "store"
_TRASH_DIRNAME = ".trash"


def iter_active_node_rel_paths(root):
    """Rutas relativas posix de los nodos .md ACTIVOS bajo ROOT/store.

    Excluye cualquier ruta bajo `.trash` y ordena determinista. Fail-closed:
    si el store no existe se aborta (GC sin store podria creer todo huerfano)
    y una entrada `.md` que sea enlace se rechaza en vez de seguirse.
    """
    root_path = Path(root)
    base = root_path / _STORE_DIRNAME
    if not base.is_dir():
        raise AttachmentError(
            "store-missing",
            "el store de nodos no existe: no se hace GC sin el store",
        )
    paths = []
    for candidate in sorted(base.rglob("*.md")):
        rel = candidate.relative_to(root_path)
        if _TRASH_DIRNAME in rel.parts:
            continue
        if candidate.is_symlink():
            raise AttachmentError(
                "unsafe-path",
                "entrada .md sospechosa (enlace) en el store: " + rel.as_posix(),
            )
        if not candidate.is_file():
            continue
        paths.append(rel.as_posix())
    return paths


def _referenced_from_node_texts(root_path, rel_paths):
    """sha256 (hex validados) referenciados por los nodos dados.

    Fail-closed: cualquier nodo ilegible (E/S o frontmatter roto) aborta el
    escaneo; nunca se deduce que un blob es huerfano con nodos ileidos a medias.
    """
    referenced = set()
    for rel in rel_paths:
        try:
            text = (root_path / rel).read_text(encoding="utf-8")
            entries = read_attachment_entries(text)
        except Exception as exc:
            raise AttachmentError(
                "node-unreadable",
                "un nodo activo no se pudo leer: " + rel,
            ) from exc
        for entry in entries:
            sha256 = str((entry or {}).get("sha256") or "")
            if _SHA256_RE.fullmatch(sha256):
                referenced.add(sha256)
    return referenced


def collect_referenced_hashes(root):
    """Conjunto de sha256 referenciados por TODOS los nodos activos."""
    root_path = Path(root)
    return _referenced_from_node_texts(root_path, iter_active_node_rel_paths(root))


def _file_sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _classify_blob_entries(root_path, referenced):
    """Clasifica los archivos bajo ROOT/attachments sin borrar nada.

    Devuelve `(candidates, corrupt, unrecognized, nodes_scanned)`; los paths
    son relativos a ROOT en formato posix. Solo se consideran blob los
    archivos cuya ruta coincide EXACTAMENTE con el layout del hash
    (`attachments/ab/cd/<64hex>`) y solo `.meta` los `<64hex>.meta` planos;
    todo lo demas queda en `unrecognized` y JAMAS se borra.
    """
    candidates = []
    corrupt = []
    unrecognized = []
    blob_rels = {}
    meta_rels = {}
    attachments = root_path / "attachments"
    if attachments.is_dir():
        for path in sorted(attachments.rglob("*")):
            if path.is_symlink() or not path.is_file():
                continue
            rel = path.relative_to(attachments).as_posix()
            parts = rel.split("/")
            sha = None
            if (
                len(parts) == 3
                and _SHA256_RE.fullmatch(parts[2])
                and parts[0] == parts[2][:2]
                and parts[1] == parts[2][2:4]
            ):
                sha = parts[2]
                blob_rels[sha] = "attachments/" + rel
            elif (
                len(parts) == 1
                and rel.endswith(".meta")
                and _SHA256_RE.fullmatch(rel[: -len(".meta")])
            ):
                meta_rels[rel[: -len(".meta")]] = "attachments/" + rel
            else:
                unrecognized.append("attachments/" + rel)
    for sha in sorted(blob_rels):
        if sha in referenced:
            continue
        rel = blob_rels[sha]
        try:
            actual = _file_sha256(root_path / rel)
            size = (root_path / rel).stat().st_size
        except OSError:
            corrupt.append({"sha256": sha, "blob": rel, "size": None})
            continue
        if actual != sha:
            corrupt.append({"sha256": sha, "blob": rel, "size": size})
            continue
        candidates.append(
            {
                "sha256": sha,
                "kind": "blob",
                "blob": rel,
                "meta": meta_rels.get(sha),
                "size": size,
                "corrupt": False,
            }
        )
    for sha in sorted(meta_rels):
        if sha in referenced or sha in blob_rels:
            continue
        rel = meta_rels[sha]
        try:
            size = (root_path / rel).stat().st_size
        except OSError:
            size = None
        candidates.append(
            {
                "sha256": sha,
                "kind": "meta-only",
                "blob": None,
                "meta": rel,
                "size": size,
                "corrupt": False,
            }
        )
    return candidates, corrupt, unrecognized


def gc_scan(root):
    """Escaneo de SOLO lectura para el GC de blobs bajo ROOT.

    Devuelve un dict con `nodes_scanned`, `referenced_count`, `candidates`
    (blobs y `.meta` sin NINGUNA referencia activa; cada blob lleva su
    `.meta` relacionado), `corrupt` (blobs cuyo contenido no coincide con su
    sha256: se reportan y NUNCA se borran) y `unrecognized` (archivos bajo
    ROOT/attachments que no siguen el layout del hash: NUNCA se borran).
    Los paths son relativos a ROOT, formato posix, sin rutas absolutas.
    """
    root_path = Path(root)
    rel_paths = iter_active_node_rel_paths(root)
    referenced = _referenced_from_node_texts(root_path, rel_paths)
    candidates, corrupt, unrecognized = _classify_blob_entries(root_path, referenced)
    return {
        "nodes_scanned": len(rel_paths),
        "referenced_count": len(referenced),
        "candidates": candidates,
        "corrupt": corrupt,
        "unrecognized": unrecognized,
    }


def gc_execute(root, confirmation):
    """Borrado de blobs sin referencia: SOLO con la frase literal exacta.

    La confirmacion se valida ANTES de escanear y de mutar nada. Los
    borrados son directos (sin archivos temporales). Ante el PRIMER fallo de
    E/S se detiene todo: no se borra ningun otro blob, no queda residual y se
    reporta `failed`. Un blob corrupto o no reconocido nunca se borra.
    """
    if not isinstance(confirmation, str) or confirmation != GC_CONFIRMATION:
        raise AttachmentError(
            "confirmation-required",
            "confirmacion literal requerida para borrar blobs sin referencia",
        )
    scan = gc_scan(root)
    root_path = Path(root)
    deleted = []
    failed = []
    for candidate in scan["candidates"]:
        targets = [rel for rel in (candidate.get("blob"), candidate.get("meta")) if rel]
        for rel in targets:
            try:
                (root_path / rel).unlink()
            except FileNotFoundError:
                continue
            except OSError:
                failed.append({"path": rel, "error": "io-error"})
                break
            deleted.append(rel)
        if failed:
            break
    return dict(
        scan,
        deleted=deleted,
        failed=failed,
    )
