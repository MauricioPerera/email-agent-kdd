# GLM-REPORT-IMAP

## Resumen

Implementado `src/email/imap_reader.py` conforme al contrato existente `outputs/email-agent-kdd/knowledge/contracts/fetch-imap-messages.md`. La función `fetch_imap_messages(account, config, connection_factory=None)` valida `account_id`/`email` y `host`/`username`/`password` (str no vacíos), `mailbox` opcional (default `INBOX`) y `limit` int `1..100` con `bool` rechazado, ANTES de abrir conexión. Si `connection_factory` es `None` usa `imaplib.IMAP4_SSL(host, port)`; si se inyecta, la usa para toda conexión. Secuencia fija: `login` → `select(mailbox, readonly=True)` → `search(None, "ALL")` → `fetch(id, "(RFC822)")` por cada id → `close()` → `logout()`. Los ids de `search` se ordenan ascendentemente y se trunca por `limit` después de ordenar. Cada payload crudo se parsea íntegramente con `src.email.parse.parse_raw_email(raw, account_id)` (sin reparsear headers). `close`/`logout` corren en `finally` (independientes entre sí: si uno falla, el otro igual corre). Todo error de transporte se relanza como `RuntimeError` con `host` + `account_id` y la password se reemplaza por `***` si apareciera en el mensaje original. Solo stdlib; sin disco, sin red fuera de la fábrica, sin loguear secretos, sin enviar correo.

Nota de discrepancia menor (informativa, no bloqueante): el frontmatter del contrato declara `target: src/email/fetch.py`, mientras la tarea pide crear `src/email/imap_reader.py`. No toqué el contrato ni la prueba; el oráculo congelado no importa el target (no depende de la ruta), así que implementé en la ruta pedida.

## Archivos tocados

- `src/email/imap_reader.py` (creado, único archivo de código)
- `outputs/email-agent-kdd/GLM-REPORT-IMAP.md` (creado, este reporte)

## Verificación

- `python -m pytest -q outputs/email-agent-kdd/tests/frozen_fetch_imap.py` → **11 passed**.
- `python -m pytest -q outputs/email-agent-kdd/tests -o python_files="frozen_*.py"` → **84 passed** (suite completa, 0 fallos).
- Sanity check adicional con doble inyectado (sin red, sin disco): búsqueda `[2, 1, 3]` → registros en orden `[1, 2, 3]`; `select` recibido con `readonly=True`; secuencia observada `login, select, search, fetch(1..3), close, logout`; `account` sin `email` y `limit: True` → `ValueError` sin abrir conexión (0 llamadas a la fábrica); `fetch` del id 2 → `RuntimeError` con host y account_id, sin la password (verificado por búsqueda de substring), y `close`/`logout` ejecutados igualmente.

## Estado

LISTO. Ambas órdenes de prueba en verde y comportamiento confirmado con dobles inyectados. Ninguna contradicción del oráculo con el contrato que impida avanzar (solo la diferencia de ruta `target` señalada arriba, sin efecto en las pruebas congeladas).