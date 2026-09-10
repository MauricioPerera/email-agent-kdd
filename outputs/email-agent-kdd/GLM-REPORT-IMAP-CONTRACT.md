# GLM-REPORT-IMAP-CONTRACT

## Resumen
Definido el contrato CCDD para el lector IMAP de solo lectura `fetch_imap_messages` (target futuro `src/email/fetch.py`). No se creó ni modificó nada en `src/email`: el contrato exige delegar el parseo íntegro en `parse_raw_email(raw_message: bytes, account_id: str) -> dict` de `src/email/parse.py` (verificado que existe con esa firma documentada en `knowledge/contracts/parse-raw-email.md`). El test congelado usa un oráculo independiente (modelo de referencia propio en el test) con dobles de transporte: no importa `src.email`, no abre sockets, no toca disco y congela 7 casos (defaults, mailbox/limit explícitos con orden determinista, 3 rechazos de `limit`/campos con `ValueError` antes de abrir conexión, y error de transporte envuelto en `RuntimeError` sin password, con `close`/`logout` en `finally`).

## Archivos tocados
- `outputs/email-agent-kdd/knowledge/contracts/fetch-imap-messages.md` (NUEVO): frontmatter (task/intent/target/signature/budgets/deps_allowed/forbids) + las 7 secciones CCDD con `PARAR y reportar si...` en Constraints. Congela en `frozen-cases` 7 casos con passwords placeholder `frozen-*` y hosts reservados `.test`.
- `outputs/email-agent-kdd/tests/frozen_fetch_imap.py` (NUEVO): 11 tests. Congela exactamente `def fetch_imap_messages(account: dict, config: dict, connection_factory=None) -> list`.
- `outputs/email-agent-kdd/GLM-REPORT-IMAP-CONTRACT.md` (NUEVO): este reporte.

Ningún archivo existente fue modificado ni borrado. `src/` intacto.

## Verificación
- `python -m pytest tests/frozen_fetch_imap.py -q` → **11 passed in 0.22s** (ejecutado en background, sin procesos foreground).
- El test verifica: frontmatter y budgets (ciclomática ≤20, anidamiento ≤4, líneas ≤120, params ≤3); 7 secciones + frase de parada; frases obligatorias del contrato (`readonly=True`, `(RFC822)`, `finally`, `connection_factory`, `imaplib.IMAP4_SSL`, `search(None, "ALL")`, delegación en `parse_raw_email`); recomputación independiente de cada caso (defaults `INBOX`/`50`, orden ascendente de ids, secuencia fija `login→select readonly→search ALL→fetch RFC822→close→logout`, `ValueError` para `limit` fuera de 1..100 / no-int / bool / campos faltantes sin abrir conexión, `RuntimeError` con host+account_id y sin password); matriz de casos (éxito + ValueError + RuntimeError) y ausencia de credenciales/host reales.
- Primera ejecución: 10/11 (un fallo en una aserción auxiliar del propio test sobre el caso sin `email`); corregida la aserción del test, segunda ejecución 11/11.

## Estado
LISTO. Contrato congelado y test en verde; pendiente de implementación por el flujo gate (el target `src/email/fetch.py` no existe, por diseño).