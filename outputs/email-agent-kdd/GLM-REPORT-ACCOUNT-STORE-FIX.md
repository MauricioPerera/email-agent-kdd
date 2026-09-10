# GLM-REPORT-ACCOUNT-STORE-FIX

## Resumen
Fallo real detectado por la prueba congelada: `src/email/account_store.py` escribía el JSON con `write_text(payload + "\n", encoding="utf-8")`, que en Windows abre el archivo en modo texto y traduce `\n` a `\r\n` (CRLF), rompiendo los bytes deterministas exigidos por el contrato (`frozen-example` + LF). Corregido: la escritura atómica ahora usa bytes UTF-8 explícitos (`write_bytes((payload + "\n").encode("utf-8"))`), sin traducción de fin de línea en ninguna plataforma. No se tocó el contrato ni las pruebas.

## Archivos tocados
- `src/email/account_store.py` (1 línea, dentro de `save_email_account`)

## Verificación
- `python -m pytest -q outputs/email-agent-kdd/tests/frozen_store_email_account.py` → **20 passed** (incluye `test_save_writes_frozen_example_bytes`, que compara `read_bytes()` contra `expected.encode("utf-8")`).
- Suite completa: `python -m pytest -q outputs/email-agent-kdd/tests -o python_files="frozen_*.py"` → **113 passed**.
- Sin red, sin procesos foreground, sin secretos.

## Estado
LISTO — prueba congelada y suite completa en verde en Windows.