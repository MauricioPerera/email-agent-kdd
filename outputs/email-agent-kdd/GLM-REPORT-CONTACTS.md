# GLM Report — extract_contacts

## Resumen

Implementado el contrato `knowledge/contracts/extract-contacts.md`: `extract_contacts(record: dict) -> list` extrae los contactos de los headers `from`, `to` y `cc` usando `email.utils.getaddresses`, en ese orden y con el orden interno de cada header. El email se normaliza a minúsculas antes de deduplicar (primera aparición gana su `name`), los headers ausentes o vacíos aportan contactos sin lanzar error, y la función es pura (no modifica el registro, no evalúa contenido del header, no toca la red). Presupuestos del contrato respetados (≤80 líneas, ≤5 parámetros por función, sin dependencias fuera de `deps_allowed` ni `forbids`).

## Archivos tocados

- Creado: `src/email/contacts.py` (implementación de `extract_contacts` + helper `_new_contacts`).
- Creado: `outputs/email-agent-kdd/GLM-REPORT-CONTACTS.md` (este reporte).
- No se modificaron contratos ni tests existentes.

## Estado

- PASS: `python -m pytest -q outputs/email-agent-kdd/tests/frozen_extract_contacts.py outputs/email-agent-kdd/tests/frozen_persist_email_okf.py outputs/email-agent-kdd/tests/frozen_normalize_email.py` → **13 passed** en 0.26s.
- Verificación adicional: `extract_contacts` reproduce los 4 casos congelados del contrato (`from_to_cc`, `dedup_by_lowercase_email`, `missing_cc_header`, `empty_headers`) exactamente.
- Sin procesos persistentes; el script de verificación fue efímero y se eliminó.