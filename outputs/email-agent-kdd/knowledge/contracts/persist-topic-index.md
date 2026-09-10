---
task: persist-topic-index
intent: persistir el índice Markdown de temas de un record delegando en extract_topics
target: ../../../../src/email/topic_index.py
signature: "def persist_topic_index(root: str, record: dict, message_path: str) -> int"
language: python
budget:
  cyclomatic_max: 12
  nesting_max: 3
  lines_max: 90
  params_max: 3
deps_allowed: [os, pathlib, re]
forbids: [eval, exec, subprocess, network_access, pickle, socket]
tests_frozen: true
stop_rule: "PARAR y reportar si src.email.topics.extract_topics no existe con la firma esperada, si la estructura del store difiere de root/store/topics/ o si algún invariant resulta insatisfacible dentro del presupuesto."
---

## Intent

`persist_topic_index(root: str, record: dict, message_path: str) -> int` calcula los temas del
`record` (delegando SIEMPRE en `src.email.topics.extract_topics(record)`) y, por cada tema seguro,
crea o actualiza el nodo Markdown en `root/store/topics/<topic>.md` que mantiene la lista ordenada,
normalizada y deduplicada de `message_path` asociada a ese tema. Devuelve la cantidad de temas
actualizados (nodos escritos). Es el índice temático del store; NO clasifica semánticamente ni
clasifica por conversación (eso vive en `persist_conversation_index`).

## Interface

`def persist_topic_index(root: str, record: dict, message_path: str) -> int`

- `root`: raíz explícita del store (directorio que debe existir). Bajo ella se usa SIEMPRE
  `store/topics/<topic>.md`, con `<topic>` = cada tema seguro devuelto por `extract_topics(record)`.
- `record`: dict de email ya parseado. Este módulo solo lo pasa a `extract_topics`; no interpreta
  ninguna clave por sí mismo.
- `message_path`: str no vacío con la ruta del nodo de mensaje a registrar (p. ej.
  `store/emails/msg-0001.md`). Se normaliza a separadores `/` antes de almacenar.
- Devuelve: `int` — número de temas seguros procesados, igual al número de nodos escritos por esta
  llamada (cada tema seguro implica exactamente una reescritura de su nodo, aunque el resultado sea
  byte a byte idéntico al anterior). `0` si `extract_topics` devuelve `[]` o ningún tema es seguro.
- Lanza: `ValueError` si `root` no es un directorio existente, si `record` no es dict, o si
  `message_path` está vacío/solo espacios o contiene `\x00`; `OSError` propagada si el sistema de
  archivos falla; `ValueError` si un nodo existente no matchea el formato esperado.

Formato del nodo (determinista, byte a byte para la misma lista):

```markdown
---
type: Topic
topic: factura
message_count: 2
---
- store/emails/msg-0001.md
- store/emails/msg-0007.md
```

## Invariants

- **Delegación de los temas**: los temas SIEMPRE salen de `src.email.topics.extract_topics(record)`;
  este módulo no tokeniza, no normaliza y no recorta: ya vienen normalizados (casefold), deduplicados,
  ordenados y limitados a 12 por el contrato `extract-topics`. Aquí no se re-derivan del asunto ni de
  ninguna otra clave.
- **Seguridad del nombre de tema**: un tema es seguro solo si es un único componente de fichero
  válido: no vacío, sin separadores (`/`, `\`), sin `..`, sin `\x00` y matcheando `^\w{1,64}$`
  (Unicode, mismo criterio de `extract_topics`). Los temas inseguros se IGNORAN (no lanzan), nunca se
  usan para construir rutas.
- **Ubicación fija**: cada nodo vive exactamente en `<root>/store/topics/<topic>.md`; nunca fuera de
  ese directorio ni con subdirectorios derivados del tema.
- **Raíz explícita**: no hay raíz implícita, ni cwd, ni `~`, ni variables de entorno para resolver
  `root`; si `root` no existe como directorio se lanza `ValueError` antes de escribir nada.
- **Lista ordenada, normalizada y deduplicada**: el cuerpo del nodo contiene una entrada
  `- <message_path>` por mensaje, con separadores normalizados a `/`, sin duplicados, ordenadas
  ascendentemente (sorted lexicográfico). El mismo conjunto de paths produce SIEMPRE el mismo archivo.
- **Fusión idempotente**: si el nodo ya existe, se leen sus entradas válidas, se hace unión con la
  nueva, se deduplica, se ordena y se reescribe completo. Añadir un path ya presente NO cambia el
  archivo byte a byte (idempotencia) ni duplica entradas.
- **Frontmatter invariable**: `type: Topic` y `topic: <tema>` SIEMPRE presentes y coherentes con el
  nombre de fichero; `message_count` = número de entradas de la lista. Nunca se escriben `subject`,
  participantes, cuerpo, `raw`, bytes ni secretos: solo el tema y las rutas de nodos.
- **Escritura atómica**: se escribe a un fichero temporal en el mismo directorio y se hace
  `os.replace`; nunca queda un nodo a medio escribir ni escrituras parciales tras fallo.
- **No mutación / pureza de entrada**: `record` queda idéntico tras la llamada; sin red, sin
  subprocess, sin leer el fichero de mensaje apuntado por `message_path` (solo se almacena su ruta).
- **Sin enriquecimiento**: no se añaden puntuaciones, resúmenes, fechas ni metadatos adicionales.
  Este nodo es solo el índice de rutas del tema.
- **Determinismo**: sin fechas, sin orden de ingesta en la salida, sin aleatoriedad, sin estado global.

## Examples

- `persist_topic_index("store", {"subject": "Re: Factura 123"}, "store/emails/msg-0001.md")` crea
  `store/store/topics/factura.md` y `store/store/topics/123.md` y devuelve `2`.
- Segunda llamada con `message_path="store\\emails\\msg-0002.md"` y el mismo `record`: cada nodo pasa
  a contener `- store/emails/msg-0001.md` y `- store/emails/msg-0002.md` (barra normalizada, ordenada)
  y devuelve `2` de nuevo.
- Repetir la misma llamada exacta: cada archivo queda byte a byte idéntico (idempotencia, sin
  duplicado) y devuelve `2` (el conteo es de temas procesados, no de cambios efectivos).
- Un `record` cuyo asunto no produce temas (`{"subject": ""}`): devuelve `0`, no se crea
  `store/topics/` ni ningún nodo.
- Un tema de más de 64 chars o con separador (no puede salir de `extract_topics`, pero por defensa):
  se ignora y no cuenta en el retorno.
- Dos records con el mismo asunto normalizado apuntan al MISMO nodo de tema.
- `persist_topic_index("no-existe", record, "a.md")` → `ValueError` (raíz inexistente).
- `persist_topic_index(root, "no-dict", "a.md")` → `ValueError` (`record` no es dict).
- `persist_topic_index(root, {}, "")` → `ValueError` (`message_path` vacío).
- `persist_topic_index(root, record, "a\x00b.md")` → `ValueError` (byte nulo).
- Si un nodo existente fue editado a mano y ya no matchea el formato (sin frontmatter `type: Topic`,
  `topic:` distinto del nombre de fichero, o sin líneas `- <path>`): `ValueError` y ese archivo NO se
  sobreescribe.

## Do / Don't

**Do**
- Importar y llamar `extract_topics` desde `src.email.topics` para obtener los temas.
- Validar `root` (directorio existente), `record` (dict) y `message_path` antes de tocar disco.
- Filtrar cada tema con la regla de seguridad (`^\w{1,64}$`, sin separadores ni `..`) antes de
  construir su ruta.
- Fusionar leyendo el nodo existente, deduplicar con set y ordenar con `sorted` antes de reescribir.
- Escribir de forma atómica (temporal en el mismo directorio + `os.replace`); crear `store/topics/`
  si falta.
- Normalizar separadores de `message_path` a `/` para determinismo multiplataforma.

**Don't**
- No reimplementes la extracción ni normalices temas aquí; delega en `extract_topics`.
- No escribas `subject`, participantes, cuerpo, `raw`, bytes del mensaje ni credenciales/secretos en
  el nodo: solo `type`, `topic`, `message_count` y las rutas.
- No hagas red, no leas el mensaje apuntado por `message_path`, no mutes `record`.
- No uses una raíz implícita ni aceptes `root` vacío/`None`.
- No uses el tema como categoría semántica ni añadas puntuaciones, etiquetas adicionales o fechas
  (fuera de alcance del MVP).
- No dejes escrituras parciales ni sobrescribas un nodo existente que no matchee el formato.

## Tests

Property-tests congelados (oráculo independiente, sin importar el target):

```python
# tests/email/test_topic_index.py
import pytest

from src.email.topic_index import persist_topic_index


def _node_text(topic, paths):
    head = (f"---\ntype: Topic\ntopic: {topic}\n"
            f"message_count: {len(paths)}\n---\n")
    return head + "".join(f"- {p}\n" for p in sorted(set(paths)))


def test_nodos_formato_y_ubicacion(tmp_root):
    n = persist_topic_index(str(tmp_root), {"subject": "Re: Factura 123"}, "store/emails/a.md")
    assert n == 2  # ["123", "factura"] según extract-topics
    for topic in ("123", "factura"):
        node = tmp_root / "store" / "topics" / f"{topic}.md"
        assert node.exists()
        assert node.read_text(encoding="utf-8") == _node_text(topic, ["store/emails/a.md"])


def test_fusion_dedupe_orden_idempotencia(tmp_root):
    persist_topic_index(str(tmp_root), {"subject": "informe"}, "store/emails/b.md")
    persist_topic_index(str(tmp_root), {"subject": "informe"}, "store/emails/a.md")
    persist_topic_index(str(tmp_root), {"subject": "informe"}, "store\\emails\\a.md")  # ya presente
    node = tmp_root / "store" / "topics" / "informe.md"
    assert node.read_text(encoding="utf-8") == _node_text(
        "informe", ["store/emails/a.md", "store/emails/b.md"]
    )


def test_sin_temas_retorna_cero_y_no_crea_nada(tmp_root):
    n = persist_topic_index(str(tmp_root), {"subject": ""}, "store/emails/a.md")
    assert n == 0
    assert not (tmp_root / "store" / "topics").exists()


def test_no_mutacion_y_sin_secretos(tmp_root):
    record = {"subject": "Re: Factura", "body": "SECRETO"}
    snapshot = repr(record)
    n = persist_topic_index(str(tmp_root), record, "store/emails/a.md")
    assert n == 1
    assert repr(record) == snapshot
    text = (tmp_root / "store" / "topics" / "factura.md").read_text(encoding="utf-8")
    assert "SECRETO" not in text and "password" not in text


def test_errores(tmp_root):
    record = {"subject": "dato"}
    with pytest.raises(ValueError): persist_topic_index("no-existe", record, "a.md")
    with pytest.raises(ValueError): persist_topic_index(str(tmp_root), "no-dict", "a.md")
    with pytest.raises(ValueError): persist_topic_index(str(tmp_root), {}, "")
    with pytest.raises(ValueError): persist_topic_index(str(tmp_root), record, "a\x00b.md")


def test_escritura_atomica_sin_parciales(tmp_root, monkeypatch):
    def boom(src, dst): raise OSError("disco lleno")
    monkeypatch.setattr(os, "replace", boom)
    with pytest.raises(OSError):
        persist_topic_index(str(tmp_root), {"subject": "dato"}, "store/emails/a.md")
    assert not list((tmp_root / "store" / "topics").glob("*.tmp"))
```

## Constraints

- Presupuestos: ciclomática ≤ 12, anidamiento ≤ 3, líneas ≤ 90, parámetros ≤ 3.
- Solo dependencias de `deps_allowed` (`os`, `pathlib`, `re`); cero terceros (anti-slopsquatting).
- Prohibido: `eval`, `exec`, `subprocess`, red, `pickle`; leer o embeber el contenido del mensaje;
  escribir `raw`/bytes/secretos; fechas o marcas de ingesta en el nodo.
- Rendimiento: O(n) sobre el número de entradas por nodo; sin estado global ni locks.
- Límites del MVP: sin fusión de temas (sin renombrado ni consolidación de nodos), sin puntuación ni
  relevancia, sin índice global de temas (cada nodo es autosuficiente), sin concurrencia
  multi-proceso garantizada (escritura atómica por fichero).

## PARAR y reportar si

- `src.email.topics.extract_topics` no existe o su firma difiere de `def extract_topics(record: dict)
  -> list[str]` → PARAR y reportar antes de implementar.
- La estructura real del store difiere (`root/store/topics/` no es la ubicación pactada, o existe ya
  otro índice de temas con formato distinto) → PARAR y reportar.
- Los temas reales de `extract_topics` no cumplen la regla de seguridad (contienen separadores, `..`,
  superan 64 chars) de forma sistemática → PARAR y reportar en lugar de silenciarlos por diseño.
- `message_path` en el proyecto no es una ruta relativa al store (rutas absolutas o IDs) → PARAR y
  reportar el formato real antes de fijar la normalización.
- Alguna regla de Invariants resulta insatisfacible en código (p. ej. complejidad > umbral, o la
  validación del formato del nodo existente excede el presupuesto) → PARAR y pedir excepción, no
  improvisar.
- El `record` real no trae `subject` con la semántica que consume `extract_topics` → PARAR y reportar
  los nombres reales.