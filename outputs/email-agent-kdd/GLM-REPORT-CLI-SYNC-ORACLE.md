# Reporte — Oráculo de referencia para cli-sync

## Resumen

Se creó `outputs/email-agent-kdd/tests/frozen_cli_sync.py`, oráculo independiente del contrato `outputs/email-agent-kdd/knowledge/contracts/cli-sync.md` (target `src/email/cli.py`, `cli_main`). No importa `src.email`, no abre red, no usa credenciales reales, no lanza procesos ni toca disco fuera de un tempdir propio.

Verifica: frontmatter (task/signature/target/presupuestos/deps/forbids/tests/test_command), las 7 secciones y la frase `PARAR y reportar si...` (incluidas sus condiciones de firmas ausentes y de reimplementación), la delegación congelada en las seis dependencias (`load_email_accounts`, `resolve_credential`, `fetch_imap_messages`, `sync_email_account`, `persist_email_okf`, `extract_contacts`) con sus firmas exactas, la prohibición de reimplementarlas, los hosts default `gmail`/`outlook` y la compatibilidad declarada de `search`/`account` (`cli_search`, `cli_accounts`, usages `search ROOT QUERY`, `account add/list`, `no cambia en nada`).

Los 12 `frozen-cases` se re-derivan con una CLI de referencia propia (`_SyncWorld` + `_reference_sync`): store JSON espejo en `<root>/.email-agent/accounts.json`, resolver de credenciales espejo sobre `env://` ficticio, sesión IMAP simulada, persistencia de referencia y contacto de referencia con dedupe por email en minúsculas. Se contrasta código exacto (0/1/2), una sola línea JSON en stdout con exactamente las 5 claves del resumen, `persisted_paths` en orden (separador `/`), host elegido (verbatim o default por provider), nodos escritos (mensajes y contactos con `type: Email Contact`), conteo de llamadas fetch/persist/contactos y ausencia de `password`, del secreto y de `credential_ref` en toda la salida.

## Archivos tocados

- `outputs/email-agent-kdd/tests/frozen_cli_sync.py` (creado, único archivo modificado)

## Verificación

`python -m pytest outputs/email-agent-kdd/tests/frozen_cli_sync.py -q`

```
.............                                                            [100%]
13 passed in 0.33s
```

13 pruebas: 4 de estructura del contrato (frontmatter/presupuestos, 7 secciones + frase de parada, delegación en las seis dependencias, compatibilidad search/account) y 9 de re-derivación de los 12 frozen-cases (forma y determinismo; ayuda; 3 casos sync exitoso con host explícito y defaults gmail/outlook; 5 errores de operación con código 1 y cero escrituras; 3 errores de argumentos con código 2; ausencia de secretos en los 12 casos).

Durante el ajuste se detectó en el propio contrato una ambigüedad de aridad: el texto dice "tres o cuatro argumentos tras el subcomando", pero los frozen-cases fijan `["sync", root, account]` → 0 y `["sync"]`/`["sync", root]` → 2, es decir, 2 o 3 args tras `sync` (3–4 tokens contando el subcomando). El oráculo sigue a los frozen-cases (vinculantes).

## Estado

LISTO — oráculo creado y en verde (13/13); `src/email/cli.py` no implementado y ningún otro archivo modificado.