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
  "automl": {"optimizador": "Optuna", "muestreador": "TPE", "podador": "…", "metrica_objetivo": "roc_auc",
             "n_trials_por_familia": 0, "espacios_busqueda": {"lgbm": {"…": "…"}},
             "apilamiento": {"en_busqueda": false, "base": "mejor de cada familia (D48)", "metamodelo": "rl_regularizada", "cv_interna": "agrupada por presentación"}},
  "tratamiento_desbalance": "class_weight como hiperparámetro",
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
    "punto_operacion_oof": {"umbral": 0.0, "sensibilidad": 0.0, "precision": 0.0, "tasa_alerta": 0.0, "matriz_confusion": [[0, 0], [0, 0]]},
    "desglose": {"CCC": {}, "resto": {}},
    "shap": {"explicador": "tree", "coste_s": 0, "estabilidad": {"spearman_media": 0.0, "spearman_rango": [0.0, 0.0], "top10_solape_media": 0.0, "top10_solape_rango": [0.0, 0.0]}},
    "equidad_oof": {"gender": {"subgrupos": {"F": {"n": 0, "retiros": 0, "retiros_prueba": 0, "sensibilidad": 0.0, "sensibilidad_ic95": [0.0, 0.0],
                                             "tasa_falsos_positivos": 0.0, "tasa_falsos_positivos_ic95": [0.0, 0.0], "solo_descriptiva": false}},
                               "diferencia_sensibilidad": 0.0, "diferencia_sensibilidad_ic95": [0.0, 0.0],
                               "diferencia_tasa_falsos_positivos": 0.0, "diferencia_tasa_falsos_positivos_ic95": [0.0, 0.0]}}
  }],
  "metricas_test": null
}
```

- `variante`: `principal`, `sin_sensibles`, `con_sensibles`, `sin_exclusion_retirados` (D20) o `ablacion_<grupo>`.
  Las variantes que reutilizan hiperparámetros indican `hiperparametros_de: "<id del experimento principal>"`.
- Las referencias tienen los mismos campos que las familias (la mayoritaria, sin hiperparámetros).
- `ablacion_<grupo>`: uno de los 5 grupos de `grupo_ablacion` del catálogo (D46), sobre el modelo `mejor_automl`.
- `mejor_automl` (D44): candidato distinto de la RL con mayor `roc_auc_oof`, apilamiento incluido. `parsimonia.mejor`:
  candidato de mayor `roc_auc_oof`, RL incluida. `perdida` = ROC-AUC *out-of-fold* del mejor − la del candidato;
  `cumple` = límite superior de `ic95_bootstrap` < `margen` (D49-rev). `delong_p` solo se informa.
- `lectura` (D49): `ventaja_relevante`, `detectable_sin_relevancia`, `equivalencia_practica` o `no_concluyente`.
  Los IC *bootstrap* son del 95 % sin ajustar; la significación usa `delong_p_holm`.
- `equidad_oof` (D50): `gender`, `disability`, `age_band`, `imd_band` (con `faltante`); métricas en el umbral de
  decisión; diferencia = máxima entre subgrupos si hay más de dos. `retiros_prueba` es un recuento descriptivo de 2014J;
  `solo_descriptiva` = `retiros_prueba < 30`.
- `metricas_test` es `null` mientras `evaluado_en_prueba` sea `false`. En la Entrega 3 llevará por momento las mismas
  métricas, el punto de operación en prueba y `plan_evaluacion` (ruta y commit del archivo que declaraba la configuración).

## `tipo: "comparacion"`

`experimentos` (ids comparados), `origen_predicciones` (`oof` o `prueba`) y `contrastes`: por semana
`{modelo_a, modelo_b, roc_auc_a, roc_auc_b, diferencia, delong_p, delong_p_holm, ic95_bootstrap: [inf, sup], n_bootstrap, semilla, lectura}`.
Holm se aplica sobre los 4 momentos de cada par de modelos comparado.

## `manifest.json`

```json
{
  "generado": "2026-11-03T10:20:00",
  "commit": "a1b2c3d",
  "experimentos": ["experimentos/exp-2026-11-03-01.json"],
  "figuras": [{"archivo": "figuras/exp-2026-11-03-01_roc.png", "descripcion": "Curva ROC del modelo seleccionado", "experimento": "exp-2026-11-03-01"}],
  "capturas": [{"archivo": "capturas/explicabilidad-local.png", "descripcion": "Vista de explicación local de un estudiante"}],
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
