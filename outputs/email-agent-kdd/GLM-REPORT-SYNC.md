# GLM-REPORT-SYNC

## Resumen
Implementado `sync_email_account(account, fetch_messages, persist_message, update_contacts=None)` en `src/email/sync.py` conforme al contrato `knowledge/contracts/sync-email-account.md`: validacion de `account_id` y callables ANTES de cualquier llamada externa (fetch recibe 0 llamadas en error de validacion), `fetch_messages(account)` exactamente una vez, verificacion de lista de dicts antes de persistir, persistencia una vez por mensaje en orden (`persisted_paths` en ese orden), `update_contacts` llamada exactamente una vez con copia (`list(messages)`) despues de persistir todo, y retorno con exactamente las 5 claves (`account_id`, `fetched`, `persisted`, `persisted_paths`, `contacts_updated`). Toda falla (validacion, fetch no-lista/no-dict, o excepcion de `fetch_messages`/`persist_message`/`update_contacts`) se relanza como `RuntimeError` generico con `account_id` y etapa, sin cuerpos, secretos ni detalle de la excepcion original (encadenamiento suprimido via `from None` implicito del mensaje). No muta `account` ni la lista de mensajes; sin red, disco, subprocess ni print. Deps: solo stdlib (`typing`).

## Archivos tocados
- `src/email/sync.py` (implementacion, 60 lineas, unica modificacion de codigo)
- `outputs/email-agent-kdd/GLM-REPORT-SYNC.md` (este reporte)
- Sin cambios en el contrato ni en los tests congelados.

## Verificacion
- `python -m pytest -q outputs/email-agent-kdd/tests/frozen_sync_email_account.py -o python_files="frozen_*.py"` -> **9 passed** (0.26s)
- `python -m pytest -q outputs/email-agent-kdd/tests -o python_files="frozen_*.py"` -> **136 passed** (0.45s), 0 fallos
- Smoke manual (offline, dobles inyectados): happy path 2 mensajes (orden `uno`, `dos`; contacts 1 vez con copia, `contacts_updated=True`), `{"email":...}` sin `account_id` -> `RuntimeError` y 0 llamadas a fetch, `persist_message`/`update_contacts` lanzando excepcion -> `RuntimeError` sin filtrar el mensaje original, receptor de contacts puede mutar la copia sin afectar el estado interno.
- Presupuestos del contrato: lineas 60 <= 80, params 4 <= 5, ciclomatica y anidamiento holgados.

## Estado
COMPLETADO. Contrato implementado en el target unico, suite completa verde (136/136), reporte actualizado.