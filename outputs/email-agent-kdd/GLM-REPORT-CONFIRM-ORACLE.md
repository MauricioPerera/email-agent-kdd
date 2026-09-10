# GLM-REPORT-CONFIRM-ORACLE

## Resumen

El oracle `tests/frozen_confirm_draft.py` evaluaba el bloque `frozen-invalid-inputs` del contrato con `eval()` plano. Si el bloque venia en estilo JSON (`null`, `true`, `false`), `eval` fallaba con `NameError: name 'null' is not defined` porque `eval` no conoce los literales JSON.

Correccion minima aplicada en `test_invalid_inputs_rejected_with_valueerror`: se pasa a `eval` un namespace que mapea los literales JSON a sus equivalentes Python:

```python
invalid = eval(
    _fenced_block(text, "frozen-invalid-inputs"),
    {"null": None, "true": True, "false": False},
)
```

Esto interpreta el bloque sin error tanto en estilo JSON (`null`) como en estilo Python (`None`). No se cambio el contrato ni codigo de produccion.

## Archivos tocados

- `outputs/email-agent-kdd/tests/frozen_confirm_draft.py` (unico cambio: namespace JSON en el `eval` del bloque `frozen-invalid-inputs`).

## Estado

- Comando ejecutado: `python -m pytest -q` sobre los 7 archivos frozen indicados.
- Resultado: **45 passed** en 0.30s (antes: 1 failed, 44 passed).
- Sin procesos persistentes dejados en ejecucion.