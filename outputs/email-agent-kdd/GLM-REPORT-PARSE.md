# GLM-REPORT-PARSE

## Resumen

Implementado el parseo determinista de mensajes RFC 5322 crudos a registro serializable OKF: task-contract con las 7 secciones CCDD (frontmatter `budget` 8/3/100/2, `deps_allowed: [email, hashlib]`, `forbids: [eval, exec, subprocess, network_access, filesystem_write]`), oracle congelado independiente (12 casos: validación de tipos, registro completo con igualdad exacta, determinismo, multipart con preferencia text/plain sobre text/html, fallback HTML, adjuntos como metadatos sin bytes, headers de threading, charset latin-1, bytes inválidos con U+FFFD, headers ausentes serializables) e implementación `src/email/parse.py` con stdlib puro (`email`, `hashlib`), sin red, disco ni logs. No se modificó ningún archivo existente (incluido `knowledge/index.md`, pendiente de línea por la regla de no tocar existentes).

## Archivos tocados

- `outputs/email-agent-kdd/knowledge/contracts/parse-raw-email.md` (nuevo)
- `outputs/email-agent-kdd/tests/frozen_parse_raw_email.py` (nuevo)
- `src/email/parse.py` (nuevo)
- `outputs/email-agent-kdd/GLM-REPORT-PARSE.md` (este reporte)

## Verificación

- Comando: `python -m pytest -q outputs/email-agent-kdd/tests -o python_files="frozen_*.py"` → **73 passed** en 0.32s (12 nuevos de `frozen_parse_raw_email.py`, 61 preexistentes intactos).
- Oráculo corregido tras primera corrida (2 fallos eran errores del oráculo, no del target): weekday real del 10-Sep-2026 es `Thu` (normalizado por `policy.default`) y la newline previa al boundary MIME pertenece al delimitador (RFC 2046), cuerpo `"Cuerpo en texto."`.
- Registro de salida serializable verificado con `json.dumps` en el caso de headers ausentes; `attachments` sin clave `content` (solo `{filename, content_type, size, sha256}`).

## Estado

- DONE: contrato, oracle congelado e implementación verificados end-to-end.
- Pendiente (no pedido): agregar línea del contrato `parse-raw-email.md` en `knowledge/index.md`.
- Sin procesos persistentes, sin red, sin descargas.