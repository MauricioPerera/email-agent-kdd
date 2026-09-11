# Objetivo 15 — Instaladores guiados

Los instaladores ahora comprueban Python 3.10+, la disponibilidad de `pip` y
el comando de instalación antes de continuar. Si falta un requisito, detienen
el proceso con una instrucción específica y no modifican credenciales ni
configuración de correo.

La selección de Python en macOS y Linux prefiere `python3` y usa `python` como
respaldo. Windows utiliza `python`. En todos los casos la instalación se hace
con `python -m pip`, evitando depender de un ejecutable `pip` distinto del
intérprete validado.

Los instaladores no prueban ni crean almacenes seguros durante la instalación;
esa comprobación ocurre al abrir el formulario de cuenta, donde el sistema
puede explicar si falta Credential Manager, Keychain o Secret Service.

Validación local: 912 tests existentes más el test de requisitos de instalador.
