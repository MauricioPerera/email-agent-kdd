---
task: conversation-key
intent: Derivar una clave de conversación estable y segura para ruta a partir de un record de email.
target: ../../../../src/email/conversation.py
signature: "def conversation_key(record: dict) -> str"
language: python
budget:
  max_complexity: 10
  max_nesting: 3
  max_params: 1
tests_frozen: true
---

## Intent

`conversation_key(record: dict) -> str` devuelve, para un record de email ya parseado, una clave
determinista que agrupa el email en su conversación (hilo). La clave es estable entre corridas y
segura para usarla como componente de ruta de fichero/directorio (hexadecimal, sin separadores).

## Interface

- Entrada: `record: dict` — un solo email con claves opcionales:
  - `message_id: str` (puede faltar, venir vacío o con espacios/ángulos `<...>`)
  - `in_reply_to: str` (opcional, mismas tolerancias)
  - `references: str | list[str]` (opcional; si es lista, varios IDs)
  - `subject: str` (puede faltar o venir vacío)
  - `from: str`, `to: str | list[str]`, `cc: str | list[str]` (participantes; pueden faltar)
- Salida: `str` — sha256 hexadecimal minúscula de 64 caracteres (hex del digest, sin prefijo `0x`,
  sin `/`, `\`, `:`, espacios ni `..`), seguro como segmento de ruta.
- Metadatos temáticos: FUERA de esta función. En MVP, si se desea adjuntar metadatos, la lista va
  SIEMPRE vacía (`[]`) — la futura clasificación temática vive en otro módulo y no se implementa aquí.
- No persiste nada, no muta `record`, no toca red, no lee ficheros, no importa un modelo externo.
- Función pura: misma entrada → misma salida, siempre.

## Invariants

1. **Prioridad de enlace**: si `in_reply_to` o `references` existen y normalizan a algo no vacío, la
   clave se deriva de ese(os) identificador(es) normalizado(s) — nunca de `subject` ni participantes.
2. **Segunda prioridad**: si no hay `References` ni `In-Reply-To`, se usa `message_id` normalizado.
3. **Fallback determinista**: si tampoco hay `message_id`, la clave se deriva de:
   subject normalizado (sin prefijos `Re:`, `Fwd:`, `Rv:` — repetidos y con espacios/case
   arbitrarios — y con espacios colapsados) + combinación ORDENADA (sorted, sin duplicados) de los
   emails de los participantes (`from` + `to` + `cc`, normalizados a minúsculas). Nunca fecha, ni
   orden de ingesta, ni contenido del cuerpo, ni un modelo externo.
4. **Normalización de IDs**: `"<abc@x>"`, `"abc@x"`, `" abc@x "` → mismo valor; el prefijo
   `Re: RE: Fwd: Re:` del subject colapsa al mismo subject base; la comparación es insensible a
   mayúsculas en lo necesario para que equivalentes den la MISMA clave.
5. **Estabilidad**: dos llamadas con records equivalentes (difieren solo en case de IDs, ángulos,
   espacios, orden de la lista `references`) devuelven la MISMA clave. La misma cadena de entrada en
   cualquier momento del futuro devuelve la misma clave (sin salt, sin fecha, sin aleatorio).
6. **Seguridad de ruta**: la salida SIEMPRE matchea `^[0-9a-f]{64}$` — nunca contiene separadores,
   `..`, UTF-8 raro ni longitud variable.
7. **No mutación**: tras la llamada, `record` es idéntico byte a byte (misma profundidad, mismas
   claves, mismos valores). No se escribe en disco ni se abre socket.
8. **Degradación**: cualquier campo ausente, `None`, vacío o con basura no lanza excepción — se
   salta ese campo y el algoritmo cae al siguiente nivel de prioridad. El record mínimo `{}` produce
   una clave válida (fallback con subject vacío y sin participantes).
9. **Metadatos**: la función no devuelve metadatos; el MVP no clasifica temas (lista vacía por
   convención en el llamador). Fuera de alcance.

## Examples

Casos congelados (oráculo independiente, sin importar el target):

```python
# E1 — References presente: gana sobre todo lo demás
conversation_key({"references": "<a@x>", "message_id": "<b@x>", "subject": "Hola"})
# == conversation_key({"references": "<a@x>", "subject": "Otro asunto"})  (misma clave)

# E2 — In-Reply-To presente, sin References
conversation_key({"in_reply_to": "<r@y>", "subject": "Re: Hola"})
# == conversation_key({"in_reply_to": "r@y", "subject": "Fwd: Hola"})  (misma clave; ángulos/case no importan)

# E3 — Sólo Message-ID
conversation_key({"message_id": "<m1@z>", "subject": "Presupuesto"})
# == conversation_key({"message_id": "m1@z"})  (misma clave, subject irrelevante)

# E4 — Fallback por subject + participantes
conversation_key({"subject": "Re: Re: FWD: Presupuesto Q3", "from": "Ana@X.com", "to": ["bob@y.com"]})
# == conversation_key({"subject": "Presupuesto Q3", "from": "ana@x.com", "to": "BOB@Y.COM"})  (misma clave)

# E5 — Fallback: orden/duplicados de participantes irrelevante
conversation_key({"subject": "S", "from": "a@x", "to": ["b@y", "a@x"]})
# == conversation_key({"subject": "S", "from": "a@x", "to": ["a@x", "b@y", "b@y"]})

# E6 — Record mínimo
conversation_key({})  # -> str de 64 hex minúsculas, válido como ruta

# E7 — Formatos basura no lanzan
conversation_key({"references": "   ", "message_id": None, "subject": "", "to": []})  # clave válida

# E8 — No mutación
r = {"subject": "Hola", "to": ["a@x"]}
antes = dict(r); conversation_key(r); assert r == antes

# E9 — Distintas conversaciones → claves distintas
assert conversation_key({"subject": "A"}) != conversation_key({"subject": "B"})

# E10 — Salida segura para ruta (siempre)
assert re.fullmatch(r"[0-9a-f]{64}", conversation_key({"subject": "x"}))
```

## Do / Don't

**Do**
- Normalizar IDs: quitar `<` `>` y espacios; colapsar mayúsculas para comparar.
- Quitar prefijos `Re:`/`Fwd:`/`Rv:` repetidos, en cualquier case y con espacios variables.
- Ordenar y deduplicar participantes con sorted/set antes de hashear.
- Devolver sha256 hex minúscula de 64 chars.
- Tolerar campos ausentes/None/vacíos sin excepción.

**Don't**
- No uses fecha, `Date`, orden de ingesta, índice de llegada ni contenido del cuerpo.
- No llames a un modelo externo ni a ninguna red.
- No persistas, no escribas ficheros, no mutes `record`.
- No devuelvas la clave cruda con caracteres no hex ni longitud variable.
- No implementes clasificación temática ni devuelvas metadatos (lista vacía en MVP; otro módulo).
- No devuelvas `None` ni lances excepciones por campos sucios.

## Tests

Property-tests congelados (oráculo: reimplementan la normalización y el hashing esperado, no
importan `src/email/conversation.py`):

```python
import hashlib, re

def _norm_id(v):
    if v is None: return []
    if isinstance(v, str): v = [v]
    out = []
    for s in v:
        s = s.strip().strip("<>").strip()
        if s: out.append(s.lower())
    return out

def _norm_subject(s):
    s = (s or "").strip()
    while True:
        low = s.lower()
        for p in ("re:", "fwd:", "rv:"):
            if low.startswith(p):
                s = s[len(p):].strip(); break
        else:
            return re.sub(r"\s+", " ", s).lower()

def _oracle(record):
    ids = _norm_id(record.get("references")) + _norm_id(record.get("in_reply_to")) \
          or _norm_id(record.get("message_id"))
    if not ids:
        parts = set()
        for k in ("from", "to", "cc"):
            v = record.get(k)
            if isinstance(v, str): v = [v]
            parts |= {x.strip().lower() for x in (v or []) if x and x.strip()}
        ids = [_norm_subject(record.get("subject"))] + sorted(parts)
    return hashlib.sha256("|".join(ids).encode("utf-8")).hexdigest()

def test_formato_ruta_seguro():
    for r in ({}, {"subject": "x"}, {"references": "<a@b>"}):
        assert re.fullmatch(r"[0-9a-f]{64}", conversation_key(r))

def test_prioridad_references():
    assert conversation_key({"references": "<a@x>", "subject": "uno"}) == \
           conversation_key({"references": "<a@x>", "subject": "dos"})
    assert conversation_key({"references": "<a@x>"}) != conversation_key({"references": "<b@x>"})

def test_normalizacion_ids():
    assert conversation_key({"message_id": "<M1@Z>"}) == conversation_key({"message_id": " m1@z "})
    refs = {"references": ["<a@x>", "b@y"]}
    refs_alt = {"references": ["a@x", "<B@Y>"]}
    assert conversation_key(refs) == conversation_key(refs_alt)

def test_fallback_subject_participantes():
    assert conversation_key({"subject": "Re: FWD: Presupuesto", "from": "A@x"}) == \
           conversation_key({"subject": "Presupuesto", "from": "a@x", "to": ["a@x"]})
    assert conversation_key({"subject": "S", "to": ["b@y", "a@x"]}) == \
           conversation_key({"subject": "S", "to": ["a@x", "b@y"]})
    assert conversation_key({"subject": "A"}) != conversation_key({"subject": "B"})

def test_no_mutacion_y_pureza():
    r = {"subject": "Hola", "to": ["a@x"], "message_id": "<m@z>"}
    snapshot = repr(r)
    k1 = conversation_key(r); k2 = conversation_key(r)
    assert repr(r) == snapshot and k1 == k2 == _oracle(r)

def test_oracle_consistente():
    casos = [
        {}, {"subject": "x"}, {"references": "<a@x>", "message_id": "<b@x>"},
        {"in_reply_to": "r@y"}, {"message_id": "<m@z>", "subject": "Re: s"},
        {"subject": "Fwd: hola", "from": "ana@x.com", "to": ["bob@y.com"], "cc": "car@z.io"},
        {"references": "  ", "subject": "", "to": []},
    ]
    for c in casos:
        assert conversation_key(c) == _oracle(c)
```

## Constraints

- Solo stdlib: `hashlib`, `re`. Cero dependencias de terceros (anti-slopsquatting).
- Complejidad ciclomática ≤ 10 por función; anidamiento ≤ 3; un solo parámetro (`record`).
- Longitud del record tolerada: campos ausentes, `None`, vacío, listas anidadas a un nivel.
- Rendimiento: O(n) sobre el tamaño del record; sin I/O, sin locks, sin estado global.
- Seguridad: la clave no filtra contenido (es un hash); nunca construye rutas a partir del subject
  crudo; inyección de `..` o separadores en los campos es imposible por diseño (salida = hex).
- Límites del MVP: sin fusión de hilos que pierden `References` a mitad de cadena, sin clasificación
  temática (lista vacía), sin deduplicación entre fuentes (IMAP vs mbox). Quedan para módulos futuros.
- Prohibido: fecha/orden de ingesta/contenido arbitrario/modelo externo; red; persistencia; mutación.

## PARAR y reportar si

- El record real del proyecto no trae `references` / `in_reply_to` / `message_id` con las claves
  aquí asumidas → PARAR y reportar los nombres reales antes de implementar.
- Existe ya un módulo de threading/conversaciones que solapa con esta función → PARAR y reportar.
- La firma o el target (`src/email/conversation.py`) difieren de lo pactado → PARAR y reportar.
- Alguna regla de Invariants resulta insatisfacible en código (p. ej. complejidad > umbral) → PARAR
  y pedir excepción, no improvisar.