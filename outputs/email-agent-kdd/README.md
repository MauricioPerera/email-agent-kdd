# Email Agent (MVP)

Agente de correo para usar desde la terminal. Permite configurar una cuenta, descargar los correos recientes, buscar entre ellos, redactar y enviar. Pensado como producto mínimo (MVP): hace lo esencial, sin extras.

## Requisitos

- Python 3 instalado en el equipo.
- Una cuenta de correo (Gmail u Outlook) y la contraseña (o contraseña de aplicación) guardada en una variable de entorno propia.

## Cómo empezar

Todos los comandos se escriben en la terminal, desde la carpeta del proyecto. Para ver la ayuda general:

```
python -m src.email --help
```

## Comandos principales

### 0. Configurar una cuenta paso a paso (account setup)

```
python -m src.email account setup ./mi-store
```

Asistente interactivo que configura una cuenta en `ROOT` (por ejemplo, `./mi-store`) haciéndote **cuatro preguntas**:

1. El **identificador** de la cuenta (por ejemplo, `personal`).
2. El **proveedor**: `gmail` o `outlook`.
3. El **correo** completo (por ejemplo, `micorreo@gmail.com`).
4. El **nombre de la variable de entorno** donde ya guardaste la contraseña (por ejemplo, `GMAIL_PASS`).

**Nunca pide la contraseña**: tú ya la tienes en una variable de entorno y aquí solo se escribe su nombre. Si en cualquier pregunta escribes `cancelar`, el asistente se detiene sin guardar nada.

### 1. Añadir una cuenta

```
python -m src.email account add ./mi-store personal gmail micorreo@gmail.com env://GMAIL_PASS
```

Formato general:

```
python -m src.email account add ROOT ACCOUNT_ID PROVIDER EMAIL CREDENTIAL_REF
```

- `ROOT`: carpeta de datos del proyecto donde se guarda la configuración.
- `ACCOUNT_ID`: identificador que tú eliges para la cuenta (por ejemplo, `gmail1`).
- `PROVIDER`: proveedor (por ejemplo, `gmail` o `outlook`).
- `EMAIL`: dirección de correo completa.
- `CREDENTIAL_REF`: referencia a la contraseña, con el formato `env://NOMBRE` (ver abajo).

### 2. Ver las cuentas guardadas

```
python -m src.email account list ./mi-store
```

Muestra las cuentas configuradas en ese `ROOT`.

### 3. Descargar los correos (sincronizar)

```
python -m src.email sync ./mi-store personal
```

Trae los mensajes recientes de la cuenta para consultarlos sin conexión. `HOST` es opcional (formato general: `python -m src.email sync ROOT ACCOUNT_ID [HOST]`): sobreescribe el servidor IMAP; si se omite, se usa el del proveedor configurado.

Cada cuenta conserva un **cursor UID local** en `.email-agent/cursors.json` dentro del `ROOT`: guarda hasta qué mensaje se descargó. En las ejecuciones posteriores, `sync` descarga solo los mensajes nuevos y no repite los ya traídos. No edites ese archivo: lo gestiona el programa (y si falta, la primera sincronización lo crea de nuevo).

### 4. Buscar correos

```
python -m src.email search ./mi-store factura
```

Busca entre los correos ya descargados usando `QUERY` como palabras clave.

### 4. Consultar el store (query)

```
python -m src.email query ./mi-store "factura contact:ana@example.com"
```

Formato general:

```
python -m src.email query ROOT INSTRUCTION
```

- `ROOT`: carpeta de datos del proyecto.
- `INSTRUCTION`: la consulta, que va **entre comillas** para que la terminal la entregue como un único argumento.

La búsqueda actual es **léxica determinista**: los términos se combinan con `AND` (todos deben cumplirse) y admite filtros `contact:`, `conversation:`, `topic:`, `account:` y `date:` junto a palabras clave libres.

**Filtros `account:` y `date:`**

- `account:ACCOUNT_ID` limita la consulta a los correos de una cuenta concreta, usando el mismo identificador que configuraste en `account add`/`account setup` (por ejemplo, `personal` o `gmail1`).

  ```
  python -m src.email query ./mi-store "factura account:personal"
  ```

- `date:YYYY-MM-DD` limita la consulta a los correos de una fecha concreta. El formato es **estricto**: exactamente `YYYY-MM-DD` (año de 4 dígitos, guion, mes de 2 dígitos, guion, día de 2 dígitos). Otras formas (por ejemplo `2026-9-10` o `10/09/2026`) no son válidas.

  ```
  python -m src.email query ./mi-store "factura date:2026-09-10"
  ```

- Los filtros se **combinan con `AND`** entre sí y con el resto de términos: solo se devuelven los correos que cumplen todos los criterios a la vez.

  ```
  python -m src.email query ./mi-store "factura account:personal date:2026-09-10 contact:ana@example.com"
  ```

### 5. Leer un nodo (read)

```
python -m src.email read ./mi-store store/emails/ID.md
```

Formato general:

```
python -m src.email read ROOT REL_PATH
```

`REL_PATH` debe ser una ruta Markdown relativa devuelta por `query`/`search`. La lectura rechaza rutas absolutas, con `~`, con `..` y cualquier intento de traversal.

### 6. Ver la lista de contactos (contact list)

```
python -m src.email contact list ./mi-store
```

Muestra la libreta de contactos guardada en ese `ROOT` (archivo `contacts.json`), una por línea:

```
{"name": "Ana Garcia", "email": "ana@example.com"}
```

Cada contacto sale como **una línea JSON** con solo las claves `name` y `email`, ordenado por `email` ascendente. Si todavía no hay contactos (o aún no se guardó la libreta), el comando **no imprime nada** y termina correctamente. Es una operación de solo lectura: no crea ni modifica nada.

### 7. Redactar

```
python -m src.email draft ./mi-store personal destino@ejemplo.com "Presupuesto septiembre" "Hola, te comparto el presupuesto."
```

Formato general:

```
python -m src.email draft ROOT ACCOUNT_ID TO SUBJECT BODY
```

Prepara un borrador con destinatario (`TO`), asunto (`SUBJECT`) y cuerpo (`BODY`). Devuelve un identificador de borrador (`DRAFT_ID`) que se usa en el envío.

### 8. Enviar

```
python -m src.email send ./mi-store personal ID_DEL_DRAFT "CONFIRMAR ENVIO"
```

Reemplaza `ID_DEL_DRAFT` por el identificador real que devolvió el comando `draft` (por ejemplo, `a1b2c3d4`). La frase `CONFIRMAR ENVIO` va **entre comillas** y escrita exactamente así. Si no coincide exactamente, el envío no se ejecuta y no se envía nada.

**Importante:** aunque la confirmación son dos palabras, en la línea de comandos se escribe entre comillas para que llegue al programa como **un único argumento** (`argv[4]`). Sin las comillas, la terminal la partiría en dos argumentos (`CONFIRMAR` y `ENVIO`) y el envío fallaría.

## Sobre la contraseña (credential_ref)

El programa NO pide contraseñas interactivamente y NO las guarda. En la configuración solo se guarda una referencia con el formato:

```
env://NOMBRE
```

donde `NOMBRE` es el nombre de una variable de entorno que TÚ ya debes tener configurada en tu equipo. Ejemplo: `env://GMAIL_PASS` significa que la contraseña está en la variable `GMAIL_PASS`. El programa solo la lee en el momento de conectar (IMAP/SMTP); nunca aparece escrita en archivos de configuración. Si la variable no existe, el comando falla.

## Proveedores soportados

- Gmail y Outlook se conectan por los protocolos estándar IMAP (lectura) y SMTP (envío), que son los valores por defecto.

## Límites actuales

- Los adjuntos (archivos dentro de un correo) NO se admiten todavía.
- No hay inicio de sesión con OAuth implementado: el acceso es con contraseña vía variable de entorno.