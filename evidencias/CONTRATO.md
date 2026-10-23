# Contrato de evidencias plataforma → memoria

La memoria solo usa lo que está en esta carpeta. Cada evidencia debe poder rastrearse hasta un commit.

## Estructura

```
evidencias/
├── manifest.json            # Índice de todo lo exportado (obligatorio)
├── experimentos/<id>.json   # Un archivo por experimento (esquema abajo)
├── figuras/                 # PNG/SVG a 300 ppp: ROC, PR, matrices de confusión, SHAP global/local, comparativas
├── capturas/                # Capturas de pantalla de la interfaz (PNG), nombre descriptivo
├── arquitectura/            # Diagramas (PNG/SVG + fuente .mmd/.puml/.drawio)
├── pruebas/                 # Informes de pruebas y cobertura (JUnit XML, HTML o resumen JSON)
└── usabilidad/              # Resultados anonimizados (CSV) + instrumento utilizado (cuestionario)
```

## Esquema de `experimentos/<id>.json`

```json
{
  "id": "exp-2026-11-03-01",
  "fecha": "2026-11-03T10:15:00",
  "commit": "a1b2c3d",
  "descripcion": "AutoML sobre OULAD, ventana de 4 semanas, métrica objetivo F1",
  "dataset": {
    "nombre": "OULAD",
    "version": "2017",
    "n_registros": 0,
    "n_variables": 0,
    "ventana_prediccion": "semana 4 de 39",
    "distribucion_clases": {"no_desercion": 0, "desercion": 0}
  },
  "particion": {"estrategia": "estratificada", "test_size": 0.2, "semilla": 42, "validacion": "5-fold CV estratificada sobre entrenamiento"},
  "automl": {"optimizador": "Optuna", "n_trials": 100, "metrica_objetivo": "f1", "modelos_candidatos": ["logreg", "rf", "gb", "xgb", "lgbm"]},
  "tratamiento_desbalance": "class_weight=balanced",
  "modelo_seleccionado": {"tipo": "lgbm", "hiperparametros": {}},
  "metricas_cv": {"f1_media": 0.0, "f1_desv": 0.0},
  "metricas_test": {
    "accuracy": 0.0, "precision": 0.0, "recall": 0.0, "f1": 0.0, "roc_auc": 0.0, "pr_auc": 0.0,
    "matriz_confusion": [[0, 0], [0, 0]], "umbral": 0.5
  },
  "comparativa_candidatos": [{"modelo": "logreg", "f1_cv": 0.0, "roc_auc_cv": 0.0}],
  "tiempo_ejecucion_s": 0,
  "figuras": ["figuras/exp-2026-11-03-01_roc.png", "figuras/exp-2026-11-03-01_shap_global.png"]
}
```

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
- Los valores `0` del ejemplo son marcadores: se rellenan con resultados reales, nunca a mano.
- No borrar experimentos antiguos citados en la memoria; añadir nuevos con otro `id`.

## Ampliaciones (2026-10-17)

Estas ampliaciones **añaden** campos; no cambian los anteriores. El ejemplo de arriba es ilustrativo: en los
experimentos de modelado, la partición y la métrica siguen las decisiones D7-rev, D29-rev y D6
(`../memoria/plan/decisiones.md`).

### Campos comunes a todo experimento

| Campo | Contenido |
|---|---|
| `tipo` | `exploracion`, `cortes`, `modelado` o `comparacion`. Si falta (exp-2026-10-05-01 y -02), es `exploracion` |
| `entorno` | Versión de Python y de cada biblioteca usada (ya presente en exp-2026-10-05-02) |
| `dataset.sha256` | SHA-256 de cada archivo de entrada (ya presente en exp-2026-10-05-02) |
| `calidad_datos` | Recuentos de anomalías detectadas (ya presente en exp-2026-10-05-02) |

### `tipo: "cortes"`

`cortes`: lista con una entrada por semana `{semana, dia_corte, n_variables, variables_por_grupo, exclusiones,
entrenamiento: {n, desercion, no_desercion, prevalencia}, prueba: {…}}`; `bajas_dia_0` (bajas con
`date_unregistration == 0`); `catalogo_variables` (nombre, grupo, origen, fecha máxima usada).
`n_variables` = columnas de entrada del modelo, sin identificadores ni etiqueta.

### `tipo: "modelado"` (una configuración en un momento)

Además de los campos del esquema base (`particion`, `automl`, `modelo_seleccionado`, `metricas_cv`, `metricas_test`,
`comparativa_candidatos`):

| Campo | Contenido |
|---|---|
| `semana` | 0, 4, 8 o 12 |
| `variante` | `principal`, `sin_sensibles`, `con_sensibles`, `sin_exclusion_retirados` (D20) o `ablacion_<grupo>` |
| `evaluado_en_prueba` | `true` / `false`. Si es `false`, `metricas_test` es `null` |
| `plan_evaluacion` | Ruta y commit del archivo que declaraba la configuración antes de evaluarla en prueba |
| `referencias` | Métricas de clase mayoritaria, RL por defecto y RL optimizada, con el mismo formato |
| `calibracion` | `{metodo, brier_cv, brier_test, figura}` |
| `punto_operacion` | `{umbral, sensibilidad, precision, tasa_alerta}` en *out-of-fold* y en prueba |
| `desglose` | Métricas de CCC frente al resto y por módulo (informativas) |
| `shap` | `{explicador, coste_s, estabilidad: {spearman_media, spearman_rango, top10_solape_media, top10_solape_rango}}` |
| `equidad` | Por variable sensible y subgrupo: `{n, sensibilidad, tasa_falsos_positivos}` |
| `semillas` | Semillas de partición, Optuna, modelos y *bootstrap* |

### `tipo: "comparacion"`

`experimentos` (ids comparados), `origen_predicciones` (`oof` o `prueba`) y, por semana, `{modelo_a, modelo_b,
roc_auc_a, roc_auc_b, diferencia, delong_p, ic95_bootstrap: [inf, sup], n_bootstrap, semilla}`.

### Regla adicional

- Ningún experimento con `evaluado_en_prueba: true` sin `plan_evaluacion` cuyo commit sea anterior al del experimento.
