# GLM-REPORT-CREDENTIALS-CONTRACT

## Resumen

Contrato CCDD y oracle para `resolve_credential(credential_ref: str, environ=None) -> str`: resuelve solo referencias `env://NAME` (NAME no vacio, `[A-Za-z0-9_]+`), lee del mapping `environ` inyectable (fallback `os.environ` si `None`), devuelve el secreto verbatim solo en memoria y rechaza referencias invalidas o variables ausentes/vacias con `ValueError` sin filtrar el secreto. SOLO contrato y oracle: NO se implemento el target ni se toco `src`.

## Archivos tocados

- `outputs/email-agent-kdd/knowledge/contracts/resolve-credential.md` (NUEVO): frontmatter CCDD (task, intent, target `src/email/credentials.py`, signature, budget, test_command, tests, deps_allowed `[os, re]`, forbids) + 7 secciones (Intent, Interface, Invariants, Examples, Do / Don't, Tests, Constraints) con regla literal `PARAR y reportar si...` en Constraints. Ejemplo frozen en `frozen-inputs` con marcador ficticio `env://TEST_EMAIL_AGENT_API_KEY` / `sk-fake-123`.
- `outputs/email-agent-kdd/tests/frozen_resolve_credential.py` (NUEVO): oracle independiente. NO importa `src.email` ni `credentials.py`; el target aun no existe. Verifica estructura del contrato (frontmatter, 7 secciones, firma, `PARAR y reportar si`, deps/forbids), el bloque `frozen-inputs`, y ejercita un modelo de referencia local con las reglas exactas del contrato: resolucion verbatim con mapping inyectado, rechazo `ValueError` de otros esquemas (`keyring://`, `file://`, `plain:`), nombre vacio/malformado, variables ausentes, valores vacios/no-str, mapping no mutado, `os.environ` sin el marcador ficticio, mensajes de error sin el secreto y sin canales de escape (print/open/write/system/Popen/socket/dump). Todo offline, sin red ni credenciales reales.

## Verificación

- `lint_task_contract` (ccdd-complexity): `{"ok": true, "errors": 0}` con 1 warning no bloqueante (`tc-no-algorithm`, la regla de referencia `env://NAME` es del QUÉ). El lint exigió añadir `test_command`, incorporado al frontmatter.
- `python -m pytest tests/frozen_resolve_credential.py -q` → `8 passed in 0.37s` (solo este archivo).
- Verificado que no se modifico `src/` ni archivos existentes: solo los 2 archivos nuevos y el reporte.

## Estado

LISTO. Contrato lintado (`ok: true`) y oracle pasando (8/8). Pendiente para el siguiente paso: crear stub de `src/email/credentials.py` y delegar la implementacion via `run_ephemeral_agent` contra `run_task_gate` + `mutation_audit`.