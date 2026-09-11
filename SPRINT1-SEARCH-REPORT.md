# SPRINT1-SEARCH-REPORT — Exclusión de `.trash` en query.py y search.py

Fecha: 2026-09-10. Sin red, sin secretos, sin commit.

## Subobjetivo

`query.py` y `search.py` deben excluir cualquier archivo o índice bajo `root/.trash`
de los resultados, conservando firmas y comportamiento actual.

## Cambios

### src/email/search.py
- Constante `TRASH_DIRNAME = ".trash"`.
- En `search_email_nodes`, el bucle `rglob("*")` salta — **antes de leer** el
  archivo — cualquier `.md` cuyo primer componente relativo sea `.trash`.
- Firma `search_email_nodes(root: str, query: str) -> list` intacta. Docstring
  actualizada.

### src/email/query.py
- Constante `TRASH_DIRNAME = ".trash"`.
- `_scan_terms`: salta (antes de leer) los `.md` bajo `root/.trash`, por lo que
  los términos libres nunca matchean copias en la papelera.
- `_resolve_node`: devuelve `None` si la ruta resuelta del índice cae bajo
  `.trash` (una entrada de índice que apunte a la papelera no cuenta como
  resultado).
- `query_email`: si algún índice derivado de `conversation:`/`topic:` cae bajo
  `.trash`, se trata como índice ausente (`[]`) y **no se lee**.
- Firma `query_email(root: str, instruction: str) -> list` intacta.

Punto clave: el salto ocurre **antes** de `read_text`, de modo que contenido
con bytes UTF-8 inválidos dentro de `.trash` tampoco se lee (ver pruebas).

## Pruebas nuevas

`outputs/email-agent-kdd/tests/frozen_trash_search_exclusion.py` — 9 tests:

- Árbol base: nodo activo `store/emails/msg-0001.md` + copia **idéntica** en
  `.trash/store/emails/msg-0001.md`, más dentro de `.trash` otros `.md` y
  **índices de tema y conversación** (`store/topics/factura.md`,
  `store/conversations/<hex-64>.md`) con bytes UTF-8 **inválidos**: si el
  target los leyera, fallaría con `UnicodeDecodeError`; la prueba exige el
  resultado correcto, así que la lectura de esos índices queda descartada.
- `search_email_nodes` devuelve solo el nodo activo; `[]` cuando solo existe
  la copia en `.trash`.
- `query_email`: término libre solo matchea el activo; `topic:factura` con el
  índice activo presente ignora el índice gemelo en `.trash`; con el índice
  solo en `.trash` devuelve `[]` sin leerlo; ídem con `conversation:`.
- Entrada de índice que resuelve a `.trash` queda excluida.
- Comportamiento previo conservado: filtros `topic:`/`contact:` y búsqueda
  funcionan igual en un árbol sin papelera; errores de root/query vacía siguen
  elevando `ValueError`.

## Resultados

- Test nuevo: `9 passed`.
- Tests existentes de query/search: `frozen_query_email.py`,
  `frozen_search_email_nodes.py`, `frozen_cli_query.py`,
  `frozen_cli_search.py` → `50 passed`.
- Suite completa `outputs/email-agent-kdd/tests`: `567 passed`.

## Archivos tocados

- `src/email/query.py` (modificado)
- `src/email/search.py` (modificado)
- `outputs/email-agent-kdd/tests/frozen_trash_search_exclusion.py` (nuevo)
- `SPRINT1-SEARCH-REPORT.md` (nuevo, este informe)

Ningún otro archivo modificado.