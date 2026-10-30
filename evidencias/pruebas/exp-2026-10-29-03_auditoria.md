# Auditoría de fugas del experimento exp-2026-10-29-03

**Fecha:** 2026-10-29
**Auditor:** agente `revisor-fuga` (solo lectura; no escribió el código y no modificó ningún archivo del repositorio)
**Commit auditado:** `4e1511e` (código registrado en el JSON), con las salidas de la exportación todavía sin confirmar
**Veredicto:** **apto con observaciones.** No hay hallazgos críticos, mayores ni menores. Las observaciones son para la
memoria y para la API.

## Alcance

- Experimento: modelo final D41 preparado sin evaluar en 2014J, con la variante con sensibles sin desplegar (P-13) y los
  parámetros efectivos de Optuna (P-4): `evidencias/experimentos/exp-2026-10-29-03.json`,
  `evidencias/pruebas/exp-2026-10-29-03_pruebas.xml` y `evidencias/manifest.json`.
- Código en `4e1511e`: `ml/modelo_final.py`, `ml/configs/modelo_final.json`, `ml/tests/test_modelo_final.py` y sus
  dependencias (`cargar_entrenamiento`, `divisiones`, `umbral`, `construir`, `predicciones_principal`,
  `explicar`/`agregar`, `codificador`). También los cambios ajenos al experimento: `ml/evidencias.py`
  (`ruta_registrada`), `ml/experimento.py`, `ml/tests/test_experimento.py`, `ml/sensibilidad_fuga.py`,
  `ml/shap_analisis.py`, `LICENSE` y `README.md`.
- Datos no versionados, solo lectura: los 8 paquetes `.joblib` de `data/procesado/modelos/`, los OOF de
  exp-2026-10-27-01 y exp-2026-10-28-01 y los cortes.
- Referencias normativas: `decisiones.md` de la memoria (D31-rev, D8-concreción-rev, D41, D41-concreción, D45, D54,
  D33-concreción, P-4, P-13), `.claude/skills/rigor-ml/SKILL.md` y `evidencias/CONTRATO.md`.

**Cómo se trabajó.** Con un script temporal fuera del repositorio se cargaron los 8 paquetes, se recalcularon los
umbrales con una implementación propia y se compararon el modelo, el calibrador y el explicador con un reajuste
independiente. No se confió en el JSON.

## Comprobaciones realizadas y resultado

| # | Comprobación | Resultado |
|---|---|---|
| 1 | 2014J no se lee | Correcto. `ml/experimento.py:103` carga solo entrenamiento: n = 19023 / 18304 / 17629 / 17146, 0 filas de 2014J, pliegues 1-5. `ml/automl/particion.py:14` rechaza filas sin pliegue (`test_rechaza_filas_sin_pliegue`, por el camino de `entrenar_final`). Entrenamiento, calibración (`cv=divisiones(pliegue)`), umbral (OOF alineadas con SHA-256 comprobado) y fondo del explicador (`modelo_final.py:73`) salen solo de esas filas. `metricas_test` es null. Configuración confirmada en dd6d58f y 4e1511e (16:40:19); ejecución a las 16:40:42 con el árbol limpio |
| 2 | El modelo es el especificado | Correcto. Los 8 SHA-256 coinciden. Hiperparámetros iguales a la RL de 27-01 (y a 28-01 en la variante); `liblinear`, `random_state=42`. `cv` = las 5 divisiones agrupadas, `ensemble=False`, un calibrador. Métodos: isotónica, Platt, Platt, isotónica (desplegado, = 27-01); isotónica, Platt, isotónica, Platt (con sensibles, = 28-01). `coef_` e `intercept_` idénticos a `construir(...).fit(X, y)` con todo el entrenamiento; el `CalibratedClassifierCV` reajustado reproduce las probabilidades. Columnas: desplegado sin sensibles (= 27-01); variante = 28-01 (añade `gender`, `imd_band`, `age_band`, `disability`). `n_jobs=8` no afecta a la RL |
| 3 | Umbral (D41, D45) | Correcto. Recalculado con implementación propia (máxima precisión con sensibilidad ≥ 0,70; a igual precisión, el umbral más alto). Desde 27-01: 0,213612 / 0,150952 / 0,132519 / 0,117117 (= JSON, paquete y D41-concreción). Desde 28-01: 0,206093 / 0,150952 / 0,142088 / 0,118287 (= 28-02). La redacción como «aproximación» es fiel a D41 |
| 4 | Explicador del paquete | Correcto. Aditividad ≤ 3,6e-15. Frente a `shap_estabilidad.explicar(base, X, X)`, diferencia máxima 0,0 en los 8 paquetes (mismo estimador que 29-02, D33-concreción). Fondo = media de las filas transformadas. `OneHotEncoder(handle_unknown="ignore")` mantiene la aditividad con categorías nuevas |
| 5 | La variante no se confunde con el desplegado | Correcto. Nombre `<id>_con_sensibles_semana_<k>.joblib`; `origen` con `variante: "con_sensibles"`, `desplegado: False`, experimento 28-01, id y commit; en el JSON, `con_sensibles.desplegado: false` en cada momento |
| 6 | Contrato y JUnit | Correcto. Están todos los campos del esquema `modelo_final` (`con_sensibles`, `optuna`, `variables_con_sensibles`, `modelos_sha256` con `carpeta`). Commit 4e1511e; el manifiesto añade el JSON y el XML; JUnit 146/0/0 sin omitidas. Sin nombre del equipo ni del usuario. `test_modelo_final` (9/9), la prueba de la carpeta y `test_parametros_efectivos_de_optuna` pasan al repetirlas |
| 7 | P-4 | Correcto. `git diff e49f339 HEAD -- ml/automl/busqueda.py` solo añade `DESCRIPCION_OPTUNA` y `NIVEL_N_JOBS`; `create_study`, `TPESampler(seed=semilla)`, `MedianPruner(5, 1)`, `enqueue_trial` y `optimize` son idénticos; Optuna 5.0.0 en ambos. En los objetos: `n_startup_trials=10`, `n_ei_candidates=24`, `group=False`, `constant_liar=True`, `multivariate` resuelto a True; podador 50 / 5 / 1 / 1 / 1. `vale_para` es cierto |
| 8 | Decisiones | Sin desviaciones respecto de D31-rev, D41, D41-concreción, D54, D45, D8-concreción-rev, P-13 ni D33-concreción |
| 9 | Cambios ajenos al experimento | Correctos. `ruta_registrada` y su uso en `experimento.py`, probados; el texto del ruido en `sensibilidad_fuga.py` es solo redacción; `shap_analisis.py` (sin ejecutar) solo lee entrenamiento y OOF; `LICENSE` MIT y README con CC BY 4.0 (el README conserva el marcador «[Completar: …]», ajeno a la auditoría) |

## Hallazgos

Ninguno crítico, mayor ni menor.

## Observaciones

- **O1. Desplazamiento del punto de operación (para 5.4.3).** Con el umbral transferido, la sensibilidad del modelo
  final sobre sus propias filas de entrenamiento es:

  | Semana | Desplegado | Con sensibles |
  |---|---|---|
  | 0 | 0,715 | 0,801 |
  | 4 | 0,769 | 0,774 |
  | 8 | 0,762 | 0,765 |
  | 12 | **0,679** | 0,713 |

  En la semana 0 con sensibles, la tasa de alerta es 0,60 frente a 0,54 OOF. Es una medida dentro de la muestra y
  sesgada, que no debe informarse como estimación, pero indica que la diferencia de la aproximación D41 puede ser de
  varias centésimas en los dos sentidos. Refuerza el riesgo de D45, pendiente de confirmar antes de evaluar en prueba:
  conviene confirmarla antes de la Entrega 3. El JSON no lo recoge.
- **O2. Paquetes con sensibles en la API.** Los paquetes con sensibles contienen y explican `gender`, `imd_band`,
  `age_band` y `disability`. La API debe cargar solo los paquetes con `origen["desplegado"] is True` o el nombre sin
  sufijo, nunca por el patrón `*_semana_<k>.joblib`, y conviene una prueba que lo garantice.
- **O3. SHAP extremos.** Sigue vigente la O1 de exp-2026-10-29-02. Dentro de la muestra, el máximo |SHAP| del desplegado
  es 9,4 / 2,5 / 4,8 / 7,6, pero en filas nuevas (2014J o la plataforma) pueden aparecer valores como los OOF (−40,6).
  Se atiende en la interfaz (D33-concreción).
- **O4. Variables vacías en la semana 0.** `proporcion_entregadas` y `antelacion_media` no tienen ningún valor; el
  imputador las descarta y `agregar` les asigna SHAP 0. Ya ocurría en 27-01. En la interfaz deben aparecer como «sin
  contribución», no como variables evaluadas.
- **O5. Barrera de 2014J.** `divisiones` solo rechaza los pliegues vacíos (NA); una marca 0 o −1 no se rechazaría. La
  barrera principal es el filtro de lectura (`experimento.py:103`), así que solo afecta a la robustez.
- **O6. Redacción.**
  - `umbral_transferido` escribe «0.7» con punto decimal (`modelo_final.py:255`).
  - `con_sensibles` es un texto en la raíz y un objeto en cada momento; el CONTRATO lo documenta, pero conviene tenerlo
    en cuenta al citarlo.
  - Para la memoria (P-4): `constant_liar=True` no tiene efecto, porque los ensayos son en serie.
