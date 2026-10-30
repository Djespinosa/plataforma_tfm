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
│   ├── validacion.py         # cohorte de prueba y pliegues genéricos (flujo web)
│   ├── motor.py              # parte genérica del experimento y modelo final (extraída de experimento.py)
│   ├── explicacion.py        # paquete genérico, predicción y SHAP por familia
│   └── equidad.py
├── configs/                  # configuraciones de experimentos (JSON) y plan de evaluación en prueba
├── experimento.py            # CLI: ejecuta una configuración y exporta
└── tests/                    # pytest
api/                          # Flask: factoría, rutas/, servicios/, textos.py, trabajador.py, importar.py, migraciones/ (docs/diseno-api.md §2)
docs/                         # documentos de diseño (diseno-api.md)
web/                          # Angular (semana 3)
data/procesado/               # cortes generados (no versionado: añadir a .gitignore al crearlo)
```

## Convenciones Python (las de `ml/exploracion_oulad.py`)

- Identificadores, mensajes y docstrings en **español**; nombres de columnas de OULAD tal cual.
- `from __future__ import annotations`, anotaciones de tipo, `pathlib.Path`, rutas relativas a `RAIZ`.
- Constantes en mayúsculas al inicio; funciones pequeñas y puras; `main()` con `argparse` y `--salida` para ensayos.
- Comprobaciones de integridad con `raise ValueError` o `sys.exit` con mensaje claro, no `assert`.
- Figuras con `matplotlib.use("Agg")` y `DPI = 300`.
- Dependencias en `requirements.txt` con versión exacta (`==`); se añade una biblioteca cuando el código la use.
- Pruebas con `pytest` en `ml/tests/`, con datos sintéticos pequeños (nunca los CSV reales en pruebas unitarias).

## API REST (diseño del bloque E, 2026-10-30; detalle en `docs/diseno-api.md`)

| Método y ruta | Requisito (prioridad) |
|---|---|
| `GET /api/estado` (motor de BD, trabajador activo, commit) | operación |
| `POST /api/conjuntos` (CSV) · `GET /api/conjuntos` · `GET /api/conjuntos/{id}` | RF-01 (M) |
| `POST /api/experimentos/validacion` (sin crear: esquema efectivo y avisos) · `POST /api/experimentos` → 202 | RF-02, RF-03 (M) |
| `GET /api/experimentos/{id}` (estado, etapa, progreso, latido, reproducibilidad) | RF-03 (M), RNF-03, RNF-06 |
| `GET /api/experimentos` · `POST /api/experimentos/{id}/reintentar` | RF-08 (S) |
| `GET /api/experimentos/{id}/evaluacion` (OOF, referencias, contraste con la RL optimizada, desplegado y motivo, punto de operación, calibración, equidad) | RF-04 (M) |
| `GET /api/modelos` · `GET /api/modelos/{id}` · `POST /api/modelos/{id}/predicciones` (CSV) · `GET /api/predicciones/{lote}` | RF-05 (M) |
| `GET /api/modelos/{id}/explicacion-global` · `GET /api/predicciones/{lote}/filas/{fila}/explicacion` | RF-06 (M) |
| `GET /api/predicciones/{lote}/exportar` (CSV) · `GET /api/experimentos/{id}/evaluacion/exportar` (JSON) | RF-09 (C) |
| `POST /api/experimentos/{id}/evaluacion-prueba` (una sola vez, cohorte reservada) | pendiente de decisión del estudiante |

Errores en JSON `{"error": "<mensaje en español>"}` (400, 404, 409, 413, 415, 422, 500, 503). Todos los textos visibles
salen de `api/textos.py` y cumplen `guardarrailes-interfaz`. RF-07 no tiene ruta propia. Ninguna ruta calcula métricas con
filas de predicción. Entrenamiento en segundo plano: la tabla `experimento` es la cola y un proceso aparte
(`flask --app api trabajador`) la consume de uno en uno.

## Modelo de datos PostgreSQL (diseño del bloque E)

`conjunto_datos` (archivo, momento, SHA-256, resumen de columnas) → `experimento` (id texto `web-AAAA-MM-DD-NN` o id
importado, origen, configuración efectiva JSON, estado, etapa, progreso, latido, tiempos, reproducibilidad JSON) →
`modelo` (solo desplegados: momento, familia, ruta y SHA-256 del paquete, umbral, columnas, explicador, evaluación JSON,
explicación global JSON) → `lote_prediccion` (archivo, SHA-256, umbral, alertas) → `prediccion` (fila, identificador,
probabilidad calibrada, alerta, log-odds) → `explicacion` (contribuciones SHAP JSON por variable original).
Los artefactos binarios (CSV subidos, `paquete.joblib`, `oof.parquet`) van a `data/plataforma/` (no versionada); la base
de datos guarda la ruta y el SHA-256. JSON = JSONB en PostgreSQL. Migraciones con Alembic.

## Decisiones técnicas (bloque E, 2026-10-30)

| Decisión | Alternativa descartada | Motivo |
|---|---|---|
| Segundo plano: la tabla `experimento` como cola + proceso `flask trabajador` (uno, con `pg_try_advisory_lock`, latido cada 30 s, huérfanos → `interrumpido` al arrancar, sin reanudar) | Hilo dentro de Flask; Celery/RQ + Redis | Un entrenamiento de horas no comparte proceso con las consultas (RNF-03) ni muere al reiniciar el servidor; sin dependencias nuevas |
| Progreso por etapa (familia, referencias, apilamiento, comparación, modelo final, explicación global, equidad) | *Callbacks* por ensayo de Optuna | `busqueda.buscar` se reutiliza sin cambios |
| Predicción síncrona; SHAP de todas las filas al predecir con explicador lineal o de árbol; con permutación (rf, mlp, apilamiento), por fila bajo demanda y guardada | Predicción como trabajo en la cola | La cola puede estar ocupada horas; la permutación cuesta ≈ 1-6 s/100 filas |
| Explicador por familia: RL lineal exacto; gb, xgb, lgbm, catboost TreeSHAP (log-odds); rf, mlp, apilamiento permutación sobre logit de la probabilidad sin calibrar | TreeSHAP en RF | En RF TreeSHAP da probabilidad, no log-odds (D32) |
| Extremos marcados con \|φ\| > 5 log-odds (`explicacion.LIMITE_EXTREMO`, el de exp-2026-10-29-05), sin recortar; variables sin valores en el entrenamiento como «sin contribución» | Recortar a ±5; mostrarlas con φ = 0 | Auditorías O1 (29-02), O3 y O4 (29-03) |
| `ml/automl/validacion.py`: k = 5 fijo; sin grupo `StratifiedKFold`, con grupo `StratifiedGroupKFold`, ambos con semilla; error si hay < 5 grupos | Cambiar de esquema en silencio; k configurable | Decisión 2 del estudiante; `particion.PLIEGUES` = {1..5} |
| `ml/automl/motor.py` y `explicacion.py` extraídos de `experimento.py`, `modelo_final.py` y `shap_estabilidad.py` (movimientos con reexportación) | Duplicar el código en `api/` | Regla 7; no regresión con un `--ensayo` antes y después |
| Modelo OULAD importado con `flask importar-paquetes`: carga solo `origen["desplegado"] is True`, verifica SHA-256, evaluación del JSON origen | Cargar por patrón de nombre; código OULAD en `api/` | Auditoría O2; D10 |
| `ml/` en `sys.path` desde `api/__init__.py` | Convertir `ml/` en paquete | Los paquetes `joblib` serializan clases como `automl.*` |
| SQLAlchemy 2.1.6 sin Flask-SQLAlchemy; psycopg[binary] 3.3.6; Alembic 1.20.1 | Flask-SQLAlchemy; `create_all` en PostgreSQL | Una capa menos; la BD guarda experimentos de horas que una migración no debe perder (SQLite de pruebas usa `create_all`) |
| PostgreSQL `postgres:16.15` en Docker Compose, puerto del host `PG_PUERTO` (5433), solo `127.0.0.1`; `.env` no versionado + `.env.example`; python-dotenv 1.2.4 | `latest`; puerto 5432 | Decisión 3 del estudiante; hay un PostgreSQL 12 local en 5432 |
| Sin flask-cors (proxy de Angular en desarrollo) ni waitress | Dependencias para CORS y servidor WSGI | Uso local, mismo origen |
| Pruebas: SQLite en memoria para unitarias; funcionales RF-01..RF-09 contra el PostgreSQL del contenedor (`-m postgres`), con requisito y motor en el JUnit; pytest-cov 7.1.0 | Todo contra SQLite | Decisión 3 del estudiante; punto 34 del bloque E |

## Interfaz Angular

Flujo guiado de seis pasos: carga → configuración → entrenamiento → evaluación → predicción → explicación.
Todo texto visible sigue la skill `guardarrailes-interfaz`. Accesibilidad WCAG 2.1 AA desde el principio
(etiquetas, contraste, foco visible, sin información solo por color); la auditoría formal es de la Entrega 3.
