# Contradicción cli-sync vs persist_email_okf

## Resumen

El contrato `cli-sync.md` obliga a que `cli_main(["sync", ROOT, ...])` persista cada mensaje en
`persist_email_okf(record, "<root>/store/emails/" + record["raw_sha256"] + ".md")` (línea 32 del
contrato), con ROOT recibido como argumento libre de la CLI. Pero `src/email/persist.py`
(`persist_email_okf`, `persist.py:16-26`) resuelve toda ruta contra `Path.cwd()` y **rechaza
cualquier ruta absoluta** (`ValueError`), además de cualquier segmento `..` y `~`. Consecuencia:

- Si el usuario pasa un ROOT **absoluto** (lo natural en una CLI, y lo que ya aceptan
  `account add`/`account list` vía `account_store._store_path` y `search` vía `search_email_nodes`),
  el `sync` hace el fetch IMAP completo y luego falla en la etapa `persist` (envuelto por
  `sync_email_account` en `RuntimeError` → código `1`), sin haber persistido nada.
- Si ROOT es relativo, `<root>/store/emails/<sha>.md` solo se resuelve "bajo ROOT" si cwd es
  exactamente el padre de ROOT; en cualquier otro cwd los nodos caen en otro árbol distinto del
  store de cuentas. La contradicción es real, no cosmética: `sync C:\store personal` con cuenta
  creada en `C:\store` es un caso que el propio flujo `account add → sync` produce.

Veredicto: el contrato cli-sync no es implementable tal como está; hay que decidir de qué lado
queda la política de rutas ANTES de escribir el código.

## Evidencia

1. **cli-sync.md:32** — "`persist(record)` llama `src.email.persist.persist_email_okf(record,
   "<root>/store/emails/" + record["raw_sha256"] + ".md")`". ROOT no está restringido a relativo
   en ningún punto del contrato; `--help` debe imprimir literalmente `sync ROOT ACCOUNT_ID [HOST]`.
2. **cli-sync.md:48** — "Cada mensaje se persiste una sola vez en `<root>/store/emails/<raw_sha256>.md`
   via `persist_email_okf`": invariant acopla la ruta al ROOT del usuario.
3. **src/email/persist.py:17-26** — `root = Path.cwd().resolve()`; `Path(text).is_absolute()`
   → `ValueError("ruta insegura: absoluta ...")`; segmento `..` → `ValueError`; y el target debe
   quedar estrictamente bajo cwd.
4. **persist-email-okf.md** congela ese comportamiento: frozen-unsafe-paths incluye
   `C:\Windows\system32\evil.md`, `/etc/passwd` y `~/.ssh/id_rsa.md`, y los ejemplos solo usan
   rutas relativas (`store/emails/msg-0001.md`). El contrato de persist dice "Se resuelve y valida
   antes de escribir" y "Don't: escribir fuera de la raíz permitida", donde la raíz permitida es
   cwd — nunca recibida como parámetro.
5. **Inconsistencia interna del sistema**: `account_store._store_path` (línea 33) usa
   `Path(root)/.email-agent/accounts.json` y `save_email_account` devuelve `str(path.resolve())`
   — acepta ROOT absoluto sin restricción; `search_email_nodes` (`search.py:13`) igual. El único
   módulo restrictivo es `persist`. Un usuario que hizo `account add C:\store ...` con éxito no
   puede hacer `sync C:\store personal`.
6. **tests/frozen_cli_sync.py** congela además la dependencia:
   línea 355-356 exige la firma `def persist_email_okf(record: dict, path: str) -> str` y su
   espejo (línea 134, 226) reimplementa la persistencia relativa a cwd. Ambos puntos son parte
   del oracle que habría que mover si cambia la delegación.
7. **Hallazgo colateral (mismo contrato, no es el foco)**: cli-sync.md:33 pide que los nodos de
   contacto se escriban en `<root>/store/contacts/<email>.md`, pero `extract_contacts`
   (`contacts.py:20-36`) es pura y solo devuelve la lista; `persist_email_okf` siempre renderiza
   `type: Email Message` (persist.py:6, 46), así que no sirve para contactos. La escritura de
   contactos tendría que hacerse a mano en la CLI, lo que choca con cli-sync.md:75 ("Don't:
   ... persistencia ... dentro de la CLI"). Necesita su propia dependencia/contrato.

## Opciones

**A) Restringir ROOT a ruta relativa bajo cwd** (código: ninguno; solo contratos).
- Pro: no se toca `persist.py` ni su contrato congelado; la política de seguridad existente se
  mantiene intacta; es lo más barato de verificar hoy.
- Contras: la CLI deja de ser amigable — obliga a `cd` al padre del store antes de cada sync.
  Introduce una regla de ROOT distinta para `sync` frente a `account`/`search` (que aceptan
  absolutos), la peor clase de inconsistencia para un usuario. Requiere **añadir** la restricción
  al contrato cli-sync (hoy no existe) y congelarla en `frozen_cli_sync.py` con un caso
  `sync <root-absoluto> → código 1/2`. La raíz del problema (persist atado a cwd) sigue ahí para
  cualquier futuro llamador.

**B) Nueva función `persist_email_okf_at(record, root, rel_path)` con contrato propio**.
- Pro: corrige la contradicción sin tocar nada congelado: `persist_email_okf` conserva firma,
  política y frozen-tests; la nueva función recibe la raíz permitida como parámetro explícito,
  la valida (resolverla y exigir que `rel_path` caiga estrictamente dentro, prohibiendo `..` y
  `~`), y hace la misma escritura atómica. La seguridad no se afloja: el límite deja de ser
  "cwd" para pasar a ser "raíz declarada por el llamador, validada". Natural para una CLI y
  consistente con `account`/`search`. Implementable en un módulo nuevo (`src/email/persist_at.py`),
  lo que ni siquiera roza el presupuesto `lines_max: 80` de `persist.py` (68 líneas; añadir
  ~25 líneas lo reventaría).
- Contras: una segunda función de persistencia que conviene mantener en paralelo (duplicación
  parcial de `_render`/`_validate`, resuelta importándolas del módulo original); hay que
  redactar contrato + oracle nuevos antes de implementar.

**C) Cambiar `persist_email_okf` para aceptar raíz segura** (parámetro extra o aceptar absolutas
  bajo una raíz dada).
- Pro: una sola función, sin duplicación.
- Contras: **rompe o amplía su contrato congelado**: cambia la firma de
  `persist-email-okf.md:5`, invalida el ejemplo `persist_email_okf(record, "store/emails/...")`
  tal como está congelado, y si acepta rutas absolutas entra en conflicto directo con el
  frozen-unsafe-paths (`C:\Windows\system32\evil.md`, `/etc/passwd`), que es precisamente el
  caso de uso de ROOT absoluto. Cada variante concreta (default hacia atrás compatible, raíz
  implícita desde env, etc.) debilita la garantía "una ruta insegura se rechaza antes de abrir
  ningún archivo" al meter una raíz elegible en el propio escritor de evidencia. Es la opción
  con más riesgo de regresión en todos los llamadores existentes.

## Recomendación

**Opción B**, en módulo nuevo `src/email/persist_at.py` con firma
`def persist_email_okf_at(record: dict, root: str, rel_path: str) -> str`, y con
`cli-sync.md` delegando en ella para mensajes (y, de paso, resolviendo el hallazgo colateral
con una dependencia análoga para contactos). Razones: única variante que no toca nada congelado,
mueve la política de seguridad del "cwd implícito" a una "raíz validada explícita" (más honesta
para una CLI), y mantiene `persist_email_okf` como la puerta restrictiva original.

Antes de implementar `cli sync` habría que tocar, en este orden:

1. **Nuevo contrato** `knowledge/contracts/persist-email-okf-at.md` (+ `tests/frozen_persist_email_okf_at.py`),
   lint y gate. Debe congelar: rechazo de `root` inexistente/relativo-ambiguo si se decide así,
   prohibición de `..`/`~` en `rel_path`, escritura atómica, idempotencia de contenido idéntico y
   `OSError` en conflicto — reutilizando la semántica de `persist.py`.
2. **Enmienda de `cli-sync.md`**: línea 32 (delegación), invariant línea 48, sección Tests
   (línea 82) y Constraints (firma de la dependencia de persistencia). Debe re-lintear y
   re-gatear porque congela una firma distinta en su lista de seis dependencias.
3. **Enmienda de `tests/frozen_cli_sync.py`**: espejo de persistencia (línea 134, 226) y la firma
   congelada `src.email.persist.persist_email_okf` (líneas 355-356) deben apuntar a
   `persist_email_okf_at`; los `persist_paths` relativos de los frozen-cases pueden quedarse tal
   cual (siguen siendo relativos a ROOT), pero el oracle debe derivarlos desde ROOT, no desde cwd.
4. **Contrato de escritura de contactos** (nuevo, p.ej. `store-email-contact.md`) para cubrir el
   vacío de `<root>/store/contacts/<email>.md` señalado arriba; sin él, la rama `update_contacts`
   del cli-sync queda sin dependencia válida.
5. Solo entonces: task-contract de la rama `sync` de `cli.py` y gate de integración
   (`run_integration_gate`) con los módulos reales.

## Estado

- **LISTO** (análisis solamente). No se modificó ningún archivo de código, contrato ni prueba;
  este informe es el único archivo escrito.
- Verificado contra: `cli-sync.md`, `persist-email-okf.md`, `src/email/persist.py`,
  `src/email/sync.py`, `src/email/cli.py`, `src/email/contacts.py`, `src/email/account_store.py`,
  `src/email/search.py`, `tests/frozen_cli_sync.py`. Sin red ni procesos foreground.
- Pendiente de decisión del usuario: aprobar Opción B antes de redactar los contratos de los
  pasos 1-4.