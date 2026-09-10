# GLM-REPORT-CLI-SYNC-CONTRACT

## Resumen

Sincronizado `knowledge/contracts/cli-sync.md` con la API vigente de `src.email`:

- **Persistencia**: la rama `sync` persiste exclusivamente via `src.email.persist_at.persist_email_okf_at(record: dict, root: str, rel_path: str) -> str`, con `rel_path = store/emails/<raw_sha256>.md` relativo a ROOT (derivado del hash del registro).
- **Contactos**: `update_contacts` aplica `src.email.contacts.extract_contacts(record: dict) -> list` a cada mensaje, fusiona con dedupe por email en minusculas y llama UNA vez a `src.email.contact_store.store_email_contacts(root: str, contacts: list[dict]) -> int`.
- **Eliminado**: toda regla sobre nodos de contacto `.md` escritos por `cli.py` y toda mencion/prohibicion de `persist_email_okf` (src.email.persist) con ruta absoluta, en Interface, Invariants, Do/Don't, Tests y Constraints (incluida su clausula PARAR).

## Archivos tocados

- `outputs/email-agent-kdd/knowledge/contracts/cli-sync.md` — unico archivo editado (Interface, Invariants, Examples, Do/Don't, Tests, Constraints).
- `outputs/email-agent-kdd/GLM-REPORT-CLI-SYNC-CONTRACT.md` — este reporte (creado).

## Estado

OK. Conservado sin cambios: codigos `0`/`1`/`2`, una linea JSON en stdout (`account_id`, `fetched`, `persisted`, `persisted_paths`, `contacts_updated`), secretos solo en memoria y ausentes de stdout/stderr, sesion IMAP de solo lectura dentro de `fetch_imap_messages`, host por provider (`gmail`/`outlook` + override por argv), y semantica intacta de `search`/`account`. No se tocaron tests ni codigo. Sin servidores.