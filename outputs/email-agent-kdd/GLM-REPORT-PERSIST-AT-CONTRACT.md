# GLM-REPORT-PERSIST-AT-CONTRACT

## Resumen

Contrato CCDD + oráculo congelado para la nueva función de persistencia con raíz explícita `persist_email_okf_at(record, root, rel_path) -> str`. Solo contrato y oráculo: NO se implementó código de producción ni stub. El target declarado es `src/email/persist_at.py` (módulo nuevo, no creado; el contrato es la pieza que antecede a la delegación al implementador). La variante replica la validación y el render OKF de `persist_email_okf` pero la raíz permitida llega por parámetro (no depende del cwd): `root` str no vacío, `rel_path` relativa sin `..` ni `~` con destino dentro de root, escritura atómica UTF-8 con LF puros, idempotencia byte a byte, conflicto de contenido distinto → `OSError`, crea padres, devuelve ruta absoluta. Rechaza rutas fuera y no persiste secretos adicionales.

## Archivos tocados

- `outputs/email-agent-kdd/knowledge/contracts/persist-email-okf-at.md` — creado: 7 secciones CCDD (Intent, Interface, Invariants, Examples, Do / Don't, Tests, Constraints) + cláusula de parada "PARAR y reportar si...". `lint_task_contract` → `ok: true` (0 errors, 0 warnings), con `test_command` y budget ajustado al tope global (`lines_max: 80`).
- `outputs/email-agent-kdd/tests/frozen_persist_email_okf_at.py` — creado: oráculo independiente que renderiza el nodo OKF sin importar `src.email` (parte de referencia); 11 tests: 5 de estructura/contenido del contrato siempre activos, y 6 casos de comportamiento contra el target cuando exista (raíz vacía, record inválido, traversal/absolutas/`~` con cero escrituras parciales, frozen-example con LF puro y padres creados, idempotencia, conflicto `OSError` con destino intacto y sin `.tmp` remanentes).

## Verificación

- `python -m pytest outputs/email-agent-kdd/tests/frozen_persist_email_okf_at.py -v` → **5 passed, 6 skipped en 0.28s**. Los skips son los casos contra el target: `src/email/persist_at.py` no existe y el encargo prohíbe crear stub, por lo que el archivo es contrato/oráculo puro hasta la implementación.
- Sin red, sin secretos reales, sin procesos en segundo plano; no se tocó `src/` ni contratos/tests existentes (incluido `persist-email-okf.md` y su frozen test, que quedan intactos).

## Estado

LISTO: contrato y oráculo congelados y verificados. Pendiente (fuera de esta tarea): implementar `persist_email_okf_at` en `src/email/persist_at.py` vía el flujo de delegación CCDD cuando se ordene; al existir el target, los 6 casos congelados de comportamiento se activan solos.