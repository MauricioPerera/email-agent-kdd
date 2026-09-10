# GLM-REPORT-PERSIST-CONTRACT

## Resumen

El test congelado `test_frozen_example_account_and_hash_and_body` esperaba que el body del bloque `frozen-example` terminara en `\n` (`node.split("---\n", 2)[2] == "Hola desde el MVP.\n"`), pero el regex del oracle (`\`\`\`frozen-example\n(.*?)\n\`\`\``) capturaba el contenido sin el salto final porque el body estaba pegado al fence de cierre. Corrección: se añadió una línea en blanco antes del fence de cierre del bloque `frozen-example` en el contrato, de modo que el nodo OKF de ejemplo termina con salto de línea en el body, como corresponde a un nodo Markdown con frontmatter. No se tocó el oracle (los tests son congelados), ni `src/email/normalize.py`, ni se creó `persist.py`.

## Archivos tocados

- `outputs/email-agent-kdd/knowledge/contracts/persist-email-okf.md` — línea en blanco añadida antes del fence de cierre del bloque `frozen-example`.

## Estado

PASS: `python -m pytest -q outputs/email-agent-kdd/tests/frozen_persist_email_okf.py outputs/email-agent-kdd/tests/frozen_normalize_email.py` → 7 passed. Sin procesos persistentes.