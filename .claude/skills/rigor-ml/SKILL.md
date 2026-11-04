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
        convalidadas (526 matrículas de 523 estudiantes, todas con `num_of_prev_attempts ≥ 1`) tienen `date_submitted = -1`: son notas de
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
- [ ] Las columnas de entrada salen del catálogo de variables; `NO_VARIABLES` de `ml/cortes_oulad.py` (incluido
      `pliegue`, que vale NA en 2014J y delataría la partición) se descarta de forma explícita.
- [ ] **Regla 3 de CLAUDE.md:** la prueba no interviene en ninguna decisión. Las configuraciones que se evaluarán en
      prueba (principal, referencias, variantes D8 y D20) se declaran en un archivo confirmado en un commit **anterior**
      a la primera evaluación en prueba. Cada configuración se evalúa en prueba una sola vez.
- [ ] Referencias: clase mayoritaria; regresión logística por defecto (criterio de éxito); regresión logística
      **optimizada con el mismo presupuesto** que AutoML (comparación justa, resultado central).
- [ ] Semillas fijas y registradas (Optuna, modelos, *bootstrap*).
- [ ] **Entrega 2 (prompt de la memoria, 2026-10-23):** ningún modelo se evalúa en 2014J; todas las métricas son
      *out-of-fold*. De 2014J solo se exportan recuentos descriptivos (población, prevalencia, subgrupos, solapamiento).
- [ ] **D38 Variantes sin nueva búsqueda:** D8 (con y sin sensibles), la ablación y D20 **reutilizan los hiperparámetros**
      de la configuración principal (mismo momento y familia) y solo reentrenan; se declara. La búsqueda principal se hace
      **sin variables sensibles**, así que la ventaja de la variante "con" es una cota inferior (D38).
      **Salvaguarda (D38-concreción):** si excluirlas cuesta ≥ 0,02 de ROC-AUC *out-of-fold* calibrada (estimación
      puntual, con − sin) en algún momento, en algún candidato o entre los mejores de cada variante, la configuración
      principal pasa a ser "con" y se repite la búsqueda para ella. Resultado: no activada (exp-2026-10-28-01, máx. 0,0181,
      MLP en la semana 4, cuyo IC llega a 0,0242: no se afirma que el coste sea < 0,02 con seguridad).
      **D38-concreción-D20:** la inflación de D20 se describe como **estimación previsiblemente sesgada a la baja**, no como
      cota inferior garantizada (TPE estocástico, calibración elegida por Brier, ruido de reentrenamiento; control de la
      semana 0: +0,0045 en el apilamiento y −0,0023 en la RL).
      Implementación de D8: `ml/variante.py` con `ml/configs/con_sensibles.json`; compara por modelo la ROC-AUC
      *out-of-fold* calibrada con − sin sobre las mismas filas (las "sin" son las OOF del principal, por SHA-256), y la
      salvaguarda se activa si la diferencia puntual es ≥ 0,02 en algún candidato o entre los mejores de cada variante,
      en algún momento. El script avisa; no cambia la configuración por su cuenta.

## 3. AutoML y optimización

- [ ] Candidatos de la búsqueda: RL regularizada, RF, GB, XGBoost, LightGBM, CatBoost y MLP. El apilamiento **no** entra
      en la búsqueda (D48, abajo).
- [ ] Optuna con TPE y poda (valor intermedio = media acumulada tras cada pliegue); métrica objetivo ROC-AUC (**D6**)
      media en los pliegues de D29-rev; se registran `n_trials`, semilla, configuración del muestreador y del podador,
      espacio de búsqueda por modelo y tiempo. La RL optimizada recibe el mismo nº de ensayos que cada familia.
      Se exportan los parámetros efectivos de TPE y del podador (`test_parametros_efectivos_de_optuna`), el tiempo
      máximo por búsqueda (ninguno), el nivel al que actúa `n_jobs`, el hardware sin nombre del equipo y el JUnit de
      todas las pruebas en el commit del experimento.
- [ ] **D53** Primer ensayo de cada familia = su configuración por defecto (`enqueue_trial`, `PREDETERMINADOS` de
      `ml/automl/busqueda.py`), para que la optimizada nunca quede por debajo de ella en la métrica objetivo (D6 sin
      cambios: media de ROC-AUC de los 5 pliegues, sin calibrar). Los valores por defecto que caen fuera del espacio se
      encolan con el valor más cercano y se declaran en el Anexo C (`PREDETERMINADOS_NOTA`). En la RL es exactamente la
      referencia `rl_defecto` (C = 1, L2, sin pesos de clase; `liblinear` en ambas RL, misma entrada); el espacio de la
      RL incluye C = 1 con L2. `rl_defecto` pasa por la **misma calibración anidada** y elección por Brier que los
      candidatos (la mayoritaria, sin calibrar). Pruebas: `test_rl_optimizada_nunca_por_debajo_de_la_rl_por_defecto`,
      `test_rl_defecto_con_la_misma_calibracion_anidada_que_los_candidatos`.
- [ ] **D30** Desbalance: pesos de clase como hiperparámetro; sin sobremuestreo por defecto.
- [ ] Implementación (F2, `ml/automl/busqueda.py`; se declara en el Anexo C): GB = `HistGradientBoostingClassifier`
      (admite vacíos y es mucho más rápido que el clásico); RL con `liblinear` y L1 o L2 (`saga` con red elástica no
      convergía); MLP y XGBoost reciben los pesos de clase como pesos por muestra. Entrada: one-hot con "faltante" en las
      categóricas; RL y MLP imputan por la mediana con indicador y estandarizan; los árboles tratan los vacíos estructurales
      de forma nativa y solo imputan `date_registration` (D28).
- [ ] **D48 Apilamiento sin fuga**, paso posterior a la búsqueda: combina el mejor modelo de cada familia con sus
      hiperparámetros ya fijados (sin nueva búsqueda, como D38). Metamodelo: RL regularizada. Para cada pliegue externo
      *f*, el metamodelo se entrena con predicciones *out-of-fold* de una validación cruzada **interna** agrupada por
      presentación sobre los otros 4 pliegues; nunca ve predicciones de los datos con que se evalúa. Modelo final: igual
      sobre las 15 presentaciones (metamodelo con las predicciones *out-of-fold* de los 5 pliegues). `StackingClassifier`
      no recibe `groups`: pasar los *splits* precalculados como `cv`. Su coste computacional se informa por separado.
      Sus probabilidades son la salida del metamodelo logístico, sin calibración anidada adicional (añadirla exigiría
      una tercera validación cruzada anidada); se declara (**D52**).

## 4. Métricas, calibración y umbral

- [ ] **D31-rev** Orden: selección → calibración → umbral → reentrenamiento → evaluación única en prueba (Entrega 3).
- [ ] **Calibración anidada (2026-10-23).** Para cada pliegue externo *f*: modelo y calibrador (Platt e isotónica) se
      ajustan solo con los otros 4 pliegues, con `CalibratedClassifierCV(cv=<divisiones internas agrupadas por
      presentación>)` (nunca `cv=5` sin grupos), y se predice *f*. Ninguna probabilidad calibrada *out-of-fold* procede de un
      calibrador que vio esa matrícula. Método elegido por Brier sobre esas predicciones. **No es válido** calibrar con los
      5 pliegues y fijar el umbral sobre esas mismas probabilidades.
- [ ] **D54** `CalibratedClassifierCV(..., ensemble=False)`: dentro de cada pliegue externo, el calibrador se ajusta con las
      predicciones *out-of-fold* de las divisiones internas agrupadas y el modelo base se reentrena con los 4 pliegues
      completos, como el modelo final. Con `ensemble=True` la probabilidad calibrada promediaba 4 modelos entrenados con
      3/5 de los datos y penalizaba de forma desigual a las familias (MLP −0,025 en la semana 0 de exp-2026-10-26-01).
      Prueba: `test_calibrador_de_cada_pliegue_externo_no_usa_filas_de_ese_pliegue` (estimador espía).
- [ ] **D6/D31/D45** Umbral = el que alcanza sensibilidad ≥ 0,70 (exacto, **sin margen**) con máxima precisión sobre las
      probabilidades calibradas *out-of-fold* anidadas. Nunca se ajusta con prueba. Riesgo asumido y declarado: quedar por
      debajo de 0,70 en prueba por variabilidad o cambio de cohorte.
- [ ] Modelo final (desplegado y, en la Entrega 3, evaluado en prueba): reentrenado con las 15 presentaciones y calibrado
      con `CalibratedClassifierCV` sobre los 5 pliegues agrupados; se le aplica el umbral anterior. SHAP sobre su modelo base
      sin calibrar (D32). Se declara que umbral y modelo final proceden de ajustes distintos.
- [ ] **D41-concreción** (preparado, no evaluado; exp-2026-10-29-03): en cada momento, la RL desplegada con los
      hiperparámetros y el método de calibración del principal (D38), reentrenada con las presentaciones de entrenamiento y
      calibrada sobre los 5 pliegues agrupados con `ensemble=False` (D54). Umbral recalculado desde las OOF calibradas del
      principal, que debe coincidir con su JSON: 0,213612 / 0,150952 / 0,132519 / 0,117117 (semanas 0/4/8/12). Un
      `.joblib` por momento (modelo calibrado, umbral, columnas, fondo del explicador) en `data/procesado/modelos/`, no
      versionado, con su SHA-256 en el JSON. 2014J no se lee; `metricas_test` = null. D45 pendiente antes de evaluar.
- [ ] **P-13** Modelo final de la variante con sensibles: se prepara igual que D41-concreción (hiperparámetros de
      exp-2026-10-27-01, calibración elegida en exp-2026-10-28-01, umbral desde sus OOF) para informar en prueba ambas
      variantes como dato informativo, sin usarlas para elegir. No se despliega.
- [ ] **D21** En prueba, la sensibilidad se informa literalmente junto con umbral, precisión y **tasa de alerta** (D19).
- [ ] **D4/D22** Umbrales congelados: ROC-AUC ≥ 0,75 y sensibilidad ≥ 0,70 en las semanas 8 y 12, cada una por separado,
      sobre 2014J global. Superar a las referencias en **todos** los momentos.
- [ ] Reporte: ROC-AUC, PR-AUC, precisión, sensibilidad, F1, matriz de confusión, Brier, curva de calibración,
      media ± desviación entre pliegues y tiempo de ejecución.
- [ ] **D23** Desglose: CCC frente al resto; métricas por módulo solo informativas.

## 5. Comparación estadística

- [ ] **D40 ROC-AUC informado:** media ± desviación entre pliegues **y** ROC-AUC de las predicciones *out-of-fold* agrupadas
      (métrica principal; sobre ella se calculan DeLong, Holm y la parsimonia). Se declara que esas predicciones proceden de
      5 modelos distintos.
- [ ] **D44** Mejor modelo del motor AutoML = el candidato **distinto de la RL** con mayor ROC-AUC *out-of-fold* (puede ser
      el apilamiento). Así *Δ*ₖ (mejor AutoML − RL optimizada) no es 0 por construcción.
- [ ] **D5/F3/D49** Por momento: *Δ*ₖ, su **IC 95 % *bootstrap* sin ajustar** (pareado, remuestreo de matrículas), *p* de
      **DeLong** (pareada) y *p* **corregido por Holm** sobre los 4 momentos. Diferencia mínima relevante: **0,02**. Lectura
      que se exporta: significativa y ≥ 0,02 → ventaja relevante; significativa y < 0,02 → detectable sin relevancia práctica;
      no significativa → no concluyente, salvo IC dentro de ±0,02 → equivalencia práctica. Implementación propia de DeLong
      con prueba unitaria contra un caso conocido. La lectura usa el **signo** de *Δ*ₖ (AutoML − RL): una desventaja
      significativa ≥ 0,02 es `desventaja_relevante`, nunca una ventaja.
- [ ] **D46-rev** Ablación (solo en validación cruzada) sobre el **mejor modelo del motor** (D44; principal) y la **RL
      desplegada** (complementario), reutilizando sus hiperparámetros (D38). La pérdida (completo − sin el grupo, mismas
      filas) es una **estimación sesgada al alza** de la contribución, no una cota superior garantizada. Los IC
      *bootstrap* y DeLong no recogen la variabilidad del reentrenamiento (control de la semana 0: ≈ 0,0045); las pérdidas
      de ese orden no se leen como contribución aunque su IC excluya el 0. Por momento, con los 5 grupos de `GRUPOS` en
      `ml/cortes_oulad.py` (columna `grupo_ablacion` del catálogo; reparto de D51-rev): (1) demográficas y matrícula;
      (2) aula virtual, clics agregados, 25 (totales, por tipo de actividad, por ventana semanal, días activos); (3) aula
      virtual, variables derivadas, 8 (regularidad, tendencia, recencia, inactividad, percentiles de cohorte);
      (4) evaluaciones, incluidas las convalidadas; (5) contexto del módulo.
- [ ] **D20** Sensibilidad a la fuga: repetir cada momento **sin** excluir a los ya retirados (salvo las bajas anteriores al
      día 0) e informar la diferencia de ROC-AUC (figura por semana). Se mantienen la exclusión por matrícula tardía y
      D26/D27, para que solo cambie la exclusión de los ya retirados. Es un análisis, no un criterio de éxito.
- [ ] **D39-concreción** (exp-2026-10-29-01): (1) lectura primaria, cada variante con sus OOF en su propia población, IC
      por *bootstrap* de estudiantes sobre la población con fuga (2000 réplicas, semilla 42); (2) complementaria, modelo
      con fuga en las filas comunes frente al principal (IC pareado, DeLong informativo); (3) descomposición: inflación
      total = efecto de evaluar con casos triviales [fuga(su población) − fuga(comunes)] + efecto de entrenar con ellos
      [fuga(comunes) − principal(comunes)]; (4) mismos dos modelos que la ablación (D46-rev), hiperparámetros del
      principal, mismos pliegues, n y prevalencia por población y momento, 2014J fuera. Inflación: estimación
      previsiblemente sesgada a la baja (D38-concreción-D20).
- [ ] **D33/D49-rev** Parsimonia por **no inferioridad**: "el mejor" es el candidato de mayor ROC-AUC *out-of-fold* (incluida
      la RL). Se despliega el modelo más simple (RL < árboles < MLP < apilamiento) cuya pérdida de ROC-AUC *out-of-fold*
      frente al mejor (mejor − candidato) tenga el **límite superior del IC *bootstrap* del 95 % < 0,02**. DeLong ya no decide
      (con ≈ 21 000 predicciones declara significativas diferencias triviales); su *p* solo se informa. Nunca con prueba.
      Dentro de "árboles" (RF, GB, XGBoost, LightGBM, CatBoost), si varios cumplen, el de mayor ROC-AUC *out-of-fold*. Se
      exporta, por candidato frente al mejor: diferencia, IC, *p* de DeLong y si cumple la regla. La lectura en cuatro
      casos de D49 se mantiene para el contraste central.

## 6. Explicabilidad y equidad

- [ ] **D32** SHAP sobre la salida **sin calibrar** (log-odds). La interfaz muestra la probabilidad calibrada.
- [ ] **D33** TreeSHAP para árboles; permutación con muestra de fondo para MLP y apilamiento (se informa el coste).
- [ ] **D33-concreción** La RL desplegada se explica con **SHAP lineal exacto** en log-odds sin calibrar,
      φ_j = coef_j · (x_j − media de las filas de ajuste transformadas) (≡ `shap.LinearExplainer` con fondo independiente =
      filas de ajuste; en el modelo final, todo el entrenamiento). Por colinealidad, contexto de la presentación y actividad
      se leen por bloques. Estabilidad en dos versiones: la principal excluye las variables con SHAP nulo en todos los
      pliegues; la secundaria las incluye. Los SHAP locales extremos (p. ej. −40,6 log-odds) se atienden en la interfaz,
      no en el modelo. Implementación de la plataforma: |φ| > 5 (`automl.explicacion.LIMITE_EXTREMO`, de
      exp-2026-10-29-05) se marca y se avisa, sin recortar.
- [ ] **OE4** SHAP local para el 100 % de las predicciones que emite la plataforma.
- [ ] **D9** Estabilidad: Spearman de las importancias medias |SHAP| entre pares de pliegues y solapamiento del top-10
      (media y rango), solo entre pliegues, sin umbral.
- [ ] **D8** Variables sensibles (`gender`, `disability`, `age_band`, `imd_band`): entrenar con y sin ellas. Si quitarlas
      cuesta < 0,02 de ROC-AUC **en validación cruzada**, el defecto es sin ellas. Sensibilidad y tasa de falsos
      positivos por subgrupo. En prueba se informan ambas variantes, sin usarlas para elegir.
- [ ] **D50 Equidad** (probabilidades igualadas, hardt2016). Atributos: `gender`, `disability`, `age_band`, `imd_band`
      (con su grupo de faltantes). Por subgrupo, momento y conjunto (*out-of-fold*; 2014J solo en la evaluación final):
      matrículas, **retiros**, sensibilidad (indicador principal) y tasa de falsos positivos (secundario) en el umbral de
      decisión, cada una con IC *bootstrap*; diferencia entre subgrupos de cada métrica (la máxima si hay más de dos
      categorías). Métrica **"solo descriptiva"** si el subgrupo tiene < 30 retiros en 2014J (recuento descriptivo,
      permitido en la Entrega 2). La diferencia se exporta con todos los subgrupos y sin los "solo descriptiva"; su IC es
      un *bootstrap* de percentiles sobre un máximo menos un mínimo (sesgado hacia arriba) y se declara. Si falta el
      recuento de prueba de un subgrupo, el cálculo falla (no cuenta 0).
- [ ] Entrega 2: estabilidad de SHAP (D9) solo con TreeSHAP y si F3 termina a tiempo (permutación: Entrega 3); equidad
      *out-of-fold* (D50).

## 7. Reproducibilidad

- [ ] Exportación según la skill `contrato-evidencias` (árbol limpio, commit, id, versiones, SHA-256 de entradas).
- [ ] El código de cada número de la memoria está en el repositorio y se ejecuta con un solo comando.

## Limitaciones conocidas que se declaran (no se "arreglan" en silencio)

- Optuna selecciona con los mismos pliegues con los que se informan las métricas *out-of-fold*: ligero optimismo de las
  métricas de validación (sin búsqueda anidada, por coste).
- Las variantes (D8, ablación, D20) reutilizan los hiperparámetros de la configuración principal (D38): la ventaja de
  "con sensibles" es una cota inferior (D38); la inflación de D20, una estimación previsiblemente sesgada a la baja
  (D38-concreción-D20), y la pérdida de la ablación, una estimación sesgada al alza (D46-rev), no cotas garantizadas.
- Los IC *bootstrap* y DeLong se calculan sobre predicciones ya ajustadas y no recogen la variabilidad del
  reentrenamiento (≈ 0,0045 en el control de la semana 0; D46-rev).
- Umbral sin margen (D45): la sensibilidad en prueba puede quedar por debajo de 0,70.
- CCC solo tiene una presentación de entrenamiento (2014B): en el pliegue que la contiene, CCC no se ve al entrenar.
- Withdrawn como aproximación a la deserción (D2).
