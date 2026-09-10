# GLM-REPORT-CREDENTIALS

## Resumen

Implementado `resolve_credential(credential_ref, environ=None) -> str` en `src/email/credentials.py` contra el contrato `knowledge/contracts/resolve-credential.md`: acepta solo `env://NAME` con `NAME` no vacío en `[A-Za-z0-9_]+` (regex full-match), resuelve contra el mapping inyectable (`os.environ` si `environ is None`, lectura solo `.get`, sin mutar), y devuelve el valor verbatim. Referencias no-str o mal formadas (otros esquemas, nombre vacío, caracteres fuera del patrón) y valores ausentes, no-str o vacíos (incluido solo espacios) → `ValueError` con mensajes genéricos sin `NAME` ni secreto. Sin red, disco, procesos ni imports fuera de `os`/`re`.

## Archivos tocados

- `src/email/credentials.py` — creado (única implementación pedida, 36 líneas, ciclomática 5, params 2).

## Verificación

- Prueba congelada: `python -m pytest -q outputs/email-agent-kdd/tests/frozen_resolve_credential.py` → **8 passed**.
- Suite completa: `python -m pytest -q outputs/email-agent-kdd/tests -o python_files="frozen_*.py"` → **146 passed**.
- Sanity propio (script offline): verbatim (`"v  con espacios"`, `"sk-fake-123"`), rechazo de 11 referencias inválidas (`keyring://`, `file://`, `plain:`, `env://`, nombre con espacio/guion, trailing space, `ENV://`, `env//missing`, `""`, `None`, `123`), rechazo de valores `''`/`'   '`/`None`/`5`, mensajes de error sin secreto, y mapping inyectado sin mutar. → `IMPLEMENTACION OK`.

## Estado

LISTO — `credentials.py` implementado, oráculo congelado y suite completa en verde. No se modificaron contrato, tests ni otros archivos.