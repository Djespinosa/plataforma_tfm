---
description: Lanza la auditoría independiente de fugas y uso indebido del conjunto de prueba
argument-hint: "[archivo, carpeta o id de experimento; por defecto ml/]"
---

Usa el subagente **revisor-fuga** para auditar `$ARGUMENTS` (si está vacío, todo `ml/` y la última exportación de modelado).
Muéstrame su informe completo con los hallazgos ordenados por gravedad y su veredicto. No corrijas nada sin que te lo pida.
