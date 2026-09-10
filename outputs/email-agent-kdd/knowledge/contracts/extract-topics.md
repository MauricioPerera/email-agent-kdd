---
task: extract-topics
intent: Extraer etiquetas de tema deterministas desde el asunto de un email sin leer el cuerpo ni usar red o modelo externo.
target: ../../../../src/email/topics.py
signature: "def extract_topics(record: dict) -> list[str]"
language: python
target_line: null
budget:
  max_cyclomatic: 10
  max_nesting: 3
  max_length: 60
tests_frozen: true
stop_rule: "PARAR y reportar si el implementador necesita leer record['body'], llamar a la red, usar un modelo externo o mutar record."
---

# Contrato: extract_topics

## Intent

`extract_topics(record)` produce, a partir de `record["subject"]`, una lista de **etiquetas de tema** (tokens normalizados) que sirve como señal barata y reproducible para agrupar emails en el MVP de KDD. Las etiquetas son **derivadas y deterministas**: NO sustituyen a una futura clasificación semántica; solo describen de qué palabras trata el asunto.

## Interface

```python
def extract_topics(record: dict) -> list[str]
```

- **Entrada:** `record: dict` con la clave `"subject"` (valor `str`). Otras claves del record SON IGNORADAS por diseño (en particular `body` jamás se lee).
- **Salida:** `list[str]` con como máximo **12** temas, sin duplicados, ordenados lexicográficamente (orden `sorted()` por defecto de Python sobre `str`, casefolded). Puede ser `[]` si no hay tokens válidos.
- **Efectos:** ninguno. Función pura: no muta `record`, no imprime, no abre archivos, no hace red, no usa `random` ni `datetime`.

Pipeline exacto (en este orden):

1. Tomar `record["subject"]`. Si no existe o no es `str`, tratarlo como `""` (NO lanzar excepción).
2. Quitar prefijos de respuesta/reenvío **repetidos**: aplicar repetidamente la eliminación de un prefijo `Re:`, `RE:`, `re:`, `Fwd:`, `FWD:`, `fwd:`, `Rv:`, `RV:`, `rv:` al inicio (tolerando espacios entre prefijos) hasta que no quede ninguno. Ej.: `"Re: RE: Fwd: Hola"` → `"Hola"` (se usa un bucle sobre una lista fija de prefijos, con `casefold()` para comparar de forma insensible a mayúsculas).
3. Separar tokens: extraer secuencias alfanuméricas Unicode con `re.findall(r"\w+", subject, flags=re.UNICODE)`. `\w` incluye letras Unicode, dígitos y `_`. Cualquier otro carácter actúa como separador. Los tokens compuestos por guiones o puntos (p. ej. `id-123`, `v1.2`) se dividen.
4. Normalizar cada token con `str.casefold()`.
5. Eliminar tokens vacíos (tras el paso 3 no deberían existir, pero se filtra por robustez) y los que estén en la lista fija de stopwords.
6. Deduplicar preservando primera aparición (para estabilidad), luego devolver `sorted(set)` — el orden final SIEMPRE es lexicográfico.
7. Truncar a los primeros **12** del resultado ordenado.

Stopwords fijas (lista pequeña, hardcoded, sin depender de librerías externas):

```python
STOPWORDS = frozenset({
    # español
    "de", "la", "el", "los", "las", "del", "al", "a", "y", "o", "en", "con",
    "para", "por", "que", "se", "su", "sus", "lo", "un", "una", "es", "no",
    "sobre", "re", "rv", "fw", "fwd",
    # inglés
    "the", "a", "an", "and", "or", "of", "to", "in", "on", "for", "with",
    "is", "it", "this", "that", "re", "fw", "fwd",
})
```

Es aceptable que `re`, `fw`, `fwd` aparezcan una sola vez en el `frozenset` (son sets, no listas).

## Invariants

1. **Determinismo:** para el mismo `record`, la salida es idéntica en cada llamada (sin dependencia de hora, aleatoriedad, hash-seed u orden de dict).
2. **Pureza:** `record` NO se muta (ni en claves existentes ni añadiendo claves); sin `print`/`open`/`eval`/`exec`/`__import__`; sin `Global`/`Nonlocal`.
3. **No fuga de datos:** el cuerpo (`record["body"]` o cualquier otra clave) NUNCA se lee ni se copia a la salida. Solo se accede a `record.get("subject")`.
4. **Sin modelo ni red:** ninguna dependencia externa; solo stdlib (`re`, `str`). Sin llamadas HTTP, sin subprocess, sin import de terceros.
5. **Cota de salida:** `len(resultado) <= 12` siempre.
6. **Orden y unicidad:** la salida no contiene duplicados y está ordenada lexicográficamente (coincide con `sorted(resultado) == resultado`).
7. **Normalización:** todo token de salida cumple `token == token.casefold()` y `token != ""`.
8. **Robustez:** nunca lanza excepción ante `subject` ausente, `None`, no-`str`, o `record` sin claves; devuelve `[]` en esos casos.
9. **Los temas son etiquetas derivadas:** el contrato NO promete comprensión semántica; un tema es un token del asunto, punto. Cualquier uso como "categoría" final es responsabilidad del consumidor y queda fuera de este contrato.

## Examples

| Entrada (`record["subject"]`) | Salida |
|---|---|
| `{"subject": "Re: Re: Factura 123"}` | `["123", "factura"]` |
| `{"subject": "FWD: Informe trimestral Q3"}` | `["informe", "q3", "trimestral"]` |
| `{"subject": "Re: RE: Fwd: Re: Oferta de trabajo"}` | `["oferta", "trabajo"]` ("de" es stopword) |
| `{"subject": "Presupuesto-v2 y entrega!!"}` | `["entrega", "presupuesto", "v2"]` |
| `{"subject": "Café y AÑO nuevo"}` | `["año", "café", "nuevo"]` (Unicode, casefold, orden lexicográfico) |
| `{"subject": ""}` | `[]` |
| `{}` (sin `subject`) | `[]` |
| `{"subject": None}` | `[]` |
| `{"subject": 12345}` | `[]` (no-`str` → `""`) |
| `{"subject": "Re: " + "token%d " % i for 20 tokens distintos}` | los 12 primeros lexicográficamente |

Con 20 tokens distintos en el asunto, se devuelven exactamente 12 (los menores lexicográficamente).

## Do / Don't

**Do:**
- Usar `casefold()` para normalizar y comparar prefijos.
- Usar un bucle `while` que quite prefijos hasta estabilizar (prefijos repetidos).
- Usar `re.findall(r"\w+", ...)` con `flags=re.UNICODE`.
- Devolver `sorted(...)[:12]` al final.
- Mantener la lista de stopwords como `frozenset` literal dentro del módulo.

**Don't:**
- NO leer `record["body"]`, `record["text"]`, `record["html"]` ni ninguna otra clave distinta de `subject`.
- NO mutar `record` (ni `record["subject"] = ...` ni `record.update(...)` ni `record.pop(...)`).
- NO hacer red, HTTP, subprocess, ni cargar modelos (ni locales ni remotos).
- NO usar stemming, lematización, N-gramas, TF-IDF ni nada más allá de tokenizar+normalizar (eso es alcance futuro).
- NO devolver más de 12 temas ni duplicados.
- NO lanzar excepciones por entrada malformada.
- NO usar `record["subject"]` con indexado directo si puede faltar (usar `.get` con chequeo de tipo).

## Tests

Pruebas congeladas (oráculo independiente, NO importan el target — solo definen comportamiento esperado). Deben ejecutarse contra el target una vez implementado, y las expectativas NO se regeneran a partir de la implementación.

```python
# tests/email/test_extract_topics.py
import pytest

from src.email.topics import extract_topics


def test_basico_con_prefijos_repetidos():
    assert extract_topics({"subject": "Re: Re: Factura 123"}) == ["123", "factura"]


def test_prefijos_mixtos_case_insensitive():
    assert extract_topics({"subject": "Re: RE: Fwd: Re: Oferta de trabajo"}) == [
        "oferta", "trabajo"
    ]


def test_separadores_no_alfanumericos():
    assert extract_topics({"subject": "Presupuesto-v2 y entrega!!"}) == [
        "entrega", "presupuesto", "v2"
    ]


def test_unicode_casefold_orden_lexicografico():
    assert extract_topics({"subject": "Café y AÑO nuevo"}) == [
        "año", "café", "nuevo"
    ]


def test_vacio_y_malformado_devuelve_lista_vacia():
    assert extract_topics({"subject": ""}) == []
    assert extract_topics({}) == []
    assert extract_topics({"subject": None}) == []
    assert extract_topics({"subject": 12345}) == []


def test_maximo_doce_temas():
    subject = " ".join(f"tema{i:02d}" for i in range(20))
    out = extract_topics({"subject": subject})
    assert len(out) == 12
    assert out == sorted(out)
    assert out == [f"tema{i:02d}" for i in range(12)]


def test_sin_duplicados_y_ordenado():
    out = extract_topics({"subject": "dato dato DATO Dato reporte"})
    assert out == ["dato", "reporte"]


def test_no_muta_record():
    record = {"subject": "Re: Hola", "body": "SECRETO"}
    before = dict(record)
    out = extract_topics(record)
    assert record == before
    assert out == ["hola"]
    # el body jamás influye ni se copia
    assert all("secr" not in t for t in out)


def test_pureza_estatica():
    import ast
    import pathlib
    src = pathlib.Path("src/email/topics.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    forbidden = {"print", "open", "eval", "exec", "__import__"}
    calls = [
        n.func.id for n in ast.walk(tree)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
    ]
    assert not (forbidden & set(calls))
    imports = [
        n.names[0].name.split(".")[0] for n in ast.walk(tree)
        if isinstance(n, (ast.Import, ast.ImportFrom))
    ]
    assert set(imports) <= {"re"}


def test_propiedad_determinismo():
    record = {"subject": "Re: Contrato y Plazo de entrega"}
    assert extract_topics(record) == extract_topics(record)
    assert extract_topics(record) == ["contrato", "entrega", "plazo"]


def test_propiedad_cota_y_orden():
    for subject in ["a b c d e f g h i j k l m n o p", "uno", "Re: dos tres"]:
        out = extract_topics({"subject": subject})
        assert len(out) <= 12
        assert out == sorted(out)
        assert len(set(out)) == len(out)
```

## Constraints

- Solo stdlib (`re` y builtins). Ninguna dependencia de terceros.
- Función pura: sin I/O, sin red, sin estado global, sin `random`, sin `datetime`.
- Máximo 12 temas de salida, siempre.
- No leer ni exponer el cuerpo del mensaje (prevención de fuga de datos por diseño).
- Los temas producidos son **etiquetas derivadas del asunto**, no categorías semánticas: no sustituyen a la clasificación semántica futura y no deben usarse como veredicto de categoría.
- **PARAR y reportar si** el implementador necesita: leer `record["body"]` u otra clave, mutar `record`, introducir dependencias externas, llamar a la red o a un modelo (local u online), usar stemming/lematización, superar los 12 temas, o si algún ejemplo congelado resulta imposible de satisfacer con la firma `def extract_topics(record: dict) -> list[str]`.