# Sprint 76 — Gate antivirus fail-closed

## Resultado

Se añadió `src/email/antivirus.py` con estados seguros y adaptador local para
ClamAV. El escaneo recibe los bytes por stdin, no crea archivos temporales y
oculta rutas, contenido y detalles del motor en los errores de usuario. Estados
ausentes, infectados, desconocidos, con timeout o con error bloquean la operación.

`attachment extract` ejecuta este gate después de verificar el hash y antes de
decodificar texto. El scanner puede inyectarse en pruebas. PDF, HTML y formatos
ofimáticos continúan bloqueados porque aún requieren sandbox, aunque el gate ya
está preparado para ellos.

## Verificación

- `python -m pytest -q` — 982 pruebas.
- `python -m compileall -q src`.
- `git diff --check`.
- pruebas offline con scanner falso, sin credenciales ni red.
