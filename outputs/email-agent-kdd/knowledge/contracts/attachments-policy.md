---
title: Política de adjuntos (MVP) — email-agent
kind: kdd-contract
status: decision-mvp
date: 2026-09-10
scope:
  - normalize_email
  - persistencia OKF
  - CLI draft/send
  - envío SMTP
decides:
  - Los adjuntos se detectan y se conservan como metadatos (name, mime_type, size, sha256).
  - normalize_email PUEDE incluir en su salida, de forma TRANSITORIA y solo en memoria, los bytes de cada adjunto y los `raw` del mensaje, porque su propio contrato (normalize-email.md) los exige para auditoría; esta garantía NO restringe esa salida en memoria.
  - La garantía del MVP es de PERSISTENCIA Y EXPOSICIÓN: persist_email_okf / persist_email_okf_at, drafts, SMTP y las salidas de CLI NUNCA persisten ni exponen el contenido binario de los adjuntos ni los `raw`.
  - La CLI draft/send rechaza adjuntos explícitos; SMTP no envía adjuntos en el MVP.
future:
  - retrieve_attachment(message_id, attachment_sha256) -> bytes (interfaz SEPARADA, NO implementada)
  - autorización explícita, límites de tamaño, antivirus
non_goals:
  - implementar retrieve_attachment
  - soportar envío de adjuntos
  - exponer binarios al agente
---

# Contrato KDD: Política de adjuntos (MVP)

## Intent

Tratar los adjuntos del correo como metadatos de referencia (qué hay, cómo se llama, de qué tipo, cuánto pesa y qué hash tiene) y NO como contenido persistido ni expuesto: el agente puede saber que existe un adjunto y citarlo por identidad, pero en el MVP ningún artefacto duradero (nodos OKF, drafts, correos enviados, salidas de CLI) retiene o entrega su binario. El límite del MVP es deliberado: `normalize_email` PUEDE manejar y devolver el contenido de los adjuntos (y el `raw` del mensaje) TRANSITORIAMENTE en memoria, porque el contrato `normalize-email.md` lo exige para auditoría; lo que esta política prohíbe es que esos bytes cruce a la persistencia o a cualquier salida expuesta. Esto reduce la superficie de exfiltración de datos, evita que binarios potencialmente peligrosos terminen en nodos OKF o en salidas de CLI, y deja el acceso duradero al contenido como una operación futura explícita, autorizada y acotada.

## Interface

### Estado MVP (decisión vigente)

- `normalize_email`:
  - PUEDE detectar adjuntos del mensaje y conservar por cada uno, como mínimo:
    - `name`: nombre del adjunto (string, puede faltar).
    - `mime_type`: tipo MIME declarado (string).
    - `size`: tamaño en bytes (int).
    - `sha256`: hash SHA-256 del contenido binario (string hex).
  - PUEDE incluir además, TRANSITORIAMENTE y solo en memoria, los bytes de cada adjunto y los `raw` del mensaje: el contrato `normalize-email.md` los exige para auditoría. Esta política NO restringe la salida de `normalize_email`; lo que prohíbe es que esos bytes lleguen a cualquier artefacto persistido o salida expuesta.
- Persistencia OKF (`persist_email_okf` / `persist_email_okf_at`):
  - En los nodos OKF la metadata de adjuntos debe quedar reducida a los 4 campos anteriores: NI binarios, NI `raw`, NI fragmentos decodificados, NI datos del adjunto más allá de esos campos.
- CLI `draft` / `send`:
  - RECHAZAN adjuntos explícitos (error de uso, no aviso silencioso). Si el usuario o el agente pide adjuntar algo, la operación falla con mensaje claro.
  - Sus salidas nunca incluyen el contenido binario de adjuntos ni los `raw`.
- Envío SMTP:
  - NO envía adjuntos en el MVP. El cuerpo sale solo.

### Futuro (DISEÑO PROPUESTO — NO implementado, NO asumir existencia)

- `retrieve_attachment(message_id, attachment_sha256) -> bytes`:
  - Interfaz separada de la ingesta/normalización; se ejecutaría bajo autorización explícita, con límites de tamaño y verificación antivirus.
  - Por defecto NO expondría binarios al agente.
- Esta sección declara intención de diseño. Ninguna parte del código debe depender de que exista hoy.

## Invariants

1. **Solo 4 campos en lo persistido.** Ningún nodo OKF, draft, correo enviado ni salida de CLI contiene de un adjunto más que `name`, `mime_type`, `size`, `sha256`. Cualquier otro campo persistido o expuesto es violación del contrato. La salida EN MEMORIA de `normalize_email` NO está sujeta a esta invariante: puede incluir los bytes del adjunto y los `raw` del mensaje (exigidos por `normalize-email.md` para auditoría).
2. **Binario nunca en reposo accesible al agente.** El contenido binario de adjuntos y los `raw` NO se persisten: ni en nodos OKF, ni en drafts, ni en logs, ni en cachés. `normalize_email` puede procesarlos y devolverlos transitoriamente en memoria (calcular `sha256`/`size`, auditoría), pero deben desaparecer al terminar la llamada: ningún artefacto posterior los retiene.
3. **Drafts sin adjuntos.** Un draft generado por el agente nunca lleva adjuntos; la CLI rechaza la petición explícita.
4. **SMTP sin adjuntos.** Ningún correo enviado por el agente contiene adjuntos en el MVP.
5. **Metadata sin secretos.** La metadata visible en OKF no puede contener binarios, `raw`, ni datos sensibles del adjunto (p. ej. el propio contenido codificado, claves embebidas, rutas locales del remitente).
6. **Futuro separado.** El acceso a contenido, si llega a existir, vivirá en una interfaz distinta (`retrieve_attachment`) con autorización explícita; la ingesta y el drafting no ganan capacidad de leer binarios como efecto colateral.
7. **Fallo explícito.** Pedir adjuntos por CLI es un error declarado, nunca una omisión silenciosa ni un "se ignoró el adjunto" sin aviso.

## Examples

### Válido — mensaje con adjunto normalizado

```text
nodo OKF:
  from:    alice@example.com
  subject: Factura junio
  body:    "Adjunto la factura del mes."
  attachments:
    - name:      factura-junio.pdf
      mime_type: application/pdf
      size:      184320
      sha256:    9f2c...e1
```

El agente puede razonar: "hay un PDF de ~180 KB llamado factura-junio.pdf" y responder "recibí tu factura". No puede mostrar su contenido ni reenviarlo.

### Válido — deduplicación por hash

Dos correos distintos adjuntan el mismo archivo → ambos nodos llevan el mismo `sha256`. Es evidencia de duplicado sin necesidad del binario; el contenido idéntico se identifica por hash único, no por doble almacenamiento.

### Válido — salida transitoria de normalize_email con bytes en memoria

```text
normalize_email(raw_message, "personal") -> {
  ...
  raw: <bytes originales del mensaje>,          # VÁLIDO: exigido por normalize-email.md para auditoría
  attachments:
    - name:      factura-junio.pdf
      mime_type: application/pdf
      size:      184320
      sha256:    9f2c...e1
      content:   <bytes del pdf>                 # VÁLIDO: transitorio, solo en memoria
}
```

Esto NO viola el contrato. La violación aparece si cualquiera de esos bytes llega a `persist_email_okf` / `persist_email_okf_at`, a un draft, a SMTP o a una salida de CLI.

### Inválido — binario en el nodo OKF

```text
nodo OKF:
attachments:
  - name: foto.jpg
    data: <base64 del archivo>   # VIOLACIÓN: binario persistido
```

```text
nodo OKF:
raw: <bytes originales del mensaje>   # VIOLACIÓN: raw persistido; el raw vive solo en la salida de normalize_email
```

### Inválido — CLI con adjunto

```text
$ email-agent draft --attach informe.pdf
ERROR: adjuntos no soportados en el MVP (ver attachments-policy.md)
```

Comportamiento correcto: error claro, no se genera draft parcial.

### Inválido — draft "con adjunto" silencioso

Un draft que ignora el adjunto pedido y sale sin aviso: viola la invariante 7 (fallo explícito).

## Do / Don't

**Do**

- Calcular `sha256` y `size` del adjunto como interacción transitoria con su binario (en memoria, para metadatos y auditoría).
- Dejar que `normalize_email` devuelva el contenido del adjunto y los `raw` del mensaje transitoriamente, como exige `normalize-email.md`.
- Usar el hash como clave de deduplicación y de referencia estable entre nodos.
- Documentar en el nodo OKF la presencia del adjunto con SOLO los 4 campos (sin `content`, sin `raw`).
- Rechazar en CLI con mensaje que apunte a esta política.
- Mantener cualquier acceso futuro y duradero a contenido en una interfaz separada con autorización explícita.

**Don't**

- No persistir el binario ni el `raw` (ni en bruto ni en base64) en nodos OKF, drafts, logs ni cachés del agente.
- No exponer el binario ni el `raw` por CLI, drafts ni correos enviados por SMTP.
- No implementar `retrieve_attachment` "de paso": es diseño futuro, no deuda actual.
- No permitir que la metadata persistida o expuesta contenga datos más allá de los 4 campos.

## Tests

Pruebas propuestas (a definir al implementar; hoy solo política):

1. **Solo-campos persistidos:** dado un mensaje con N adjuntos, la salida persistida (nodos OKF, drafts, salidas de CLI) contiene por adjunto exactamente las claves `name`, `mime_type`, `size`, `sha256` (ni más ni menos; `name` puede faltar si el mensaje no lo trae). La salida EN MEMORIA de `normalize_email` NO se rige por este test: puede incluir `content` y `raw`.
2. **Sin binario ni raw en OKF:** persistir un mensaje con adjunto vía `persist_email_okf` / `persist_email_okf_at` y verificar que ningún nodo OKF contiene el binario, su representación base64 ni los `raw` del mensaje (búsqueda por subcadena del contenido codificado y por longitud de valores).
3. **Hash correcto:** `sha256` del nodo coincide con el SHA-256 del adjunto original; `size` coincide con su longitud en bytes.
4. **Deduplicación:** dos mensajes con el mismo adjunto producen el mismo `sha256`; dos adjuntos distintos dentro del mismo mensaje producen hashes distintos.
5. **CLI rechaza:** `draft` con flag de adjunto termina con error y mensaje que mencione la política; no se crea draft. Idem `send`.
6. **SMTP sin adjuntos:** capturar el mensaje enviado y verificar que no tiene partes de adjunto (solo cuerpo/texto).
7. **Metadata sin secretos:** la metadata expuesta en OKF no contiene binarios, base64, `raw` ni campos ajenos a los 4 permitidos.
8. **Transitorio de verdad:** tras `normalize_email` (y tras persistir), ningún artefacto persistido ni caché contiene los bytes de adjuntos ni los `raw`: viven solo en el retorno de la llamada.
9. **Futuro ausente:** no existe ninguna función pública DE ACCESO DURADERO que devuelva bytes de adjuntos, más allá de la salida transitoria de `normalize_email` (guardia: si se introduce `retrieve_attachment`, este contrato debe revisarse primero).

## Constraints

- Límite de tamaño para metadatos: `size` es un entero; no se impone límite de lectura del binario en el MVP porque el binario no se retiene (solo vive transitoriamente en la salida de `normalize_email`), pero cualquier futura `retrieve_attachment` DEBE tener límite máximo de tamaño configurable y verificado antes de devolver bytes.
- Antivirus: requisito obligatorio del diseño futuro (`retrieve_attachment`); en el MVP no aplica a la lectura duradera de contenido.
- Autorización: el acceso futuro y duradero a contenido requiere autorización explícita por operación; no se hereda de la autorización de lectura del correo ni de la capacidad transitoria de `normalize_email`.
- Privacidad — riesgos cubiertos por esta decisión:
  - **Exfiltración accidental:** un agente con acceso persistido al binario podría reenviar o reproducir documentos privados en un draft. Bloqueado por invariantes 2–4 (no persistencia + drafts sin adjuntos).
  - **Fuga por contexto:** binarios (o su base64) inflados a artefactos duraderos pueden contener PII/secretos; bloqueado por la invariante 2 en cuanto a persistencia y por las invariantes 3–4 y la regla CLI en cuanto a salidas expuestas. La salida transitoria en memoria de `normalize_email` NO está cubierta por esta garantía (la exige `normalize-email.md` para auditoría).
  - **Persistencia innecesaria:** guardar binarios multiplica superficie de breach (backups, nodos, logs). El hash permite referenciar sin retener.
  - **Metadatos también filtran:** `name` puede contener información sensible (nombres de archivo con datos personales); se conserva por utilidad, pero la persistencia debe tratarlo como dato personal y sin secretos (invariante 5).
  - **Malware:** adjuntos son el vector clásico; al no persistir ni enviar binarios, el MVP elimina el vector en escritura; el vector de lectura queda para el diseño futuro con antivirus y límites.
- Deduplicación por hash: SHA-256 como identidad del adjunto; permite detectar repetidos entre mensajes sin almacenar contenido. No es criptografía de seguridad aquí, es identidad de datos.
- Ámbito: esta política es de decisión MVP. Cualquier feature de adjuntos (lectura, envío, extracción de texto) requiere revisar y actualizar este contrato ANTES de tocar código.

## PARAR y reportar si...

- Se necesita el **contenido binario** de un adjunto MÁS ALLÁ de la manipulación transitoria en memoria que `normalize_email` ya hace (leerlo de forma duradera, extraer texto, mostrarlo, reenviarlo, guardarlo): PARAR. Es fuera del MVP; requiere este contrato actualizado y la interfaz futura con autorización.
- Alguien pide **enviar adjuntos** por SMTP o añadir flags de adjuntos en la CLI que no rechacen: PARAR.
- Cualquier etapa POSTERIOR a `normalize_email` (persistencia, drafting, SMTP, CLI, logs, cachés) recibe o retiene los bytes de adjuntos o los `raw` del mensaje: PARAR y reportar el leak antes de persistir.
- Existe cualquier ruta de código que persista binarios o `raw` en OKF, o los incluya en drafts, correos enviados o salidas de CLI: PARAR — es violación directa del contrato.
- Se propone implementar `retrieve_attachment` o similar "porque ya está el hash": PARAR — es diseño futuro con requisitos propios (autorización, límites, antivirus) y este contrato debe revisarse primero.
- `name` u otro metadato parece contener secretos o credenciales embebidas: PARAR y reportar antes de persistir el nodo.
- Los hashes no cuadran (mismo archivo → distinto `sha256`, o `size` inconsistente): PARAR — puede indicar normalización defectuosa o manipulación.