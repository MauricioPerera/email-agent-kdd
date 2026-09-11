# IMPLEMENT-SOFT-DELETE-CLI-REPORT

## Resumen

Integración de la capa de borrado reversible `src/email/deletion.py` en el CLI `src/email/cli.py` mediante el subcomando `message`, con cuatro operaciones:

- `message delete ROOT REL_PATH` — mueve un nodo `.md` a `ROOT/.trash` vía `soft_delete` y devuelve su manifiesto como una sola línea JSON en stdout.
- `message restore ROOT TRASH_REL_PATH` — devuelve el elemento de `.trash` a su ubicación original vía `restore` (acepta la ruta del `.md` o la del manifiesto).
- `message trash ROOT` — lista los manifiestos vía `list_trash`, una línea JSON por elemento.
- `message purge ROOT TRASH_REL_PATH CONFIRMAR BORRADO PERMANENTE` — borrado definitivo vía `purge`, solo con la frase literal exacta (aceptada citada como un solo argumento o como tres tokens).

Comportamiento de códigos de salida:

- `0` en éxito y en `--help`.
- `2` para argumentos inválidos: subcomando desconocido bajo `message`, número de argumentos incorrecto o invocación sin subcomando (con usage a stderr).
- `1` para fallos de operación con mensaje claro a stderr, incluyendo la confirmación de `purge` inexacta o ausente: sin la frase exacta `CONFIRMAR BORRADO PERMANENTE` no se ejecuta ninguna eliminación (la capa `deletion.py` además lo garantiza).

No se modificó `deletion.py`; el CLI es una capa fina de presentación que delega en `soft_delete`, `restore`, `list_trash` y `purge`. La ayuda (`--help`/-h) muestra las cuatro líneas de `message` y `cli_main` despacha el subcomando.

## Archivos tocados

- `src/email/cli.py` — nuevo handler `_run_message` (junto a los demás handlers), constantes de usage `_MESSAGE_ACTION_USAGE`, despacho `message` en `cli_main`, líneas de `message` en la salida de `--help` y en el error de subcomando inválido, y mención de `message` en el docstring del módulo. Los imports de `deletion` ya existían.
- `README.md` — nueva sección breve "Papelera (borrado reversible)" con los cuatro comandos y la regla de confirmación.
- `IMPLEMENT-SOFT-DELETE-CLI-REPORT.md` — este reporte (nuevo).

No se tocó `src/email/deletion.py` ni el test congelado. Sin cambios de red ni secretos; sin commit.

## Pruebas

1. Test congelado de la capa: `python -m pytest outputs/email-agent-kdd/tests/frozen_message_deletion.py -q` → **14 passed**.
2. Humo manual del CLI (tempdir aislado): `--help` incluye las líneas de `message`; ciclo `delete` → `trash` → `restore` → `delete` → `purge` (frase exacta citada y en tokens separados) todos con código `0` y salida JSON de una línea; confirmación inexacta → código `1` sin tocar el disco; `message delete` con argumentos faltantes, subcomando inexistente e invocación vacía → código `2` con usage a stderr.
3. Suite completa configurada (`python -m pytest -q`, pytest.ini con `python_files = frozen_*.py`): **557 passed, 6 skipped** (mismos skips previos; sin regresiones).

## Estado

**COMPLETADO.** Las cuatro operaciones `message` funcionan sobre la capa existente sin modificarla, la confirmación exacta de `purge` está blindada en el CLI y en `deletion.py`, la ayuda refleja los comandos y toda la suite pasa.