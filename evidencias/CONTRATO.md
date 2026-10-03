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
