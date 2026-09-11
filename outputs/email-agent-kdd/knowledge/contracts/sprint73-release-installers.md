---
type: KDD Contract
id: email-agent-sprint73-release-installers
objective: Instalar desde una release estable sin depender de una rama mutable
status: frozen
---

- Windows y macOS/Linux usan `v0.1.0` por defecto;
- cada instalador permite una referencia alternativa explícita;
- ambos instaladores verifican `email-agent --help` después de instalar;
- el instalador no solicita ni imprime credenciales;
- la referencia estable coincide con el tag y el marketplace publicados.
