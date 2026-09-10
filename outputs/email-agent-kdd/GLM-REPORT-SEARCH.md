# GLM-REPORT-SEARCH

## Resumen
Implementado `search_email_nodes(root, query)` en `src/email/search.py` segun el contrato `outputs/email-agent-kdd/knowledge/contracts/search-email-nodes.md`. Recorrido recursivo con `pathlib`, solo archivos con extension final `.md` (insensible a mayusculas), coincidencia AND literal de terminos del query (split por espacios, lowercase en contenido y terminos), rutas relativas con `/` ordenadas lexicograficamente. Errores por contrato: root inexistente/no directorio, query sin terminos, `.md` no leible como UTF-8. Solo `pathlib`; sin eval/exec/red ni modificacion de archivos.

## Archivos tocados
- `src/email/search.py` (creado)

## Estado
- `python -m pytest -q` sobre los 4 suites congelados: 20 passed.
- Sin procesos persistentes dejados.