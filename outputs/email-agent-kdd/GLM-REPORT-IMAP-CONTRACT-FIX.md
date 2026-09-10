# GLM-REPORT-IMAP-CONTRACT-FIX

## Resumen
Correccion documental unica: en `knowledge/contracts/fetch-imap-messages.md` se cambio el frontmatter `target` de `src/email/fetch.py` a `src/email/imap_reader.py`, que es el archivo realmente implementado por el contrato (verificado: `src/email/` contiene `imap_reader.py` y no existe `fetch.py`). No se toco codigo ni pruebas.

## Archivos tocados
- `outputs/email-agent-kdd/knowledge/contracts/fetch-imap-messages.md` — solo linea 4 del frontmatter (`target`).
- `outputs/email-agent-kdd/GLM-REPORT-IMAP-CONTRACT-FIX.md` — este informe (creado).

## Verificacion
- Prueba congelada del contrato: `python -m pytest -q outputs/email-agent-kdd/tests/frozen_fetch_imap.py` -> **1 failed, 10 passed**.
  - El unico fallo es `test_contract_frontmatter_and_budgets` (linea 110 del oraculo), que tiene codificada en duro la asercion `assert "target: src/email/fetch.py" in frontmatter`. Al corregir el target del contrato, ese assert obsoleto falla por diseño: el oraculo congelado refleja el target erroneo que se corrigio. Los otros 10 tests (comportamiento de `fetch_imap_messages`) pasan.
- Suite completa: `python -m pytest -q outputs/email-agent-kdd/tests -o python_files="frozen_*.py"` -> **1 failed, 83 passed**. Mismo unico fallo; los 83 restantes pasan.
- Sin red, sin procesos foreground.

## Estado
**BLOQUEADO / PENDIENTE DE DECISION.** El cambio documental pedido esta hecho y verificado, pero la instruccion "no modifiques codigo ni pruebas" choca con el propio oraculo congelado: `tests/frozen_fetch_imap.py:110` aserta el target viejo (`src/email/fetch.py`), por lo que la prueba del contrato no puede pasar sin actualizar esa unica linea del test a `src/email/imap_reader.py`. La suite completa falla solo por esa linea. Accion requerida del usuario: aprobar el cambio de esa linea 110 (mismo error documental, en forma de test) o mantener pruebas intactas y aceptar el 1 failed conocido.