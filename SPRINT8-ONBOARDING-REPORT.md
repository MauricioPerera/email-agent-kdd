# Sprint 8 — Onboarding (setup CLI, setup GUI, comprobación de conexión)

Alcance: completar la auditoría/corrección del onboarding offline partiendo de los tres artefactos
parciales (`frozen_onboarding_cli_setup.py`, `frozen_onboarding_connection_check.py`,
`frozen_onboarding_gui_secrets.py`). Todo verificado sin red real, sin cuentas reales, sin secretos,
sin commit/push/publicación. Las tres pruebas frozen NO se borraron.

## Cambios en código

- `src/email/cli.py`: se añadió `from builtins import input` al bloque de imports. El asistente
  `account setup` usaba el builtin `input()` y el test frozen parchea `cli.input`; sin el enlace a
  nivel de módulo el parcheo fallaba con `AttributeError`. Sin cambio de comportamiento.

## Cambios en documentación

- `README.md`: (1) se eliminó la línea duplicada «La sincronización manual usa páginas y cursor:»;
  (2) se corrigió la afirmación «la contraseña se guarda en el almacén seguro del sistema cuando
  está disponible» — implicaba un respaldo menos seguro que no existe — por la conducta real:
  solo Windows Credential Manager, PARAR si no está disponible, sin alternativa insegura; (3) se
  documentó que el asistente de terminal funciona igual en los tres sistemas y que en macOS/Linux
  es la vía recomendada; (4) se documentó la preflight IMAP/SMTP que nunca envía correo.
- `SECURITY.md`: la promesa genérica «almacén seguro disponible del sistema operativo» se concretó
  al almacén real (Windows Credential Manager) con PARAR explícito y sin respaldo en texto plano.
- `plugins/email-agent/skills/email-agent/SKILL.md`: se documentó la división por plataforma del
  alta (GUI = Credential Manager de Windows, con PARAR si falta; terminal = referencia `env://`
  portable), manteniendo intacta la garantía de no-filtración de secretos.
- `installers/install.ps1` e `installers/install.sh`: auditados sin corrección necesaria — no
  piden ni imprimen secretos, comprueban `email-agent --help` antes de declarar éxito y apuntan a
  las dos vías de alta (`account setup-gui` / `account setup`).

## Correcciones en los artefactos frozen (andamiaje, no oráculo)

Tres casos no podían pasar con NINGUNA implementación; se corrigió el andamiaje del test
conservando todas las aserciones de comportamiento:

1. `frozen_onboarding_cli_setup.py` — éxito: la aserción `"GMAIL_APP_PASSWORD" not in out`
   se contradecía con la obligación de imprimir el prompt 4, cuyo ejemplo ES esa cadena. El
   oráculo real (la referencia `env://` jamás en stdout) ya estaba cubierto; se sustituyó por
   `out.count("GMAIL_APP_PASSWORD") == 1` (solo puede aparecer en el ejemplo del prompt). El
   texto del prompt no se tocó porque lo congela `frozen_cli_account_setup.py:245`.
2. `frozen_onboarding_cli_setup.py` — store corrupto: el ayudante `_run` hacía `json.loads` del
   store que el propio test había escrito corrupto. Se protegió con `try/except ValueError`
   (las aserciones del caso no leen el store).
3. `frozen_onboarding_connection_check.py` — elección de fábrica por puerto: en el caso 587 faltaba
   en la lista esperada la conexión IMAP del stub (sigue parcheado en la prueba y se construye de
   nuevo). Se añadió la entrada; la garantía oráculo (465 → SMTP_SSL, 587 → STARTTLS) no cambia.
4. `frozen_onboarding_gui_secrets.py` — ayudante `_form`: inyectaba `form.provision` y `form.store`
  pero olvidaba `form.discovery`, que tres casos leen para contar llamadas. Se asigna en la rama
   de inyección; el oráculo no cambia.

## Resultados

- Tres pruebas frozen de onboarding: **37 passed** (`frozen_onboarding_cli_setup.py` 10,
  `frozen_onboarding_connection_check.py` 6, `frozen_onboarding_gui_secrets.py` 21).
- Suite completa del repo: **761 passed, 0 failed** (`python -m pytest -q`, ~4 s, offline).

## Limitaciones multiplataforma

- **GUI (`account setup-gui`)**: el secreto solo se persiste en Windows Credential Manager
  (`store_windows_credential` vía `provision_account.py`). En macOS/Linux el formulario abre
  (tkinter está disponible) pero el provisionamiento termina en PARAR: mensaje de advertencia,
  código `1`, cero escrituras y sin respaldo inseguro. En esos sistemas la vía soportada es
  `account setup` (referencia `env://NOMBRE`).
- **Preflight de conexión**: usa `IMAP4_SSL` para IMAP y, para SMTP, `SMTP_SSL` con puerto 465 o
  `SMTP` + `STARTTLS` con 587; otros puertos usan la ruta no-SSL explícita. La verificación solo
  autentica (IMAP readonly sobre INBOX, SMTP sin mensaje) y jamás envía correo.
- **Instaladores**: `install.ps1` (Windows) y `install.sh` (macOS/Linux) son equivalentes en
  contenido y validación; ninguno acepta ni muestra secretos.
- **Verificación offline de la GUI**: ejercitada con widgets falsos en memoria (sin abrir ventanas
  ni tkinter real); el arranque real de `mainloop` no se automatiza en este sprint.