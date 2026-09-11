# Email Agent

CLI local y orientada a agentes para sincronizar correo por IMAP, guardar conocimiento en Markdown OKF, buscar por conversación, contacto, temática y destinatario real, y enviar únicamente después de una confirmación explícita.

## Instalación rápida

Requiere Python 3.10 o superior.

```text
python -m pip install .
email-agent --help
```

Para una instalación aislada se recomienda `pipx install .`. En Windows, macOS y Linux también están disponibles los scripts de instalación de `installers/`.

## Primer uso

Ejecuta `email-agent account setup-gui .` y completa el formulario local. La contraseña se guarda en el almacén seguro del sistema cuando está disponible; nunca se guarda en el repositorio ni se envía al agente.

La sincronización manual usa páginas y cursor:

```text
email-agent sync . CUENTA --limit 50
email-agent sync . CUENTA --unread
```

Para revisar periódicamente:

```text
email-agent watch . CUENTA --every 300 --limit 50
```

## Búsqueda y notificaciones

`query . "para:ventas+cliente@dominio.com"` filtra por la dirección real de entrega. Las reglas locales se crean con `notification add . NOMBRE "para:direccion@dominio.com"`.

## Gestión de cuentas

El alta puede hacerse con el formulario local `email-agent account setup-gui ROOT` o con el asistente de terminal `email-agent account setup ROOT`. Las cuentas vinculadas se consultan con `email-agent account list ROOT`.

El formulario valida los campos y comprueba autenticación IMAP y SMTP antes de guardar. La prueba SMTP solo autentica la cuenta: nunca envía un correo.

Para desvincular una cuenta se requiere una confirmación literal e independiente:

```bash
email-agent account remove ROOT ACCOUNT_ID CONFIRMAR DESVINCULAR
```

La desvinculación elimina la referencia de cuenta, la configuración pública de servidores y el secreto almacenado en Windows Credential Manager; no elimina los correos ya descargados. Un agente puede asistir al usuario, pero nunca debe completar esa confirmación por su cuenta.

## Envío

Los mensajes se preparan con `draft`. El comando `send` exige exactamente `CONFIRMAR ENVIO`; un agente nunca debe saltarse esa confirmación ni reintentar un resultado SMTP incierto.

## Inicio automatico, plataformas y privacidad

El núcleo es multiplataforma. Para reanudar la descarga tras reiniciar el equipo, el CLI incluye adaptadores para Windows Task Scheduler, macOS LaunchAgents y servicios systemd de usuario en Linux:

```bash
email-agent startup status ROOT ACCOUNT_ID
email-agent startup install ROOT ACCOUNT_ID --every 300 --limit 50
email-agent startup remove ROOT ACCOUNT_ID
```

`startup install` modifica la configuración de inicio del sistema y requiere confirmación directa del usuario. El contenido se procesa localmente y los adjuntos se conservan como metadatos hasta que el usuario solicite extracción.

Consulta [SECURITY.md](SECURITY.md) y [docs/RELEASE.md](docs/RELEASE.md) antes de publicar una release.
