# Reporte: contrato KDD de confirmacion de borrador

## Resumen

- Definidos solo los artefactos KDD para confirmar un borrador sin enviarlo. NO se implemento la funcion ni se toco codigo o tests existentes: `src/email/confirm.py` no existe.
- Contrato `confirm_email_draft(draft: dict, confirmation: str) -> dict`: acepta solo la frase exacta `"CONFIRMAR ENVIO"` (sin strip, sin mayusculas, sin variantes), valida que `draft["status"]` sea exactamente `"pending"`, devuelve copia nueva (no muta la entrada) con `status: "confirmed"` y `confirmation_hash` determinista `sha256(draft["id"] + "|" + confirmation)` hex minuscula. Nunca red ni disco.
- Frontmatter valido: budgets `20/4/80/5`, `deps_allowed: [hashlib]`, `forbids: [eval, exec, subprocess, network_access, smtplib]`, 7 secciones CCDD (Intent, Interface, Invariants, Examples, Do / Don't, Tests, Constraints) con clausula PARAR y reportar si.
- Oracle `tests/frozen_confirm_draft.py` (9 tests, independiente del target): verifica frontmatter, 7 secciones, frase exacta y variantes rechazadas documentadas, estado `confirmed` del ejemplo frozen, no-mutacion del `draft`, y hash estable recomputando la regla `sha256` contra el `frozen-example` (id del contrato `create-draft`, hash `0a512837eab16053495647aec4f4b20125fbd92ab4e1d5e0cebd0c34d6742fc1`).
- Contrato enlazado en `knowledge/index.md`.

## Archivos tocados

- `outputs/email-agent-kdd/knowledge/contracts/confirm-draft.md` (nuevo)
- `outputs/email-agent-kdd/tests/frozen_confirm_draft.py` (nuevo)
- `outputs/email-agent-kdd/knowledge/index.md` (enlace agregado, 1 linea)
- `outputs/email-agent-kdd/GLM-REPORT-CONFIRM-CONTRACT.md` (este reporte)

## Estado

- PASS: `python -m pytest -q` sobre los 7 suites frozen → **45 passed in 0.28s** (8 nuevos de confirmacion, 37 preexistentes intactos).
- Pendiente: implementar el target `src/email/confirm.py` contra este contrato (no pedido en este paso).