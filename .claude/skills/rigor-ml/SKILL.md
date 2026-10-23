---
name: rigor-ml
description: Checklist verificable de las decisiones metodológicas cerradas del TFM (etiqueta, población, cortes por semana, limpieza, partición 2014J, validación cruzada agrupada por presentación, AutoML, calibración, umbral, DeLong, parsimonia, SHAP, equidad, sensibilidad a la fuga). Usar SIEMPRE antes de escribir o revisar código que construya conjuntos de datos, variables, modelos, métricas o explicaciones, y antes de exportar cualquier resultado a evidencias/.
---

# Rigor del flujo de ML

**Fuente de verdad:** `../memoria/plan/decisiones.md` (solo lectura; nunca se escribe en `../memoria/`).
Si esta skill y ese archivo discrepan, prevalece `decisiones.md` y hay que avisar al estudiante para
actualizar esta skill. Los identificadores (D2, D29-rev…) son los de ese registro. Las secciones siguen la
numeración de `../memoria/.claude/skills/dominio-proyecto/references/rigor-ia.md`, que es la guía que
aplicará el analista de resultados de la memoria.

Cada punto se puede comprobar en el código o en el JSON exportado. Una casilla sin cumplir bloquea la exportación.

## 1. Datos, etiqueta y población

- [ ] **D2** Positivo = `final_result == "Withdrawn"`; `Fail`, `Pass` y `Distinction` son negativos.
- [ ] **D3/D25** Cortes k ∈ {0, 4, 8, 12}; día de corte = 7k; información hasta el día 7k **inclusive**.
- [ ] **D24/D25** En cada corte se excluye a quien tenga `date_unregistration ≤ 7k` (incluye las bajas antes del día 0
      y las del mismo día del corte). Se informan, por corte y partición, el tamaño de la población y la prevalencia.
- [ ] **D26** Se eliminan los `Withdrawn` sin `date_unregistration` (93). **D27** Se eliminan los `Fail` con
      `date_unregistration` (9). Recuentos esperados en exp-2026-10-05-02 (`calidad_datos`); el script debe
      comprobarlos y fallar si cambian.
- [ ] **D28** `date_registration` faltante (45): imputación por la mediana **calculada solo en entrenamiento**
      (dentro del pipeline, por pliegue) + indicador de faltante. La baja posterior a la duración se conserva.
- [ ] **Prohibido como variable:** `date_unregistration`, `final_result` y cualquier derivado de ellos.
- [ ] Clics (`studentVle.date`) y entregas (`studentAssessment.date_submitted`) solo con fecha ≤ 7k.
- [ ] **Matrícula tardía (propuesta a, confirmada 2026-10-17):** se excluye del corte k a quien tenga
      `date_registration > 7k`. La tabla de población por corte informa cuántos se excluyen por matrícula tardía.
      Las 45 matrículas sin `date_registration` se consideran matriculadas antes del inicio a efectos de elegibilidad
      (coherente con la imputación por mediana de D28); se declara.
- [ ] **Evaluaciones (propuesta b, confirmada 2026-10-17), configuración principal:**
      - Comportamiento de entrega (entregó o no; antelación = `date` − `date_submitted`) solo de evaluaciones con
        fecha límite `date ≤ 7k`, contando como entregadas solo las de `date_submitted ≤ 7k`.
      - Notas **solo de CMA** entregadas hasta el corte; **ninguna nota de TMA**.
      - Exámenes (`assessment_type == "Exam"`) fuera, filtrados por tipo (11 tienen `date` vacía).
      - **`is_banked` (decidido 2026-10-17 tras revisar los datos; el estudiante puede revocarlo):** las 1909 filas
        convalidadas (526 estudiantes, todos con `num_of_prev_attempts ≥ 1`) tienen `date_submitted = -1`: son notas de
        un intento previo, conocidas desde el día 0. Se excluyen del comportamiento de entrega y de las notas CMA, y
        forman variables propias disponibles desde la semana 0: nº de evaluaciones convalidadas y nota media
        convalidada (CMA y TMA: el retraso de corrección no aplica a un intento previo). 1 nota convalidada vacía.
      - Supuesto declarado: OULAD no registra la fecha de publicación de las notas; la distinción CMA (calificación
        automática) / TMA (por tutor) procede de kuzilek2017 y la disponibilidad inmediata de las CMA es una suposición.
      - Variante opcional de ablación (solo si hay tiempo): añadir notas de TMA entregadas al menos 14 días antes del
        corte (`date_submitted ≤ 7k − 14`, supuesto de plazo de corrección) e informar la diferencia de ROC-AUC.
- [ ] Comparación con la cohorte (F3): estadísticos de la misma presentación calculados solo con datos ≤ 7k.

## 2. Diseño experimental

- [ ] **D7-rev** Entrenamiento = las 15 presentaciones anteriores a 2014J (2013B, 2013J, 2014B); prueba = 2014J (7).
      Sin aleatoriedad en la partición. `code_module` y el tipo B/J son variables.
- [ ] **D29-rev** Validación interna: 5 pliegues **agrupados por presentación** (`code_module` + `code_presentation`,
      3 por pliegue). Todo lo que tenga validación interna (Optuna, calibración, apilamiento, umbral) usa **los mismos**
      pliegues. Estudiantes repetidos entre presentaciones: se cuentan y se declaran.
- [ ] Preprocesamiento (imputación, escalado, codificación) dentro de un `Pipeline` ajustado por pliegue.
- [ ] **Regla 3 de CLAUDE.md:** la prueba no interviene en ninguna decisión. Las configuraciones que se evaluarán en
      prueba (principal, referencias, variantes D8 y D20) se declaran en un archivo confirmado en un commit **anterior**
      a la primera evaluación en prueba. Cada configuración se evalúa en prueba una sola vez.
- [ ] Referencias: clase mayoritaria; regresión logística por defecto (criterio de éxito); regresión logística
      **optimizada con el mismo presupuesto** que AutoML (comparación justa, resultado central).
- [ ] Semillas fijas y registradas (Optuna, modelos, *bootstrap*).

## 3. AutoML y optimización

- [ ] Candidatos: RL regularizada, RF, GB, XGBoost, LightGBM, CatBoost, MLP y apilamiento de los mejores.
- [ ] Optuna con TPE; métrica objetivo ROC-AUC (**D6**) media en los pliegues de D29-rev; se registran `n_trials`,
      semilla, espacio de búsqueda por modelo y tiempo.
- [ ] **D30** Desbalance: pesos de clase como hiperparámetro; sin sobremuestreo por defecto.
- [ ] Apilamiento: la validación interna del metamodelo también agrupada por presentación (en scikit-learn 1.4,
      `StackingClassifier` no recibe `groups`: pasar los *splits* precalculados como `cv`).

## 4. Métricas, calibración y umbral

- [ ] **D31-rev** Orden: selección → calibración (Platt o isotónica, elegida por Brier en validación interna) con los
      mismos pliegues → umbral → reentrenamiento → evaluación única en prueba. Con `CalibratedClassifierCV` usar
      `cv=<splits agrupados>` y `ensemble=False`: así hay un único modelo base reentrenado (sobre el que se calcula SHAP,
      D32) y un calibrador ajustado con predicciones *out-of-fold*.
- [ ] **D6/D31** Umbral = el que alcanza sensibilidad ≥ 0,70 con máxima precisión sobre las probabilidades calibradas
      *out-of-fold*. Nunca se ajusta con prueba.
- [ ] **D21** En prueba, la sensibilidad se informa literalmente junto con umbral, precisión y **tasa de alerta** (D19).
- [ ] **D4/D22** Umbrales congelados: ROC-AUC ≥ 0,75 y sensibilidad ≥ 0,70 en las semanas 8 y 12, cada una por separado,
      sobre 2014J global. Superar a las referencias en **todos** los momentos.
- [ ] Reporte: ROC-AUC, PR-AUC, precisión, sensibilidad, F1, matriz de confusión, Brier, curva de calibración,
      media ± desviación entre pliegues y tiempo de ejecución.
- [ ] **D23** Desglose: CCC frente al resto; métricas por módulo solo informativas.

## 5. Comparación estadística

- [ ] **D5/F3** Por momento: prueba de **DeLong** (pareada, mismas observaciones) e **IC 95 % *bootstrap*** de la diferencia
      de ROC-AUC entre el mejor AutoML y la RL optimizada. Implementación propia con prueba unitaria contra un caso conocido.
- [ ] **F3** Ablación por grupos de variables (demográficas, actividad, evaluaciones) y por momento.
- [ ] **D20** Sensibilidad a la fuga: repetir cada momento **sin** excluir a los ya retirados e informar la diferencia de
      ROC-AUC (figura por semana). Es un análisis, no un criterio de éxito.
- [ ] **D33** Parsimonia: la plataforma despliega el modelo más simple cuya diferencia con el mejor no sea significativa
      (DeLong). `[DECIDIR con el estudiante antes de implementar]`: (i) el orden de complejidad entre familias,
      fijado de antemano; (ii) que la comparación se haga con predicciones *out-of-fold* y no con prueba (si se hace con
      prueba, la prueba decide qué se despliega, en conflicto con la regla 3).

## 6. Explicabilidad y equidad

- [ ] **D32** SHAP sobre la salida **sin calibrar** (log-odds). La interfaz muestra la probabilidad calibrada.
- [ ] **D33** TreeSHAP para árboles; permutación con muestra de fondo para MLP y apilamiento (se informa el coste).
- [ ] **OE4** SHAP local para el 100 % de las predicciones que emite la plataforma.
- [ ] **D9** Estabilidad: Spearman de las importancias medias |SHAP| entre pares de pliegues y solapamiento del top-10
      (media y rango), solo entre pliegues, sin umbral.
- [ ] **D8** Variables sensibles (`gender`, `disability`, `age_band`, `imd_band`): entrenar con y sin ellas. Si quitarlas
      cuesta < 0,02 de ROC-AUC **en validación cruzada**, el defecto es sin ellas. Sensibilidad y tasa de falsos
      positivos por subgrupo. En prueba se informan ambas variantes, sin usarlas para elegir.

## 7. Reproducibilidad

- [ ] Exportación según la skill `contrato-evidencias` (árbol limpio, commit, id, versiones, SHA-256 de entradas).
- [ ] El código de cada número de la memoria está en el repositorio y se ejecuta con un solo comando.

## Limitaciones conocidas que se declaran (no se "arreglan" en silencio)

- La selección y el umbral usan las mismas predicciones *out-of-fold*: ligero optimismo de las métricas de validación.
- CCC solo tiene una presentación de entrenamiento (2014B): en el pliegue que la contiene, CCC no se ve al entrenar.
- Withdrawn como aproximación a la deserción (D2).
