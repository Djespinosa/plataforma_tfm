---
name: arquitectura
description: Estructura del repositorio, capas (núcleo ML ← API Flask ← interfaz Angular), convenciones de código Python y TypeScript, API REST y modelo de datos PostgreSQL de la plataforma. Usar al crear archivos o módulos nuevos, al diseñar endpoints o tablas, o cuando se dude dónde va algo.
---

# Arquitectura

## Capas y dependencia

```
web/ (Angular)  →  api/ (Flask + PostgreSQL)  →  ml/ (núcleo ML, Python puro)
```

- `ml/` no importa Flask ni conoce la base de datos. Se usa desde scripts y desde la API.
- `api/` envuelve `ml/` **sin reescribirlo** (regla 7 de CLAUDE.md). Si la API necesita algo nuevo, se añade en `ml/`
  con su prueba y la API lo llama.
- `web/` solo habla con `api/` por HTTP/JSON.
- **D10:** la plataforma recibe una tabla genérica (el usuario elige objetivo y columnas ignoradas). Lo específico de
  OULAD (cortes, población, variables del aula virtual) vive en scripts de `ml/` y nunca en `api/` ni en `web/`.

## Estructura del repositorio

Existente: `ml/exploracion_oulad.py`, `evidencias/`, `data/raw/oulad/` (no versionado). Propuesta para lo nuevo
(se crea cada carpeta cuando haga falta, no antes):

```
ml/
├── exploracion_oulad.py      # existente
├── cortes_oulad.py           # script D10: conjuntos por momento (OE2)
├── evidencias.py             # funciones comunes de exportación (al escribir el 2.º script que exporte)
├── automl/                   # paquete del núcleo, agnóstico al conjunto de datos
│   ├── particion.py          # pliegues agrupados, partición fija
│   ├── busqueda.py           # espacios de búsqueda y Optuna
│   ├── calibracion.py        # calibración y umbral
│   ├── comparacion.py        # DeLong, bootstrap
│   ├── explicacion.py        # SHAP y estabilidad
│   └── equidad.py
├── configs/                  # configuraciones de experimentos (JSON) y plan de evaluación en prueba
├── experimento.py            # CLI: ejecuta una configuración y exporta
└── tests/                    # pytest
api/                          # Flask (semana 2)
web/                          # Angular (semana 3)
data/procesado/               # cortes generados (no versionado: añadir a .gitignore al crearlo)
```

## Convenciones Python (las de `ml/exploracion_oulad.py`)

- Identificadores, mensajes y docstrings en **español**; nombres de columnas de OULAD tal cual.
- `from __future__ import annotations`, anotaciones de tipo, `pathlib.Path`, rutas relativas a `RAIZ`.
- Constantes en mayúsculas al inicio; funciones pequeñas y puras; `main()` con `argparse` y `--salida` para ensayos.
- Comprobaciones de integridad con `raise ValueError` o `sys.exit` con mensaje claro, no `assert`.
- Figuras con `matplotlib.use("Agg")` y `DPI = 300`.
- Dependencias en `requirements.txt` con versión mínima; se añade una biblioteca cuando el código la use.
- Pruebas con `pytest` en `ml/tests/`, con datos sintéticos pequeños (nunca los CSV reales en pruebas unitarias).

## API REST (propuesta, se concreta en la semana 2)

| Método y ruta | Paso del flujo (OE5) |
|---|---|
| `POST /api/conjuntos` (CSV) · `GET /api/conjuntos/{id}` | Carga de datos y vista previa de columnas |
| `POST /api/entrenamientos` (conjunto, columna objetivo, columnas ignoradas, presupuesto) | Configuración |
| `GET /api/entrenamientos/{id}` (estado, progreso) | Entrenamiento (tarea en segundo plano) |
| `GET /api/modelos/{id}/evaluacion` | Evaluación: métricas, punto de operación, calibración |
| `POST /api/modelos/{id}/predicciones` (CSV) | Predicción |
| `GET /api/predicciones/{id}` | Probabilidad calibrada + explicación SHAP local |
| `GET /api/modelos/{id}/explicacion-global` | Explicación global |

Errores en JSON `{"error": "<mensaje en español>"}`. El entrenamiento corre en segundo plano (hilo o proceso; sin Celery
salvo que haga falta) y su estado se guarda en la base de datos.

## Modelo de datos PostgreSQL (propuesta)

`conjunto_datos` (archivo, columnas, filas, fecha) → `entrenamiento` (conjunto, configuración JSON, estado, semilla,
tiempos) → `modelo` (entrenamiento, familia, hiperparámetros, métricas JSON, umbral, ruta del artefacto `joblib`) →
`prediccion` (modelo, fila, probabilidad, alerta) → `explicacion` (predicción, contribuciones SHAP JSON).
Los artefactos binarios van a disco; la base de datos guarda la ruta.

## Interfaz Angular

Flujo guiado de seis pasos: carga → configuración → entrenamiento → evaluación → predicción → explicación.
Todo texto visible sigue la skill `guardarrailes-interfaz`. Accesibilidad WCAG 2.1 AA desde el principio
(etiquetas, contraste, foco visible, sin información solo por color); la auditoría formal es de la Entrega 3.
