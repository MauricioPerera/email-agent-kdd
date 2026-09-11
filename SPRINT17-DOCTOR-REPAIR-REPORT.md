# Objetivo 17 — Reparación guiada del diagnóstico

`email-agent doctor [ROOT] --fix` amplía el diagnóstico con una lista de
acciones recomendadas para Python, pip, Tkinter y el almacén seguro nativo.

El modo es deliberadamente informativo: `repair.performed` siempre es `false`.
No instala paquetes, no cambia PATH, no modifica la configuración del sistema,
no solicita contraseñas y no ejecuta comandos sugeridos. El usuario decide si
aplica cada instrucción y después puede repetir `doctor`.
