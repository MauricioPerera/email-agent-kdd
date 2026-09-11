# Publicación

Antes de publicar el repositorio:

1. Confirmar el propietario y la licencia.
2. Revisar que no haya datos bajo `.email-agent/`, `store/`, `drafts/` o `work/`.
3. Ejecutar `python -m pytest -q` y `python -m compileall -q src`.
4. Construir el paquete con `python -m build` en un entorno limpio.
5. Publicar un tag semántico y hashes de los artefactos.
6. Probar instalación limpia en Windows, macOS y Linux.
7. Publicar el plugin y apuntar su marketplace a la release estable.

La publicación pública del repositorio requiere una decisión explícita del propietario; este documento no la ejecuta.
