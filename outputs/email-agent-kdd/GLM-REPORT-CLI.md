# GLM-REPORT-CLI

## Resumen

Implementado el contrato `cli-search.md`: `src/email/cli.py` con `cli_main(argv: list) -> int`, capa fina de presentacion sobre `src.email.search.search_email_nodes` (sin reimplementar la busqueda). Soporta `--help`/`-h` (usage en stdout, retorno `0`), `search ROOT QUERY` (resultados en stdout, una ruta por linea, en el orden devuelto, retorno `0` incluso sin coincidencias), errores de argumentos (argv vacio, subcomando desconocido, aridad incorrecta) con mensaje amigable + usage en stderr y retorno `2`, y fallos de la busqueda (excepcion de `search_email_nodes`) con mensaje amigable en stderr y retorno `1`, sin tracebacks. Sin `subprocess`, red ni `eval`/`exec`; solo `argparse` + `sys` (stdlib) y el import local de `src.email.search`. Verificado ademas fuera de los tests congelados con un smoke-test end-to-end contra la busqueda real: codigos `0`/`2`/`1` y separacion stdout/stderr correctos.

## Archivos tocados

- `src/email/cli.py` (creado)
- `outputs/email-agent-kdd/GLM-REPORT-CLI.md` (creado)

Contratos y tests: sin modificaciones.

## Estado

- `python -m pytest -q` sobre los 5 archivos congelados solicitados: **29 passed**.
  (`frozen_cli_search.py`, `frozen_search_email_nodes.py`, `frozen_extract_contacts.py`, `frozen_persist_email_okf.py`, `frozen_normalize_email.py`).
- Sin procesos persistentes dejados.