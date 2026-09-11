# Seguridad y privacidad

- Las credenciales se resuelven en memoria y no deben aparecer en logs, commits, nodos OKF ni mensajes del agente.
- El formulario local debe guardar contraseñas únicamente en el almacén seguro disponible del sistema operativo.
- IMAP se abre en modo de solo lectura y el cursor evita duplicados.
- El envío es una operación externa y requiere la frase exacta `CONFIRMAR ENVIO`.
- Un resultado SMTP incierto no se reintenta automáticamente.
- Las notificaciones se evalúan localmente y se deduplican por hash del mensaje.
- Reporta vulnerabilidades sin incluir contraseñas, tokens, archivos de correo o datos personales.
