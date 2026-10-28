# Auditoría de fugas del experimento exp-2026-10-27-01

**Fecha:** 2026-10-27
**Auditor:** agente `revisor-fuga` (solo lectura; no escribió el código y no modificó ningún archivo del repositorio)
**Commits auditados:** `e49f339` (código registrado en el JSON) y `f9861f4` (evidencias confirmadas)
**Veredicto:** **apto con observaciones.** No hay hallazgos críticos ni mayores.

## Alcance

- Experimento: `evidencias/experimentos/exp-2026-10-27-01.json`, sus 3 figuras en `evidencias/figuras/` y `evidencias/manifest.json`.
- Código: `ml/experimento.py`, `ml/automl/*.py`, `ml/cortes_oulad.py`, `ml/evidencias.py`, `ml/configs/principal.json` y `ml/tests/`.
- Datos no versionados, solo lectura: `data/procesado/cortes/semana_{0,4,8,12}.parquet`, `data/procesado/oof/exp-2026-10-27-01_semana_*.parquet` y `data/raw/oulad/*.csv`.
- Referencias normativas: `evidencias/CONTRATO.md` y `.claude/skills/rigor-ml/SKILL.md` en `f9861f4`.

**Cómo se trabajó.** Para auditar `f9861f4` sin tocar ningún repositorio, se extrajo ese commit con `git archive` a una carpeta temporal; las pruebas y la reproducción se ejecutaron sobre esa extracción (con copia de los CSV para la única prueba que los necesita). Los cambios sin confirmar del repositorio original se ignoraron.

## Comprobaciones realizadas y resultado

| # | Comprobación | Resultado |
|---|---|---|
| 1 | Trazabilidad: commit, fecha y diferencias entre commits | Correcta. `commit` = `e49f339` (confirmado a las 10:45:53). El experimento empezó a las 10:47:53 (`fecha`), duró 24 389,6 s y terminó hacia las 17:34, en coherencia con las fechas de los OOF. `f9861f4` (18:12) solo añade el JSON, las 3 figuras y `manifest.json` (`git diff --stat e49f339 f9861f4`), y el manifiesto registra `commit: e49f339`. `ml/configs/principal.json` no cambia desde `d36dec0`; `ml/cortes_oulad.py` y `ml/evidencias.py`, desde `a496076` (evidencias de exp-2026-10-23-02). |
| 2 | SHA-256 | Correctos. Los 7 CSV coinciden con `dataset.sha256`, igual al de exp-2026-10-23-02. Los 4 parquet de cortes coinciden con `dataset.cortes_sha256` y con `salidas_sha256` de exp-2026-10-23-02. Los 4 parquet OOF coinciden con `predicciones_oof_sha256`. |
| 3 | 2014J fuera de toda decisión | Se cumple. `ml/experimento.py:88` filtra `particion == "entrenamiento"` al leer, así que las filas de 2014J no se cargan. `ml/automl/particion.py:14` falla si algún pliegue es NA. Los OOF no tienen filas de 2014J ni pliegues NA. De 2014J solo se usa `retiros_prueba` (`ml/experimento.py:91-97`), recuento descriptivo del JSON de cortes. `evaluado_en_prueba: false` y `metricas_test: null`, con su motivo en `motivos_null`. |
| 4 | Fuga entre pliegues: Pipeline, búsqueda y pliegues | Sin fugas. Imputación, escalado y one-hot van dentro del `Pipeline` (`ml/automl/preprocesado.py`, `ml/automl/busqueda.py:175-180`) y se ajustan por pliegue. Optuna usa las 5 divisiones de D29-rev (`busqueda.py:207-213`). Cada una de las 15 presentaciones cae en un solo pliegue en los 4 momentos. |
| 5 | Calibración anidada D37/D54 | Se cumple. En `ml/automl/calibracion.py:29-37`, por pliegue externo, `CalibratedClassifierCV(cv=divisiones(pliegue.iloc[ajuste]), ensemble=False)` se ajusta solo con `Xa` (los otros 4 pliegues) y predice el pliegue externo. Pasan `test_calibrador_de_cada_pliegue_externo_no_usa_filas_de_ese_pliegue` (estimador espía), `test_calibracion_anidada_no_ve_las_etiquetas_del_pliegue_evaluado` y `test_calibracion_anidada_usa_divisiones_internas_agrupadas`. |
| 6 | Apilamiento D48/D52 | Se cumple. `ml/automl/apilamiento.py:38-40`: para cada pliegue externo, `StackingClassifier` recibe como `cv` las divisiones precalculadas de los 4 pliegues de ajuste; el metamodelo nunca ve el pliegue evaluado. La salida es la del metamodelo, sin calibrar, y así lo declara el JSON. Pasa `test_apilamiento_no_ve_las_etiquetas_del_pliegue_evaluado`. |
| 7 | Umbral D45 | Se cumple. Se fija sobre las probabilidades OOF calibradas del modelo desplegado (`calibracion.py:49-55`), con sensibilidad ≥ 0,70 exacta y sin margen. No usa 2014J. |
| 8 | Fuga temporal en las variables (`ml/cortes_oulad.py`) | No se encontró ninguna. Clics con `date ≤ 7k` (l. 171). Entregas con `date ≤ 7k` y `date_submitted ≤ 7k` (l. 220). Notas solo de CMA con `date_submitted ≤ 7k` (l. 225), ninguna de TMA. Exámenes filtrados por tipo (l. 157, 215). `is_banked` en variables propias, conocidas desde el día 0 (l. 212-234). Percentiles de cohorte por presentación sobre la población elegible del corte, con datos ≤ 7k (l. 205-207). Tipos de actividad solo del entrenamiento (l. 144). Población filtrada con `date_unregistration ≤ 7k` y por matrícula tardía (l. 128-136). `date_unregistration` y `final_result` están en `EXCLUIDAS`. Las 47 numéricas y las 4 categóricas del JSON no incluyen nada de `NO_VARIABLES` ni variables sensibles: 47 + 4 + 4 sensibles = 55 = `n_variables` de los cortes. |
| 9 | Población | Correcta. `n` y `retiros` por momento (19 023/4 111, 18 304/3 320, 17 629/2 641, 17 146/2 154) coinciden con `cortes[].por_particion.entrenamiento` de exp-2026-10-23-02. D26/D27 eliminan 93 y 9 matrículas, como en `calidad_datos`, y `comprobar_calidad` lo verifica. |
| 10 | Reproducción desde los parquet OOF | **0 discrepancias.** Se recalcularon métricas por pliegue, media, desviación, ROC-AUC y PR-AUC OOF y Brier de las 7 familias, el apilamiento y las 3 referencias; ROC-AUC y Brier sin calibrar; `mejor_automl` (D44); DeLong, IC *bootstrap*, Holm y `lectura` (D49 con signo); toda la parsimonia (D49-rev); `punto_operacion_oof`; el desglose CCC/resto y todo `equidad_oof` (D50, uniendo los atributos sensibles del parquet de cortes, alineados fila a fila). |
| 11 | Figuras | Las 3 PNG regeneradas desde los OOF con el código de `f9861f4` son **idénticas byte a byte** a las confirmadas. |
| 12 | Contrato y skill | Se cumplen. Campos comunes completos (`id`, `tipo`, `fecha`, `commit`, `dataset` con `tablas_usadas` y `sha256`, `entorno`, `tiempo_ejecucion_s`, `figuras`, `motivos_null` para `metricas_test` y `momentos.shap`). Esquema de `modelado` completo: semillas 42/42/42, Optuna/TPE/MedianPruner, espacios, predeterminados D53, `rl_optimizada` con `igual_que`, `retiros_prueba` y `solo_descriptiva` (< 30), `sin_solo_descriptiva` y `metodo_ic_diferencia`. D53: `roc_auc_media_busqueda ≥ roc_auc_media_predeterminado` en todas las familias y momentos. |
| 13 | Coherencia con exp-2026-10-26-01 | Coherente. Configuración, entorno, variables y población iguales. En los 4 momentos coinciden hiperparámetros, `roc_auc_media_busqueda`, ROC-AUC sin calibrar y apilamiento; solo cambian las predicciones calibradas, como se espera de D54. En `dataset` solo se añade `tablas_usadas`. El modelo desplegado (RL) y las lecturas no cambian. En la semana 4, `mejor_automl` pasa de apilamiento a catboost porque la ROC-AUC calibrada de catboost sube de 0,6720 a 0,6802. |
| 14 | `pytest ml/tests` en `f9861f4` | **102 superadas, 0 fallidas, 0 omitidas** (121 s; 5 avisos de scikit-learn en datos sintéticos). |
| 15 | Datos personales | Se cumple. El JSON y el manifiesto no contienen rutas absolutas, nombres de usuario ni de equipo, ni correos. |

## Hallazgos

### Críticos
Ninguno.

### Mayores
Ninguno.

### Menores

**M1. Figura de familias: la mayoritaria aparece en el eje junto a los modelos** (`ml/experimento.py:318`, `evidencias/figuras/exp-2026-10-27-01_familias_roc_auc.png`).
- Evidencia: la referencia mayoritaria se dibuja con su ROC-AUC OOF agrupada (0,4402 / 0,4301 / 0,4328 / 0,4283), artefacto de juntar constantes que cambian entre pliegues; en cada pliegue vale 0,5. El JSON lo explica en `momentos[].referencias[0].nota`, pero la figura no. El título dice "barra: ± desviación entre pliegues" sobre un punto que es la ROC-AUC agrupada, no la media de los pliegues.
- Riesgo: leerse en la memoria como "la mayoritaria es peor que el azar". No es una fuga.
- Corrección propuesta: declararlo en el pie de figura; si se regenera, mostrar su media por pliegue (0,5) o quitarla.

**M2. Algunos valores del JSON no se pueden reproducir desde los OOF** (`ml/experimento.py:136-143`, `ml/experimento.py:233-236`).
- Evidencia: el parquet no guarda `p_ref_rl_defecto_sin_calibrar` ni la probabilidad del método de calibración no elegido, así que `referencias[rl_defecto].roc_auc_oof_sin_calibrar` y el Brier del método descartado (`calibracion.brier_por_metodo`) no se pueden recalcular. Sí se comprobó que el método elegido es el de menor Brier.
- Corrección propuesta: en experimentos futuros, guardar en el parquet OOF las predicciones sin calibrar de `rl_defecto` y las de ambos métodos.

### Informativos (para declarar en la memoria; no bloquean)

**I1. El contraste central y la parsimonia usan predicciones calibradas** (`ml/experimento.py:168`, `196-207`). La isotónica crea empates y baja la ROC-AUC OOF (semana 0: RL optimizada 0,6513 sin calibrar, 0,6456 calibrada). `rl_defecto` y `rl_optimizada` pueden acabar con métodos distintos (semana 0: Platt e isotónica). Es coherente con `calibracion_definicion` y con la elección por Brier; conviene declarar que *Δ*ₖ y D49-rev se calculan sobre probabilidades calibradas.

**I2. La calibración nunca puede quedarse "sin calibrar"** (`ml/automl/calibracion.py:43`). La elección por Brier es solo entre Platt e isotónica; en la semana 0 la RL tiene mejor Brier sin calibrar (0,1617) que con isotónica (0,1620). Conforme con `rigor-ml` §4.

**I3. Los recuentos de 2014J deciden qué subgrupos de equidad se excluyen** (`ml/automl/equidad.py:62-72`). Deciden `solo_descriptiva` y, con ello, qué subgrupo se excluye de `sin_solo_descriptiva` (`age_band = 55<=` en los 4 momentos). Es un uso de recuentos previsto en D50 y en el CONTRATO, que no afecta al modelo, al umbral ni a la selección; conviene nombrarlo en la memoria.

**I4. D54 se adoptó después de ver los resultados de validación de exp-2026-10-26-01** (la MLP perdía 0,025 en la semana 0). Está justificado metodológicamente (el modelo base de cada pliegue se ajusta como el final), solo usa validación cruzada y no cambió la búsqueda. Se declara junto a la limitación de seleccionar y evaluar con los mismos pliegues.

**I5. La sensibilidad en la semana 12 queda por encima de 0,70** (0,7117), por el salto escalonado de la isotónica. El umbral es correcto según D45 y se reprodujo exactamente.

**I6. Semana 0: el IC excluye el 0, pero la lectura es equivalencia práctica.** IC [0,0010; 0,0094] y *p* de Holm = 0,0575: al no ser significativo y quedar el IC dentro de ±0,02, corresponde `equivalencia_practica` (D49). Conviene explicarlo para que no parezca una contradicción.

**I7. D26 actúa casi solo sobre 2014J** (exp-2026-10-23-02, `eliminaciones`): elimina 87 de sus 93 matrículas en 2014J y depende de `final_result`. Regla de población ya decidida y declarada; no afecta a este experimento, pero será relevante en la evaluación de la Entrega 3.

**I8. No se exportó un informe de pruebas de este experimento.** El CONTRATO no lo exige para `modelado`. Si se quiere evidencia de las 102 pruebas en `e49f339`/`f9861f4`, puede añadirse un JUnit XML en `evidencias/pruebas/` en una exportación posterior.

## Veredicto

**Apto con observaciones.** No hay información posterior al corte en las variables, ni fugas entre pliegues en la búsqueda, la calibración anidada (D54, `ensemble=False`), el apilamiento o el umbral, ni ningún uso de 2014J que no sea un recuento descriptivo. El JSON confirmado en `f9861f4` se generó con `e49f339`, tiene trazabilidad completa (semillas, versiones y SHA-256 de entradas, cortes y OOF), cumple el CONTRATO y `rigor-ml`, y todos sus resultados y figuras se reproducen exactamente desde los parquet OOF. M1 y M2 son de presentación y de completitud de los artefactos no versionados; I1-I8 se declaran en la memoria.
