# Corrección de salida Unicode en Windows

## Resumen

La salida del subcomando `read` ahora emite UTF-8 en Windows mediante el
buffer binario de stdout. Para streams capturados o embebidos sin buffer,
intenta reconfigurar el stream a UTF-8 y conserva el fallback existente.

## Archivos tocados

- `src/email/cli.py`
- `outputs/email-agent-kdd/tests/frozen_cli_read_unicode.py`

## Pruebas

- Prueba regresiva: `test_write_stdout_emite_utf8_en_windows`.

## Estado

Implementado y verificado: 11 pruebas relacionadas pasan. La prueba de
integración contra un nodo real produjo salida decodificable como UTF-8 y
terminó con código 0.
