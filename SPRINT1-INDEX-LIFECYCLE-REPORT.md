# SPRINT1-INDEX-LIFECYCLE-REPORT.md

Fecha: 2026-09-10

## Objetivo

`add_path_to_markdown_index(index_path, message_path)` y
`remove_path_from_markdown_index(index_path, message_path)` para editar los índices
Markdown ya existentes (Conversation y Topic) sin reescribir sus módulos de origen.

## Archivos creados (únicos)

- `src/email/index_lifecycle.py`
- `outputs/email-agent-kdd/tests/frozen_index_lifecycle.py`

Ningún otro archivo modificado. Sin commit.

## Formatos soportados (exactamente los existentes)

- Conversation: `---\ntype: Conversation\nconversation_key: <64 hex>\nmessage_count: N\n---\n` + `- <ruta>\n` (`src/email/conversation_index.py`).
- Topic: `---\ntype: Topic\ntopic: <topic>\nmessage_count: N\n---\n` + `- <ruta>\n` (`src/email/topic_index.py`).

## Comportamiento

- Conserva el frontmatter verbatim; solo recalcula `message_count`.
- Union deduplicada, normalización `\` → `/` y orden lexicográfico ascendente.
- Escritura atómica: `<nombre>.tmp` en el mismo directorio + `os.replace`; sin residuos.
- `remove`: `True` si actualizó o borró el nodo; `False` si la ruta no está, el índice no existe o no habría cambio. Si la lista queda vacía, elimina el archivo del índice.
- `add`: devuelve el `message_count` final; exige índice existente con formato válido (`ValueError` si falta o está corrupto — sin él no hay frontmatter que conservar); reescritura idempotente solo si cambia el conjunto.
- Cualquier desviación (cabecera inválida, cuerpo no `- <ruta>\n`, `message_count` incoherente, entrada con `..`/NUL) → `ValueError` SIN escribir y sin ficheros `.tmp` residuales.
- Validación de rutas: str no vacío, sin byte nulo, sin segmentos `..` (path traversal), en el argumento y en cada entrada leída.
- Sin red, sin secretos, sin dependencias de otros módulos nuevos.

## Pruebas (`15 passed`)

`python -m pytest outputs/email-agent-kdd/tests/frozen_index_lifecycle.py -q` →
`15 passed in 0.37s`

Cobertura: remove/add en Conversation con dos rutas; remove/add en Topic con dos rutas
(incluye coincidencia con `\` y orden); deduplicación idempotente; borrado del índice al
quedar sin rutas (ambos formatos); índice vacío (`message_count: 0`) para add y remove
no-op; 6 casos de corrupción parametrizados (sin frontmatter, conversation_key no hex,
`message_count` incoherente, línea suelta, entrada con `..`, Topic sin entradas)
verificando ValueError + archivo intacto + sin `.tmp`; add a índice inexistente y remove
no-op; rechazo de path traversal/ruta vacía/NUL sin escribir; espía sobre `os.replace`
que verifica temporal en el mismo directorio, destino correcto y ausencia de residuos.

## Decisiones

- `add` no crea índices nuevos: el formato (Conversation vs Topic) no es deducible de
  `index_path` y crear un frontmatter genérico divergiría de los formatos existentes.
- `message_count: 0` nunca se persiste: el nodo vacío se elimina, igual que lo haría el
  ciclo de vida natural de un índice.
- Se normalizan también las entradas leídas del fichero para comparar rutas escritas con
  `\` por otros módulos; una entrada con `..` se considera fichero corrupto.