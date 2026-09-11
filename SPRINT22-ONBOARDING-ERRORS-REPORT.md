# Objetivo 22 — Errores y cancelación del onboarding

`onboard` ahora distingue el flujo de requisitos pendientes del flujo de
configuración cancelado o incompleto. Cuando no puede continuar devuelve un
recibo JSON sin datos sensibles y recomienda `email-agent doctor --fix`.

Si el usuario cancela el formulario o el asistente falla, el CLI muestra un
mensaje claro y permite volver a ejecutar `email-agent onboard ROOT`. No intenta
repetir la operación, no confirma por el usuario y no deja una contraseña en
salida o archivos temporales.
