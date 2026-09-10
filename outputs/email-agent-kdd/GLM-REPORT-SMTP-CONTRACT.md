# GLM-REPORT-SMTP-CONTRACT

## Resumen

Contrato CCDD congelado del adaptador SMTP de envio con confirmacion explicita (`send_smtp_message`) y su oracle de pruebas congelado, sin tocar `src/email`. La firma congelada es `def send_smtp_message(account: dict, config: dict, message: dict, connection_factory=None) -> dict`, target `src/email/smtp_send.py` (aun sin implementar). Reglas congeladas: `message["confirmed"] is True` por identidad (1/"true"/False/None se rechazan), validacion completa en orden fijo ANTES de abrir conexion, fabrica inyectable (por defecto `smtplib.SMTP(host, port)`), construccion de `EmailMessage` con From/To/Subject/set_content, secuencia factory->login->send_message con `quit()` en `finally`, errores de transporte como `RuntimeError` con host y account_id pero sin password ni cuerpo, recibo exacto `{account_id, from_email, to, subject, sent}` serializable a JSON, sin disco, sin logs y sin credenciales reales.

## Archivos tocados

- `outputs/email-agent-kdd/knowledge/contracts/send-smtp-message.md` (nuevo) — 7 secciones (Intent, Interface, Invariants, Examples, Do/Don't, Tests, Constraints), frontmatter lint-valido (`test_command`, budgets 20/4/80/4, deps `[smtplib, email, typing]`, forbids), 5 ejemplos resueltos y bloque `frozen-cases` con 8 casos.
- `outputs/email-agent-kdd/tests/frozen_send_smtp.py` (nuevo) — oracle independiente: 9 tests, fake SMTP (`FakeSMTPConnection` + fabrica inyectable) y modelo de referencia propio.
- `outputs/email-agent-kdd/GLM-REPORT-SMTP-CONTRACT.md` (nuevo) — este reporte.
- Ningun archivo existente fue modificado. No se creo ni modifico nada en `src/email`.

## Verificación

- `python -m pytest outputs/email-agent-kdd/tests/frozen_send_smtp.py -q` → **9 passed** (0.25 s), corrido offline: sin red, sin disco, sin procesos en foreground.
- `lint_task_contract` → `{"ok": true, "errors": 0, "warnings": 0}` (tras 1 iteracion de correccion: `test_command`, `params_max: 4` para la firma congelada de 4 params, `lines_max: 80` por el tope global, `## Examples` con >=2 ejemplos).
- Imports del test verificados por AST: `json`, `re`, `email.message`, `pathlib` — **no importa `src.email` ni `smtplib`/`socket`** (pasa con la implementacion ausente).
- Caso `missing_confirmation_no_connection` y `test_missing_confirmation_never_connects` (8 variantes de `confirmed`: None, False, 1, "true", "yes", 0, "True", []) prueban `ValueError` con `factory_calls == 0` y cero conexiones.
- `test_fake_captures_single_delivery_on_success` prueba una sola conexion, una sola entrega capturada, login una vez y `quit` una vez.

## Estado

LISTO — contrato congelado y lint verde, tests congelados en verde sin implementacion. Pendiente (no pedido): implementar `src/email/smtp_send.py` contra este contrato via `run_ephemeral_agent` y su gate.