# Auditoría de fugas del experimento exp-2026-10-29-01

**Fecha:** 2026-10-29
**Auditor:** agente `revisor-fuga` (solo lectura; no escribió el código y no modificó ningún archivo del repositorio)
**Commit auditado:** `07d7cbc` (código registrado en el JSON), con las salidas de la exportación todavía sin confirmar
**Veredicto:** **apto con observaciones.** No hay hallazgos críticos ni mayores; hay dos menores de redacción (m1, m2),
que se declaran en la memoria sin relanzar el experimento.

## Alcance

- Experimento: sensibilidad a la fuga D20/D39 sin nueva búsqueda (D38), sobre el mejor AutoML y la RL desplegada:
  `evidencias/experimentos/exp-2026-10-29-01.json`, `evidencias/figuras/exp-2026-10-29-01_sensibilidad_fuga.png`,
  `evidencias/pruebas/exp-2026-10-29-01_pruebas.xml` y `evidencias/manifest.json`.
- Código: `ml/sensibilidad_fuga.py`, `ml/configs/sin_exclusion_retirados.json`, `ml/tests/test_sensibilidad_fuga.py`, el
  cambio de `cargar_entrenamiento` en `ml/experimento.py`, `ml/cortes_oulad.py`, `ml/ablacion.py`
  (`predecir_sin_grupo`), `ml/variante.py` (`predicciones_principal`), `ml/automl/apilamiento.py` y
  `ml/automl/calibracion.py`.
- Datos no versionados, solo lectura: los 8 cortes (`semana_<k>` y `semana_<k>_sin_exclusion_retirados`), los 4 OOF de
  exp-2026-10-27-01 y los 4 de exp-2026-10-29-01, y los CSV brutos de OULAD.
- Referencias normativas: `decisiones.md` de la memoria (D20, D29-rev, D38, D39, D39-concreción, D46-rev),
  `.claude/skills/rigor-ml/SKILL.md`, `evidencias/CONTRATO.md` y la auditoría de exp-2026-10-28-03.

**Cómo se trabajó.** Con scripts temporales fuera del repositorio se recalcularon la población desde los datos brutos,
las 48 ROC-AUC y diferencias, los 24 IC bootstrap, un bootstrap alternativo por matrícula, el reentrenamiento de la RL
sobre el corte principal y el efecto aislado de los percentiles de cohorte.

## Comprobaciones realizadas y resultado

| # | Comprobación | Resultado |
|---|---|---|
| 1 | Población (D39) | Se cumple. `exclusiones` (`ml/cortes_oulad.py:128-136`) solo cambia `baja ≤ 7k` por `baja < 0`; la matrícula tardía (D34) y D26/D27 (`:281`) se aplican igual. Desde los datos brutos, las filas añadidas son exactamente las esperadas (413, 2371, 3387 y 4185 en todas las particiones): todas con 0 ≤ `date_unregistration` ≤ 7k, ninguna tardía y todas `Withdrawn`; no falta ninguna fila de la principal. En entrenamiento se añaden 411, 1222, 1901 y 2388, como en D39-concreción; n, retiros y prevalencia coinciden con `cortes_sin_exclusion_retirados` de exp-2026-10-23-02. |
| 2 | Variables de los retirados añadidos | Sin fuga. Mismos agregados con `date ≤ 7k` y `date_submitted ≤ 7k` (`ml/cortes_oulad.py:171, 215-225`); `dias_desde_ultima_actividad` ≥ 0. `date_unregistration`, `final_result` y la nota de las TMA siguen excluidas en el catálogo. En las filas comunes solo difieren las 3 columnas `percentil_*_cohorte` (ver m2): la fuga medida es de población, no de variables. |
| 3 | `filas_comunes`, bootstrap y descomposición | Correctos. Una máscara independiente por conjunto de claves coincide con la columna `comun`; orden, pliegues y etiquetas coinciden con el OOF principal y hay un solo pliegue por presentación. Las 48 ROC-AUC y diferencias se reproducen con `roc_auc_score`, y los 24 IC exactamente (2000 réplicas, semilla 42). La unidad de remuestreo es `id_student` (13, 139, 258 y 318 estudiantes tienen a la vez filas comunes y añadidas, que viajan juntas); se descartan las réplicas sin las dos clases en la réplica o en sus filas comunes, y el emparejamiento en filas comunes es correcto (`ml/sensibilidad_fuga.py:89-103`). Un bootstrap por matrícula da IC casi idénticos. La suma de la descomposición se comprueba sin redondear (`:115`). |
| 4 | 2014J fuera de toda decisión | Se cumple. `cargar_entrenamiento` filtra `particion == "entrenamiento"` al leer (`ml/experimento.py:101`); ningún OOF contiene 2014J; de los cortes solo se usan los SHA-256. |
| 5 | Sin nueva búsqueda (D38) | Se cumple. Hiperparámetros, método de calibración, semillas (42) y pliegues del principal; `n_jobs` 8. La RL reentrenada con un script independiente sobre el corte principal reproduce el OOF del principal con `max\|Δp\| = 0` en las 4 semanas. El apilamiento cumple D48 (metamodelo con divisiones internas por presentación) y la calibración es anidada con `ensemble=False`. |
| 6 | Contrato y manifiesto | Se cumplen. El esquema `sin_exclusion_retirados` de `CONTRATO.md` (commit 07d7cbc) coincide con las claves del JSON; commit 07d7cbc y fecha posterior al commit; SHA-256 de los 8 cortes (incluidos los 4 de D20), de los 4 OOF y de los CSV brutos correctos. El manifiesto añade el JSON, la figura y el JUnit. Figura de 2700×1320 a 300 ppp con coma decimal. Sin nombre del equipo ni del usuario en el JSON ni en el XML. |
| 7 | `pytest ml/tests` en `07d7cbc` | **127 superadas, 0 fallidas, 0 omitidas** (JUnit `pruebas/exp-2026-10-29-01_pruebas.xml`), incluida `test_oulad_poblacion_con_fuga_contiene_a_la_principal_y_solo_anade_retirados`. |
| 8 | Redacción | Sin lecturas causales; DeLong solo informativo; la salvedad de M1 (ruido de reentrenamiento) está en `comparacion` (`ml/sensibilidad_fuga.py:288-290`). |

## Hallazgos

### Menores

- **m1. «Cota inferior» se presenta como garantía** (`ml/sensibilidad_fuga.py:13`, `:195` en el título de la figura y
  `:280`, `configuracion.descripcion` y el esquema de `CONTRATO.md`). Procede de D38, así que no es una desviación de
  las decisiones, pero aplica el mismo razonamiento que el m2 de la auditoría de exp-2026-10-28-03: optimizar en la
  población con fuga no garantiza una ROC-AUC OOF mayor (TPE es estocástico, el método de calibración se elige por Brier
  y hay ruido de reentrenamiento de ±0,002-0,005), y la ROC-AUC del principal lleva el optimismo de haber seleccionado
  entre 50 ensayos. Lo esperable es un sesgo a la baja, no un límite estricto. En las semanas 4-12 (0,066-0,123) el
  matiz no cambia nada; en la semana 0 (0,014-0,016) conviene matizarlo.
  **Resolución (decisión del estudiante, 2026-10-29):** se declara en la memoria como «estimación previsiblemente
  sesgada a la baja (D38)», en paralelo con D46-rev, sin relanzar; el esquema de `CONTRATO.md` se ajusta en el commit
  siguiente.
- **m2. Los percentiles de cohorte son un segundo canal dentro de `efecto_entrenar`, poco declarado.** En las filas
  comunes cambian las 3 `percentil_*_cohorte` porque `ml/cortes_oulad.py:204-207` las calcula sobre la población del
  corte, que ahora incluye a los retirados (correlación entre versiones 0,996-0,9998; |Δ| medio 0,006 en la semana 0 y
  0,035-0,040 en la 12; el orden dentro de cada presentación se conserva). Es coherente con D39: la definición es la
  población elegible de la presentación en el corte, y un estudio que no excluye a los retirados los incluiría en la
  cohorte; no es fuga de información posterior. Solo se declaraba en el campo `poblacion`, no en `comparacion` ni en el
  CONTRATO. Impacto medido: la RL desplegada reentrenada en la población principal cambiando solo los 3 percentiles por
  los de la cohorte con fuga da ΔROC-AUC de +0,0004, −0,0009, −0,0006 y +0,0007 (semanas 0, 4, 8 y 12), frente a
  `efecto_entrenar` de −0,0002, −0,0052, −0,0122 y −0,0109: el canal es ≤ 0,001, por debajo del ruido de
  reentrenamiento. No se midió en el apilamiento ni en catboost por coste.
  **Resolución (decisión del estudiante, 2026-10-29):** se declara en la memoria y en el esquema de `CONTRATO.md` que
  `efecto_entrenar` incluye el recálculo de los percentiles de cohorte, cuyo efecto aislado en la RL es ≤ 0,001.

### Observaciones

- **O1.** Durante la auditoría, el árbol de trabajo tenía cambios posteriores ajenos al experimento (`CONTRATO.md` y los
  archivos de SHAP). El experimento se ejecutó con el árbol limpio (`comprobar_arbol_limpio`), así que no le afecta; esos
  cambios van en un commit separado del de estas evidencias.
- **O2.** `efecto_entrenar` es negativo en 7 de 8 casos (−0,018 a −0,003; en la RL de la semana 0 es ≈ 0): toda la
  inflación procede de evaluar con casos triviales, y entrenar con ellos empeora un poco la ordenación en las filas
  comunes. Se describe como diferencia de ROC-AUC, sin atribuirle un mecanismo; en la semana 0 del apilamiento
  (−0,0028) está dentro del rango de M1.
- **O3.** En la semana 0, la inflación se concentra en dos presentaciones: las bajas del día 0 se reparten en 2013J
  (252), 2014B (163), 2013B (2) y 2014J (2). Conviene mencionarlo al interpretar el 0,014-0,016.
- **O4.** Hay 1131-1153 estudiantes con matrículas en pliegues distintos: es el solape ya declarado en D29-rev, no nuevo
  de este experimento; el bootstrap por estudiante los mantiene juntos.

## Desviaciones de decisiones.md

Ninguna. D20, D38, D39 y D39-concreción se cumplen: lectura primaria, complementaria pareada con DeLong informativo,
descomposición exportada, los mismos dos modelos que D46-rev, n y prevalencia por población, 2014J fuera y salvedad
sobre el reentrenamiento. «Cota inferior» (m1) procede del propio D38; el matiz se registra en `decisiones.md`, como en
D46-rev.

## Veredicto

**Apto con observaciones.** No hay fuga ni uso de 2014J, se cumplen D38 y el contrato, y las cifras se reproducen. m1 y
m2 se declaran en la memoria sin relanzar el experimento.
