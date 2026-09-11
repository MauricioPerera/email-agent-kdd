# Sprint 3 — Actualización de docs de adjuntos (reporte)

Fecha: 2026-09-11 · Estado: **LISTO** · Sin commit/push, sin red, sin cambios de código.

## Alcance

Solo `README.md` y `plugins/email-agent/skills/email-agent/SKILL.md`. Fuentes:
`SPRINT3-ATTACHMENT-DESIGN.md`, el bloque attachment de los reportes
(`SPRINT3-ATTACHMENT-CORE/LIST/DOWNLOAD/ASSOCIATION/SYNC-ATTACHMENT-LINK`) y las
firmas reales de `src/email/cli.py` (`_run_attachment`,
`_run_attachment_download`) y `src/email/attachments.py`.

## README.md (español, estilo existente)

- Sección renombrada a "Adjuntos (listado y descarga)".
- Nueva frase: sync persiste solo metadatos; no hay extracción durante sync por
  defecto (no existe `sync --attachments`); el contenido solo entra vía
  `attachment download`.
- `attachment list ROOT REL_PATH` documentado como solo lectura (metadatos del
  frontmatter; nunca abre blobs ni conecta a IMAP).
- `attachment download ROOT REL_PATH INDEX DEST CONFIRMAR EXTRACCION`
  documentado como extracción autorizada: frase literal exacta + autorización
  del usuario (nunca la aporta el agente); nodo debe declarar
  `account_id`/`imap_uid`/`mailbox` (legacy rechazado, re-sincronizar); re-fetch
  RFC822 readonly por UID sin mutar cursor; límites (25 MB) y tipos bloqueados
  (`.exe/.scr/.lnk/.bat/.cmd/.js`); blob content-addressed en
  `ROOT/attachments/ab/cd/<sha256>` con verificación de hash antes/después e
  idempotencia sin sobrescritura; copia atómica en `DEST` anti-traversal;
  `stored: true` con escritura atómica y retirada de la copia si la asociación
  falla.
- Aclarado: blobs compartidos por contenido, borrar mensajes no borra blobs y
  NO existe GC todavía (`attachment gc` no está implementado).
- Códigos de salida 0/1/2 y errores nominales (`attachment-not-found`,
  `size-limit-exceeded`, `type-not-allowed`, `hash-mismatch`).
- Eliminada la frase "la extracción de contenido sigue pendiente de
  autorización explícita".

## SKILL.md (inglés, estilo existente)

- Sección Attachments reescrita: sync = solo metadatos, sin bytes al disco;
  extracción solo bajo autorización.
- `attachment list` igual que antes (read-only, frontmatter).
- `attachment download ROOT REL_PATH INDEX DEST CONFIRMAR EXTRACCION`
  documentado con los mismos invariantes que README (confirmación literal,
  tripleta de nodo obligatoria, re-fetch readonly, límites/tipos, blob
  content-addressed, anti-traversal en `DEST`, `stored: true` atómico).
- Aclarado que no hay GC todavía y que los blobs sin referencias permanecen.
- Códigos de salida documentados.
- Eliminada la frase "defer content extraction until the user requests it".

## Verificación

```
rg -c "attachment download|CONFIRMAR EXTRACCION" README.md plugins/email-agent/skills/email-agent/SKILL.md
README.md:3
plugins/email-agent/skills/email-agent/SKILL.md:1
```

Ambos documentos contienen `attachment download` y `CONFIRMAR EXTRACCION`
(en SKILL.md ambas frases coinciden en la misma línea del bullet de descarga).
Sin restos de "pendiente/defer" en el contexto de adjuntos (`rg` confirma).
Código sin modificar.