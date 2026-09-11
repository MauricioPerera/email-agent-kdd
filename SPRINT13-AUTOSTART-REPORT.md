# Sprint 13 — Autostart: serialización segura (Windows/macOS/Linux)

Alcance: auditoría y endurecimiento de `src/email/autostart.py` (serialización segura de la
línea de comandos en los tres formatos de inicio automático), pruebas frozen offline y
actualización de documentación. Sin red, sin cuentas reales, sin commit/push.

## Hallazgos de la auditoría

| # | Plataforma | Hallazgo | Riesgo |
|---|-----------|----------|--------|
| 1 | Windows | El valor de `/TR` se pasaba a `schtasks` sin tratar la raíz que termina en separador: una ruta con espacios y contrabarra final produce `"C:\dir bar\"` y la contrabarra antes de la comilla de cierre se lee como comilla escapada, partiendo el comando almacenado. | Comando corrupto / separación de argumentos |
| 2 | macOS | Los valores del plist se interpolaban en XML con `%s` sin escape: `<`, `&`, comillas o un payload como `</string><string>rm -rf ~</string><key>X</key>` rompían el XML o inyectaban nodos. | Inyección XML / plist corrupto |
| 3 | Linux | El escapado de `ExecStart` era `'"%s"' % value.replace('"', '\\"')`: la contrabarra no se escapaba (una ruta con `\` alteraba el parsing), `%` no se doblaba (un `%h`/`%U` de la ruta se expandía como especificador de systemd) y no había defensa contra saltos de línea en la unidad. | Escapado incorrecto / expansión de especificadores / inyección de directivas |
| 4 | Común | Ninguna validación rechazaba caracteres de control en la raíz (salto de línea, tabulador, NUL, DEL) antes de escribir archivos o invocar `schtasks`. | Inyección de líneas nuevas en unit/plist |

## Cambios en `src/email/autostart.py`

- `_clean_root`: valida tipo/no vacío, rechaza caracteres de control (`[\x00-\x1f\x7f]`) y normaliza con `os.path.abspath` (comportamiento previo preservado).
- Windows: `_windows_watch_root` quita la contrabarra final de la raíz (la raíz de unidad, p. ej. `C:\`, se conserva intacta porque `list2cmdline` nunca la cita) antes de construir `/TR` con `subprocess.list2cmdline`. El comando se pasa como lista a `subprocess.run`: sin shell.
- macOS: `_launchd_plist` escribe un plist estándar (`<?xml … encoding="UTF-8"?>` + DOCTYPE) con todo valor escapado vía `xml.sax.saxutils.escape` (Label y ProgramArguments). Markup en la ruta queda como texto y no puede crear claves ni nodos.
- Linux: `_systemd_quote`/`_systemd_exec_start` citan cada argumento con el escapado de systemd: `\\`, `\"` y `%%` (neutraliza especificadores). Un salto de línea en la raíz es rechazado por `_clean_root`, así que no puede inyectar directivas.
- Validaciones intactas: `account_id` (`^[A-Za-z0-9_.-]{1,64}$`), `interval >= 30`, `1 <= limit <= 100`, booleanos excluidos; `startup status/install/remove` conservan firmas, rutas (`~/Library/LaunchAgents/EmailAgent-<id>.plist`, `~/.config/systemd/user/EmailAgent-<id>.service`), valores por defecto (`--every 300 --limit 50`), `--unread`, retornos y el carácter best-effort de `startup remove` en Windows.
- `_validate_account_id` reutilizado por las tres funciones (sin duplicación).

## Pruebas frozen (offline, con stubs)

`outputs/email-agent-kdd/tests/frozen_autostart.py` — 75 pruebas, todas offline: el único punto de inyección es `subprocess.run` (stub que registra argv) y `platform.system`; `Path.home` apunta a `tmp_path`; el plist se re-parsea con `xml.etree.ElementTree` y `ExecStart` se re-parsea con un mini-parser del escapado de systemd.

Cobertura: valor de `/TR` con espacios/comillas/Unicode/`%`/backslash; contrabarra final nunca antes de comilla de cierre; raíz de unidad intacta; `--unread` y `--every/--limit` custom; payload XML (`</string>…<key>X</key>`) no rompe el plist ni agrega claves (solo `Label`, `ProgramArguments`, `RunAtLoad`); round-trip de `ExecStart` con `\\`, `\"`, `%%`; caracteres de control rechazados en las tres plataformas sin escribir archivos ni llamar a `schtasks`; `account_id`/`interval`/`limit`/`root` inválidos; fallos (`CalledProcessError` propagado, status por returncode, remove best-effort, remove por presencia de archivo); preservación (nombres de tarea, rutas, defaults, UTF-8).

## Verificación

- `python -m pytest outputs/email-agent-kdd/tests/frozen_autostart.py -q` → **75 passed**.
- `python -m compileall -q src/email` → OK.
- `python -m pytest -q` (suite completa) → **905 passed**.
- Smoke real del CLI: `startup status . TESTACC123` → `{"enabled": false}` (exit 0, consulta local de `schtasks`); `startup install /tmp/x "bad id"` → error genérico y exit 1.

## Documentación

- `README.md`: sección de inicio automático describe la serialización segura de los tres formatos y el rechazo de caracteres de control.
- `SECURITY.md`: nueva viñeta con la garantía (sin shell, sin interpolación sin escape, rechazo de control antes de escribir).
- `plugins/email-agent/skills/email-agent/SKILL.md`: nota de comportamiento defensivo de la serialización para el agente.

## Sin cambios (firma y comportamiento)

Firmas públicas (`startup_status`, `install_startup`, `remove_startup`), nombres de tarea
`EmailAgent-<account_id>`, rutas por plataforma, defaults, flags, códigos de retorno del CLI y
`_run_startup` en `cli.py` no se tocaron.