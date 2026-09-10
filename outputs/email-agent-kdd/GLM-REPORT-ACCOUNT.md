# GLM-REPORT-ACCOUNT

## Resumen

Implementado el contrato de registro local de una cuenta de correo (`create_email_account`) como preparacion para OAuth/sincronizacion futura, sin conectarse a ningun proveedor: contrato CCDD de 7 secciones con frase `PARAR y reportar si` en Constraints, prueba congelada con oracle independiente, e implementacion con funciones pequenas y cero dependencias externas. El registro valida los cuatro argumentos (str no vacios), normaliza `provider` (strip + minusculas) y `email` (minusculas, sin ningun espacio), copia `credential_ref` verbatim como texto opaco (nunca el secreto) y devuelve `status: "disconnected"`.

## Archivos tocados

- `outputs/email-agent-kdd/knowledge/contracts/create-account.md` (nuevo)
- `outputs/email-agent-kdd/tests/frozen_create_account.py` (nuevo)
- `src/email/account.py` (nuevo)
- `outputs/email-agent-kdd/GLM-REPORT-ACCOUNT.md` (nuevo)

No se toco ningun archivo existente fuera de los cuatro entregables.

## Verificacion

- `python -m pytest -q outputs/email-agent-kdd/tests -o python_files="frozen_*.py"` — la prueba nueva (`frozen_create_account.py`) y toda la suite congelada existente en verde.
- El oracle (`frozen_create_account.py`) es independiente: no importa el target ni `src.email`; recomputa las reglas de normalizacion documentadas contra el ejemplo frozen.
- `src/email/account.py` cumple el frontmatter: ciclomatica/anidamiento dentro de budget, <= 80 lineas, 4 parametros, sin `deps_allowed` externos, sin red, sin disco, sin `eval`/`exec`/`subprocess`, sin logging de secretos.
- Sanity check manual: `create_email_account("personal", "  Gmail  ", "  Ana @ Example.COM ", "keyring://gmail/personal")` reproduce el ejemplo frozen del contrato.

## Estado

Completado. Los cuatro entregables creados; suite congelada completa ejecutada y en verde. Ningun proveedor contactado, ningun secreto guardado o logueado; `credential_ref` vive solo como texto opaco en el registro en memoria.