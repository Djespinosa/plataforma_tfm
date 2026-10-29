# Auditoría de fugas del experimento exp-2026-10-28-03

**Fecha:** 2026-10-29
**Auditor:** agente `revisor-fuga` (solo lectura; no escribió el código y no modificó ningún archivo del repositorio)
**Commit auditado:** `5828399` (código registrado en el JSON), con las salidas de la exportación todavía sin confirmar
**Veredicto:** **apto con observaciones.** No hay hallazgos críticos. Hay un hallazgo mayor de interpretación (M1), que se
declara en la memoria sin relanzar la ablación.

## Alcance

- Experimento: ablación D46 por grupos de variables, sin nueva búsqueda (D38), sobre el mejor AutoML y la RL desplegada:
  `evidencias/experimentos/exp-2026-10-28-03.json`, `evidencias/figuras/exp-2026-10-28-03_ablacion.png`,
  `evidencias/pruebas/exp-2026-10-28-03_pruebas.xml` y `evidencias/manifest.json`.
- Código: `ml/ablacion.py`, `ml/configs/ablacion.json`, `ml/tests/test_ablacion.py`, `ml/variante.py`
  (`predicciones_principal`, `reentrenar`), `ml/experimento.py` (`cargar_entrenamiento`, `columnas_modelo`),
  `ml/cortes_oulad.py` (variables y catálogo), `ml/automl/preprocesado.py` y `ml/automl/busqueda.py`.
- Datos no versionados, solo lectura: los 4 parquet OOF de exp-2026-10-27-01 («completo») y los 4 de exp-2026-10-28-03
  («sin el grupo») en `data/procesado/oof/`, y los cortes en `data/procesado/cortes/`.
- Referencias normativas: `decisiones.md` de la memoria (D38, D44, D46, D48, D49-rev, D51-rev, D54),
  `.claude/skills/rigor-ml/SKILL.md` y `evidencias/CONTRATO.md`.

**Cómo se trabajó.** Con scripts temporales fuera del repositorio se hicieron: el análisis por variable del grupo
«evaluaciones» en la semana 0, la comprobación de las filas `is_banked` en los datos crudos, el recálculo de las 40
pérdidas desde los parquet, una descomposición por filas y una ablación de control que quita solo columnas constantes.

## Hallazgos

### Mayor

**M1. En la semana 0, la pérdida de «evaluaciones» del apilamiento (+0,0044, IC [0,0023; 0,0065]) refleja la
variabilidad del reentrenamiento, no información del grupo; el IC bootstrap no la recoge.**

- En la semana 0 (19 023 filas), 5 de las 9 variables del grupo son constantes (`n_evaluaciones_vencidas`,
  `n_entregadas` y `n_entregas_tardias` valen 0; `proporcion_entregadas` y `antelacion_media` están vacías), porque
  ninguna evaluación vence en el día 0 o antes. Solo varían `n_cma_calificadas`/`nota_media_cma` (47 filas, de
  FFF_2013B/2013J, con 2 positivos) y `n_convalidadas`/`nota_media_convalidada` (272 filas).
- Descomposición por filas: si en esas 319 filas se restituye la predicción «completo», el apilamiento pasa de 0,6463 a
  0,6469 (explican unas 0,0006 de las 0,0044) y la RL pasa de 0,6448 a 0,6457 (recupera toda su pérdida de 0,0008). En
  filas donde el grupo no aporta nada, las predicciones del apilamiento cambian hasta 0,31.
- Ablación de control con el mismo código (`predecir_sin_grupo`) y la misma configuración (hiperparámetros del principal,
  semilla 42, `n_jobs` 8, mismos pliegues), quitando solo las 7 columnas constantes en la semana 0 (las 5 de
  evaluaciones más `clics_folder` y `clics_repeatactivity`), que no tienen información:

  | Modelo | Completo | Sin columnas constantes | Diferencia |
  |---|---|---|---|
  | Apilamiento | 0,6507 | 0,6462 | +0,0045 |
  | RL | 0,6456 | 0,6480 | −0,0023 |

- Mecanismo probable: con semilla fija, cambiar el número de columnas cambia el submuestreo de columnas
  (`colsample_bytree` en XGB y LGBM, `max_features` en RF), la inicialización del MLP y el orden de coordenadas de
  liblinear; la calibración isotónica amplifica esos cambios.
- Consecuencia: el IC bootstrap pareado (`ml/ablacion.py:86-93`) condiciona a las predicciones ya ajustadas y no incluye
  la variabilidad de reajustar el modelo. Las pérdidas de orden ≤ 0,005 no se leen como contribución aunque su IC excluya
  el 0: evaluaciones en la semana 0, las pérdidas negativas de clics en la RL en las semanas 0 y 12 (−0,0033 y −0,0065),
  y derivadas y contexto del módulo en la semana 12. Las pérdidas grandes no se ven afectadas: evaluaciones 0,048-0,062
  en las semanas 4-12; demográficas y contexto del módulo 0,024-0,035 en la semana 0.
- **Resolución (decisión del estudiante, 2026-10-29):** no se relanza la ablación; M1 se declara en la memoria (el IC no
  recoge la variabilidad del reentrenamiento; suelo de ruido de ±0,002-0,005 según el control; las pérdidas por debajo de
  ese orden no se leen como contribución).

### Menores

- **m1. Alcance respecto a D46.** D46 define la ablación solo sobre el mejor AutoML. Aplicarla también a la RL desplegada
  es una ampliación razonable, declarada en la configuración confirmada antes de ejecutar, pero D46 no la recoge.
  Conviene registrarla en `decisiones.md`.
- **m2. «Cota superior» es una expectativa, no una garantía** (`ml/ablacion.py:251-252` y el título de la figura). Las
  pérdidas negativas y M1 muestran que la pérdida medida puede quedar por debajo de 0 o por encima de la contribución
  real por efecto del ruido. **Resolución (decisión del estudiante, 2026-10-29):** se declara en la memoria; si en un
  experimento futuro se reexporta el JSON, se usa «estimación sesgada al alza» en lugar de «cota superior».

## Comprobaciones realizadas y resultado

| # | Comprobación | Resultado |
|---|---|---|
| 1 | Fuga temporal por grupo | No hay. Clics con `date ≤ 7k` (`ml/cortes_oulad.py:171`); entregas con `date ≤ 7k` y `date_submitted ≤ 7k` (`:220`); notas solo de CMA con `date_submitted ≤ 7k` (`:225`), ninguna de TMA; exámenes fuera (`:157`); percentiles de cohorte con datos ≤ 7k (`:204-207`). `final_result` y `date_unregistration` solo se usan para la etiqueta y las exclusiones. |
| 2 | «Evaluaciones» en la semana 0 | Solo información anterior al corte. `n_evaluaciones_vencidas` usa el calendario (`assessments.date ≤ 0`) y vale 0. Las 47 notas de CMA son de entregas con `date_submitted ≤ 0`; su disponibilidad depende del supuesto declarado de que la nota de la CMA está disponible al entregarla. Las 1909 filas convalidadas tienen `date_submitted = −1`; 136 son de evaluaciones con fecha posterior a la baja del estudiante, así que las filas `is_banked` no dependen de que siga matriculado. Entre los repetidores, `n_convalidadas` no discrimina (AUC 0,496). |
| 3 | 2014J fuera de toda decisión | Se cumple. `cargar_entrenamiento` filtra `particion == "entrenamiento"` al leer (`ml/experimento.py:101`). Los OOF solo contienen 2013B, 2013J y 2014B, sin `pliegue` vacío. `evaluado_en_prueba: false` y `metricas_test: null`, con su motivo. Del experimento de cortes solo se leen SHA-256. |
| 4 | Sin nueva búsqueda (D38) | Se cumple. `predecir_sin_grupo` construye los modelos con los hiperparámetros del principal y `test_sin_busqueda_y_con_el_metodo_de_calibracion_del_principal` prohíbe `buscar`. Métodos de calibración del principal (RL isotónica en 0 y 12, Platt en 4 y 8; CatBoost isotónica en 4), semillas 42/42/42, `n_jobs` 8, pliegues del corte y `sin_sensibles`. Grupos según D51-rev: 6 demográficas sin sensibles, 25 de clics, 8 derivadas, 9 de evaluaciones y 3 de contexto. |
| 5 | Ruta abreviada del apilamiento | Validada por `test_oulad_ruta_abreviada_reproduce_el_principal_en_la_semana_8`, que pasa en el JUnit (375 s): ROC-AUC idéntica, mismos rangos y diferencias ≤ 1e-9. |
| 6 | Pérdida: filas y sentido | Correctos. `predicciones_principal` exige las mismas claves y el mismo orden (verificado en las 4 semanas). El SHA-256 de los OOF del principal se comprueba antes de ejecutar (`ml/ablacion.py:189-194`). Las 40 pérdidas recalculadas desde los parquet (completo − sin el grupo) coinciden con el JSON (diferencias < 1e-4). Los SHA-256 de los 4 parquet de 28-03 coinciden con el JSON. |
| 7 | Contrato y manifiesto | Se cumplen. Esquema `ablacion`: variante única «ablacion», `hiperparametros_de`, `grupos` con nombre y variables, y por momento `{semana, n, retiros, modelos, tiempo_s}` con `{papel, modelo, calibracion, grupos}`; `n` y `retiros` iguales a los del principal. `commit` 5828399, SHA-256 de las 7 tablas y los 4 cortes, entorno y hardware sin nombre del equipo. Figura a 300 ppp (4800×1380), eje x común y coma decimal. El manifiesto solo añade el experimento, la figura y el JUnit. |
| 8 | `pytest ml/tests` en `5828399` | **122 superadas, 0 fallidas, 0 omitidas** (JUnit `pruebas/exp-2026-10-28-03_pruebas.xml`), sin `hostname` ni nombre de usuario. |
| 9 | Redacción del JSON | `descripcion`, `reentrenamiento` y `comparacion` hablan de «pérdida», «cota superior» y «contribución» sin lecturas causales; DeLong figura solo como informativo. Falta la salvedad de M1, que se declara en la memoria. |

## Pedido P-3: hardware de exp-2026-10-27-01

El JSON de exp-2026-10-27-01 no tiene campo `hardware`: el registro se añadió en `193340c`, después de ese experimento
(commit `e49f339`). Pistas a favor del mismo equipo: Python 3.13.3 y las bibliotecas comunes con versiones idénticas,
`n_jobs` 8 en ambos, y la reproducción de sus predicciones en el equipo de exp-2026-10-28-03 (ROC-AUC idéntica y
diferencias ≤ 1e-9 en la semana 8). **El estudiante confirma (2026-10-29) que exp-2026-10-27-01 corrió en el mismo
equipo** (AMD Ryzen 7 4800H, 8/16 núcleos, 15,4 GB, Windows 11).

## Veredicto

**Apto con observaciones.** No hay fuga ni uso de 2014J, se cumplen D38 y el contrato, y las cifras se reproducen. M1 y
m2 se declaran en la memoria sin relanzar la ablación; m1 se registra en `decisiones.md`.
