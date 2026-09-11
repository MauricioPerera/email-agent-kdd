# Matriz de plataformas e instalación

Email Agent requiere Python 3.10 o superior. La CLI, la sincronización local,
la búsqueda OKF y el modo terminal siguen el mismo contrato en Windows, macOS
y Linux.

| Capacidad | Windows | macOS | Linux |
| --- | --- | --- | --- |
| Instalador | `install.ps1` | `install.sh` | `install.sh` |
| Almacén seguro | Credential Manager | Keychain mediante `security` | Secret Service mediante `secret-tool` |
| Formulario `setup-gui` | Tkinter | Tkinter | Tkinter |
| Asistente terminal | Sí | Sí | Sí |
| Inicio automático | Task Scheduler | LaunchAgent | systemd de usuario |
| Notificaciones | PowerShell nativo | `osascript` | `notify-send` |
| Requisito especial | Python en PATH | Python y Keychain disponible | Python, `secret-tool` y sesión Secret Service |

## Instalación para una persona no técnica

1. Instala Python 3.10+ y activa la opción de agregarlo al PATH.
2. Ejecuta el instalador correspondiente:

   ```text
   powershell -File installers\install.ps1   # Windows
   sh installers/install.sh                  # macOS o Linux
   ```

3. Cierra y vuelve a abrir la terminal si aparece “comando no encontrado”. El
   instalador no pide contraseñas de correo.
4. Abre el formulario local con `email-agent account setup-gui .`.

Si no hay escritorio o Tkinter, usa `email-agent account setup .`; mantiene
las mismas reglas de seguridad en terminal.

## Almacén seguro no disponible

El sistema se detiene y explica qué componente falta. No usa archivos de texto,
variables de entorno ni una alternativa insegura para guardar la contraseña.
Una plataforma no listada debe detenerse sin fallback y reportar el bloqueo.
