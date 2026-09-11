# Sprint 4 — Fase `attachment gc` (informe)

Fecha: 2026-09-11 · Estado: COMPLETADO · Alcance: solo el GC de blobs de adjuntos (listado en seco + borrado autorizado); `attachment list`, `attachment download` y `sync --attachments` intactos.

## Resumen

`email-agent attachment gc ROOT` lista en un JSON los blobs sin referencia bajo `ROOT/attachments` sin borrar nada (dry-run de solo lectura). `email-agent attachment gc ROOT CONFIRMAR BORRADO ADJUNTOS` valida la frase literal exacta ANTES de mutar y elimina cada blob candidato junto a su `.meta` relacionado. Un blob referenciado, corrupto o de forma no reconocida JAMAS se borra; un fallo de E/S detiene todo sin borrar nada mas y sin dejar temporales.

## API en `src/email/attachments.py`

- `GC_CONFIRMATION = "CONFIRMAR BORRADO ADJUNTOS"` — frase literal exacta, distinta de `CONFIRMAR EXTRACCION` y `CONFIRMAR BORRADO PERMANENTE`.
- `iter_active_node_rel_paths(root)` — rutas relativas posix de los `.md` activos bajo `ROOT/store`, orden determinista, excluyendo `.trash`. Fail-closed: store ausente → `store-missing`; un `.md` que sea enlace → `unsafe-path` (no se sigue).
- `collect_referenced_hashes(root)` / `_referenced_from_node_texts` — hashes hex válidos referenciados por cualquier nodo activo (formato nuevo y formato antiguo/legacy). Fail-closed: cualquier nodo ilegible (E/S o frontmatter roto) aborta con `node-unreadable`; nunca se deduce que un blob es huérfano con nodos leídos a medias.
- `gc_scan(root)` — escaneo de SOLO lectura. Devuelve `nodes_scanned`, `referenced_count`, `candidates` (blobs sin referencia con su `.meta` relacionado, y `.meta` huérfanos sin blob), `corrupt` (blobs cuyo contenido no coincide con su `sha256`, calculado por lectura en chunks) y `unrecognized`. Paths relativos a ROOT, formato posix, sin rutas absolutas.
- `_classify_blob_entries` — solo se consideran blob los archivos cuya ruta coincide EXACTAMENTE con `attachments/ab/cd/<64hex>` (segmentos derivados del propio hash) y solo `.meta` los `<64hex>.meta` planos; todo lo demás (`.tmp`, nombres no-hex, anidamientos incorrectos, enlaces) queda en `unrecognized` y nunca se borra ni se sigue.
- `gc_execute(root, confirmation)` — valida la confirmación ANTES de escanear y mutar. Borrados directos con `unlink` (sin archivos temporales). Ante el PRIMER fallo de E/S se detiene todo: no se borra ningún otro blob, se reporta `failed: [{path, error: io-error}]` junto a `deleted`. Los corruptos se saltan siempre. `FileNotFoundError` durante el borrado se trata como ya ausente (idempotencia), no como fallo.

## CLI en `src/email/cli.py`

- `_run_attachment_gc`: aridad 3 (`ROOT`) o 6 (`ROOT` + 3 tokens de confirmación); otra aridad → código `2`. Frase inexacta con 6 tokens → código `1` antes de mutar (mismo estándar que `download`/`purge`). `ROOT` inexistente → `2`. `AttachmentError` del escaneo (`store-missing`, `node-unreadable`, `unsafe-path`) → código `1` con mensaje "no se borro nada".
- Salida: UN objeto JSON en stdout con `mode` (`dry-run|executed`), `nodes_scanned`, `referenced_count`, `candidates`, `corrupt`, `unrecognized`, `deleted`, `failed` (vacíos en dry-run). Exit `0` salvo `failed` no vacío → `1`. Sin rutas absolutas ni secretos.
- `USAGE`, ayuda de `--help` y despacho de `attachment` actualizados (`list`, `download`, `gc`); `list` y `download` sin cambios de comportamiento.

## Documentación

- `README.md` — nueva subsección "GC (listado en seco y borrado autorizado)" con garantías y códigos de salida; se retira la nota de que "no existe recolección de basura".
- `plugins/email-agent/skills/email-agent/SKILL.md` — viñetas equivalentes en inglés, incluida la regla de que el agente nunca aporta la frase literal.

## Garantías verificadas (pruebas frozen, offline, sin red ni secretos)

1. **Preservar referencias** — blob + `.meta` referenciados por un nodo activo (formato nuevo y formato antiguo de hashes sueltos) intactos tras el borrado.
2. **Excluir `.trash`** — un blob cuya única referencia vive en `.trash/store/emails/...` es huérfano y se elimina; también se excluye un nodo bajo `store/.trash`.
3. **Dry-run sin mutación** — `gc_scan` no cambia un solo byte (comparación de rutas y contenidos antes/después); el CLI dry-run devuelve `mode: dry-run`, `deleted: []` y exit `0`.
4. **Confirmación exacta** — mayúsculas/minúsculas, tokens de más o de menos, frase de otro comando, `None` o vacío → `confirmation-required` y cero borrados; en el CLI la frase equivocada → `1` sin borrar nada.
5. **Limpieza blob + `.meta`** — el huérfano y su `.meta` se eliminan juntos; el `.meta` de un blob referenciado se conserva.
6. **Hash inválido/corrupto** — blob cuyo contenido no coincide con su nombre → `corrupt`, reportado y NUNCA borrado (ni su `.meta`); archivos con nombre no-hex, `.meta` con nombre inválido, `.meta` anidado y residual `.tmp` → `unrecognized` e intactos.
7. **Fallo parcial** — el primer `PermissionError` de `unlink` detiene todo: solo se reporta ese fallo, solo se borró lo anterior en el orden determinista, el `.meta` del fallado queda intacto y no hay temporales; el CLI devuelve `1`. Un pase posterior sin el fallo limpia normal.
8. **Idempotencia** — segundo pase sin candidatos, `deleted: []`, exit `0`, disco idéntico.
9. **Fail-closed** — store ausente (`store-missing`) o nodo ilegible (`node-unreadable`, p. ej. frontmatter con `size` no numérico) abortan el escaneo y no borran nada; en el CLI → exit `1`.
10. **Integridad de los demás comandos** — `attachment list` sigue devolviendo sus filas y el error de acción inválida ahora menciona `list`, `download` y `gc`; la suite completa no registra regresiones.

## Ejecución

- Nuevas: `frozen_attachment_gc.py` (13 pruebas) + `frozen_cli_attachment_gc.py` (12 pruebas) — 25 passed.
- Suite completa: **735 passed, 6 skipped, 0 failed** (6 skipped preexistentes, requieren entorno).
- Sin red, sin secretos reales, sin procesos en segundo plano; sin commit ni push.

## Fuera de alcance (no implementado)

- Integración del GC con el ciclo `.trash` de `message purge` (el diseño lo deja como candidato futuro).
- GC de mensajes/índices (solo blobs de adjuntos y sus `.meta`).
- Programación automática del GC: siempre es un comando explícito, nunca se dispara desde `sync` o `watch`.