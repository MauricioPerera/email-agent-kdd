# GLM-REPORT-SEARCH-CONTRACT

## Resumen

Definidos los artefactos KDD del contrato `search_email_nodes`: task-contract con frontmatter (budgets 20/4/80/5, `deps_allowed: [pathlib, re]`, `forbids: [eval, exec, subprocess, network_access]`) y las 7 secciones CCDD, mas el oracle congelado independiente (5 casos frozen-cases: coincidencia simple, AND de terminos, mayusculas/minusculas, solo `.md` con `.md.bak`/`.txt`/`.json` ignorados, y sin coincidencias). Contrato enlazado en `knowledge/index.md`. La implementacion (`src/email/search.py`) NO se creo: queda para el implementador. No se modifico codigo ni contratos/tests existentes.

## Archivos tocados

- `outputs/email-agent-kdd/knowledge/contracts/search-email-nodes.md` (nuevo)
- `outputs/email-agent-kdd/tests/frozen_search_email_nodes.py` (nuevo)
- `outputs/email-agent-kdd/knowledge/index.md` (linea nueva del contrato)
- `outputs/email-agent-kdd/GLM-REPORT-SEARCH-CONTRACT.md` (este reporte)

## Estado

- PASS: `python -m pytest -q outputs/email-agent-kdd/tests/frozen_search_email_nodes.py outputs/email-agent-kdd/tests/frozen_extract_contacts.py outputs/email-agent-kdd/tests/frozen_persist_email_okf.py outputs/email-agent-kdd/tests/frozen_normalize_email.py` → **20 passed** en 0.22s (7 nuevos del contrato de busqueda, 13 preexistentes).
- Pendiente: implementar `src/email/search.py` contra el contrato (no pedido en esta tarea).
- Sin procesos persistentes.