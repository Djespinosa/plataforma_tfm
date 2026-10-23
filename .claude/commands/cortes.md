---
description: Construye o actualiza los conjuntos de OULAD por momento de predicción y exporta sus estadísticas
argument-hint: "[semanas, por defecto 0 4 8 12] [--ensayo]"
---

Construye los cortes de OULAD con el subagente **ingeniero-datos**:

1. Semanas: `$ARGUMENTS` o, si está vacío, 0, 4, 8 y 12. Con `--ensayo`, exporta a la carpeta temporal de la sesión.
2. Comprueba en la skill `rigor-ml` §1 si hay propuestas pendientes de confirmar; si las hay, pregúntame antes de seguir.
3. Ejecuta (o crea, si no existe) `ml/cortes_oulad.py` y sus pruebas. Las pruebas deben pasar antes de exportar.
4. Sin `--ensayo`: comprueba que el árbol está limpio; si no, dime qué falta confirmar y para.
5. Lanza **revisor-fuga** sobre el código de los cortes y muéstrame su veredicto.
6. Resume, por semana y partición: población, prevalencia de `Withdrawn`, exclusiones y nº de variables por grupo,
   y el id del experimento exportado.
