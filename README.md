# Plataforma AutoML explicable para la detección temprana del riesgo de deserción estudiantil

Código del Trabajo Fin de Máster. La plataforma entrena modelos con AutoML sobre un CSV tabular, compara el mejor con
una regresión logística optimizada, calibra las probabilidades, fija un umbral de alerta y explica cada estimación con
SHAP. Es una herramienta de apoyo: la decisión corresponde siempre al personal académico.

| Carpeta | Contenido |
|---|---|
| `ml/` | Núcleo de ML (`ml/automl/`) y scripts del flujo con OULAD (cortes, experimentos, variantes, SHAP, modelo final) |
| `api/` | API REST en Flask con PostgreSQL, trabajador en segundo plano e importador de modelos |
| `web/` | Interfaz en Angular 21 |
| `scripts/` | Evidencias que cruzan `api/` y `ml/` (diagramas, capturas, informes de pruebas) |
| `evidencias/` | Resultados que cita la memoria, según [`evidencias/CONTRATO.md`](evidencias/CONTRATO.md) |
| `docs/` | Diseño de la API (`diseno-api.md`) y de la interfaz (`diseno-web.md`) |

La versión entregada está etiquetada (`v1.0-entrega2`, `v1.0.1-entrega2`).

## Requisitos

- Python 3.13 (probado con 3.13.3). Versiones exactas de las bibliotecas en `requirements.txt`.
- Node.js 20.19 o posterior y npm 10 (probado con Node 20.19.1). Versiones exactas en `web/package-lock.json`.
- Docker con Docker Compose, para PostgreSQL 16.15.
- Los datos de OULAD (Open University Learning Analytics Dataset; Kuzilek et al., 2017,
  [doi:10.1038/sdata.2017.171](https://doi.org/10.1038/sdata.2017.171)), licencia CC BY 4.0: los 7 CSV
  (`assessments`, `courses`, `studentAssessment`, `studentInfo`, `studentRegistration`, `studentVle`, `vle`) en
  `data/raw/oulad/`. No se incluyen en el repositorio.

## Instalación

Desde la raíz del repositorio (en Windows, `.venv\Scripts\activate` en lugar de `source`):

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cd web && npm ci && cd ..
```

## Configuración y base de datos

1. Copie `.env.example` a `.env` y cambie la contraseña en `POSTGRES_PASSWORD`, `DATABASE_URL` y
   `DATABASE_URL_PRUEBAS`. `.env` no se versiona.
2. Arranque PostgreSQL (solo escucha en `127.0.0.1`; la primera vez crea también la base `plataforma_pruebas`):
   ```bash
   docker compose up -d
   ```
3. Cree las tablas con las migraciones:
   ```bash
   alembic -c api/alembic.ini upgrade head
   ```

## Flujo de ML con OULAD (fuera de la aplicación)

Se ejecuta desde la raíz, en este orden. Los scripts que escriben en `evidencias/` solo lo hacen con el árbol de git
limpio: confirme un commit entre uno y otro, o ensaye fuera de `evidencias/` con `--salida <carpeta>`
(`referencia_oulad.py` escribe en `data/procesado/`). Ningún script modela ni evalúa en la cohorte de prueba 2014J:
`cortes_oulad.py` la separa y solo exporta recuentos descriptivos, y los demás la filtran al leer.

```bash
python ml/cortes_oulad.py                                   # conjuntos por momento (semanas 0, 4, 8 y 12)
python ml/experimento.py ml/configs/principal.json          # AutoML principal, validación cruzada (varias horas)
python ml/variante.py ml/configs/con_sensibles.json         # variante con variables sensibles
python ml/ablacion.py ml/configs/ablacion.json              # ablación por grupos de variables
python ml/sensibilidad_fuga.py ml/configs/sin_exclusion_retirados.json
python ml/shap_estabilidad.py ml/configs/shap.json          # SHAP y su estabilidad entre pliegues
python ml/modelo_final.py ml/configs/modelo_final.json      # paquetes desplegados en data/procesado/modelos/
python ml/referencia_oulad.py --demo 2014B --entrenamiento  # filas de referencia y CSV de demostración
```

Las variantes y el modelo final reutilizan los hiperparámetros del experimento principal indicado en su configuración
(`hiperparametros_de`), sin nueva búsqueda. Los CSV de `data/procesado/demo/` son filas de entrenamiento: sirven para
mostrar la plataforma, no para medir su rendimiento.

## Importar los modelos desplegados

```bash
flask --app api importar-paquetes
```

Carga solo los paquetes de `data/procesado/modelos/` marcados como desplegados y con el SHA-256 registrado en su
experimento de `evidencias/experimentos/`. Es idempotente.

## Arranque

En tres terminales, desde la raíz (la tercera, desde `web/`):

```bash
flask --app api run --host 127.0.0.1 --port 5000   # API
flask --app api trabajador                          # entrenamientos en segundo plano (uno a la vez)
npm start                                           # interfaz en http://localhost:4200 (reenvía /api a la API)
```

La plataforma no tiene autenticación: está pensada para uso local en `127.0.0.1`.

## Pruebas

```bash
python -m pytest ml/tests scripts/tests     # núcleo de ML y scripts de evidencias
python -m pytest api/tests                  # API: unitarias en SQLite y las marcadas «postgres» contra el contenedor
cd web && npx ng test --watch=false         # interfaz (Vitest)
```

Las pruebas de la API marcadas `postgres` necesitan el contenedor levantado y `DATABASE_URL_PRUEBAS` en `.env`.
Los informes que cita la memoria se exportan con `python -m api.exportar_pruebas` y
`python -m scripts.exportar_pruebas_web`, desde un árbol limpio.

## Licencia

El código de este repositorio se distribuye bajo la licencia MIT (ver [`LICENSE`](LICENSE)). Los datos de OULAD no se
incluyen en el repositorio y conservan su propia licencia, CC BY 4.0 (Kuzilek et al., 2017).
