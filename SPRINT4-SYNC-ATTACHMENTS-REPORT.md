# Sprint 4 — Fase `sync --attachments` (informe)

Fecha: 2026-09-11 · Estado: COMPLETADO · Alcance: solo la bandera `--attachments` de `sync`; sin GC.

## Resumen

`sync ROOT ACCOUNT_ID [--limit N] [--unread] --attachments CONFIRMAR EXTRACCION` guarda los blobs de los adjuntos permitidos durante la sincronización, reutilizando el RFC822 ya descargado en esa misma sync (un solo `FETCH (RFC822)` por mensaje, sin re-fetch). Sin la opción, el comportamiento por defecto queda intacto: jamás se persiste un byte de adjunto y el resumen conserva exactamente las 5 claves del contrato.

## Cambios por archivo

- `src/email/imap_reader.py` — `fetch_imap_messages(account, config, connection_factory=None, include_raw=False)`: con `include_raw=True` cada record lleva `record["raw_message"]` (el RFC822 ya descargado). Por defecto (`False`) los bytes se descartan como siempre y el record no cambia. La ruta por defecto se invoca sin el kwarg para no alterar la firma que los oráculos congelados inyectan.
- `src/email/attachments.py`
  - `store_record_attachments(root, record, budget_bytes)`: para un record de sync, extrae cada parte con `extract_attachment_bytes` desde el RFC822 reutilizado y la guarda con `store_attachment_bytes(authorize=True, max_bytes=MAX_ATTACHMENT_BYTES)`. Devuelve `(entries, stats)`: entradas completas para el frontmatter (`stored: true`, o `stored: false` con `skipped: <motivo>`: `size-limit-exceeded`, `type-not-allowed`, `budget-exhausted`, `part-not-found`, `hash-mismatch`, `storage-error`) y contadores con presupuesto restante. Cada fallo por entrada se degrada a `skipped`: nunca aborta la sync ni rompe el cursor. Sin `raw_message` (no debería ocurrir en esta modalidad) los adjuntos quedan como solo metadatos.
  - `store_attachment_bytes`: la escritura del blob quedó envuelta en `try/except` que elimina el `.tmp` y re-lanza — un fallo de E/S no deja blobs temporales residuales (el resto del contrato es idéntico).
- `src/email/cli.py`
  - Parseo de `--attachments CONFIRMAR EXTRACCION` (frase literal, tokens separados, posición libre respecto a `HOST`/`--limit`/`--unread`). Frase ausente o incorrecta → código `1` con error genérico, **antes** de leer cuentas, resolver credenciales o conectar. Presupuesto por env var `SYNC_ATTACHMENT_BUDGET_MB` (entero ≥ 1, default 100 MB); valor inválido → código `2` antes de conectar.
  - En modalidad autorizada: fetch con `include_raw=True`; el callback de persistencia calcula las entradas (extracción + blobs) **antes** de escribir el nodo, de modo que el nodo se persiste una sola vez, de forma atómica, ya con `stored`/`skipped` finales (formato nuevo: mapas con `part_index`); `raw_message` se elimina del record antes de persistir y nunca llega a disco. El resumen añade `attachments_stored`, `attachments_skipped`, `attachments_errors` solo en esta modalidad.
  - `USAGE`/`SYNC_USAGE` y docstrings actualizados. `watch` y `startup install` reutilizan `_run_sync` sin la opción: sin cambios.
- `outputs/email-agent-kdd/tests/frozen_cli_sync_attachments.py` — nuevo oráculo offline (11 pruebas, sin red ni secretos reales, IMAP falso inyectado).
- `README.md` y `plugins/email-agent/skills/email-agent/SKILL.md` — solo la documentación de esta bandera.

## Decisiones

1. **Nodo en formato nuevo al vuelo**: la extracción ocurre dentro del callback de persistencia (después de extraer contactos no; antes de `persist_email_okf_at`), así el nodo se escribe una única vez con el estado final y no hace falta reescribirlo con `mark_attachment_stored` (esa vía queda reservada para `attachment download`). Un nodo re-sincronizado tras haberse persistido en formato antiguo fallaría por el rechazo de sobrescritura distinta de `persist_email_okf_at` (comportamiento preexistente; el cursor normal evita re-persistir el mismo mensaje).
2. **Presupuesto**: 100 MB por sync por defecto, configurable solo por `SYNC_ATTACHMENT_BUDGET_MB` (más simple y testeable offline que otra bandera posicional). El presupuesto contabiliza los bytes realmente almacenados; los adjuntos deduplicados por hash no re-consumen presupuesto al segundo mensaje (el blob existe y es idempotente), pero el hueco del primero sí se descuenta.
3. **Fallos por adjunto**: se degradan a `skipped` en el frontmatter y al contador `attachments_errors` del resumen; la sync devuelve `0` y el cursor avanza (las claves, el nodo y los blobs sí persistidos son correctos). Un fallo que impida persistir el nodo sigue abortando la sync entera (comportamiento preexistente).
4. **Motivos `skipped` en el frontmatter**: se registran porque la extracción ocurre antes de la primera escritura del nodo; el listado (`attachment list`) los muestra tal cual.

## Garantías verificadas (pruebas frozen)

1. **Sync por defecto sin blobs**: summary de 5 claves exactas, frontmatter sin `stored:`, sin `ROOT/attachments`, cursor avanza, un fetch por mensaje.
2. **Confirmación preconexión**: frase ausente/incorrecta/invertida → código `1`, `fake.calls == []` (ni conexión), sin nodos, sin blobs, sin cursor.
3. **Env var inválida** (`0`, `-5`, `abc`, `1.5`) → código `2` sin conectar.
4. **Éxito autorizado**: 2 adjuntos guardados con bytes exactos bajo `ROOT/attachments/ab/cd/<sha256>`, `.meta` escrito, frontmatter con `part_index` y `stored: true`, `attachments_stored: 2`, un solo `fetch` por mensaje, sin secretos ni rutas absolutas en stdout/stderr/nodo.
5. **Compatibilidad de banderas**: `--limit` + `--unread` + `--attachments` funcionan combinados (`search UNSEEN`, página de 1).
6. **Presupuesto**: `SYNC_ATTACHMENT_BUDGET_MB=1` con adjuntos de 600 KB → primero `stored: true`, segundo `skipped: budget-exhausted`, solo metadatos.
7. **Tipos bloqueados** (`.exe`) → `skipped: type-not-allowed`, cero bytes en disco. **Límite por adjunto** (`MAX_ATTACHMENT_BYTES` inyectado a 8) → `skipped: size-limit-exceeded`, tamaño declarado sin truncar.
8. **Idempotencia**: re-sync tras reiniciar el cursor → re-extracción no-op (blob, `.meta` y nodo byte a byte idénticos; un solo blob + un solo `.meta`).
9. **Rollback/cursor**: blob corrupto preexistente → `skipped: hash-mismatch`, blob no sobrescrito, sin `.tmp` residuales, sync devuelve `0` y el cursor avanza.
10. **Página vacía / aridad**: sin mensajes nuevos el cursor no se reescribe; `--limit` inválido sigue dando `2`; `HOST` posicional sigue funcionando.

## Ejecución

- Nuevas: `frozen_cli_sync_attachments.py` — 11 passed.
- Suite completa (687 pruebas frozen, incluidas las de sync, adjuntos, descarga y asociación de sprints previos): **687 passed, 0 failed**.

## Fuera de alcance (no implementado)

- GC de blobs (`attachment gc`) y conteo de referencias — pedido explícitamente fuera de alcance.
- Extracción de mensajes ya sincronizados por re-fetch (es la vía de `attachment download`).
- Presupuesto persistente por cuenta; la confirmación sigue siendo por comando.