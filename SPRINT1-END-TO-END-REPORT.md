# Reporte Sprint 1 — Test end-to-end de borrado reversible + índices + contactos

**Estado:** LISTO. `python -m pytest outputs/email-agent-kdd/tests/frozen_sprint1_end_to_end.py` → **6 passed** (0.49 s). Sin red, sin secretos, sin commit, sin modificar `src` ni otros tests.

## Artefacto

- `outputs/email-agent-kdd/tests/frozen_sprint1_end_to_end.py` (único test nuevo)

## Alcance

Integra las APIs actuales (no se reescribió nada de producción):

- `src.email.deletion`: `soft_delete`, `restore`, `list_trash`
- `src.email.query`: `query_email` (`conversation:`, `topic:`, `contact:`)
- `src.email.search`: `search_email_nodes`
- `src.email.contact_rebuild`: `rebuild_contacts_from_store` (setup de `contacts.json`)

## Escenario

Store en `tmp_path` con dos nodos OKF bajo `store/emails` (`msg-a.md`, `msg-b.md`), misma `conversation_key` (hex-64) y `topic: presupuesto`, contactos compartidos (Beto en `to:` de ambos) y exclusivos (Ana/Cati en A, Zulma en B). Índices en `store/conversations/<key>.md` y `store/topics/<topic>.md` con ambas rutas.

## Verificado

1. **Ciclo de vida completo** (`test_end_to_end_soft_delete_restore_full_lifecycle`):
   - Antes: ambos nodos aparecen en `query_email` (por conversación, tema y contacto) y en `search_email_nodes`.
   - `soft_delete` de A: el nodo se mueve a `.trash`, desaparece de query/search, se retira **solo su ruta** de ambos índices (quedan con la del otro y `message_count` coherente) y `contacts.json` conserva el contacto compartido (Beto) perdiendo los exclusivos de A (Ana/Cati). El manifiesto guarda `index_snapshots` y `contacts_snapshot` íntegros.
   - `restore`: el nodo vuelve con su contenido íntegro, los índices se reincorporan (ambas rutas, conteo 2) y los contactos se reconstruyen completos (los cuatro).
   - `soft_delete` del último: los índices sin rutas se **eliminan** (`message_count` vacío → unlink) y `contacts.json` queda con `contacts` vacíos.
   - `restore` final: nodos, índices (ambas rutas) y contactos exclusivos se recrean completos.
2. **Conflicto de destino** (`test_restore_conflict_refuses_to_overwrite_and_no_data_lost`): con un nodo nuevo en la ruta original, `restore` falla con `ValueError`, no sobrescribe, el elemento y el manifiesto siguen en `.trash` y los índices/contactos quedan intactos; retirado el conflicto, restore completa sin pérdida.
3. **Corrupción sin destrucción de datos**:
   - Índice de tema corrupto → `soft_delete` aborta con `ValueError` antes de mover: nodo, índice sano y `contacts.json` intactos, sin crear `.trash`.
   - Frontmatter corrupto en otro nodo activo → aborta sin mover el objetivo y sin tocar `contacts.json`.
   - `contacts.json` no UTF-8 → aborta sin mover nada.
   - Manifiesto ilegible → `restore` aborta: elemento sigue en `.trash`, índices y contactos previos intactos; reparado el manifiesto con su texto original, restore completa.

## Limitaciones

Cubre solo el camino local (no IMAP remoto ni CLI). Los casos de corrupción son deterministas (texto plano/bytes inválidos), no fallos de E/S simulados.