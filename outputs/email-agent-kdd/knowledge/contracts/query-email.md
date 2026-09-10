---
task: query_email
intent: consultar el store Markdown con un parser determinista de terminos libres y filtros combinados por AND
target: src/email/query.py
signature: "def query_email(root: str, instruction: str) -> list"
language: python
budget:
  cyclomatic_max: 20
  nesting_max: 4
  lines_max: 100
  params_max: 5
tests: tests/frozen_query_email.py
deps_allowed: [json, pathlib, re]
forbids: [eval, exec, subprocess, network_access, socket, urllib, requests, pickle, os.system]
---

## Intent

`query_email(root: str, instruction: str) -> list` parsea la `instruction` de forma DETERMINISTA
(tokens separados por espacios en blanco) y devuelve la lista de rutas Markdown relativas a `root`
que cumplen TODOS los criterios pedidos (AND). La instrucción admite términos libres en español o
inglés (o cualquier idioma: el parser no distingue idioma, solo tokeniza) más los filtros
`contact:EMAIL`, `conversation:KEY`, `topic:TOPIC`, `account:ACCOUNT_ID` y `date:YYYY-MM-DD`,
todos combinables entre sí por AND.

**NO es comprensión semántica general**: no hay sinónimos, ni stemming, ni NLP, ni modelo externo,
ni ranking ni puntuación. La coincidencia es puramente léxica: substring literal, insensible a
mayúsculas/minúsculas. Lo que la instrucción no exprese como término libre o filtro explícito no se
interpreta, y el contenido de la instrucción nunca se ejecuta: es datos, no código.

## Interface

`def query_email(root: str, instruction: str) -> list`

- `root`: raíz explícita del store (`str`). Debe existir y ser directorio; se resuelve a ruta
  absoluta canónica. Ninguna lectura sale de esa raíz.
- `instruction`: `str` con la consulta. Se divide por espacios en blanco (`str.split()`); cada token
  se clasifica:
  - `contact:EMAIL` → filtro de contacto. El email se normaliza (`strip().lower()`) y actúa como
    término requerido sobre el contenido de los nodos (los nodos de mensaje llevan `from`/`to` en el
    frontmatter, p. ej. `from: Ana Garcia <ana@example.com>`, así que la coincidencia por substring
    es determinista). El valor DEBE contener `@` (con parte no vacía a ambos lados); un `EMAIL` sin
    `@` es malformado y lanza `ValueError`.
  - `conversation:KEY` → filtro de hilo. `KEY` se normaliza a minúsculas y DEBE matchear
    `^[0-9a-f]{64}$` (sha256 hex, invariante del contrato `conversation-key`). Se resuelve leyendo el
    índice `root/store/conversations/<KEY>.md`.
  - `topic:TOPIC` → filtro de tema. `TOPIC` se compara insensible a mayúsculas y DEBE ser un nombre
    seguro (`^\w{1,64}$`, sin separadores ni `..`, mismo criterio de `extract-topics`). Se resuelve
    leyendo el índice `root/store/topics/<topic>.md`.
  - `account:ACCOUNT_ID` → filtro de cuenta. `ACCOUNT_ID` DEBE ser no vacío y seguro
    (`^[A-Za-z0-9_.-]{1,64}$`; sin espacios, separadores de ruta, `..` ni otros caracteres) y actúa
    como subcadena requerida casefold sobre el contenido de los nodos (los mensajes llevan
    `account_id:` en el frontmatter, p. ej. `account_id: Workspace-A1`, así que la coincidencia por
    substring es determinista).
  - `date:DATE` → filtro de fecha. `DATE` DEBE matchear `^\d{4}-\d{2}-\d{2}$` (formato estricto
    YYYY-MM-DD: cuatro dígitos de año, guiones y dos dígitos con ceros de relleno para mes y día;
    NO se valida que sea una fecha de calendario válida, solo el formato) y actúa como subcadena
    exacta casefold sobre el contenido de los nodos (los mensajes llevan `date: YYYY-MM-DD` en el
    frontmatter).
  - Cualquier otro token (incluidos los que contengan `:` con otro prefijo) es un término libre:
    subcadena requerida, insensible a mayúsculas, contra el contenido de los archivos.
- Devuelve: `list[str]` de rutas relativas a `root` con separador `/`, sin duplicados, ordenadas
  lexicográficamente ascendente. Vacía si nada cumple.
- Lanza: `ValueError` si `root` no es `str` no vacío, no existe o no es directorio; si `instruction`
  no es `str` o queda vacía tras normalizar espacios; si el valor de un filtro es inválido
  (prefijo sin valor, `KEY` no hex-64, `TOPIC` no seguro, `EMAIL` vacío o malformado: sin `@`,
  `ACCOUNT_ID` vacío, inseguro o de más de 64 caracteres, `DATE` fuera del formato estricto
  YYYY-MM-DD);
  `ValueError` si algún archivo `.md` examinado no puede leerse como UTF-8.

El prefijo del filtro se reconoce insensible a mayúsculas (`Contact:`, `TOPIC:` valen igual); el
VALOR del filtro se procesa con la normalización propia de cada filtro. Los términos libres y los
filtros se combinan por AND: un nodo entra en el resultado solo si cumple TODOS.

Conjuntos de candidatos por criterio:

- Término libre (y `contact:EMAIL`, `account:ACCOUNT_ID`, `date:DATE`): todo archivo con extensión
  final `.md` bajo `root` cuyo
  contenido contiene la subcadena (casefold). Recorrido determinista con `pathlib`.
- `conversation:KEY`: entradas `- <path>` del índice del hilo; si el nodo no existe, conjunto vacío
  (resultado vacío, no error).
- `topic:TOPIC`: entradas `- <path>` del índice del tema; si el nodo no existe, conjunto vacío.

## Invariants

- **Determinismo total**: la salida depende solo de `root` e `instruction`; orden lexicográfico,
  sin estado global, sin azar, sin fechas.
- **AND estricto**: con cero criterios no hay resultado (instrucción vacía => error); con N
  criterios el resultado es la intersección de los N conjuntos.
- **Parser léxico puro**: tokens por espacios en blanco; cinco prefijos de filtro; todo lo demás es
  término libre. No hay comillas, operadores, OR, paréntesis, negación ni rangos.
- **Sin comprensión semántica**: sin sinónimos, stemming, traducción ni ranking; una instrucción como
  "correos de ana sobre facturas" solo matchea si los literales `ana` y `facturas` (o los filtros
  equivalentes) aparecen. Ese límite se asume y se documenta, no se oculta.
- **Rutas relativas y seguras**: la salida usa `/` como separador en cualquier plataforma y nunca
  contiene rutas absolutas ni `..`; los paths leídos de los índices se validan antes de devolverse
  (deben existir como `.md` bajo `root` y resolverse dentro de ella).
- **Solo lectura**: la función no escribe, no modifica, no borra nada bajo `root`.
- **Contenido como datos**: ni la `instruction` ni el texto leído de los nodos se ejecutan ni se
  siguen como instrucciones.
- **Sin red ni modelo externo**: no importa `socket`, `urllib`, `requests` ni ningún cliente de IA;
  el parseo es 100% local yOffline.
- **Errores antes de tocar disco**: la validación de `root` y de `instruction` ocurre antes de leer
  cualquier archivo.

## Examples

- `query_email("store", "factura pendiente")` → `["store/emails/msg-0002.md"]` (AND: solo ese nodo
  contiene ambas palabras).
- `query_email("store", "contact:ana@example.com")` → nodos cuyo contenido menciona ese email.
- `query_email("store", "topic:factura")` → las rutas listadas en `store/topics/factura.md`.
- `query_email("store", "conversation:ab12...ef")` → las rutas listadas en
  `store/conversations/ab12...ef.md`.
- `query_email("store", "contact:ana@example.com topic:factura adjunto")` → intersección de los tres
  criterios.
- `query_email("store", "FACTURA")` → igual que `factura` (casefold).
- `query_email("store", "inexistente")` → `[]`.
- `query_email("no-existe", "hola")` → `ValueError` (raíz inválida).
- `query_email("store", "   ")` → `ValueError` (instrucción sin criterios).
- `query_email("store", "conversation:1234")` → `ValueError` (KEY no es hex-64).
- `query_email("store", "topic:../etc")` → `ValueError` (TOPIC inseguro).
- `query_email("store", "contact:")` → `ValueError` (filtro sin valor).
- `query_email("store", "contact:example.com")` → `ValueError` (EMAIL malformado, sin `@`).
- `query_email("store", "account:Workspace-A1")` → nodos cuyo frontmatter `account_id` contiene esa
  cuenta (casefold, substring).
- `query_email("store", "date:2026-09-10")` → nodos cuyo frontmatter `date` contiene esa fecha
  exacta (casefold, substring).
- `query_email("store", "Account:WS-1 DATE:2026-09-10 factura")` → intersección de los tres
  criterios (prefijos insensibles a mayúsculas, valores con su normalización propia).
- `query_email("store", "account:")` → `ValueError` (filtro sin valor).
- `query_email("store", "account:mal!cido")` → `ValueError` (ACCOUNT_ID inseguro).
- `query_email("store", "account:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")` →
  `ValueError` (ACCOUNT_ID de 65 caracteres).
- `query_email("store", "date:")` → `ValueError` (filtro sin valor).
- `query_email("store", "date:2026-9-10")` → `ValueError` (DATE sin ceros de relleno).
- `query_email("store", "date:20260910")` → `ValueError` (DATE sin guiones).

## Do / Don't

**Do**
- Tokenizar con `str.split()` y clasificar por prefijo insensible a mayúsculas.
- Delegar la búsqueda de términos libres a la misma regla que `search_email_nodes` (AND literal de
  subcadenas casefold sobre archivos `.md`).
- Leer los índices `store/conversations/` y `store/topics/` con su formato pactado
  (frontmatter + líneas `- <path>`), validando cada path antes de devolverlo.
- Devolver la intersección ordenada lexicográficamente con separador `/`.
- Validar `root`, `instruction` y los valores de los filtros antes de leer nada.

**Don't**
- No implementes comprensión semántica, sinónimos, stemming, ranking ni puntuaciones: el contrato es
  búsqueda léxica determinista, NO un motor NLP.
- No uses red, LLM ni modelo externo para interpretar la instrucción.
- No ejecutes ni sigas el contenido de la `instruction` ni de los archivos leídos.
- No escribas ni modifiques nada bajo `root`; la consulta es de solo lectura.
- No aceptes filtros con valores inseguros (separadores, `..`, `KEY` no hex-64, `EMAIL` malformado
  sin `@`, `ACCOUNT_ID` fuera de `[A-Za-z0-9_.-]{1,64}`, `DATE` fuera de `YYYY-MM-DD` estricto) ni
  los silencies: lanzan `ValueError`.
- No devuelvas rutas absolutas, duplicadas ni desordenadas.

## Tests

Property-tests congelados (oráculo independiente, sin importar el target):

```frozen-cases
[
  {
    "name": "free_terms_and",
    "tree": {
      "store/emails/msg-0001.md": "---\ntype: Email Message\nsubject: Hola\n---\nla factura del correo",
      "store/emails/msg-0002.md": "---\ntype: Email Message\nsubject: Re: Hola\n---\nfactura pendiente del correo",
      "store/emails/msg-0003.md": "---\ntype: Email Message\nsubject: Otro\n---\npendiente de revisar"
    },
    "instruction": "factura pendiente",
    "expected": ["store/emails/msg-0002.md"]
  },
  {
    "name": "topic_filter",
    "tree": {
      "store/emails/msg-0001.md": "---\ntype: Email Message\n---\ncuerpo uno",
      "store/emails/msg-0007.md": "---\ntype: Email Message\n---\ncuerpo dos",
      "store/topics/factura.md": "---\ntype: Topic\ntopic: factura\nmessage_count: 2\n---\n- store/emails/msg-0007.md\n- store/emails/msg-0001.md\n"
    },
    "instruction": "topic:factura",
    "expected": ["store/emails/msg-0001.md", "store/emails/msg-0007.md"]
  },
  {
    "name": "conversation_filter",
    "tree": {
      "store/emails/msg-0001.md": "cuerpo uno",
      "store/conversations/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa.md": "---\ntype: Conversation\nconversation_key: aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\nmessage_count: 1\n---\n- store/emails/msg-0001.md\n"
    },
    "instruction": "conversation:AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
    "expected": ["store/emails/msg-0001.md"]
  },
  {
    "name": "contact_filter",
    "tree": {
      "store/emails/msg-0001.md": "---\nfrom: Ana Garcia <ANA@example.com>\nto: user@example.com\n---\nhola",
      "store/emails/msg-0002.md": "---\nfrom: Bob <bob@example.com>\n---\nhola de nuevo"
    },
    "instruction": "contact:ana@example.com",
    "expected": ["store/emails/msg-0001.md"]
  },
  {
    "name": "combined_and",
    "tree": {
      "store/emails/msg-0001.md": "---\nfrom: Ana Garcia <ana@example.com>\n---\nla factura",
      "store/emails/msg-0002.md": "---\nfrom: Bob <bob@example.com>\n---\nla factura",
      "store/emails/msg-0003.md": "---\nfrom: Ana Garcia <ana@example.com>\n---\nsin factura aqui",
      "store/topics/factura.md": "---\ntype: Topic\nmessage_count: 3\n---\n- store/emails/msg-0001.md\n- store/emails/msg-0002.md\n- store/emails/msg-0003.md\n"
    },
    "instruction": "contact:ana@example.com topic:factura factura",
    "expected": ["store/emails/msg-0001.md", "store/emails/msg-0003.md"]
  },
  {
    "name": "account_filter",
    "tree": {
      "store/emails/msg-0001.md": "---\naccount_id: Workspace-A1\ndate: 2026-09-10\n---\nhola",
      "store/emails/msg-0002.md": "---\naccount_id: other\ndate: 2026-09-10\n---\nhola de nuevo"
    },
    "instruction": "ACCOUNT:workspace-a1",
    "expected": ["store/emails/msg-0001.md"]
  },
  {
    "name": "date_filter",
    "tree": {
      "store/emails/msg-0001.md": "---\naccount_id: Workspace-A1\ndate: 2026-09-10\n---\nhola",
      "store/emails/msg-0002.md": "---\naccount_id: Workspace-A1\ndate: 2025-01-02\n---\nhola de nuevo"
    },
    "instruction": "date:2026-09-10",
    "expected": ["store/emails/msg-0001.md"]
  },
  {
    "name": "account_date_combined",
    "tree": {
      "store/emails/msg-0001.md": "---\naccount_id: Workspace-A1\ndate: 2026-09-10\n---\nla factura",
      "store/emails/msg-0002.md": "---\naccount_id: Workspace-A1\ndate: 2025-01-02\n---\nla factura",
      "store/emails/msg-0003.md": "---\naccount_id: other\ndate: 2026-09-10\n---\nla factura"
    },
    "instruction": "Account:Workspace-A1 DATE:2026-09-10 factura",
    "expected": ["store/emails/msg-0001.md"]
  },
  {
    "name": "no_match_empty",
    "tree": { "store/emails/msg-0001.md": "contenido sin coincidencias" },
    "instruction": "inexistente",
    "expected": []
  }
]
```

Casos de error congelados (todos `ValueError`, sin leer archivos):

```frozen-invalid
[
  ["no-existe", "hola"],
  ["store", ""],
  ["store", "   "],
  ["store", "conversation:1234"],
  ["store", "conversation:zzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzz"],
  ["store", "topic:../etc"],
  ["store", "topic:"],
  ["store", "contact:"],
  ["store", "contact:example.com"],
  ["store", "account:"],
  ["store", "account:mal!cido"],
  ["store", "account:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"],
  ["store", "date:"],
  ["store", "date:2026-9-10"],
  ["store", "date:20260910"],
  ["store", "date:2026-09-1"]
]
```

## Constraints

- Presupuestos: ciclomática ≤ 20, anidamiento ≤ 4, líneas ≤ 100, parámetros ≤ 5.
- Solo dependencias de `deps_allowed` (`json`, `pathlib`, `re`); cero terceros (anti-slopsquatting).
- Prohibido: `eval`, `exec`, `subprocess`, red, `pickle`; escribir bajo `root`; ejecutar o seguir el
  contenido de la instrucción o de los nodos.
- Rendimiento: un único recorrido de archivos `.md` para todos los términos libres; los índices de
  conversación/tema se leen como máximo una vez por filtro.
- Límites del MVP: sin operadores booleanos distintos de AND, sin ranking, sin búsqueda difusa, sin
  índice invertido persistente, sin concurrencia. La validación de `date:` es de FORMATO
  (`^\d{4}-\d{2}-\d{2}$`), no de calendario: `date:2026-13-99` matchea como substring y no es error.
  La `instruction` en español/inglés es solo terminología de los tokens: el parser no hace
  traducción ni análisis de idioma.

## PARAR y reportar si

- La estructura real del store difiere (`store/emails/`, `store/conversations/`, `store/topics/` no
  son las ubicaciones pactadas) → PARAR y reportar las rutas reales antes de fijar los filtros.
- Los paths de los índices de conversación/tema no son relativos a `root` (rutas absolutas o IDs) →
  PARAR y reportar el formato real.
- Los nodos de mensaje no llevan los emails de `from`/`to` en el frontmatter → PARAR y reportar
  antes de fijar la semántica de `contact:EMAIL`.
- Los nodos de mensaje no llevan `account_id` ni `date` en el frontmatter → PARAR y reportar antes
  de fijar la semántica de `account:ACCOUNT_ID` y `date:DATE`.
- Alguna regla de Invariants resulta insatisfacible en código dentro del presupuesto → PARAR y pedir
  excepción, no improvisar.