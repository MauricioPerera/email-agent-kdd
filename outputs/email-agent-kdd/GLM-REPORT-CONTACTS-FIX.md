# GLM Report — reconciliación extract_contacts con parse_raw_email

## Resumen

`extract_contacts` ahora funciona con ambos formatos de registro sin romper el contrato: usa `record["headers"]` si existe (formato de `normalize_email`) y, si no existe (o no es dict), cae a los campos top-level `from`, `to`, `cc` que produce `parse_raw_email`. Nunca mezcla ambas fuentes en una misma llamada; la deduplicación y el orden From → To → Cc se mantienen idénticos.

## Archivos tocados

- `outputs/email-agent-kdd/knowledge/contracts/extract-contacts.md`: intent, interface (precedencia de fuente), invariants (equivalencia entre formatos), examples, descripción del oráculo, dos casos nuevos en `frozen-cases` y cláusula `PARAR y reportar si...` actualizada (ya no considera "registro sin `headers`" una condición de parada, porque es el formato de `parse_raw_email`).
- `outputs/email-agent-kdd/tests/frozen_extract_contacts.py`: dos tests nuevos (`test_frozen_cases_top_level_format`, `test_frozen_cases_top_level_equivalent_to_headers`) y docstring actualizado. Todos los tests y casos preexistentes quedaron intactos.
- `src/email/contacts.py`: fallback mínimo (guard `isinstance(headers, dict)`); firma sin cambios, sigue pura, sin red/disco/logs, dependencia única `email` (ya en `deps_allowed`).

No se tocó `parse.py`, `sync.py` ni ningún otro archivo.

## Verificación

- Los 6 casos congelados del contrato ejecutados contra `extract_contacts`: PASS (`from_to_cc`, `dedup_by_lowercase_email`, `missing_cc_header`, `empty_headers`, `top_level_format`, `top_level_equivalent_to_headers`). Verificación adicional de pureza (el registro de entrada no se muta): PASS.
- Prueba congelada de contactos: `python -m pytest -q outputs/email-agent-kdd/tests/frozen_extract_contacts.py` → **8 passed**.
- Suite completa: `python -m pytest -q outputs/email-agent-kdd/tests -o python_files="frozen_*.py"` → **138 passed** (15 suites congeladas).

## Estado

LISTO — contrato reconciliado, oráculo ampliado, implementación compatible con `parse_raw_email` (formato que usará `sync`).