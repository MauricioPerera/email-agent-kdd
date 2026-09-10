---
task: cli-send
intent: Añadir los subcomandos draft y send a la CLI de email con confirmación explícita, registro de contactos salientes tras el envío exitoso y sin exponer secretos.
target: ../../src/email/cli.py
signature: "def cli_main(argv: list) -> int"
kind: group
language: python
budget:
  complexity: 8
  nesting: 3
  length: 120
stop_rule: Si el test congelado o el gate exige algo que contradiga este contrato, PARAR y reportar si el conflicto es de firma, de dependencia o de entorno; NO improvisar código fuera de contrato.
children:
  - ../../src/email/draft.py
  - ../../src/email/outgoing_contacts.py
  - ../../src/email/contact_store.py
---

## Intent

Extender `src/email/cli.py` con un punto de entrada `cli_main(argv: list) -> int` que expone dos subcomandos (`draft`, `send`) delegando TODO el comportamiento real en las funciones ya existentes de `src.email.draft` (`create_email_draft`, `confirm_email_draft`, `send_smtp_message`) y en la resolución de credencial existente; la CLI es solo orquestación, parsing de argumentos, persistencia del draft y salida impresa. Fuera de alcance: adjuntos, y cualquier cambio a `sync` / `search` / `account` (deben quedar intactos).

## Interface

```python
def cli_main(argv: list) -> int
```

Comandos (posición estricta, sin flags):

1. `draft ROOT ACCOUNT_ID TO SUBJECT BODY`
   - Delega en `src.email.draft.create_email_draft(...)` para construir el borrador.
   - Guarda el draft pending como JSON determinista (claves ordenadas, `sort_keys=True`, `indent=2`, encoding UTF-8) en `ROOT/drafts/<id>.json`, donde `<id>` es el id devuelto por el draft.
   - Crea el directorio `ROOT/drafts/` si no existe.
   - Imprime en stdout UNA línea JSON: `{"id": "<id>", "path": "<ruta del archivo>"}`.
   - Devuelve `0`.

2. `send ROOT ACCOUNT_ID DRAFT_ID CONFIRMAR_ENVIO`
   - Carga el draft desde `ROOT/drafts/<DRAFT_ID>.json`. Si no existe, imprime error genérico en stderr y devuelve `1`.
   - EXIGE que el cuarto argumento sea EXACTAMENTE la frase de confirmación (`CONFIRMAR ENVIO`, mayúsculas, acento incluido, sin normalización). Cualquier otra cosa (minúsculas, sin acento, vacío, "yes", "y") se rechaza: error genérico en stderr, devuelve `1`, y NO se resuelve credencial ni se abre conexión SMTP.
   - Delega en `confirm_email_draft(...)` para validar el estado del draft (solo pending-confirmado avanza).
   - **Puente `status` -> `confirmed`:** `confirm_email_draft(...)` devuelve el draft con `status == "confirmed"` y `confirmation_hash`, pero SIN la clave booleana `confirmed` que `send_smtp_message` exige (`message["confirmed"] is True`). Tras la confirmación exitosa, la CLI construye una copia NUEVA del dict confirmado (p. ej. `dict(confirmed)`) que conserva TODOS los campos (`account_id`, `to`, `subject`, `body`, `status`, `confirmation_hash` y los demás) y añade EXACTAMENTE `confirmed=True`. Esa copia — no el draft original, no el dict devuelto por `confirm_email_draft`, que NO se mutan — es lo que se pasa a `send_smtp_message(...)` y a `extract_outgoing_contacts(...)`.
   - Resuelve la credencial SOLO en memoria (nunca en disco, nunca en el draft JSON).
   - Delega en `send_smtp_message(...)` ÚNICAMENTE después de confirmación exitosa.
   - Después de que `send_smtp_message(...)` retorne sin excepción (y SOLO entonces), la rama `send` registra los contactos salientes en dos delegaciones, SIN reimplementar lógica:
     1. Delega en `extract_outgoing_contacts(confirmed)` (de `src.email.outgoing_contacts`, recibiendo el draft confirmado) para derivar los contactos leyendo SOLO los destinatarios; devuelve un esquema compatible `{name, email}`.
     2. Delega el resultado UNA sola vez en `store_email_contacts(root, contacts)` (de `src.email.contact_store`) para fusionarlo y actualizar la libreta.
   - **Lista vacía:** si la extracción devuelve `[]` (draft sin destinatarios válidos), NO es un error: se delega igual una sola vez al store y la rama sigue exitosa con su única línea JSON.
   - **Fallo de la extracción o del store:** error genérico en stderr (sin contenido de excepción cruda), devuelve `1`, sin traceback, y NO imprime la línea JSON de éxito. Documentar: el SMTP ya pudo haber enviado el mensaje; el llamador NO debe reintentar automáticamente (reenviar duplicaría el correo; la libreta puede actualizarse por otra vía sin reenvío).
   - Imprime en stdout UNA línea JSON con el resultado (`{"id": "<id>", "status": "sent"}`) — solo si la actualización de contactos también terminó bien.
   - Devuelve `0`.

Códigos de salida:

| Código | Significado |
|--------|-------------|
| `0` | Operación completada, una línea JSON en stdout |
| `1` | Error operacional (draft inexistente, confirmación ausente/incorrecta, fallo de envío, fallo del store de contactos post-envío) — mensaje genérico en stderr |
| `2` | Uso incorrecto (argv vacío, subcomando desconocido, número de argumentos equivocado) — mensaje de uso genérico en stderr |

Errores genéricos: NUNCA incluir el contenido de la excepción cruda, traceback, rutas de credencial, usuario ni host SMTP en stderr. Mensajes tipo `"error: draft inexistente"`, `"error: confirmacion requerida"`, `"error: uso incorrecto"`.

## Invariants

1. **Delegación pura:** `cli_main` no implementa lógica de draft ni de SMTP; todo pasa por `create_email_draft` / `confirm_email_draft` / `send_smtp_message` y el resolvedor de credencial existente.
2. **Confirmación exacta:** `send_smtp_message` solo puede invocarse si el argumento de confirmación es la frase literal exacta Y `confirm_email_draft` aceptó el draft. Es inaceptable resolver credencial o abrir conexión antes de ambos.
3. **Secretos fuera de salida:** contraseña, token o credencial NUNCA aparecen en stdout, stderr, ni en ningún JSON persistido. El draft JSON en `ROOT/drafts/` no contiene credenciales.
4. **Credencial solo en memoria:** la credencial se resuelve en el flujo de `send`, se usa y se descarta; jamás se escribe a archivo ni a variable global persistente.
5. **JSON determinista:** el draft guardado en `ROOT/drafts/<id>.json` es byte-a-byte reproducible para los mismos datos de entrada (claves ordenadas, sin timestamps no controlados en la salida serializada más allá de lo que `create_email_draft` produzca determinísticamente).
6. **Un draft = un archivo:** `draft` con los mismos datos e id produce el mismo archivo; guardar no corrompe ni duplica: re-escribir el mismo `<id>.json` es idempotente (mismo contenido).
7. **Envío idempotente-seguro:** reenviar el mismo `DRAFT_ID` tras confirmación exitosa re-invoca `send_smtp_message` con el mismo payload (la deduplicación, si existe, es responsabilidad de la capa inferior, no de la CLI).
8. **Intactos:** `sync`, `search` y `account` (y todo lo demás en `src/email/`) no cambian; este contrato no toca sus firmas ni sus tests congelados.
9. **Adjuntos rechazados:** el MVP no soporta adjuntos. Si el draft o los argumentos contienen o sugieren adjuntos, la CLI devuelve `2` con error genérico, sin excepción cruda.
10. **Códigos y salida:** exactamente una línea JSON en stdout por operación exitosa; nada más impreso en stdout. Errores solo en stderr, genéricos.
11. **Sin excepción cruda hacia el top:** `cli_main` captura fallos operacionales y los traduce a `1`/`2` con mensaje genérico; nunca deja propagar un traceback.
12. **Orden de delegación post-envío:** `extract_outgoing_contacts(confirmed)` y `store_email_contacts(root, contacts)` se invocan estrictamente DESPUÉS de un `send_smtp_message` exitoso; nunca antes, y `store_email_contacts` se invoca EXACTAMENTE una vez por rama `send` exitosa (también cuando el resultado es una lista vacía).
13. **Extracción solo de destinatarios:** la extracción delegada lee únicamente `confirmed["to"]` (el draft confirmado) y devuelve un esquema compatible `{name, email}` con `store_email_contacts`; la deduplicación, normalización y fusión en la libreta son responsabilidad de `outgoing_contacts`/`contact_store`: la CLI no reimplementa lógica, solo delega y ordena.
14. **Fallo post-envío no retriable:** si la extracción o el store fallan, la CLI devuelve `1` con stderr genérico, sin traceback y sin la línea JSON de éxito; el mensaje documenta que el SMTP ya pudo haber enviado y que el llamador no debe reintentar automáticamente (un reenvío duplicaría el correo; la libreta puede actualizarse por otra vía sin reenvío).
15. **Puente `status` -> `confirmed=True` sin mutación:** tras `confirm_email_draft` exitoso (que fija `status == "confirmed"`), `send_smtp_message` exige `message["confirmed"] is True`; la CLI construye una copia NUEVA con los mismos campos y EXACTAMENTE `confirmed=True`, y jamás muta el draft persistido (sigue `pending`, sin clave `confirmed`) ni el dict devuelto por `confirm_email_draft` (sigue sin la clave `confirmed`).

## Examples

```python
# draft: crea y persiste el borrador, imprime el id y la ruta
cli_main(["draft", "/root/ws", "acc-1", "a@b.c", "Hola", "Cuerpo"])
# -> 0, stdout: {"id": "d-123", "path": "/root/ws/drafts/d-123.json"}

# send con confirmación exacta: envía, registra contactos salientes y
# actualiza la libreta (orden: send_smtp_message -> extract_outgoing_contacts
# -> store_email_contacts UNA vez); stdout: {"id": "d-123", "status": "sent"}
cli_main(["send", "/root/ws", "acc-1", "d-123", "CONFIRMAR ENVIO"])
# -> 0, stdout: {"id": "d-123", "status": "sent"}

# lista vacía: extract_outgoing_contacts(confirmed) -> [] NO es error;
# store_email_contacts(root, []) una sola vez y la rama sigue exitosa (0)

# fallo del store tras SMTP: -> 1, stderr genérico sin traceback;
# el SMTP ya pudo haber enviado: el llamador NO debe reintentar automáticamente

# send sin confirmación exacta: rechazo ANTES de resolver credencial o SMTP
cli_main(["send", "/root/ws", "acc-1", "d-123", "confirmar envio"])  # -> 1, stderr genérico
cli_main(["send", "/root/ws", "acc-1", "d-123", "CONFIRMAR ENVIOS"]) # -> 1, stderr genérico
cli_main(["send", "/root/ws", "acc-1", "d-123", ""])                 # -> 1, stderr genérico

# send con draft inexistente
cli_main(["send", "/root/ws", "acc-1", "no-existe", "CONFIRMAR ENVIO"])  # -> 1

# uso incorrecto
cli_main([])                                        # -> 2
cli_main(["bogus", "x"])                            # -> 2
cli_main(["draft", "/root/ws", "acc-1", "a@b.c"])   # -> 2 (faltan SUBJECT y BODY)
```

## Do / Don't

**Do**
- Delegar todo el comportamiento en `src.email.draft` y el resolvedor de credencial existente.
- Tras `confirm_email_draft` exitoso, construir una copia NUEVA del draft confirmado con EXACTAMENTE `confirmed=True` (conservando todos los campos) para pasársela a `send_smtp_message` y a `extract_outgoing_contacts`, sin mutar el original.
- Verificar la frase de confirmación EXACTA antes de tocar credencial o red.
- Registrar contactos salientes SOLO tras un `send_smtp_message` exitoso: delegar en `extract_outgoing_contacts(confirmed)` y luego en `store_email_contacts(root, contacts)` UNA sola vez (lista vacía incluida).
- Ante fallo de la extracción o del store post-envío: devolver `1` con stderr genérico y documentar que el SMTP ya pudo haber enviado (el llamador NO debe reintentar automáticamente).
- Escribir el JSON del draft con `sort_keys=True`, `indent=2`, `ensure_ascii=False`, UTF-8.
- Devolver códigos `0`/`1`/`2` según la tabla y una sola línea JSON por éxito.
- Mantener `sync`/`search`/`account` byte-idénticos.

**Don't**
- No imprimir la credencial, el traceback, el host SMTP ni el usuario en ninguna salida.
- No persistir la credencial en `ROOT/drafts/`, en el JSON del draft, ni en ningún archivo nuevo.
- No invocar `send_smtp_message` antes de la confirmación exacta + `confirm_email_draft`.
- No invocar `extract_outgoing_contacts` ni `store_email_contacts` antes de un envío exitoso, ni llamar al store más de una vez por rama.
- No reimplementar extracción, deduplicación ni fusión de contactos en la CLI: solo delegar.
- No tratar la lista vacía como error ni omitir la única llamada al store en ese caso.
- No reintentar el envío si el store falla después de SMTP: reportar `1` y salir.
- No normalizar la frase de confirmación (sin `.lower()`, sin `.strip()` de acentos, sin trim).
- No mutar el draft persistido ni el dict devuelto por `confirm_email_draft`: el puente `status -> confirmed=True` se hace sobre una copia nueva.
- No implementar adjuntos, ni aceptarlos, ni silenciarlos: devolver `2`.
- No añadir subcomandos, flags, ni tocar `sync`/`search`/`account`.
- No dejar que una excepción cruda llegue al llamante: traducirla a `1` o `2` genéricos.

## Tests

Propiedad 1 — `draft` persiste JSON determinista y devuelve una línea JSON:
```python
def test_draft_guarda_json_determinista(tmp_root):
    rc = cli_main(["draft", str(tmp_root), "acc-1", "a@b.c", "Hola", "Cuerpo"])
    assert rc == 0
    drafts = list((tmp_root / "drafts").glob("*.json"))
    assert len(drafts) == 1
    contenido = drafts[0].read_text(encoding="utf-8")
    relectura = json.loads(contenido)
    # determinista: re-escribir con los mismos datos produce el mismo byte-stream
    contenido2 = drafts[0].read_text(encoding="utf-8")
    assert contenido == contenido2
    # credencial NUNCA en el draft persistido
    assert "password" not in json.dumps(relectura).lower()
```

Propiedad 2 — `send` sin frase exacta NO toca credencial ni SMTP:
```python
def test_send_rechaza_confirmacion_inexacta(tmp_root, monkeypatch):
    cli_main(["draft", str(tmp_root), "acc-1", "a@b.c", "Hola", "Cuerpo"])
    draft_id = next((tmp_root / "drafts").glob("*.json")).stem
    llamadas = {"cred": 0, "smtp": 0}
    monkeypatch.setattr("src.email.cli.resolver_credencial", lambda *a, **k: llamadas.__setitem__("cred", llamadas["cred"] + 1) or ("u", "p"))
    monkeypatch.setattr("src.email.cli.send_smtp_message", lambda *a, **k: llamadas.__setitem__("smtp", llamadas["smtp"] + 1))
    for frase in ["confirmar envio", "CONFIRMAR ENVIOS", "", "CONFIRMAR  ENVIO", "yes"]:
        rc = cli_main(["send", str(tmp_root), "acc-1", draft_id, frase])
        assert rc == 1
    assert llamadas["cred"] == 0
    assert llamadas["smtp"] == 0
```

Propiedad 3 — `send` con confirmación exacta delega en send_smtp_message:
```python
def test_send_confirmado_delega_en_smtp(tmp_root, monkeypatch):
    cli_main(["draft", str(tmp_root), "acc-1", "a@b.c", "Hola", "Cuerpo"])
    draft_id = next((tmp_root / "drafts").glob("*.json")).stem
    llamadas = {"smtp": 0}
    monkeypatch.setattr("src.email.cli.resolver_credencial", lambda *a, **k: ("u", "p"))
    monkeypatch.setattr("src.email.cli.send_smtp_message", lambda *a, **k: llamadas.__setitem__("smtp", llamadas["smtp"] + 1) or {"ok": True})
    rc = cli_main(["send", str(tmp_root), "acc-1", draft_id, "CONFIRMAR ENVIO"])
    assert rc == 0
    assert llamadas["smtp"] == 1
```

Propiedad 4 — códigos de uso incorrecto e inexistencia:
```python
def test_codigos_uso_y_existencia(tmp_root):
    assert cli_main([]) == 2
    assert cli_main(["bogus"]) == 2
    assert cli_main(["draft", str(tmp_root), "acc-1", "a@b.c", "s"]) == 2
    assert cli_main(["send", str(tmp_root), "acc-1", "falta", "CONFIRMAR ENVIO"]) == 1
```

Propiedad 5 — secretos nunca en salida:
```python
def test_secretos_no_en_salida(tmp_root, capsys, monkeypatch):
    secreto = "S3CR3T0-CLAVE"
    monkeypatch.setattr("src.email.cli.resolver_credencial", lambda *a, **k: ("user@x", secreto))
    cli_main(["draft", str(tmp_root), "acc-1", "a@b.c", "Hola", "Cuerpo"])
    draft_id = next((tmp_root / "drafts").glob("*.json")).stem
    monkeypatch.setattr("src.email.cli.send_smtp_message", lambda *a, **k: {"ok": True})
    rc = cli_main(["send", str(tmp_root), "acc-1", draft_id, "CONFIRMAR ENVIO"])
    capturado = capsys.readouterr()
    assert rc == 0
    assert secreto not in capturado.out
    assert secreto not in capturado.err
    for f in (tmp_root / "drafts").glob("*.json"):
        assert secreto not in f.read_text(encoding="utf-8")
```

Propiedad 6 — intactos (regresión):
```python
def test_sync_search_account_intactos():
    import src.email.sync as sync_mod
    import src.email.search as search_mod
    import src.email.account as account_mod
    # sus funciones exportadas existentes siguen presentes con la misma firma pública
    for mod, fns in ((sync_mod, ["sync_mail"]), (search_mod, ["search_messages"]), (account_mod, ["load_account"])):
        for fn in fns:
            assert hasattr(mod, fn)
```

Propiedad 7 — tras un envío exitoso, delega en orden y llama al store UNA vez:
```python
def test_send_exitoso_delega_contactos_en_orden(cli, tmp_root, monkeypatch, capsys):
    # stubs que registran secuencia: smtp -> extract -> store(UNA vez)
    secuencia, stores = [], []
    monkeypatch.setattr(cli, "send_smtp_message", lambda *a: secuencia.append("smtp"))
    monkeypatch.setattr(cli, "extract_outgoing_contacts", lambda m: secuencia.append(("extract", m["to"])) or [{"name": "A", "email": "a@b.c"}])
    monkeypatch.setattr(cli, "store_email_contacts", lambda root, cs: stores.append((root, cs)) or 1)
    cli.cli_main(["draft", str(tmp_root), "acc-1", "a@b.c", "Hola", "Cuerpo"])
    draft_id = next((tmp_root / "drafts").glob("*.json")).stem
    capsys.readouterr()
    rc = cli.cli_main(["send", str(tmp_root), "acc-1", draft_id, "CONFIRMAR ENVIO"])
    assert rc == 0
    assert secuencia == ["smtp", ("extract", ["a@b.c"])]
    assert len(stores) == 1 and stores[0][1] == [{"name": "A", "email": "a@b.c"}]
    lineas = [ln for ln in capsys.readouterr().out.splitlines() if ln.strip()]
    assert json.loads(lineas[0]) == {"id": draft_id, "status": "sent"}
```

Propiedad 8 — lista vacía: store([]) una vez y éxito sin cambio de salida:
```python
def test_send_lista_vacia_no_es_error(cli, tmp_root, monkeypatch, capsys):
    stores = []
    monkeypatch.setattr(cli, "send_smtp_message", lambda *a: None)
    monkeypatch.setattr(cli, "extract_outgoing_contacts", lambda m: [])
    monkeypatch.setattr(cli, "store_email_contacts", lambda root, cs: stores.append((root, cs)) or 0)
    cli.cli_main(["draft", str(tmp_root), "acc-1", "a@b.c", "Hola", "Cuerpo"])
    draft_id = next((tmp_root / "drafts").glob("*.json")).stem
    rc = cli.cli_main(["send", str(tmp_root), "acc-1", draft_id, "CONFIRMAR ENVIO"])
    assert rc == 0
    assert stores == [(str(tmp_root), [])]
```

Propiedad 9 — fallo del store tras SMTP: 1, stderr genérico, sin traceback:
```python
def test_fallo_del_store_tras_smtp(cli, tmp_root, monkeypatch, capsys):
    def romper(root, cs):
        raise RuntimeError("boom")
    monkeypatch.setattr(cli, "send_smtp_message", lambda *a: None)
    monkeypatch.setattr(cli, "extract_outgoing_contacts", lambda m: [{"name": "A", "email": "a@b.c"}])
    monkeypatch.setattr(cli, "store_email_contacts", romper)
    cli.cli_main(["draft", str(tmp_root), "acc-1", "a@b.c", "Hola", "Cuerpo"])
    draft_id = next((tmp_root / "drafts").glob("*.json")).stem
    rc = cli.cli_main(["send", str(tmp_root), "acc-1", draft_id, "CONFIRMAR ENVIO"])
    capturado = capsys.readouterr()
    assert rc == 1
    assert "sent" not in capturado.out          # sin línea de éxito
    assert "traceback" not in capturado.err.lower()
    assert "boom" not in capturado.err          # sin excepción cruda
```

Propiedad 10 — el mensaje entregado a SMTP lleva `confirmed is True` y nada se muta:
```python
def test_mensaje_para_smtp_confirmed_true_sin_mutar(cli, tmp_root, monkeypatch):
    confirmada_original = {}
    confirm_real = cli.confirm_email_draft
    def envoltorio_confirm(draft, frase):
        resultado = confirm_real(draft, frase)
        confirmada_original["objeto"] = resultado
        confirmada_original["copia_antes"] = copy.deepcopy(resultado)
        return resultado
    monkeypatch.setattr(cli, "confirm_email_draft", envoltorio_confirm)
    recibidos = []
    monkeypatch.setattr(cli, "send_smtp_message", lambda a, c, m: recibidos.append(m))
    cli.cli_main(["draft", str(tmp_root), "acc-1", "a@b.c", "Hola", "Cuerpo"])
    draft_id = next((tmp_root / "drafts").glob("*.json")).stem
    rc = cli.cli_main(["send", str(tmp_root), "acc-1", draft_id, "CONFIRMAR ENVIO"])
    assert rc == 0
    mensaje = recibidos[0]
    assert mensaje.get("confirmed") is True       # puente status -> confirmed=True
    assert mensaje.get("status") == "confirmed"
    for clave, valor in confirmada_original["copia_antes"].items():
        assert mensaje.get(clave) == valor         # conserva todos los campos
    assert mensaje is not confirmada_original["objeto"]   # copia nueva
    assert "confirmed" not in confirmada_original["objeto"]  # original intacto
    draft_en_disco = json.loads(
        (tmp_root / "drafts" / (draft_id + ".json")).read_text(encoding="utf-8")
    )
    assert draft_en_disco["status"] == "pending" and "confirmed" not in draft_en_disco
```

## Constraints

- Lenguaje: Python 3 stdlib puro; sin dependencias de terceros nuevas.
- No modificar archivos distintos de `src/email/cli.py` (ni sus tests congelados de `sync`/`search`/`account`).
- Sin adjuntos en el MVP: rechazados con código `2`.
- Sin persistencia de credenciales: memoria solamente.
- Sin reintento automático tras un fallo del store post-envío: el SMTP ya pudo haber enviado; reportar `1` y salir.
- Sin timestamps no deterministas añadidos por la CLI a la salida serializada.
- Sin excepciones crudas hacia el llamante: siempre `0`/`1`/`2` con salida limpia.
- Complejidad ciclomática de `cli_main` ≤ 8; si el parsing supera ese límite, extraer sub-funciones de parseo con su propio contrato, no engordar `cli_main`.
- Si el gate o el test congelado exige cambiar una firma de `src.email.draft` o de `sync`/`search`/`account`, PARAR y reportar si el conflicto es de firma, de dependencia o de entorno; no adaptar silenciosamente.