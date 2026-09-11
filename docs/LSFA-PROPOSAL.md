# LSFA: Local Secure Forms for Agent CLIs

Estado: propuesta experimental  
Versión: 0.1  
Implementación de referencia: `email-agent`

## Resumen

LSFA propone un mecanismo pequeño para que un agente que opera una CLI pueda
solicitar datos al usuario sin pedirle que copie comandos complejos y sin
exponer secretos al agente.

La CLI decide cómo presentar la solicitud: formulario gráfico local, preguntas
interactivas en terminal o modo headless previamente autorizado. El usuario
introduce los datos directamente en la interfaz elegida. La CLI valida la
información, ejecuta las comprobaciones necesarias y guarda los secretos en el
almacén seguro del sistema operativo. El agente recibe únicamente un resultado
estructurado.

El caso de referencia es la configuración de una cuenta IMAP/SMTP.

## Motivación

Las interfaces de agentes suelen fallar en uno de dos extremos:

- Piden al usuario introducir contraseñas en el chat, en argumentos de shell o
  en variables que luego quedan expuestas en historiales y logs.
- Obligan a construir una aplicación completa cuando solo se necesitan unos
  pocos datos para completar una operación.

LSFA limita la interfaz al contexto de la tarea actual. No pretende reemplazar
una aplicación completa ni eliminar la configuración manual para usuarios
avanzados o entornos sin interfaz gráfica.

## Objetivos

LSFA debe:

1. Evitar que valores sensibles pasen por el canal del agente.
2. Permitir que el agente inicie el flujo sin pedir al usuario que copie una
   línea compleja.
3. Solicitar únicamente los campos necesarios para la operación.
4. Validar los datos antes de almacenarlos o ejecutar una acción externa.
5. Funcionar con UI gráfica, terminal y entornos headless.
6. Devolver estados verificables sin devolver secretos.
7. Mantener una confirmación humana independiente para acciones destructivas o
   irreversibles.

## No objetivos

LSFA no define:

- un sistema de identidad del usuario;
- un gestor de contraseñas nuevo;
- una UI visual universal;
- un protocolo de comunicación entre modelos;
- una autorización implícita para que el agente envíe, borre o comparta datos.

## Modelo de confianza

| Actor | Puede recibir |
|---|---|
| Usuario | Todos los campos que introduce y el resultado visible |
| CLI | Los valores necesarios para validar y completar la operación |
| Agente | Estado, diagnósticos seguros e identificadores no sensibles |
| Almacén del sistema | El secreto persistido |
| Logs | Metadatos no sensibles; nunca valores de campos secretos |

La propiedad esencial es que la CLI actúa como frontera entre la interfaz de
usuario y el agente. Un secreto no debe aparecer en argumentos, stdin del
agente, stdout, stderr, logs, archivos temporales ni mensajes de error.

Esta garantía protege contra exposición accidental al agente y a sus canales.
No pretende proteger contra malware con control total de la máquina del usuario.

## Flujo normativo

```text
Agente solicita una operación
        |
        v
CLI crea una solicitud temporal y muestra el propósito
        |
        v
Usuario completa el formulario local
        |
        v
CLI valida campos y prueba la conexión/operación
        |
        v
Usuario confirma el almacenamiento o la acción
        |
        v
CLI guarda el secreto en el almacén seguro
        |
        v
CLI devuelve solo un resultado estructurado
```

La solicitud debe expirar, poder cancelarse y estar ligada a una operación
concreta. Cerrar la ventana no equivale a aceptar.

## Solicitud

Una implementación puede transportar la solicitud por argumentos fijos,
stdin estructurado o una API local. El transporte no debe obligar al usuario a
copiar comandos. El modelo lógico mínimo es:

```json
{
  "operation": "connect_email",
  "purpose": "Configurar una cuenta de correo",
  "presentation": "auto",
  "fields": [
    {"name": "email", "type": "email", "sensitivity": "private", "required": true},
    {"name": "password", "type": "secret", "sensitivity": "secret", "required": true},
    {"name": "imap_host", "type": "hostname", "sensitivity": "public", "required": true},
    {"name": "imap_port", "type": "integer", "default": 993, "sensitivity": "public"},
    {"name": "smtp_host", "type": "hostname", "sensitivity": "public", "required": true},
    {"name": "smtp_port", "type": "integer", "default": 465, "sensitivity": "public"}
  ],
  "validation": {"preflight": "imap_auth_and_smtp_auth"},
  "expires_in_seconds": 600
}
```

Los tipos `secret` deben usar controles de entrada ocultos y nunca formar parte
de la respuesta al agente.

## Resultado

Los resultados mínimos son `accepted`, `declined`, `cancelled`, `invalid`,
`failed` y `expired`.

Ejemplo exitoso:

```json
{
  "status": "accepted",
  "operation": "connect_email",
  "account_id": "rckflr-ardf-dev",
  "credential_stored": true,
  "imap_verified": true,
  "smtp_verified": true
}
```

Ejemplo de fallo:

```json
{
  "status": "failed",
  "operation": "connect_email",
  "reason_code": "imap_authentication_failed",
  "retryable": true
}
```

`reason_code` debe ser estable, genérico y no contener contraseñas, tokens,
respuestas completas de servidores ni datos privados innecesarios.

## Validación previa

La validación tiene dos niveles:

1. Validación local: formato de correo, campos obligatorios, rangos, hostname,
   puertos y restricciones del proveedor.
2. Validación de operación: autenticación IMAP y autenticación SMTP sin enviar
   un correo.

Una cuenta no debe marcarse como conectada ni persistirse hasta completar la
política de validación definida para la operación. La prueba SMTP debe cerrar
la sesión después de autenticarse y no debe ejecutar `send_message`.

## Modos de presentación

### Gráfico

La CLI abre una ventana local y espera a que el usuario acepte, rechace o
cancele. Es el modo recomendado para usuarios no técnicos.

### Terminal

La CLI formula preguntas sencillas. Los secretos se leen con entrada oculta y
no se aceptan como argumentos visibles.

### Headless

La CLI usa un almacén de secretos o una referencia previamente autorizada. No
debe convertir automáticamente un secreto en texto plano ni imprimirlo.

### Automático

El agente solicita `presentation: auto`; la CLI elige gráfico si hay UI,
terminal si existe un TTY y headless solo si existe una política explícita.

## Confirmaciones

La confirmación debe ser independiente del agente para:

- guardar o reemplazar un secreto;
- enviar correo;
- desvincular una cuenta;
- eliminar datos;
- conceder permisos nuevos.

El agente puede explicar la operación y esperar el resultado, pero no puede
inventar, reutilizar ni completar silenciosamente la confirmación.

## Ejemplo de correo

El agente solicita conectar una cuenta. La CLI abre el formulario con correo,
contraseña, IMAP y SMTP. Tras completar los campos:

1. descubre o muestra los servidores;
2. valida formato y puertos;
3. prueba IMAP en modo lectura;
4. prueba autenticación SMTP sin enviar;
5. muestra el resultado al usuario;
6. guarda la contraseña en Credential Manager, Keychain o Secret Service;
7. devuelve al agente solo el estado y las comprobaciones realizadas.

La alternativa manual sigue disponible para scripts y servidores sin UI.

## Requisitos de una implementación conforme

Una implementación conforme debe demostrar que:

- no incluye secretos en `argv`, logs, stdout o stderr;
- no deja archivos temporales con secretos;
- valida el esquema antes de ejecutar la operación;
- distingue aceptar, rechazar, cancelar, fallo y expiración;
- aplica expiración y cancelación;
- usa el almacén seguro nativo cuando está disponible;
- no guarda una cuenta si falla la validación requerida;
- no ejecuta acciones destructivas sin confirmación humana;
- ofrece una ruta terminal o headless equivalente cuando no hay UI.

## Relación con otros protocolos

LSFA puede transportarse sobre MCP, ACP, stdio, sockets locales u otros
canales, pero no depende de ellos. MCP ya define elicitation para solicitar
información al usuario y recomienda un flujo fuera de banda para secretos.
ACP también define respuestas de aceptación, rechazo y cancelación. LSFA
concreta una variante local orientada a CLIs, con almacén seguro y una frontera
explícita entre agente y usuario.

La propuesta no compite con formatos de UI ricos: una implementación podría
usar un renderer declarativo, pero la conformidad dependería de la protección
del secreto y del resultado, no de la tecnología visual.

## Plan de evolución

1. Implementación de referencia para configuración de correo.
2. Pruebas de no filtración y pruebas multiplataforma.
3. Adaptadores nativos de almacenamiento seguro.
4. Segundo caso de uso, por ejemplo una API key.
5. Revisión pública en el repositorio.
6. Propuesta de extensión o perfil para protocolos de agentes existentes.

## Preguntas abiertas

- ¿Debe el formulario ser creado por la CLI o por un proceso local separado?
- ¿Cómo se autentica la solicitud cuando el agente y la CLI son procesos
  distintos?
- ¿Qué capacidades mínimas deben negociarse para gráfico, terminal y
  headless?
- ¿Cómo se audita una operación sin registrar datos sensibles?
- ¿Qué política de expiración y reintentos es segura para cada operación?

## Estado de esta propuesta

LSFA es una propuesta de diseño y una guía para la implementación experimental
en `email-agent`. No es todavía un estándar aprobado ni debe presentarse como
uno.
