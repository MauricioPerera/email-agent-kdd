# SPRINT1-DELETION-INDEX-REPORT

Fecha: 2026-09-10 · Ámbito: integración `deletion.py` ↔ `index_lifecycle.py`

## Veredicto

LISTO. `src/email/deletion.py` integra el helper existente de índices y el
comportamiento está verificado con un nuevo test congelado (6 casos) más los
dos tests congelados existentes (29 casos). Total: **35 passed**.

## Qué hace (implementación en `src/email/deletion.py`)

### soft_delete

1. Valida `root`, `rel_path`, el nodo fuente y el destino en `.trash`
   (sin sobrescribir elementos ya borrados).
2. **Antes de mover el archivo**, `_snapshot_affected_indices` recorre
   `root/store/conversations/*.md` y `root/store/topics/*.md` (ordenados,
   recursivos), parsea cada uno con `index_lifecycle._parse` y captura el
   texto íntegro de los que contienen la ruta normalizada EXACTA.
   - Cualquier índice corrupto bajo esos dos directorios lanza `ValueError`
     aquí: **aborta antes de mover el mensaje y sin escribir manifiesto**.
3. Mueve el mensaje a `.trash/<rel_path>` y escribe el manifiesto JSON
   atómico, ahora con campo opcional `index_snapshots`:
   `{ruta relativa del índice: contenido original del índice}`.
4. Después del manifiesto, retira la ruta de cada índice afectado con
   `remove_path_from_markdown_index` (escritura atómica; si la lista queda
   vacía el archivo del índice **desaparece**). Orden manifiesto→índices
   deliberado: si una escritura de índice falla, los snapshots ya están en
   el manifiesto y `restore` puede reconstruir.

### restore

- Aplica los índices **antes** de mover y de retirar el manifiesto:
  - índice ausente → se reescribe desde el snapshot (validado con `_parse`
    antes del `os.replace` atómico);
  - índice existente → `add_path_to_markdown_index` (unión deduplicada),
    que **no sobrescribe** cambios no relacionados hechos mientras el
    mensaje estuvo en `.trash`;
  - si alguna validación/escritura falla → `ValueError` seguro: el mensaje
    sigue en `.trash`, el manifiesto conserva los snapshots y se puede
    reintentar.
- Manifiesto antiguo sin `index_snapshots` (o con `None`): comportamiento
  previo intacto, no toca índices.
- Las rutas de índice del snapshot se validan (relativas seguras, `.md`,
  solo bajo `store/conversations` o `store/topics`).

No se modificaron: CLI, `query.py`, `search.py`, IMAP, contactos ni firmas
públicas existentes (`soft_delete`, `restore`, `list_trash`, `purge`).

## Tests

Nuevo: `outputs/email-agent-kdd/tests/frozen_deletion_index_integration.py`
(sin red, sin secretos, sin commit)

| Caso | Resultado |
|---|---|
| 2 mensajes en la misma conversación/tema; borrar uno conserva el otro y su índice; los snapshots van al manifiesto; restore repone índices byte a byte | ok |
| Borrar el último elimina los archivos de índice; restaurar ambos los recrea idénticos desde snapshots | ok |
| Índice corrupto (message_count incoherente) aborta `soft_delete` antes de mover: mensaje intacto, sin manifiesto, otro índice sin cambios | ok |
| Manifiesto antiguo (5 claves, sin `index_snapshots`) restaura sin tocar índices | ok |
| Índice corrompido tras el borrado: `restore` falla sin destruir mensaje ni manifiesto; reparado el índice, el reintento completa | ok |
| `purge` sigue eliminando elemento + manifiesto con confirmación exacta | ok |

Ejecución:

```
python -m pytest outputs/email-agent-kdd/tests/frozen_deletion_index_integration.py \
  outputs/email-agent-kdd/tests/frozen_message_deletion.py \
  outputs/email-agent-kdd/tests/frozen_index_lifecycle.py -q
# 35 passed
```

Solo se corrieron los tres archivos indicados.

## Notas

- `deletion.py` ya contenía la integración (archivo sin trackear de una
  sesión previa); este sprint la verificó end-to-end contra los requisitos y
  congeló el test de integración que faltaba.
- `soft_delete` puede elevar `OSError` si la retirada del índice falla
  DESPUÉS de mover: no es pérdida de datos (el mensaje está en `.trash` y el
  snapshot permite reconstruir con `restore`).