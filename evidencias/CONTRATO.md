# Contrato de evidencias plataforma → memoria

La memoria solo usa lo que está en esta carpeta. Cada evidencia debe poder rastrearse hasta un commit.
Revisado el 2026-10-23 al diseño vigente, con D44-D51-rev (`../memoria/plan/decisiones.md`; checklist en `.claude/skills/rigor-ml`).

## Estructura

```
evidencias/
├── manifest.json            # Índice de todo lo exportado (obligatorio)
├── experimentos/<id>.json   # Un archivo por experimento (esquemas abajo)
├── figuras/                 # PNG/SVG a 300 ppp: ROC, PR, calibración, SHAP global/local, comparativas
├── capturas/                # Capturas de pantalla de la interfaz (PNG), nombre descriptivo
├── arquitectura/            # Diagramas (PNG/SVG + fuente .mmd/.puml/.drawio)
├── pruebas/                 # Informes de pruebas y cobertura (JUnit XML, HTML o resumen JSON)
└── usabilidad/              # Resultados anonimizados (CSV) + instrumento utilizado (cuestionario)
```

## Campos comunes a todo experimento

```json
{
  "id": "exp-2026-10-27-01",
  "tipo": "cortes",
  "fecha": "2026-10-27T10:15:00",
  "commit": "a1b2c3d",
  "descripcion": "…",
  "dataset": {"nombre": "OULAD", "version": "2017", "tablas_usadas": ["…"], "sha256": {"courses.csv": "…"}},
  "entorno": {"python": "…", "pandas": "…", "scikit-learn": "…"},
  "tiempo_ejecucion_s": 0,
  "figuras": ["figuras/exp-2026-10-27-01_….png"]
}
```

- `tipo`: `exploracion`, `cortes`, `modelado` o `comparacion`. Si falta (exp-2026-10-05-01 y -02), es `exploracion`.
- `entorno`: versión de Python y de **cada** biblioteca que usa el script. `dataset.sha256`: de cada archivo de entrada.
- Experimentos de modelado (desde la F3): `hardware` = `{procesador, nucleos_fisicos, nucleos_logicos, memoria_gb, sistema}`,
  sin el nombre del equipo; `pruebas` = `{informe: "pruebas/<id>_pruebas.xml", superadas, fallidas, omitidas}`, JUnit de
  todas las pruebas de `ml/tests` ejecutadas en el commit del experimento antes de modelar (sin `hostname`).
- Un valor que no se puede calcular se deja en `null` y se añade su motivo en `motivos_null: {"<ruta.del.campo>": "…"}`.

## `tipo: "exploracion"`

Esquema de exp-2026-10-05-02: `dataset` (con `distribucion_clases` y `distribucion_final_result`), `exploracion`,
`calidad_datos`.

## `tipo: "cortes"` (preparación de datos; sin modelos)

| Campo | Contenido |
|---|---|
| `reglas` | Decisiones aplicadas (D2, D24-D28, matrícula tardía, evaluaciones, `is_banked`) con su texto |
| `eliminaciones` | Por regla (D26, D27) y partición: matrículas eliminadas |
| `bajas_dia_0`, `bajas_antes_dia_0` | Bajas con `date_unregistration == 0` y `< 0`: antes y después de D26-D27 y eliminadas por cada regla, total y por partición |
| `particion` | `{entrenamiento: [presentaciones], prueba: [presentaciones], n_matriculas, n_estudiantes_unicos}` por partición |
| `pliegues` | Composición de los 5 pliegues (presentaciones) y, por corte, `n` y prevalencia de cada uno |
| `solapamiento` | Estudiantes en más de un pliegue; estudiantes a la vez en entrenamiento y en 2014J |
| `cortes` | Por semana: `{semana, dia_corte, proporcion_curso: {B, J}, n_variables, variables_por_grupo, por_particion: {entrenamiento, prueba}}`; cada partición con `{n, desercion, no_desercion, prevalencia, excluidos_baja, excluidos_matricula_tardia}` y el mismo desglose para `CCC` y `resto` |
| `cortes_sin_exclusion_retirados` | Igual que `cortes`, para la población de D20 |
| `subgrupos` | Por corte, partición, variable sensible y valor (incluido faltante): `{n, prevalencia}` |
| `evaluaciones` | Recuentos afectados por las reglas (`is_banked`, exámenes excluidos, notas TMA descartadas), cada uno en filas, matrículas y estudiantes, total y por partición, con su `definicion` |
| `tipos_actividad` | Tipos con variable (solo entrenamiento) y tipos de 2014J sin variable, con sus clics y matrículas |
| `catalogo_variables` | Ruta a un CSV en `experimentos/` con nombre, tabla de origen, tipo, momento desde el que existe, cálculo, grupo de ablación y motivo de exclusión |
| `pruebas_antifuga` | Ruta al informe de pruebas en `pruebas/` y resumen `{superadas, fallidas}` |

`n_variables` = columnas de entrada del modelo, sin identificadores ni etiqueta.

## `tipo: "modelado"` (una variante, los 4 momentos; solo validación en la Entrega 2)

```json
{
  "variante": "principal",
  "experimento_cortes": "exp-…",
  "particion": {"estrategia": "temporal", "entrenamiento": "presentaciones anteriores a 2014J (15)", "prueba": "2014J (7)",
                "validacion": "5 pliegues agrupados por presentación", "semillas": {"optuna": 42, "modelos": 42, "bootstrap": 42}},
  "automl": {"optimizador": "Optuna", "muestreador": "TPE", "parametros_muestreador": {"n_startup_trials": 10, "…": "…"},
             "podador": "…", "parametros_podador": {"…": "…"}, "tiempo_maximo_por_busqueda": "ninguno: …",
             "n_jobs": {"valor": 8, "nivel": "…"}, "metrica_objetivo": "roc_auc",
             "n_trials_por_familia": 0, "espacios_busqueda": {"lgbm": {"…": "…"}},
             "apilamiento": {"en_busqueda": false, "base": "mejor de cada familia (D48)", "metamodelo": "rl_regularizada", "cv_interna": "agrupada por presentación"}},
  "tratamiento_desbalance": "class_weight como hiperparámetro",
  "calibracion_definicion": "…", "brier_sin_calibrar_definicion": "…",
  "evaluado_en_prueba": false,
  "momentos": [{
    "semana": 8,
    "familias": [{"modelo": "lgbm", "hiperparametros": {}, "tiempo_s": 0,
                  "por_pliegue": [{"pliegue": 1, "roc_auc": 0.0, "pr_auc": 0.0, "brier": 0.0}],
                  "roc_auc_media": 0.0, "roc_auc_desv": 0.0, "roc_auc_oof": 0.0, "pr_auc_oof": 0.0}],
    "apilamiento": {"base": ["rl", "lgbm", "…"], "tiempo_s": 0, "por_pliegue": [], "roc_auc_media": 0.0, "roc_auc_desv": 0.0, "roc_auc_oof": 0.0, "pr_auc_oof": 0.0},
    "referencias": [{"modelo": "mayoritaria"}, {"modelo": "rl_defecto"}, {"modelo": "rl_optimizada"}],
    "mejor_automl": "lgbm",
    "contraste_central": {"modelo_a": "lgbm", "modelo_b": "rl_optimizada", "diferencia": 0.0, "ic95_bootstrap": [0.0, 0.0], "delong_p": 0.0, "delong_p_holm": 0.0, "lectura": "…"},
    "parsimonia": {"regla": "no inferioridad (D49-rev)", "mejor": "lgbm", "margen": 0.02,
                   "candidatos": [{"modelo": "rl", "perdida": 0.0, "ic95_bootstrap": [0.0, 0.0], "delong_p": 0.0, "cumple": true}]},
    "modelo_desplegado": {"modelo": "…", "motivo": "D33/D49-rev: …"},
    "calibracion": {"metodo": "isotonica", "brier_sin_calibrar": 0.0, "brier_calibrado": 0.0, "anidada": true},
    "punto_operacion_oof": {"umbral": 0.0, "umbral_exacto": 0.0, "sensibilidad": 0.0, "precision": 0.0, "tasa_alerta": 0.0, "matriz_confusion": [[0, 0], [0, 0]]},
    "desglose": {"CCC": {}, "resto": {}},
    "shap": {"explicador": "tree", "coste_s": 0, "estabilidad": {"spearman_media": 0.0, "spearman_rango": [0.0, 0.0], "top10_solape_media": 0.0, "top10_solape_rango": [0.0, 0.0]}},
    "equidad_oof": {"gender": {"subgrupos": {"F": {"n": 0, "retiros": 0, "retiros_prueba": 0, "sensibilidad": 0.0, "sensibilidad_ic95": [0.0, 0.0],
                                             "tasa_falsos_positivos": 0.0, "tasa_falsos_positivos_ic95": [0.0, 0.0], "solo_descriptiva": false}},
                               "diferencia_sensibilidad": 0.0, "diferencia_sensibilidad_ic95": [0.0, 0.0],
                               "diferencia_tasa_falsos_positivos": 0.0, "diferencia_tasa_falsos_positivos_ic95": [0.0, 0.0],
                               "sin_solo_descriptiva": {"subgrupos_excluidos": [], "diferencia_sensibilidad": 0.0, "diferencia_sensibilidad_ic95": [0.0, 0.0],
                                                        "diferencia_tasa_falsos_positivos": 0.0, "diferencia_tasa_falsos_positivos_ic95": [0.0, 0.0]},
                               "metodo_ic_diferencia": "…"}}
  }],
  "metricas_test": null
}
```

- `variante`: `principal`, `sin_sensibles`, `con_sensibles`, `sin_exclusion_retirados` (D20), `ablacion` (D46), `shap`
  (D9, D32) o `modelo_final` (D41).
  Las variantes que reutilizan hiperparámetros indican `hiperparametros_de: "<id del experimento principal>"`.
- `con_sensibles` (D8, `ml/variante.py`): sin búsqueda; `reentrenamiento` y `comparacion` (texto); por momento
  `{semana, n, retiros, mejor_automl_principal, desplegado_principal, por_modelo, mejores, tiempo_s}`. Cada fila de
  `por_modelo` lleva los campos de una familia más `roc_auc_con`, `roc_auc_sin`, `diferencia` (con − sin = coste de
  excluirlas), `ic95_bootstrap` (pareado), `delong_p` y `alcanza_margen` (diferencia ≥ 0,02); `mejores` compara el mejor
  candidato de cada variante (`mejor_con`, `mejor_sin`). `salvaguarda_d38`: `{regla, margen, activada, activadores}`.
- `umbral` va redondeado a 6 decimales; `umbral_exacto` (desde 2026-10-29) es el valor con que se calculan las alertas.
  Con la isotónica hay bloques de empates en el umbral: aplicar el redondeado puede dejarlos fuera (P-18).
- Las figuras de un experimento se pueden redibujar desde sus predicciones *out-of-fold* (`ml/figuras_experimento.py`)
  con un sufijo nuevo (p. ej. `_v2`), sin sobrescribir las anteriores; el manifiesto registra el commit del dibujo.
  Las variantes (D8, ablación, D20, SHAP) se redibujan desde su JSON; en SHAP, con la estabilidad sin variables nulas
  de un análisis `shap_estabilidad_y_extremos` (`--estabilidad`). Ejes y etiquetas con coma decimal y sin códigos de
  decisión.
- Las referencias tienen los mismos campos que las familias (la mayoritaria, sin hiperparámetros). `rl_optimizada` repite
  los de la familia `rl` y añade `igual_que`.
- `shap` es `null` con su motivo en `motivos_null` (`"momentos.shap"`) mientras no se calcule (F3).
- `ablacion` (D46, `ml/ablacion.py`): sin búsqueda; un solo JSON con los 5 grupos de `grupo_ablacion` del catálogo
  (`grupos`: nombre y variables de cada uno) y `reentrenamiento` y `comparacion` (texto). Por momento
  `{semana, n, retiros, modelos, tiempo_s}`; cada elemento de `modelos` es `{papel, modelo, calibracion, grupos}`, con
  `papel` = `mejor_automl` (D44) o `rl_desplegada` (D49-rev), y cada fila de `grupos` lleva `grupo`,
  `variables_quitadas`, `roc_auc_completo`, `roc_auc_sin_grupo`, `perdida` (completo − sin el grupo; estimación
  sesgada al alza de la contribución), `ic95_bootstrap` (pareado), `delong_p` y `tiempo_s`.
- `sin_exclusion_retirados` (D20, D39, `ml/sensibilidad_fuga.py`): sin búsqueda; mismos papeles que `ablacion`;
  `poblacion`, `reentrenamiento` y `comparacion` (texto). Por momento `{semana, poblaciones, modelos, tiempo_s}`, con
  `poblaciones` = `{principal: {n, retiros, prevalencia}, con_fuga: {n, retiros, prevalencia}, retirados_anadidos}`.
  Cada elemento de `modelos` es `{papel, modelo, calibracion, roc_auc_fuga_su_poblacion, roc_auc_fuga_comunes,
  roc_auc_principal, inflacion, efecto_evaluar, efecto_entrenar, suma_comprobada, tiempo_s}`; cada componente es
  `{valor, ic95_bootstrap}` (`efecto_entrenar` añade `delong_p`). `inflacion` = con fuga en su población − principal
  (lectura primaria; estimación previsiblemente sesgada a la baja por D38, no una cota garantizada) = `efecto_evaluar` +
  `efecto_entrenar`. `efecto_entrenar` incluye el recálculo de los percentiles de cohorte sobre la población con fuga
  (efecto aislado en la RL ≤ 0,001; auditoría de exp-2026-10-29-01, m2). Los IC salen de un mismo bootstrap
  por estudiante sobre la población con fuga.
- `shap` (D9, D32, D33, `ml/shap_estabilidad.py`): sin búsqueda; `reentrenamiento`, `metodo` y `explicadores` (texto).
  Por momento `{semana, n, retiros, modelos, tiempo_s}`; cada elemento de `modelos` es `{papel, modelo, explicador,
  salida, coste_s, aditividad_error_max, concordancia_con_oof_principal_spearman_min, importancia_global, estabilidad}`,
  con `importancia_global` = lista ordenada de `{variable, media_abs, rango_pliegues}` (media de |SHAP| en log-odds sin
  calibrar, por variable original) y `estabilidad` = `{pares, spearman_media, spearman_rango, top10_solape_media,
  top10_solape_rango}`. Un modelo sin explicador en esta entrega lleva `explicador: null` y `motivo`. Los valores SHAP
  *out-of-fold* por fila van en `data/procesado/oof/<id>_shap_semana_<k>.parquet` (SHA-256 en el JSON).
- `modelo_final` (D41, D31-rev, `ml/modelo_final.py`): sin búsqueda ni evaluación en prueba (`metricas_test: null`);
  `reentrenamiento` y `umbral_transferido` (texto). Por momento `{semana, n, retiros, presentaciones, modelo,
  hiperparametros, calibracion: {metodo, cv, ensemble}, umbral: {valor, valor_exacto, origen, punto_operacion_oof},
  diagnostico_d41, explicador,
  coeficientes_no_nulos, columnas_transformadas, aditividad_error_max, tiempo_s}`. Los paquetes del modelo (modelo
  calibrado, umbral, columnas y fondo del explicador) van en `data/procesado/modelos/<id>_semana_<k>.joblib`, no
  versionados, con su SHA-256 en `modelos_sha256`. Cada momento lleva además `con_sensibles` (P-13): `{desplegado:
  false}` y los mismos campos para la variante con sensibles, con su método de calibración y su umbral out-of-fold
  (paquete `<id>_con_sensibles_semana_<k>.joblib`); a nivel raíz, `variables_con_sensibles`, `con_sensibles` (texto) y
  `optuna` (parámetros efectivos del muestreador y el podador, con `vale_para`, P-4). `diagnostico_d41` (P-19):
  `{sensibilidad_en_entrenamiento, tasa_alerta_en_entrenamiento, lectura}`, el modelo final con el umbral transferido
  sobre sus propias filas de entrenamiento; diagnóstico de la aproximación D41, dentro de la muestra, no rendimiento.
- `mejor_automl` (D44): candidato distinto de la RL con mayor `roc_auc_oof`, apilamiento incluido. `parsimonia.mejor`:
  candidato de mayor `roc_auc_oof`, RL incluida. `perdida` = ROC-AUC *out-of-fold* del mejor − la del candidato;
  `cumple` = límite superior de `ic95_bootstrap` < `margen` (D49-rev). `delong_p` solo se informa.
- `lectura` (D49): `ventaja_relevante`, `detectable_sin_relevancia`, `equivalencia_practica` o `no_concluyente`, con el
  signo de la diferencia (AutoML − RL); una desventaja significativa ≥ 0,02 es `desventaja_relevante`.
  Los IC *bootstrap* son del 95 % sin ajustar; la significación usa `delong_p_holm`.
- `equidad_oof` (D50): `gender`, `disability`, `age_band`, `imd_band` (con `faltante`); métricas en el umbral de
  decisión; diferencia = máxima entre subgrupos si hay más de dos, con todos los subgrupos y en `sin_solo_descriptiva`
  sin los marcados `solo_descriptiva`; `metodo_ic_diferencia` declara el *bootstrap* de percentiles sobre un máximo menos
  un mínimo. `retiros_prueba` es un recuento descriptivo de 2014J; `solo_descriptiva` = `retiros_prueba < 30`.
- `metricas_test` es `null` mientras `evaluado_en_prueba` sea `false`. En la Entrega 3 llevará por momento las mismas
  métricas, el punto de operación en prueba y `plan_evaluacion` (ruta y commit del archivo que declaraba la configuración).

## `tipo: "comparacion"`

`experimentos` (ids comparados), `origen_predicciones` (`oof` o `prueba`) y `contrastes`: por semana
`{modelo_a, modelo_b, roc_auc_a, roc_auc_b, diferencia, delong_p, delong_p_holm, ic95_bootstrap: [inf, sup], n_bootstrap, semilla, lectura}`.
Holm se aplica sobre los 4 momentos de cada par de modelos comparado.

Con `analisis: "equidad_con_sensibles"` (D8, D50, `ml/equidad_variante.py`), solo descriptivo y sin `contrastes`:
`metodo` y `lectura` (texto) y, por momento, `{semana, n, retiros, modelo, con, sin}`. `modelo` es el desplegado del
principal; `con` y `sin` llevan `calibracion`, `punto_operacion_oof` (umbral out-of-fold propio de cada variante, D45)
y `equidad_oof` con el esquema de D50. `sin` se recalcula desde las predicciones del principal y debe coincidir con su
JSON.

Con `analisis: "shap_estabilidad_y_extremos"` (D9, D32, `ml/shap_analisis.py`), desde un experimento `shap` sin
reentrenar: `metodo` (texto: `estabilidad`, `extremos`) y `lectura`; por momento `{semana, modelos}`, y cada modelo
`{papel, modelo, estabilidad: {todas, sin_nulas, variables_nulas}}` (cada versión con `variables` y los campos de
estabilidad del esquema `shap`; `todas` reproduce el experimento de origen y `sin_nulas` es la lectura principal). La RL
desplegada añade `extremos`: `{n, filas_con_extremo, proporcion, shap_abs_max, variables, alerta}`, con `variables` =
lista de `{variable, filas, shap_min, shap_max}` más `valor_min`, `valor_max`, `percentil_min`, `percentil_max`,
`filas_sin_valor` y `faltantes_entrenamiento` (o `valores` si es categórica) y `alerta` = `{umbral_exacto, alertadas,
cambian_al_acotar, dejan_de_alertar, pasan_a_alertar, cambian_entre_filas_con_extremo}`. El percentil se calcula sobre
las filas de entrenamiento con valor; una fila sin valor no tiene percentil (P-22). La alerta usa el umbral exacto y debe
reproducir las alertas y la sensibilidad del punto de operación registrado (P-18). Lleva `pruebas` (JUnit).

Con `analisis: "diagnostico_d41"` (P-19, `ml/diagnostico_d41.py`), desde un modelo final (`variante: "modelo_final"`) sin reentrenar: `metodo` y
`lectura` (texto), `modelos_sha256` (los del modelo final, comprobados al cargar cada paquete) y `pruebas` (JUnit). Por
momento `{semana, n, retiros, desplegado, con_sensibles}`, y cada variante `{umbral_exacto,
sensibilidad_en_entrenamiento, tasa_alerta_en_entrenamiento, lectura, sensibilidad_oof, tasa_alerta_oof}`: el paquete
aplicado a sus propias filas de entrenamiento frente al punto de operación *out-of-fold* del que salió el umbral. Es un
diagnóstico de la aproximación del umbral transferido, dentro de la muestra y sesgado: no es rendimiento.

Con `analisis: "explicacion_global_api"` (matiz D-3 del bloque E, `scripts/evidencia_global_api.py`), sin reentrenar: los
paquetes desplegados del modelo final importados con el importador de la API en SQLite en memoria. `experimentos` =
[modelo final, experimento `shap`, análisis de estabilidad], `metodo` (texto: `identidad`, `comparacion`), `lectura`,
`modelos_sha256` y `pruebas` (JUnit de `ml/tests`). Por momento `{semana, modelo, paquete, fuente_api, identidad,
comparacion_oof}`: `identidad` = `{identica, variables, sin_contribucion, n_filas, referencia_sha256}` (solo se exporta si la
explicación global de la API es exactamente la media de |SHAP| de `modelo_final.predecir_y_explicar` sobre las mismas
filas de referencia, y si estas son exactamente las de entrenamiento que reconstruye `experimento.cargar_entrenamiento`); `comparacion_oof` = `{todas: {variables, spearman}, sin_nulas: {variables, spearman}, variables_nulas,
top10: {solape, entran, salen, cambian_posicion: [{variable, posicion_api, posicion_oof}]}}`, descriptiva y sin umbral
(modelo final frente a la media *out-of-fold* de 5 modelos de pliegue: no son el mismo estimador).

Con `analisis: "no_regresion"` (`ml/no_regresion.py`, docs/diseno-api.md §6.2), sin `contrastes` ni métricas nuevas:
el mismo ensayo de `experimento.py` en un commit base (git worktree temporal con una copia de `data/`) y en el commit nuevo.
`commit_base`, `commit_nuevo`, `arbol_de_trabajo` (`true` solo en ensayos con cambios sin confirmar; nunca en una
exportación), `comando` (el del ensayo) y `metodo` (texto); `ensayos` = `{base, nuevo}`, cada uno `{id, commit,
configuracion, pruebas}` (ids de la carpeta temporal, no de `evidencias/`); `comparaciones` = `{momentos: {claves_comparadas,
claves_excluidas, valores_comparados, igual, diferencias}, predicciones_oof: [{semana, filas, columnas, igual, diferencia,
tolerancia, diferencia_maxima, sha256_base, sha256_nuevo, sha256_igual}]}`, con `momentos` comparado sin las claves
`tiempo*` (igualdad exacta, NaN igual a NaN, también el orden de las claves) y las predicciones con
`pandas.testing.assert_frame_equal(check_exact=False, rtol=0, atol=tolerancia)` (columnas no numéricas exactas;
`tolerancia` = 1e-9 porque RandomForest con `n_jobs` > 1 suma los árboles en el orden en que acaban los hilos, con
diferencias de redondeo de ~1e-16 que la isotónica y el apilamiento propagan a ~1e-13); `diferencia_maxima` =
`{columna: máx |base − nuevo|}` de las columnas decimales con diferencia distinta de 0; `diferencias` = lista de
`{ruta, base, nuevo}` y `diferencia` = mensaje de `assert_frame_equal` o `null`; `identico` (ambas comparaciones iguales,
las predicciones dentro de la tolerancia); `oof_sha256` = `{base, nuevo}` por semana; `dataset` (el del ensayo nuevo), `hardware` y
`pruebas` (JUnit del commit nuevo).

## Informes de pruebas de la API (`pruebas/api-<fecha>-NN_*`)

`api/exportar_pruebas.py` (docs/diseno-api.md §10), sin experimento asociado: `_pruebas.xml` (JUnit de todo `api/tests`
con `--tb=short`, sin `hostname`; propiedad de la suite `motor_bd_funcionales` y de cada caso funcional `requisito`), `_cobertura.json`
(coverage.py, rutas relativas, de `api/` y `ml/automl/` sin las pruebas) y `_resumen.json` = `{id, fecha, commit, comando,
entorno, superadas, fallidas, omitidas, funcionales, motor_bd_funcionales, funcionales_por_requisito, cobertura: {<paquete>: {archivos, lineas,
cubiertas, porcentaje}}, informes}`; solo las funcionales (y las unitarias marcadas `postgres`) usan
PostgreSQL, el resto SQLite en memoria. Solo se exporta con todas superadas y ninguna omitida. En `manifest.json`, sus
entradas de `pruebas` llevan `id` en lugar de `experimento`.

## Capturas de la interfaz (`capturas/web-<vista>.png`)

Manuales (docs/diseno-web.md §12, decisión W-10): Chrome a 1440 × 900, zoom 100 %, con `web/` y `api/` confirmados en un
commit. `python -m scripts.registrar_capturas [--experimento-web <id>]`, con el árbol limpio salvo los PNG, añade o
sustituye en `capturas` una entrada por PNG nuevo o cambiado (sin confirmar nada entre la toma y el registro; las ya
confirmadas sin cambios conservan su entrada): `{archivo, descripcion, commit, datos: {experimento, csv?: {ruta, sha256}}}`
(`commit` = el del código que se ve; `experimento` = el que muestra la vista; `csv` = el archivo cargado en ella). Nunca
2014J, ni la evaluación única en la cohorte de prueba con datos de OULAD, ni métricas de prueba.

## `manifest.json`

```json
{
  "generado": "2026-11-03T10:20:00",
  "commit": "a1b2c3d",
  "experimentos": ["experimentos/exp-2026-11-03-01.json"],
  "figuras": [{"archivo": "figuras/exp-2026-11-03-01_roc.png", "descripcion": "Curva ROC del modelo seleccionado", "experimento": "exp-2026-11-03-01"}],
  "capturas": [{"archivo": "capturas/web-explicacion-local.png", "descripcion": "Explicación local de un caso marcado (semana 4)", "commit": "a1b2c3d", "datos": {"experimento": "exp-2026-10-29-03", "csv": {"ruta": "data/procesado/demo/semana_4_2014B.csv", "sha256": "…"}}}],
  "arquitectura": [],
  "pruebas": [],
  "usabilidad": []
}
```

## Reglas
- Exportar siempre desde un árbol de trabajo limpio (sin cambios sin confirmar); registrar el commit.
- Los valores `0` de los ejemplos son marcadores: se rellenan con resultados reales, nunca a mano.
- No borrar experimentos antiguos citados en la memoria; añadir nuevos con otro `id`.
- De 2014J, hasta la evaluación final de la Entrega 3, solo se exportan recuentos descriptivos: nunca predicciones ni métricas.
- Ningún experimento con `evaluado_en_prueba: true` sin `plan_evaluacion` cuyo commit sea anterior al del experimento.
- Sin datos personales del autor en ningún archivo exportado.
