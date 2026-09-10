# GLM-REPORT-CLI-MODULE

## Resumen
Punto de entrada de módulo para `python -m src.email`. Se creó `src/email/__main__.py` con el mínimo requerido: importa `cli_main` de `src.email.cli` y ejecuta `sys.exit(cli_main(sys.argv[1:]))`. Cero lógica duplicada; ni `cli.py` ni contratos ni pruebas fueron tocados.

## Archivos tocados
- `src/email/__main__.py` — creado (delega en `cli_main` y propaga su exit code).
- `outputs/email-agent-kdd/GLM-REPORT-CLI-MODULE.md` — este reporte.

## Verificación
- `python -m src.email --help` → usage correcto, exit 0.
- `python -m src.email` → error de subcomando por stderr, exit 2.
- `python -m src.email search outputs "cli_main"` → lista nodos .md, exit 0.
- Suite congelada: `python -m pytest -q outputs/email-agent-kdd/tests/*.py` → **45 passed** (los 7 oráculos: cli_search, search_email_nodes, extract_contacts, persist_email_okf, normalize_email, create_draft, confirm_draft).

## Estado
LISTO. Nota fuera de alcance (no arreglada): los archivos de pruebas se llaman `frozen_*.py`, así que `pytest` con su patrón por defecto (`test_*.py`) al apuntar a la carpeta reporta "no tests ran"; funciona con paths explícitos (`tests/*.py`) o `-o python_files="frozen_*.py"`. Añadir un `pytest.ini` con `python_files = frozen_*.py` lo resolvería, pero queda fuera de esta tarea.