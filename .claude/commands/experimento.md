---
description: Ejecuta un experimento de AutoML desde una configuración y lo exporta a evidencias/
argument-hint: "<ruta de la configuración en ml/configs/> [--ensayo] [--prueba]"
---

Ejecuta el experimento `$ARGUMENTS` con el subagente **ingeniero-ml**:

1. Lee la configuración y muéstrame un resumen (momento, candidatos, `n_trials`, semilla, variantes) y el tiempo estimado.
2. `--ensayo`: pocos *trials*, salida a la carpeta temporal de la sesión, sin exportar. Útil antes de cada ejecución larga.
3. Sin `--prueba`: solo validación cruzada (selección, calibración, umbral, métricas *out-of-fold*). Es el modo por defecto.
4. Con `--prueba`: **para y pídeme confirmación explícita**. Antes comprueba que la configuración está en el plan de
   evaluación confirmado en un commit anterior, que esa configuración no se ha evaluado ya en prueba y que **revisor-fuga**
   da "apto". Cada configuración se evalúa en prueba una sola vez.
5. Exporta según `contrato-evidencias` desde un árbol limpio y resume las métricas frente a las referencias
   (y frente a los umbrales de D4 en las semanas 8 y 12 si hubo evaluación en prueba).
