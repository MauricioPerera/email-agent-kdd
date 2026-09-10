# Reporte: consistencia documental deps_allowed (cli-search)

## Resumen

Se actualizo `deps_allowed` en el front-matter del contrato `cli-search.md` de `[argparse]` a `[argparse, sys]`, porque `src/email/cli.py` usa `sys` para escribir en stderr. No se modifico codigo, ni tests, ni ninguna otra parte del contrato.

Consecuencia esperada y reportada: el test congelado `outputs/email-agent-kdd/tests/frozen_cli_search.py::test_contract_frontmatter_and_budgets` aserta literalmente `deps_allowed: [argparse]` (linea 48), por lo que falla con el nuevo valor. Corregir ese test requiere tocar un archivo de tests, lo cual quedo prohibido en el encargo.

## Archivos tocados

- `outputs/email-agent-kdd/knowledge/contracts/cli-search.md` — front-matter: `deps_allowed: [argparse]` -> `deps_allowed: [argparse, sys]`.
- `outputs/email-agent-kdd/GLM-REPORT-CLI-DEPS.md` — este reporte (creado).

## Estado

- Contrato actualizado: hecho.
- Pytest (5 suites congeladas): 1 failed, 28 passed. El unico fallo es `test_contract_frontmatter_and_budgets`, que sigue pinneando `deps_allowed: [argparse]`. Todas las pruebas de comportamiento del CLI, busqueda, contactos, persistencia y normalizacion pasan.
- Procesos persistentes: ninguno dejado.