---
type: KDD Contract
id: email-agent-sprint74-verified-release-installer
objective: Instalar el wheel de una release verificando su integridad
status: frozen
---

- el modo normal descarga el wheel y `SHA256SUMS.txt` desde la release `v0.1.0`;
- el hash SHA-256 se verifica antes de invocar pip;
- un hash ausente o distinto detiene la instalación;
- el modo normal no requiere Git y usa `--no-index` al instalar el wheel;
- el modo `--source`/`-FromSource` es explícito y queda reservado para desarrollo;
- ambos modos verifican `email-agent --help` al finalizar;
- no se solicitan ni manejan credenciales.
