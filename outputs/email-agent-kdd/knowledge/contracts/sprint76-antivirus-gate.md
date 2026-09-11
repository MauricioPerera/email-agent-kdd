---
type: KDD Contract
id: email-agent-sprint76-antivirus-gate
objective: Escanear adjuntos antes de procesarlos con politica fail-closed
status: frozen
---

- el adaptador antivirus acepta bytes y no expone rutas ni contenido en errores;
- los estados publicos son `clean`, `infected`, `unavailable` y `error`;
- solo `clean` permite continuar la extraccion;
- ausencia, timeout, error o estado desconocido detienen el flujo;
- el adaptador por defecto usa ClamAV por stdin, sin temporales;
- el scanner es inyectable en pruebas;
- los parsers activos siguen bloqueados hasta contar con sandbox.
