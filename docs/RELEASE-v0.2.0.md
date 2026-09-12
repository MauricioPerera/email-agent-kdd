# Email Agent v0.2.0

Actualización de la CLI y del plugin desde v0.1.0, con los cambios de adjuntos
y las correcciones de seguridad y fiabilidad del Sprint 78.

## Incluido

- Validación TLS en IMAP/SMTP e identidad de mensajes ligada a UIDVALIDITY.
- Estado persistente de envío y exclusión entre procesos. Los envíos ambiguos
  requieren una nueva autorización explícita; no se reintentan automáticamente.
- Extracción de texto de adjuntos con antivirus obligatorio; PDF aislado en Linux
  con Bubblewrap, prlimit y `/usr/bin/python3`.
- Paquete, plugin, catálogo e instaladores alineados a v0.2.0.
- Instalación desde wheels verificados con SHA-256 y sin índice de paquetes,
  incluyendo pypdf 6.18.1 y typing_extensions 4.16.0 (necesario en Python 3.10).

## Distribución

La release adjunta el wheel de la CLI, su sdist, los dos wheels de dependencias
con sus licencias incluidas y `SHA256SUMS.txt`. No se publica en PyPI ni se
sobrescribe v0.1.0. Los hashes detectan alteraciones respecto del manifiesto;
no constituyen una firma independiente del propietario de la release.

## Requisitos y migración

- Python 3.10 o posterior; CI cubre 3.10–3.13 en Windows, macOS y Linux.
- Re-sincronizar nodos antiguos sin UIDVALIDITY antes de operar sobre ellos.
  No inventar identidades ni modificar la base de estados para desbloquear envíos.
- `attachment extract` necesita un antivirus disponible y un resultado limpio.
  PDF solo está habilitado con el sandbox Linux; en Windows/macOS se rechaza.
  No se instala antivirus ni Bubblewrap automáticamente con estos wheels.
- El envío y las acciones irreversibles mantienen sus confirmaciones humanas.
  La publicación no accede a cuentas ni cambia datos de correo.

## Evidencia

La preparación local en Windows/Python 3.12 completó 1079 pruebas con seis
omisiones específicas de plataforma, compilación, construcción de sdist/wheel
e instalación sin índice en un entorno vacío fuera del checkout.
Las pruebas de instaladores ejecutan los scripts con descargas sintéticas y
bloquean pip ante hashes ausentes, duplicados o archivos alterados.

La matriz CI añade una instalación sin índice de los tres wheels en un venv
vacío para cada plataforma/versión de Python, además de las pruebas existentes
de transporte, persistencia e integración PDF. La release publicada enlaza
la ejecución correspondiente al commit exacto del tag.
