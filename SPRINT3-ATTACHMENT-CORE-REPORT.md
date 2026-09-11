# Sprint 3 — Núcleo de almacenamiento seguro de adjuntos (reporte)

**Estado: LISTO.** Test nuevo: 18/18 passed (`frozen_attachments.py`, 0.33 s, offline).

## Nota de honestidad sobre el estado previo

Al iniciar esta pasada ya existía `src/email/attachments.py` (creado en una sesión anterior
del mismo día, junto a `frozen_attachments_core.py`). Esta pasada NO reescribió el núcleo:
lo validó contra el diseño línea por línea y contra el nuevo oracle pedido. No se cambió
`attachments.py`, ni `parse.py`, ni `persist.py`, ni el CLI.

## Entregado

- `src/email/attachments.py` — núcleo (preexistente, verificado contra el diseño):
  - `blob_path` / `blob_rel_path` / `meta_path`: ruta derivada SOLO del sha256
    (validado `[0-9a-f]{64}`), layout `ROOT/attachments/ab/cd/<sha256>`,
    `.meta` en `ROOT/attachments/<sha256>.meta`.
  - `store_attachment_bytes(root, sha256, content, metadata, *, authorize, max_bytes,
    allowed_types)`: sin `authorize=True` no escribe un byte
    (`confirmation-required`). Verifica hash del contenido ANTES de escribir,
    escritura atómica (`.tmp` + `replace`), re-verificación del hash leyendo de vuelta,
    detección de colisión/corrupción con aborto sin sobrescribir (`hash-mismatch`).
    Idempotente: segunda extracción con blob verificado = no-op (`idempotent: true`).
  - Límite de tamaño: 25 MB por defecto (`MAX_ATTACHMENT_BYTES`), configurable por
    llamada; exceder devuelve entrada `stored: False, skipped: size-limit-exceeded`,
    sin bytes en disco y sin truncar.
  - Tipos bloqueados por defecto: `application/x-msdownload`, `application/x-sh` y
    extensiones `.exe/.scr/.lnk/.bat/.cmd/.js` → solo metadatos
    (`skipped: type-not-allowed`); lista explícita `allowed_types` los autoriza.
  - `sanitize_display_name`: base del nombre, separadores neutralizados, caracteres
    de control → `?`, longitud acotada a 80, fallback `attachment-<part_index>`.
  - `read_attachment_entries` / `list_attachments` / `list_node_attachments`:
    leen frontmatter (formato antiguo de hashes y nuevo de mapas) y listan metadatos
    SIN abrir blobs; `read_email_node` reusa la resolución segura del store.
  - `full_entries` / `render_attachment_front_lines`: frontmatter nuevo con
    `part_index`/`stored` sin tocar nodos legacy (formato antiguo = solo hash).
  - Errores nominales vía `AttachmentError(code, message)` con códigos
    `confirmation-required`, `hash-mismatch`, `size-limit-exceeded`,
    `type-not-allowed`; mensajes sin rutas absolutas (solo `attachments/...` relativa).
- `outputs/email-agent-kdd/tests/frozen_attachments.py` — oracle congelado nuevo,
  alcance exacto pedido:

| Grupo | Tests |
|---|---|
| Traversal | ruta content-addressed; sha256 inválido rechazado antes de escribir; filenames hostiles no escapan de `store/attachments/` |
| Nombres hostiles | `sanitize_display_name` neutraliza `../../`, `C:\`, `~`, `..`, `.`, control, Unicode trick, 400 chars; sin `/`, `\`, `..`, control |
| Autorización | sin `authorize=True` → `confirmation-required`, cero bytes |
| Guardado | blob + `.meta` content-addressed con datos correctos |
| Colisión / hash mismatch | contenido ≠ sha → error sin escribir; blob corrupto → `hash-mismatch`, sin sobrescribir, sin `.tmp` huérfanos; re-check idempotente detecta corrupción |
| Límite / tipos | `max_bytes` excedido → `stored: false` sin bytes; 8 tipos/extensiones bloqueados → solo metadatos; allowlist explícito → blob; reglas `is_type_allowed` |
| Idempotencia | segunda extracción = no-op (blob + `.meta` intactos, `idempotent: true`) |
| Listado sin blobs | `list_attachments` sanea display/estado; `list_node_attachments` no materializa `attachments/` |
| Errores sanitizados | mensajes sin rutas absolutas ni tmp_path ni `C:\` ni secretos; `hash-mismatch` muestra solo la ruta relativa |

## No tocado (según lo pedido)

`parse.py`, `persist.py`, CLI: sin cambios. Sin red, sin secretos, sin commit ni push.

## Pendiente de este sprint (fuera del alcance del núcleo)

Frontmatter en `persist.py` (`part_index`/`stored`), CLI `attachment list|download`
con `CONFIRMAR EXTRACCION`, GC, índice invertido.