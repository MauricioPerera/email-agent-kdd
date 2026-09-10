# GLM-REPORT

## Resumen
Implementación del contrato `normalize_email` (knowledge/contracts/normalize-email.md): parseo MIME determinista con `email` (stdlib, política default), headers normalizados a diccionario, cuerpo `text/plain`, adjuntos (nombre, MIME, tamaño, bytes, SHA-256), hash SHA-256 sobre los bytes originales y `account_id` registrado. Sin red ni ejecución de contenido.

## Archivos tocados
- `src/__init__.py` (nuevo)
- `src/email/__init__.py` (nuevo)
- `src/email/normalize.py` (nuevo)

## Estado
- `pytest outputs/email-agent-kdd/tests/frozen_normalize_email.py`: 2 passed.
- No se modificó ningún documento existente.