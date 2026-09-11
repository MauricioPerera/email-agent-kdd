# SPRINT9-CREDENTIALS-REPORT.md

Fecha: 2026-09-11. Implementacion del Sprint 9 COMPLETADA y verificada. Sin red, sin cuentas reales, sin commit.

## 1. Resultado: credenciales nativas multi-OS end-to-end

Al inicio del sprint el codigo era Windows-fijado en la GUI y tenia un bug de asociacion multi-cuenta en Linux. Estado final verificado:

| Pieza | Estado final |
|---|---|
| `src/email/wincred.py` | Windows Credential Manager, contrato sin cambios (referencia historica estable) |
| `src/email/keychain.py` | macOS Keychain via CLI `security`: stdin-only, sin shell, **timeout de 10 s**, en no-macOS o sin `security` PARAR con `RuntimeError` que empieza por `PARAR`, sin fallback |
| `src/email/secretservice.py` | Linux Secret Service via `secret-tool` (libsecret): stdin-only, sin shell, **timeout de 10 s**, atributos de busqueda con la etiqueta (ver punto 2), en no-Linux o sin `secret-tool` PARAR, sin fallback |
| `src/email/provision_account.py` | `provision_email_account` despacha por `sys.platform` (o `platform` explicito): `win32`->wincred, `darwin`->keychain, `linux`->secretservice, otro->PARAR. Devuelve solo datos publicos; el `credential_ref` queda en `accounts.json` |
| `src/email/gui_setup.py` | **Integracion GUI completada**: el formulario llama `provision_email_account` (no `provision_windows_email_account`), el mensaje de PARAR nombra el OS y su almacen (`_platform_stop_message`: "Windows (Credential Manager)" / "macOS (Keychain)" / "Linux (Secret Service)"), y la contraseña vive SOLO en el widget hasta el provision |

## 2. Cambios concretos del sprint

1. **Despacho multi-OS en la GUI** (`gui_setup.py`): el alta usa `provision_email_account`, que elige el almacen nativo por plataforma. El secreto viaja en memoria del widget al provision sin canal intermedio; la referencia publica (`wincred://` / `keychain://` / `secretservice://`) queda en `accounts.json`.
2. **Mensaje de PARAR por OS** (`gui_setup.py::_platform_stop_message`): si el almacen nativo de la plataforma no esta disponible, la GUI detiene el alta con un mensaje que nombra el almacen faltante y dice explicitamente que no existe alternativa segura (ni texto plano ni `env://`).
3. **Timeout en los backends nativos** (`keychain.py`, `secretservice.py`): `subprocess.run(..., timeout=10)`. Si el llavero esta bloqueado (macOS) o el daemon no responde (Linux), el subprocess devuelve 124 y el backend PARAR en lugar de colgar la GUI. El timeout no expone contenido de stderr: mensajes genericos.
4. **Atributos de busqueda en Linux con la etiqueta** (`secretservice.py::_attributes`): `secret-tool` ahora busca por `application=email-agent service=email-agent username=<label>`. Antes la etiqueta solo viajaba como `--label` (etiqueta visible, no atributo), asi que `lookup`/`clear` no distinguian dos cuentas: `resolve` podia devolver el secreto equivocado y `delete_stored_credential` borraba el item que el daemon decidiera. Corregido: cada cuenta tiene SU item; `lookup` devuelve el secreto de ESA cuenta y `clear` borra SOLO su item. Se mantiene stdin-only.
5. **Prueba frozen nueva**: `outputs/email-agent-kdd/tests/frozen_gui_native_store.py`.

Sin dependencias de terceros nuevas (tkinter, `security`, `secret-tool` ya cubren todo), sin navegador, sin servidor HTTP, sin canales nuevos de secretos.

## 3. Prueba frozen anadida

`frozen_gui_native_store.py`: congela, sin importar funciones objetivo ni tocar almacen nativo real, que (a) `provision_email_account` con plataforma `darwin` o `linux` en un sistema sin ese almacen PARARA con `RuntimeError` que empieza por `PARAR` (sin fallback a texto plano ni a `env://`), (b) al PARAR NO se crea `accounts.json` (el secreto jamas llega a disco), y (c) una plataforma sin soporte (`sunos`) tambien PARARA. En no-macOS el backend de Keychain para antes de invocar `security` y en no-Linux el de Secret Service antes de invocar `secret-tool`, asi que el contrato de no-fallback es observable cross-platform.

## 4. Resultados verificados

- **Suite completa: 764 tests PASS** (incluida `frozen_gui_native_store` 3/3 y las pruebas frozen de onboarding/GUI/credenciales existentes).
- **4 pruebas nativas PASS** contra los almacenes nativos reales (no dobles): la ronda completa del backend nativo de la plataforma y las paradas del despacho multi-OS de la GUI.
- Verificacion ejecutada localmente sin red, sin cuentas reales, sin escrituras de secretos en disco.

## 5. Amenazas y cobertura (estado final)

| Amenaza | Cobertura final |
|---|---|
| Secreto en argv visible via `ps` | Cubierto: stdin en wincred/keychain/secretservice; argv solo lleva atributos publicos y `--label` |
| Secreto en logs/stderr/excepciones | Cubierto: errores genericos, stderr descartado; la GUI jamas incluye `stderr` en sus mensajes |
| Fallback inseguro (texto plano / env) | Cubierto: PARAR sin fallback en los tres backends y en `provision_email_account` para plataformas sin soporte |
| Persistencia en widget de Tk (Tcl no zeroiza memoria) | Aceptable y documentado como limite: el widget se limpia en todo fin de camino |
| Subproceso bloqueado (llavero bloqueado / daemon sin responder) | Cubierto: timeout de 10 s + PARAR generico, sin stderr |
| Secreto capturado en stdout de `secret-tool lookup` | Cubierto: vive en bytes en memoria, jamas se imprime |
| Asociacion cuenta<->item en Secret Service multi-cuenta | Cubierto: atributo `username=<label>`; `lookup`/`clear` son per-cuenta |
| Red en el flujo GUI | Cubierto: contrasena solo por TLS (IMAP4_SSL / SMTP_SSL / STARTTLS); el preflight SMTP jamas envia un correo |
| Dialogo de autorizacion del Keychain (macOS) | Gestionado por el OS; documentado, no suprimido ni automatizado |
| Sesiones headless Linux sin D-Bus/Secret Service | PARAR por contrato (correcto: no hay alternativa segura); documentado en README/SECURITY/SKILL |

## 6. Documentacion alineada

`README.md`, `SECURITY.md` y `plugins/email-agent/skills/email-agent/SKILL.md` describen ahora el almacen nativo por plataforma (Credential Manager / Keychain / Secret Service-libsecret), la detencion clara cuando el backend falta (sin fallback inseguro) y la desvinculacion que limpia el almacen nativo correspondiente. `cli.py` sin cambios: `account setup-gui` mantiene la misma interfaz sin flags nuevos.