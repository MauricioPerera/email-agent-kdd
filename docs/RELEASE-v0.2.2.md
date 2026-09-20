# Email Agent v0.2.2

## Correcciones

- Verifica la respuesta de `IMAP SELECT INBOX` durante la configuración para
  no guardar cuentas que solo pudieron autenticarse parcialmente.
- Corrige la resolución de rutas absolutas de Windows durante la persistencia
  de mensajes sincronizados.
- Añade pruebas de regresión para ambos casos.

## Distribución

La release publica el wheel de la CLI, su sdist, los wheels de dependencias y
`SHA256SUMS.txt`. Los instaladores y el prompt de onboarding descargan esta
versión y verifican todos los hashes antes de ejecutar pip.

## Verificación

- Suite: 1080 pruebas exitosas, 6 omitidas.
- Verificación real en Windows: 20 mensajes sincronizados correctamente.
