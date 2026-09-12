# Sprint 77 — Worker aislado para extracción PDF

> Corrección de auditoría (Sprint 78): el worker de este sprint era un subproceso,
> no un aislamiento de seguridad. La ausencia de llamadas de red en su código
> no bloqueaba red ni acceso a archivos ante un parser comprometido. Las garantías
> y restricciones nuevas se documentan en SPRINT78-AUDIT-REMEDIATION-REPORT.md.
> El resultado histórico siguiente no debe interpretarse como prueba de sandbox.

## Resultado

`attachment extract` admite PDF almacenados después del gate antivirus. El
contenido se entrega por stdin a `src.email.pdf_worker`, que usa `pypdf` sin red
ni archivos temporales. Se aplican límites de 25 MiB de entrada, 100 páginas,
4 MiB de salida y 15 segundos de ejecución. PDF cifrados, corruptos o fuera de
límite se rechazan con mensajes genéricos.

El resultado se escribe atómicamente y la operación no modifica el nodo OKF ni
el correo remoto. HTML y ofimática continúan fuera de alcance.

## Verificación

- `python -m pytest -q` — 983 pruebas.
- `python -m compileall -q src`.
- `git diff --check`.
- PDFs sintéticos válidos y malformados, sin credenciales ni red.
