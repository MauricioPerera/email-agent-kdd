# SPRINT2-REMOTE-DELETION-REPORT

Fecha: 2026-09-10 · Ámbito: Sprint 2 — borrado remoto IMAP (documentación, CLI y congelación de pruebas)

## Veredicto

LISTO. README corregido (TRASH_MAILBOX obligatorio y explícito, sin
autodetección vía LIST), asignación duplicada eliminada en `src/email/cli.py`
y `frozen_imap_deletion.py` ampliado con 5 pruebas offline fake IMAP nuevas
(11 → 16 casos). Suite completa: **629 passed, 6 skipped**.

## Resumen de cambios

### 1. README.md — contrato de TRASH_MAILBOX

La sección "Papelera remota (IMAP)" decía que el mailbox Trash/Papelera se
tomaba de `config["trash_mailbox"]` o "se detecta desde LIST". Eso no
corresponde a la implementación: ahora dice que `TRASH_MAILBOX` es un
**parámetro obligatorio y explícito** — se pasa siempre en el comando
(`remote-delete`/`remote-restore`) o como argumento directo del provider —
se valida **antes de conectar** (`str` no vacío, sin espacios en bordes, vía
`_validate_mailbox`) y **no existe autodetección vía `LIST`** ni valores
implícitos: si falta o es inválido, la operación aborta sin tocar el buzón.

### 2. src/email/cli.py — asignación duplicada

En `_run_message` había dos asignaciones consecutivas de `action = argv[1]`
(la primera en la línea 853 y una segunda idéntica en la 856, justo después
del `return _run_remote_message(...)` de los comandos remotos). Se eliminó
solo la segunda, previa verificación de que ambas líneas eran idénticas
(`    action = argv[1]`) y de que la rama remota siempre retorna. Sin cambios
de comportamiento; `ast.parse` OK.

### 3. outputs/email-agent-kdd/tests/frozen_imap_deletion.py — 5 pruebas nuevas

Todas offline: fake IMAP en memoria (`connection_factory` inyectado), sin
red, sin secretos reales, sin commit. Reutilizan `FakeIMAP`, `_provider` y
`_uid_calls` existentes; las APIs públicas (`ImapDeletionProvider`,
`soft_delete`, `restore`, `permanent_delete`, `PURGE_CONFIRMATION`) no cambian.

| # | Prueba | Qué verifica |
|---|---|---|
| 1 | `test_invalid_mailbox_fails_before_connecting` | mailbox inválido (`""`, `"  X"`, `None`, `42`) en `soft_delete` (trash), `restore` (trash y original) y `permanent_delete` aborta con `ValueError` **antes de conectar**: `fake.calls == []`. |
| 2 | `test_copy_failure_skips_store_and_logs_out` | UID COPY rechazado (`NO`) en `soft_delete` y en `restore`: **no se ejecuta UID STORE**, se eleva `RuntimeError` y la conexión se libera con `logout`. |
| 3 | `test_store_failure_after_copy_logs_out` | UID STORE rechazado después de un COPY ok (soft_delete y restore): el COPY sí ocurrió, el STORE se intentó, **nunca se llama EXPUNGE** y hay `logout`. |
| 4 | `test_unselect_absent_does_not_prevent_logout` | Fake sin atributo `unselect`: `soft_delete` completa su recibo y la liberación llega igual a `logout` (nunca `close`). |
| 5 | `test_purge_sanitizes_password_in_errors` | `permanent_delete` con UID EXPUNGE que falla mencionando la password: el error envuelto no la contiene (sale `***`), menciona cuenta/host y hace `logout`. |

## Pruebas ejecutadas

```
python -m pytest outputs/email-agent-kdd/tests/frozen_imap_deletion.py -q
# 16 passed in 0.30s   (11 previas + 5 nuevas)

python -m pytest -q
# 629 passed, 6 skipped in 2.69s
```

La suite completa (`testpaths = outputs/email-agent-kdd/tests`, archivos
`frozen_*.py`) incluye los 5 tests del CLI remoto congelados en
`frozen_cli_remote_deletion.py` (dispatch, host guardado, sin secretos en
salida) y todos los tests del Sprint 1: no rompieron con estos cambios.

## Archivos

| Archivo | Cambio |
|---|---|
| `README.md` | Contrato de `TRASH_MAILBOX` obligatorio/explícito, sin autodetección LIST. |
| `src/email/cli.py` | Eliminada la asignación duplicada `action = argv[1]` (línea 856). |
| `outputs/email-agent-kdd/tests/frozen_imap_deletion.py` | +5 pruebas fake IMAP (fallos COPY/STORE, unselect ausente, purge sanitiza password, mailbox inválido pre-conexión). |
| `SPRINT2-REMOTE-DELETION-REPORT.md` | Este reporte. |

## Restricciones respetadas

- Sin red (fakes en memoria, sin sockets), sin secretos reales, sin commit,
  sin push.
- APIs existentes intactas: `MailDeletionProvider`, `ImapDeletionProvider`,
  helpers `_validate_*`/`_wrap_error`/`_release` y los comandos CLI
  `message remote-*` conservan sus firmas y códigos (0/1/2).

## Estado

LISTO.
