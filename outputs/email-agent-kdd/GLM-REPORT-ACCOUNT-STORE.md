# GLM-REPORT-ACCOUNT-STORE

## Resumen

Se creo el oraculo congelado para el contrato `store-email-account.md` y este
reporte. La prueba nueva corre contra `src/email/account_store.py` (no modificado)
y expone UN FALLO REAL del modulo: el store se escribe con `\r\n` en Windows
(`Path.write_text` sin `newline=""` traduce el salto), por lo que los bytes en
disco NO son los del ejemplo frozen (`...}\r\n` vs `...}\n`). El contrato exige
JSON determinista byte a byte terminado en salto de linea. Resultado: FALLO.

## Archivos tocados

- Creado: `outputs/email-agent-kdd/tests/frozen_store_email_account.py`
  (oraculo: 20 pruebas; 8 de estructura/contrato + 12 de comportamiento con
  import del target SOLO dentro de las pruebas, contra store temporal;
  el modelo esperado es independiente, reconstruido de `frozen-inputs` /
  `frozen-example` y con las reglas reimplementadas).
- Creado: `outputs/email-agent-kdd/GLM-REPORT-ACCOUNT-STORE.md` (este).
- NO tocados: el contrato `knowledge/contracts/store-email-account.md` y
  `src/email/account_store.py`, conforme a la consigna.

## Verificacion

1. Prueba nueva: `python -m pytest -q outputs/email-agent-kdd/tests/frozen_store_email_account.py -o python_files="frozen_*.py"`
   -> 19 passed, 1 failed.
2. Suite completa: `python -m pytest -q outputs/email-agent-kdd/tests -o python_files="frozen_*.py"`
   -> 112 passed, 1 failed (la misma), sin afectar las 11 pruebas de los otros
   rebanadas.

### Fallo del modulo (sin tocar codigo, reportado)

- Prueba: `test_save_writes_frozen_example_bytes`.
- Evidencia: en disco queda `...,"status":"disconnected"}]}\r\n` (byte 163 = `\r`)
  cuando el ejemplo frozen del contrato exige `...}\n`.
- Causa raiz: `src/email/account_store.py:68` —
  `temporary.write_text(payload + "\n", encoding="utf-8")`. `Path.write_text` con
  newline por defecto traduce `\n` a `os.linesep` (`\r\n` en Windows).
- Violacion del contrato: la escritura no es "los mismos bytes exactos"
  (Invariants; `## Escritura`: JSON terminado en salto de linea); el store
  cambia de bytes entre plataformas y no coincide con el frozen-example.
  Las demas reglas (esquema exacto, orden, reemplazo, atomicidad observable,
  archivo ausente => `[]`, rechazos `ValueError`/`RuntimeError`, ausencia de
  filtrado de contenido en mensajes) PASAN.
- Arreglo propuesto (NO aplicado por consigna): escribir con
  `newline=""` (o `temporary.write_bytes((payload + "\n").encode("utf-8"))`).

### Cobertura del oraculo (lo que verifica)

Esquema exacto de las cinco claves (rechazo de `password`/`secret`/`token`,
no-str, `bytes`, status != `disconnected`, valores vacios); JSON determinista
byte a byte y `ensure_ascii=False` verificado con `aña@example.com`;
reemplazo por `account_id` sin duplicados; orden por `account_id` en disco y en
`load`; archivo ausente => `[]` sin crear directorios; escritura atomica
observable (sin `.tmp` remanentes, store intacto tras rechazo previo, unica
entrada `accounts.json`); `RuntimeError` para archivo corrupto / fuera de
esquema; mensajes de error sin filtrar el contenido de las entradas
(SECRETO-FALSO, emails); el oraculo no importa el target a nivel de modulo y el
target no importa nada fuera de `json`/`os`/`pathlib` (AST) ni usa
`smtplib`/`socket`/`urllib`/`requests`/`subprocess`. Sin red, sin procesos
foreground, sin secretos reales (solo referencias `keyring://...` falsas).

## Estado

FALLO. Oraculo y reporte creados y ejecutados; el modulo falla 1 de 20 pruebas
del oraculo por salto de linea CRLF (no determinismo de bytes). No se modifico
el codigo; se requiere el arreglo de `write_text(newline="")` en
`src/email/account_store.py:68` antes de declarar LISTO.