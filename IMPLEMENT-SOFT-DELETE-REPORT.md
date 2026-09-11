# Reporte: pieza 1 — borrado reversible (soft delete)

Fecha: 2026-09-10 · Estado: LISTO

## Alcance (exactamente lo pedido)

- Solo `src/email/deletion.py` + pruebas en `outputs/email-agent-kdd/tests/frozen_message_deletion.py`.
- **Sin integración CLI** (los subcomandos `message delete/restore/trash/purge` del USAGE de `cli.py` y su import quedan pendientes de la pieza 2).
- Sin red, sin secretos, sin commit.

## API implementada

| Función | Comportamiento |
|---|---|
| `soft_delete(root, rel_path)` | Mueve UN `.md` a `root/.trash/<rel_path>` (ruta preservada) y escribe manifiesto JSON **atómico** (`tempfile.mkstemp` + `os.replace` + `fsync`). Nunca elimina contenido. |
| `restore(root, trash_rel_path)` | Devuelve el elemento a su ubicación original y retira el manifiesto. No sobrescribe destino existente. |
| `list_trash(root)` | Lista los manifiestos de `.trash` ordenados por `trash_rel_path`. |
| `purge(root, trash_rel_path, confirmation)` | Elimina definitivamente algo **YA en `.trash`**, solo con la frase exacta `CONFIRMAR BORRADO PERMANENTE`. Acepta ruta del elemento o del manifiesto. |

## Seguridad verificada

- **Path traversal**: `~`, `/`, `\`, letra de unidad (`C:/`), `..`, componentes vacíos/`.` → `ValueError` en todas las funciones, antes de tocar disco (no se crea `.trash` si la ruta se rechaza; archivos externos intactos).
- Toda ruta resuelta se fuerza dentro de `root` (elemento) o dentro de `root/.trash` (papelera).
- `purge` con frase inexacta (mayúsculas distintas, espacios, frase similar) aborta sin tocar nada; nunca opera sobre rutas fuera de `.trash` aunque la frase sea exacta.
- Idempotencia: doble `soft_delete` falla sin destruir el manifiesto ni el elemento.

## Nota sobre el estado previo

`src/email/deletion.py` ya existía sin seguimiento en git (sesión previa) y cumplía el pedido; **no se sobrescribió** — se validó y se corrigieron 2 bugs reales detectados por las pruebas:

1. `_resolve_trash_entry` rechazaba la ruta del manifiesto `.json` (usaba `_check_rel_path`, que exige `.md`) contradiciendo su propio docstring de restore/purge → ahora usa `_check_any_rel_path`.
2. `purge` con la ruta del manifiesto borraba el `.json` en lugar del elemento `.md` → ahora deriva el `item_path` quitando el sufijo del manifiesto.

Un ajuste de prueba: el doble `soft_delete` lanza `FileNotFoundError` (el origen ya no existe) y no `ValueError`; la prueba congela la invariante real (falla sin destruir).

## Resultado de pruebas

```
python -m pytest outputs/email-agent-kdd/tests/frozen_message_deletion.py
14 passed in 0.40s
```

Casos congelados: movimiento + manifiesto atómico, ruta anidada preservada, rechazo de traversal (11 rutas inseguras) sin tocar disco, nodo inexistente, doble borrado, `list_trash` ordenado, restore completo y con conflicto de destino, purge con 7 frases inexactas, purge exacto (elemento y manifiesto), purge fuera de `.trash` rechazado, traversal en purge, ciclo completo soft→restore→purge.

## Pendiente (pieza 2, no hecho a propósito)

- Integración CLI: `message delete|restore|trash|purge` en `cli.py` (el import ya está en el árbol de trabajo).
- README: sección de borrado reversible.