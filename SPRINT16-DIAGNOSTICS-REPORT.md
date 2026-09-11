# Objetivo 16 — Diagnóstico previo a la configuración

Se agregó `email-agent doctor [ROOT]`, un comando de solo lectura que revisa
Python, pip, el sistema operativo, el almacén seguro nativo y la disponibilidad
opcional de Tkinter. No conecta con IMAP/SMTP, no lee credenciales, no escribe
archivos y no expone rutas en el resultado.

El diagnóstico devuelve JSON con `status`, checks y el siguiente paso. Si falta
Tkinter se muestra una advertencia porque el asistente de terminal sigue siendo
válido; si falta el almacén nativo o Python/pip, el estado requiere atención y
la configuración no debe continuar hasta corregirlo.
