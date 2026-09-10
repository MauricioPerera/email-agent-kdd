# GLM Report — contact_store

## Resumen

Implementado `store_email_contacts(root, contacts) -> int` en `src/email/contact_store.py` conforme al contrato `store-email-contacts.md`. La verificación con el test congelado pasó completa: **6 passed** (`python -m pytest -q outputs/email-agent-kdd/tests/frozen_store_email_contacts.py`).

Detalles de la implementación:

- Validación completa de `root` (`str` no vacío tras strip) y del esquema exacto de cada contacto (`dict` con exactamente las claves `name`/`email`, `name: str`, `email` no vacío, sin espacios/caracteres de control internos, un solo `@`, partes no vacías) **antes** de crear directorios o abrir archivos.
- Rechazo de intentos de path traversal: `/`, `\` y rutas absolutas tanto en `email` como en `name` → `ValueError` (cubierto por `test_path_traversal_rechazado`).
- Deduplicación por email normalizado `strip().lower()`; primera aparición gana el `name` (existentes primero, luego nuevas), el merge nunca sobrescribe el nombre guardado.
- Escritura determinista: JSON con única clave `contacts`, lista ordenada por `email` ascendente, `sort_keys=True`, `ensure_ascii=False`, UTF-8, `newline=""` (evita traducción CRLF en Windows) y salto de línea final.
- Escritura atómica: temporal en el mismo directorio + `os.replace`, con limpieza del `.tmp` en `finally` (sin remanentes).
- Store ausente = libreta vacía; store corrupto o fuera de esquema → `RuntimeError` con mensaje fijo (sin contenido de entradas) y archivo intacto.
- Sin red ni procesos: imports solo `json`, `os`, `pathlib` (dentro de `deps_allowed`).
- El formato de contacto de `extract_contacts` (`src/email/contacts.py:16`) coincide con las claves `name`/`email` documentadas: no se activó ninguna causa de paro del contrato.
- Dentro de presupuesto: 4 funciones cortas, anidamiento ≤ 3, ~80 líneas de módulo, 1 parámetro por función.

## Archivos tocados

- `src/email/contact_store.py` (creado — único archivo de implementación)
- `outputs/email-agent-kdd/GLM-REPORT-CONTACT-STORE.md` (este reporte)

No se modificaron contratos, tests ni otros archivos.

## Estado

- Tests: `6 passed in 0.31s` — verde en la primera ejecución.
- Contrato: cumplido; sin desvíos ni causas de paro.