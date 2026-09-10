# Reporte: Oracle CLI deps congelado

## Resumen

El oracle congelado `tests/frozen_cli_search.py` declaraba `deps_allowed: [argparse]`, pero el contrato actual `knowledge/contracts/cli-search.md` ya permite `argparse` y `sys`. Se actualizó únicamente la aserción literal del frontmatter para reflejar el contrato vigente. No se tocó código de producción ni contratos.

## Archivos tocados

- `outputs/email-agent-kdd/tests/frozen_cli_search.py` — aserción en `test_contract_frontmatter_and_budgets`: `deps_allowed: [argparse]` → `deps_allowed: [argparse, sys]`.
- `outputs/email-agent-kdd/GLM-REPORT-CLI-DEPS-ORACLE.md` — este reporte (creado).

## Estado

- Tests: `python -m pytest -q` sobre los 5 orácones congelados (cli_search, search_email_nodes, extract_contacts, persist_email_okf, normalize_email) → **29 passed in 0.30s**.
- Sin procesos persistentes.