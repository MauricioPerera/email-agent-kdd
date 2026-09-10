# Reporte GLM — send-smtp-message

## Resumen

Implementado `send_smtp_message(account, config, message, connection_factory=None) -> dict` en `src/email/smtp_send.py`, exactamente contra el contrato `knowledge/contracts/send-smtp-message.md`. Validacion completa de la entrada antes de cualquier conexion (account, config base, port 1..65535 no-bool, from_email, message con confirmacion estricta `is True`, to, subject, body), `EmailMessage` con From/To/Subject/set_content, secuencia factory->login->send_message con `quit()` en `finally`, errores de transporte envueltos en `RuntimeError` con host y account_id (sin password ni cuerpo), y recibo de claves exactas `{account_id, from_email, to, subject, sent}` con `to` copiada. Sin disco, sin logs, sin `print`, sin dependencias fuera de `smtplib`/`email`. No se modifico el contrato ni la prueba.

## Archivos tocados

- `src/email/smtp_send.py` (creado, 79 lineas, dentro de `lines_max: 80`)
- `outputs/email-agent-kdd/GLM-REPORT-SMTP.md` (creado, este reporte)

Ningun otro archivo fue creado ni modificado.

## Verificacion

- `python -m pytest -q outputs/email-agent-kdd/tests/frozen_send_smtp.py` -> **9 passed**.
- Suite completa `python -m pytest -q outputs/email-agent-kdd/tests -o python_files="frozen_*.py"` -> **93 passed**.
- Presupuestos del contrato: lineas 79 <= 80; ciclomatica maxima por funcion 16 <= 20 (medida con backend AST determinista); anidamiento <= 4; parametros del target 4 <= 4.
- Smoke test del modulo real en memoria (fabrica inyectada, sin red real): recibo exacto y JSON-serializable sin password ni cuerpo; con `confirmed` en `(None, False, 1, "true", "yes", 0, "True", [])` y con port invalidos `(70000, True, "587")` lanza `ValueError` y la fabrica nunca se invoca; con fallo en `send_message` lanza `RuntimeError` conteniendo host y account_id sin password ni cuerpo, y `quit()` corre una vez en `finally`; entrada no mutada y `to` del recibo es copia.
- Contrato y oráculo consistentes entre si; no hubo contradicciones que exigieran detenerse.

## Estado

COMPLETADO. Implementación conforme al contrato, sin red real (solo fabrica inyectada en las verificaciones), sin credenciales ni secretos impresos.