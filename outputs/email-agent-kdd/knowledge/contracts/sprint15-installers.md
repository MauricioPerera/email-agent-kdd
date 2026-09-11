---
type: KDD Contract
id: email-agent-sprint15-installers
objective: Detectar requisitos de instalación y guiar al usuario final
status: frozen
---

# Contrato del Objetivo 15

- los instaladores detectan Python ausente o inferior a 3.10;
- verifican `pip` antes de intentar instalar;
- usan el mismo intérprete para `pip` e `email-agent`;
- muestran instrucciones específicas y detienen el proceso ante un requisito faltante;
- no piden secretos ni modifican almacenes de credenciales;
- continúan verificando `email-agent --help` después de instalar.
