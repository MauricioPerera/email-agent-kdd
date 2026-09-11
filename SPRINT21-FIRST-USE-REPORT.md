# Objetivo 21 — Primer uso simplificado

Se agregó `email-agent onboard ROOT`. El comando ejecuta el diagnóstico local y
elige el flujo adecuado: abre el formulario gráfico si Tkinter está disponible
o usa el asistente de terminal cuando no hay GUI.

Si falta un requisito obligatorio, informa el problema y no inicia la
configuración. No omite validaciones, no proporciona confirmaciones y no
manipula credenciales automáticamente.
