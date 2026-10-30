---
description: Lanza la revisión independiente de calidad del código antes de un commit
---

Usa el subagente **revisor-codigo** para revisar `$ARGUMENTS` (si está vacío, el diff actual: `git diff` y los archivos
sin seguimiento). Muéstrame su informe completo con los hallazgos ordenados por gravedad y su veredicto. No corrijas
nada sin que te lo pida.
