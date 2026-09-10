---
task: persist-conversation-index
intent: persistir el índice Markdown de una conversación derivado del record mediante conversation_key
target: ../../../../src/email/conversation_index.py
signature: "def persist_conversation_index(root: str, record: dict, message_path: str) -> str"
language: python
budget:
  cyclomatic_max: 12
  nesting_max: 3
  lines_max: 90
  params_max: 3
deps_allowed: [os, pathlib, re]
forbids: [eval, exec, subprocess, network_access, pickle, socket]
---

## Intent

`persist_conversation_index(root: str, record: dict, message_path: str) -> str` calcula la clave de
conversación del `record` (delegando SIEMPRE en `src.email.conversation.conversation_key`) y
persiste/actualiza un nodo Markdown determinista en `root/store/conversations/<key>.md` que mantiene
la lista ordenada y deduplicada de `message_path` de esa conversación. Devuelve la ruta absoluta
normalizada del nodo escrito. Es el índice de hilos del store; NO clasifica temas.

## Interface

`def persist_conversation_index(root: str, record: dict, message_path: str) -> str`

- `root`: raíz explícita del store (directorio que debe existir). Bajo ella se usa SIEMPRE
  `store/conversations/<key>.md`, con `<key>` = salida de `conversation_key(record)`.
- `record`: dict de email ya parseado (mismas claves que consume `conversation_key`:
  `references`, `in_reply_to`, `message_id`, `subject`, `from`, `to`, `cc`). No se interpreta nada más.
- `message_path`: str no vacío con la ruta del nodo de mensaje a registrar (p. ej.
  `store/emails/msg-0001.md`). Se normaliza a separadores `/` antes de almacenar.
- Devuelve: `str` — ruta absoluta normalizada del nodo de conversación escrito.
- Lanza: `ValueError` si `root` no es un directorio existente, si `record` no es dict, o si
  `message_path` está vacío/solo espacios o contiene `\x00`; `OSError` propagada si el sistema de
  archivos falla; `ValueError` si el nodo existente no matchea el formato esperado.

Formato del nodo (determinista, byte a byte para la misma lista):

```markdown
---
type: Conversation
conversation_key: <64 hex>
message_count: 2
---
- store/emails/msg-0001.md
- store/emails/msg-0007.md
```

## Invariants

- **Delegación de la clave**: la clave SIEMPRE sale de `src.email.conversation.conversation_key(record)`;
  este módulo no reimplementa ni recalcula hashing, ni derivan la clave de subject/participantes.
- **Ubicación fija**: el nodo vive exactamente en `<root>/store/conversations/<key>.md`. `<key>` es
  sha256 hex de 64 chars (invariante del contrato `conversation-key`), por lo que la ruta es
  intrínsecamente segura: nunca contiene separadores, `..` ni caracteres fuera de `[0-9a-f]`.
- **Raíz explícita**: no hay raíz implícita, ni cwd, ni `~`, ni variables de entorno para resolver
  `root`; si `root` no existe como directorio se lanza `ValueError` antes de escribir nada.
- **Lista ordenada y deduplicada**: el cuerpo del nodo contiene una entrada `- <message_path>` por
  mensaje, con separadores normalizados a `/`, sin duplicados, ordenadas ascendentemente
  (sorted lexicográfico). El mismo conjunto de paths produce SIEMPRE el mismo archivo.
- **Fusión con lo existente**: si el nodo ya existe, se leen sus entradas válidas, se hace unión con
  la nueva, se deduplica, se ordena y se reescribe completo. Añadir un path ya presente NO cambia el
  archivo (idempotencia) ni duplica entradas.
- **Frontmatter invariable**: `type: Conversation` y `conversation_key: <key>` SIEMPRE presentes;
  `message_count` = número de entradas de la lista. Nunca se escriben `subject`, participantes,
  cuerpo, `raw`, bytes ni secretos: solo la clave-hash y las rutas de nodos.
- **Escritura atómica**: se escribe a un fichero temporal en el mismo directorio y se hace
  `os.replace`; nunca queda un nodo a medio escribir ni escrituras parciales tras fallo.
- **No mutación / pureza de entrada**: `record` queda idéntico tras la llamada; sin red, sin
  subprocess, sin leer el fichero de mensaje apuntado por `message_path` (solo se almacena su ruta).
- **Sin clasificación temática**: no se añaden etiquetas, resúmenes ni metadatos de tema. Eso vive en
  otro módulo futuro; este nodo es solo el índice de rutas del hilo.
- **Determinismo**: sin fechas, sin orden de ingesta en la salida, sin aleatoriedad, sin estado global.

## Examples

- `persist_conversation_index("store", record_con_refs, "store/emails/msg-0001.md")` escribe/actualiza
  `store/store/conversations/<key>.md` y devuelve su ruta absoluta.
- Segunda llamada con `message_path="store\\emails\\msg-0002.md"` y el mismo `record`: el nodo pasa a
  contener `- store/emails/msg-0001.md` y `- store/emails/msg-0002.md` (barra normalizada, ordenada).
- Repetir la misma llamada exacta: el archivo queda byte a byte idéntico (idempotencia, sin duplicado).
- Dos records de la misma conversación (misma `conversation_key`) apuntan al MISMO nodo.
- `persist_conversation_index("no-existe", record, "a.md")` → `ValueError` (raíz inexistente).
- `persist_conversation_index(root, {}, "")` → `ValueError` (`message_path` vacío).
- `persist_conversation_index(root, record, "a\x00b.md")` → `ValueError` (byte nulo).
- Si el nodo existente fue editado a mano y ya no matchea el formato (sin frontmatter `type:
  Conversation` o sin líneas `- <path>`): `ValueError` y el archivo NO se sobreescribe.

## Do / Don't

**Do**
- Importar y llamar `conversation_key` desde `src.email.conversation` para la clave.
- Validar `root` (directorio existente), `record` (dict) y `message_path` antes de tocar disco.
- Fusionar leyendo el nodo existente, deduplicar con set y ordenar con `sorted` antes de reescribir.
- Escribir de forma atómica (temporal en el mismo directorio + `os.replace`); crear
  `store/conversations/` si falta.
- Normalizar separadores de `message_path` a `/` para determinismo multiplataforma.

**Don't**
- No recalcules la clave ni la derives de otra forma; delega en `conversation_key`.
- No escribas `subject`, participantes, cuerpo, `raw`, bytes del mensaje ni credenciales/secretos en
  el nodo: solo `type`, `conversation_key`, `message_count` y las rutas.
- No hagas red, no leas el mensaje apuntado por `message_path`, no mutes `record`.
- No uses una raíz implícita ni aceptes `root` vacío/`None`.
- No añadas clasificación temática, etiquetas ni resúmenes (fuera de alcance del MVP).
- No dejes escrituras parciales ni sobrescribas un nodo existente que no matchee el formato.

## Tests

Property-tests congelados (oráculo independiente, sin importar el target):

```python
import hashlib, os, re

def _node_text(key, paths):
    head = (f"---\ntype: Conversation\nconversation_key: {key}\n"
            f"message_count: {len(paths)}\n---\n")
    return head + "".join(f"- {p}\n" for p in sorted(set(paths)))

def test_nodo_formato_y_ubicacion(tmp_root, record):
    out = persist_conversation_index(str(tmp_root), record, "store/emails/a.md")
    key = hashlib.sha256(b"x").hexdigest()  # clave esperada via conversation_key real en el oráculo
    expected = tmp_root / "store" / "conversations" / f"{key}.md"
    assert out == str(expected.resolve())
    text = expected.read_text(encoding="utf-8")
    assert re.search(r"^type: Conversation$", text, re.M)
    assert re.search(rf"^conversation_key: [0-9a-f]{{64}}$", text, re.M)
    assert text == _node_text(key, ["store/emails/a.md"])

def test_fusion_dedupe_orden_idempotencia(tmp_root, record):
    k = _key(record)
    node = tmp_root / "store" / "conversations" / f"{k}.md"
    persist_conversation_index(str(tmp_root), record, "store/emails/b.md")
    persist_conversation_index(str(tmp_root), record, "store/emails/a.md")
    persist_conversation_index(str(tmp_root), record, "store\\emails\\a.md")  # mismo, ya presente
    body = node.read_text(encoding="utf-8")
    assert body == _node_text(k, ["store/emails/a.md", "store/emails/b.md"])

def test_no_mutacion_y_sin_secretos(tmp_root, record_con_subject):
    snapshot = repr(record_con_subject)
    out = persist_conversation_index(str(tmp_root), record_con_subject, "store/emails/a.md")
    text = open(out, encoding="utf-8").read()
    assert repr(record_con_subject) == snapshot
    assert record_con_subject["subject"] not in text
    assert "raw" not in text and "password" not in text

def test_errores(tmp_root, record):
    with pytest.raises(ValueError): persist_conversation_index("no-existe", record, "a.md")
    with pytest.raises(ValueError): persist_conversation_index(str(tmp_root), {}, "")
    with pytest.raises(ValueError): persist_conversation_index(str(tmp_root), record, "a\x00b.md")
    with pytest.raises(ValueError): persist_conversation_index(str(tmp_root), "no-dict", "a.md")

def test_escritura_atomica_sin_parciales(tmp_root, record, monkeypatch):
    # si os.replace falla, no debe quedar contenido parcial en el nodo definitivo
    def boom(src, dst): raise OSError("disco lleno")
    monkeypatch.setattr(os, "replace", boom)
    with pytest.raises(OSError):
        persist_conversation_index(str(tmp_root), record, "store/emails/a.md")
    assert not (tmp_root / "store" / "conversations").glob("*.tmp")
```

## Constraints

- Presupuestos: ciclomática ≤ 12, anidamiento ≤ 3, líneas ≤ 90, parámetros ≤ 3.
- Solo dependencias de `deps_allowed` (`os`, `pathlib`, `re`); cero terceros (anti-slopsquatting).
- Prohibido: `eval`, `exec`, `subprocess`, red, `pickle`; leer o embeber el contenido del mensaje;
  escribir `raw`/bytes/secretos; fechas o marcas de ingesta en el nodo.
- Rendimiento: O(n) sobre el número de entradas del nodo; sin estado global ni locks.
- Límites del MVP: sin fusión de hilos que cambian de clave a mitad de cadena, sin clasificación
  temática, sin índice global de conversaciones (cada nodo es autosuficiente), sin concurrencia
  multi-proceso garantizada (escritura atómica por fichero).

## PARAR y reportar si

- `src.email.conversation.conversation_key` no existe o su firma difiere de
  `def conversation_key(record: dict) -> str` → PARAR y reportar antes de implementar.
- La estructura real del store difiere (`root/store/conversations/` no es la ubicación pactada, o
  existe ya otro índice de conversaciones con formato distinto) → PARAR y reportar.
- `message_path` en el proyecto no es una ruta relativa al store (p. ej. rutas absolutas o IDs) →
  PARAR y reportar el formato real antes de fijar la normalización.
- Alguna regla de Invariants resulta insatisfacible en código (p. ej. complejidad > umbral, o la
  validación del formato del nodo existente excede el presupuesto) → PARAR y pedir excepción, no
  improvisar.
- El `record` real no trae las claves que consume `conversation_key` → PARAR y reportar los nombres
  reales.