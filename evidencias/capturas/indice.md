# Capturas de la interfaz

Ninguna captura muestra métricas de 2014J: las de evaluación son out-of-fold de la validación cruzada, con su aviso visible. Las estimaciones de la cohorte 2014B (datos de demostración) llevan el aviso de que están dentro de la muestra y no miden el rendimiento. El flujo genérico (carga, configuración y seguimiento) usa el presupuesto de demostración, con su aviso visible.

| Archivo | Pantalla | Requisito | Experimento | CSV | Commit del código |
|---|---|---|---|---|---|
| `web-carga.png` | Datos para entrenar (paso 1) | RF-01 | web-2026-11-03-02 | `data/procesado/demo/entrenamiento_semana_4.csv` | 9945a8c |
| `web-configuracion.png` | Configurar el entrenamiento (paso 2) | RF-02 | web-2026-11-03-02 | `data/procesado/demo/entrenamiento_semana_4.csv` | 9945a8c |
| `web-seguimiento.png` | Seguimiento del entrenamiento (paso 3) | RF-03 | web-2026-11-03-02 | `data/procesado/demo/entrenamiento_semana_4.csv` | 9945a8c |
| `web-evaluacion-resumen.png` | Evaluación del modelo, vista resumida (paso 4) | RF-04, RF-07 | exp-2026-10-29-03 | `—` | 9945a8c |
| `web-evaluacion-detalle.png` | Evaluación del modelo, detalle técnico (paso 4) | RF-04, RF-07 | exp-2026-10-29-03 | `—` | 9945a8c |
| `web-modelos.png` | Modelos desplegados (paso 5) | RF-05 | exp-2026-10-29-03 | `—` | 9945a8c |
| `web-prediccion-lista.png` | Probabilidades estimadas del lote (paso 5) | RF-05 | exp-2026-10-29-03 | `data/procesado/demo/semana_4_2014B.csv` | 9945a8c |
| `web-explicacion-global.png` | Variables que más contribuyen (paso 6) | RF-06 | exp-2026-10-29-03 | `—` | d57a13b |
| `web-explicacion-local.png` | Explicación de una estimación (paso 6) | RF-06, RF-07 | exp-2026-10-29-03 | `data/procesado/demo/semana_4_2014B.csv` | 9945a8c |
| `web-explicacion-extrema.png` | Explicación de una estimación con contribución extrema (paso 6) | RF-06, RF-07 | exp-2026-10-29-03 | `data/procesado/demo/semana_12_2014B.csv` | d57a13b |
