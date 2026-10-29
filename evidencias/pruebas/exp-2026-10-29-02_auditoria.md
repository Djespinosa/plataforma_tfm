# Auditoría de fugas del experimento exp-2026-10-29-02

**Fecha:** 2026-10-29
**Auditor:** agente `revisor-fuga` (solo lectura; no escribió el código y no modificó ningún archivo del repositorio)
**Commit auditado:** `870b8d8` (código registrado en el JSON; el anterior, `15a5f46`, solo difiere en la maquetación de la
figura), con las salidas de la exportación todavía sin confirmar
**Veredicto:** **apto con observaciones.** No hay hallazgos críticos. Hay un hallazgo mayor de interpretación (M1) y
cuatro menores, que se declaran en la memoria sin relanzar el experimento.

## Alcance

- Experimento: SHAP *out-of-fold* y su estabilidad entre pliegues (D9, D32, D33), sin nueva búsqueda (D38):
  `evidencias/experimentos/exp-2026-10-29-02.json`, `evidencias/figuras/exp-2026-10-29-02_shap_rl_desplegada.png`,
  `evidencias/figuras/exp-2026-10-29-02_shap_mejor_automl.png`, `evidencias/pruebas/exp-2026-10-29-02_pruebas.xml` y
  `evidencias/manifest.json`.
- Código: `ml/shap_estabilidad.py`, `ml/configs/shap.json`, `ml/tests/test_shap_estabilidad.py` y sus dependencias
  (`ml/automl/{busqueda,preprocesado,calibracion,particion}.py`, `ml/experimento.py`, `variante.predicciones_principal`).
- Datos no versionados, solo lectura: los 4 parquet SHAP (`data/procesado/oof/exp-2026-10-29-02_shap_semana_<k>.parquet`),
  los OOF de exp-2026-10-27-01 y los cortes.
- Referencias normativas: `decisiones.md` de la memoria (D9, D9-concreción, D32, D33, planificación de evidencias de
  2026-10-23), `.claude/skills/rigor-ml/SKILL.md` y `evidencias/CONTRATO.md`.

**Cómo se trabajó.** Con scripts temporales fuera del repositorio se reentrenó la semana 4, se recalcularon las
importancias y la estabilidad desde los parquet, se comprobó la identidad del modelo explicado con el del principal y se
analizaron la colinealidad y los valores extremos.

## Comprobaciones realizadas y resultado

| # | Comprobación | Resultado |
|---|---|---|
| 1 | Fuga entre pliegues | No hay. En `shap_oof` (`ml/shap_estabilidad.py:128-132`) cada pliegue construye un `Pipeline` nuevo, con todo el preprocesado dentro, y lo ajusta solo con `pliegue != f`. En la RL, el fondo y el valor base salen de las filas de ajuste transformadas (`:94-97`). En catboost, `shap.TreeExplainer` trabaja en modo `tree_path_dependent` y salida bruta, con la cobertura de hojas de un modelo que solo vio las filas de ajuste. Las OOF del principal solo se usan para el diagnóstico de concordancia (`:135`). |
| 2 | 2014J fuera de toda decisión | Se cumple. `cargar_entrenamiento` filtra `particion == "entrenamiento"` al leer; las filas leídas son de 2013B, 2013J y 2014B. `evaluado_en_prueba: false` y `metricas_test: null`, con su motivo. |
| 3 | Mismo modelo base que el principal (D38, D54) | Se cumple. Hiperparámetros del principal, semilla 42, `n_jobs` 8 y columnas sin `SENSIBLES`. Con `ensemble=False`, el estimador final de `CalibratedClassifierCV` es el mismo ajuste que se explica. Comprobación exacta: en cada pliegue, `logit(p_<modelo>_sin_calibrar)` del principal menos la suma de los SHAP de la fila es constante (desviación típica ≤ 1,6·10⁻¹⁵) en las 4 semanas para la RL y en la semana 4 para catboost. La concordancia por Spearman es 1,0 con Platt (RL en semanas 4 y 8) y 0,984-0,986 con isotónica (RL en semanas 0 y 12; catboost en la 4), por los empates. |
| 4 | Reproducción | Exacta. Al reentrenar la semana 4, la diferencia máxima con el parquet es 0,0 y el resumen de los dos modelos es idéntico (salvo `coste_s`). Desde los parquet, `media_abs`, `rango_pliegues` y la estabilidad (Spearman y top-10, media y rango) coinciden en todas las semanas; no hay empates en la posición 10. Aditividad ≤ 7·10⁻¹⁵. |
| 5 | `variable_original` y `agregar` | Correctos: numérica exacta, luego `missingindicator_`, luego el prefijo categórico más largo; `nombre_columna` solo sustituye caracteres de la categoría. Las variables descartadas por el pliegue reciben 0. El lineal exacto equivale a `shap.LinearExplainer` con masker independiente = filas de ajuste (prueba con atol 1e-10); la salida bruta de catboost es `RawFormulaVal` y su sigmoide es `predict_proba`. |
| 6 | Contrato y reproducibilidad | Se cumplen. El esquema `shap` del JSON se ajusta a `CONTRATO.md`; SHA-256 de los 4 parquet correctos; configuración y código confirmados antes de ejecutar. Figuras a 300 ppp (4500×1620 y 2250×1620), con coma decimal y el subtítulo «contribución a la predicción del modelo, no causa». El manifiesto solo añade el JSON, las 2 figuras y el JUnit. |
| 7 | `pytest ml/tests` en `870b8d8` | **133 superadas, 0 fallidas, 0 omitidas** (JUnit `pruebas/exp-2026-10-29-02_pruebas.xml`), sin nombre del equipo ni rutas de usuario. |

## Hallazgos

### Mayor

**M1. La «dominancia» de las variables de contexto en la RL de las semanas 0 y 12 es en buena parte un artefacto de
colinealidad** (`ml/shap_estabilidad.py:139-143`).

- `module_presentation_length` está casi determinada por `tipo_presentacion` (B: 234-241 días; J: 261-268). Sus SHAP por
  fila tienen correlación −0,96 (semana 0) y −0,98 (semana 12): se compensan.
- La media de |suma| de los tres SHAP de contexto (`tipo_presentacion` + `module_presentation_length` + `code_module`)
  por pliegue es mucho menor que la suma de sus tres medias de |SHAP|: 0,18-0,63 frente a ≈0,3-2,2 en la semana 0
  (p. ej., 2,16 en el pliegue 1) y 0,07-0,53 frente a ≈1,0-1,3 en la semana 12.
- En la semana 0, la RL está casi sin regularizar (C = 52, L1), lo que agrava el reparto arbitrario y explica los
  rangos amplios entre pliegues (`tipo_presentacion` de 0,15 a 1,05).
- Lo mismo con la actividad: en la semana 0, `dias_activos` y `proporcion_dias_activos_28d` tienen correlación 1,0; en
  la semana 12, 0,90, con SHAP correlacionados −0,875.
- No es una fuga y no cambia las cifras exportadas.
- **Resolución (decisión del estudiante, 2026-10-29):** se declara en la memoria: colinealidad, lectura por bloques
  (contexto de presentación; actividad) y variables de contexto como tasa base de la presentación. La importancia por
  grupo queda como opción para un experimento posterior.

### Menores

- **m1. Spearman sobre las 51 variables, incluidas las nulas en todos los pliegues** (`ml/shap_estabilidad.py:114`). Los
  ceros empatados inflan la concordancia. Sin las variables siempre nulas, la media baja: semana 0 RL 0,854 → 0,798 (44
  de 51 variables); semana 4 RL 0,776 → 0,748; catboost 0,880 → 0,865; semana 8 RL 0,859 → 0,851; semana 12 RL
  0,836 → 0,826.
- **m2. La concordancia por Spearman con la isotónica es un diagnóstico débil** (`:134-135`): 0,984 no distinguiría un
  modelo ligeramente distinto. La comprobación exacta (logit de la predicción sin calibrar del principal menos la suma
  de SHAP, constante por pliegue) confirma la identidad; conviene registrarla en una próxima versión.
- **m3. Descripción de la figura de catboost** (`ml/shap_estabilidad.py:180-183`, propagada al manifiesto): dice «de el»
  en lugar de «del», y la figura solo tiene la semana 4 (en las demás, el mejor AutoML es el apilamiento). El pie de la
  memoria debe indicarlo.
- **m4. Explicador no previsto en D33.** D33 fija TreeSHAP y permutación; el modelo desplegado (RL) se explica con SHAP
  lineal exacto. Es razonable (exacto y más barato), pero es una decisión nueva que debe registrarse en `decisiones.md`.
- **Resolución de m1-m4 (decisión del estudiante, 2026-10-29):** se declaran en la memoria sin relanzar; m4 se registra
  en `decisiones.md`.

### Observaciones

- **O1. Valores SHAP locales extremos en la RL**, por extrapolación lineal de recuentos de clics con colas pesadas
  (estandarizados sin transformar): `clics_glossary` llega a −40,6 log-odds en una fila de DDD 2014B (semana 12); en la
  semana 0, `n_cma_calificadas` llega a 10,8 y `clics_resource` a 10,1. No altera el orden global (top-5 igual con la
  media recortada al p99), pero afecta a las explicaciones individuales de la interfaz y del modelo final D41.
  **Resolución (decisión del estudiante, 2026-10-29):** se atiende en la presentación de la interfaz (bloque E,
  `guardarrailes-interfaz`); el modelo y sus probabilidades no cambian.
- **O2.** La importancia por pliegue mezcla la variación del modelo y la de la población explicada (cada pliegue tiene
  presentaciones distintas). Es la lectura natural de D9 y D9-concreción para OOF, pero la memoria debe decirlo; en las
  variables de contexto, la importancia depende de la proporción B/J del pliegue.
- **O3.** En TreeSHAP, la suma por variable original de los SHAP de columnas one-hot no es un Shapley de grupo exacto en
  modelos no aditivos; es la convención habitual y basta con una frase en el método.
- **O4.** El JSON no registra el SHA-256 de las OOF del principal que consume, aunque lo verifica contra el JSON del
  principal (`:233-238`), lo que basta para la trazabilidad.
- **O5.** Lo pendiente coincide con lo planificado: apilamiento y MLP con `explicador: null` y motivo; el coste y la
  estabilidad del explicador de permutación (D33) quedan para la Entrega 3.

## Veredicto

**Apto con observaciones.** No hay fuga temporal ni entre pliegues, 2014J no se lee, el modelo explicado es exactamente
el modelo base del principal, las cifras se reproducen y la exportación cumple el contrato. M1 y m1-m4 se incorporan a
la memoria (m4 también a `decisiones.md`) antes de redactar 5.7.2.
