# Diseño de la API Flask + PostgreSQL (bloque E, Entrega 2)

Estado: aprobado por el estudiante el 2026-10-30 (D-1 a D-8 del §12) con los matices de abajo, que **prevalecen** sobre
el resto del documento.
Destinatario: agente `backend` (y `tester` para el §10). Resumen de decisiones técnicas: skill `arquitectura`.

## 0. Matices del estudiante (2026-10-30)

- **D-2:** la evaluación única en la cohorte de prueba se impone en la base de datos (restricción, no solo comprobación
  en código) y no admite repetición.
- **D-3:** la prueba comprueba solo la **identidad exacta** entre la explicación global que da la API para
  exp-2026-10-29-03 y la media de |SHAP| calculada directamente con `ml/` sobre las mismas filas. La comparación con
  exp-2026-10-29-02/05 no lleva umbral: se exporta como evidencia descriptiva (experimento con id y commit) con, por
  semana, el Spearman del orden completo, el solapamiento del top-10 y las variables que cambian de posición en el
  top-10, indicando que compara el modelo final (filas de entrenamiento) con la media OOF de 5 modelos de pliegue.
- **D-4:** las predicciones del CSV de demostración son dentro de la muestra y se etiquetan en la API y en la interfaz
  como demostración del flujo, no como rendimiento.
- **D-6:** los valores por defecto siguen siendo 50 ensayos por familia y 2000 réplicas *bootstrap*. El modo demo es
  explícito, queda en la configuración del experimento y se ve en la interfaz.
- **(a)** La comprobación de no regresión del incremento 2 (ensayo antes y después de la extracción) se exporta como
  evidencia en `evidencias/`.
- **(b)** La selección de la cohorte de prueba es parte de RF-02 (Must) y se implementa en el incremento 6; al
  incremento 9 solo va la evaluación única.
- **(c)** Congelación de la plataforma el **06/11/2026**. Si hay retraso, se recorta en este orden: RF-09, RF-08, RF-07.
  Las capturas del flujo con exp-2026-10-29-03 tienen prioridad sobre el entrenamiento web completo.

Nota sobre D-3: la explicación global de 29-03 sale del modelo final (entrenado con las 15 presentaciones) sobre sus
filas de entrenamiento; 29-02/05 promedian SHAP *out-of-fold* de 5 modelos de pliegue. No son el mismo estimador y el
orden completo no coincide (comprobado el 2026-10-30: Spearman 0,943-0,975 y solapamiento del top-10 de 0,9-1,0 con
29-02 en las 4 semanas). Por eso no se exige el mismo orden (decisión del estudiante, 2026-10-30).

Fuentes: `CLAUDE.md`; skills `arquitectura`, `guardarrailes-interfaz`, `rigor-ml` (§2-§6) y `contrato-evidencias`;
`../memoria/capitulos/04-requisitos.md` (RF, RNF, RM, RE); bloque E de `../memoria/revisiones/prompt-plataforma-evidencias-e2.md`
(puntos 29-36); código de `ml/` en el commit 82a6f9e; `exp-2026-10-27-01.json` y `exp-2026-10-29-03.json`; auditorías
de exp-2026-10-29-02 (O1) y exp-2026-10-29-03 (O2-O4).

## 1. Alcance y requisitos cubiertos

| Requisito | Prioridad | Dónde |
|---|---|---|
| RF-01 carga y validación de la tabla | M | §4.1 |
| RF-02 configuración: objetivo, clase positiva, grupo, cohorte de prueba, excluidas, sensibles | M | §4.2, §6.1 |
| RF-03 entrenamiento con configuración predefinida y seguimiento | M | §4.2, §5 |
| RF-04 evaluación (OOF, referencias, RL optimizada con DeLong e IC, desplegado y motivo, punto de operación, calibración) | M | §4.3 |
| RF-05 predicción con probabilidad calibrada y alerta, lista ordenable y filtrable | M | §4.4 |
| RF-06 explicación global y local con avisos RE-02 y RE-03 | M | §4.5 |
| RF-07 vista resumida y detallada | S | sin ruta propia: la cubren §4.3-§4.5 (lo resuelve `web/`) |
| RF-08 historial y reapertura | S | §4.2 (`GET /api/experimentos`) |
| RF-09 exportación en formato abierto | C | §4.6 (último incremento) |
| RNF-01 privacidad | M | identificadores nunca son predictores; avisos fijos; nada sale a servicios externos |
| RNF-02 autenticación | S | decisión del estudiante (§12, D-1) |
| RNF-03 un entrenamiento no bloquea las consultas; duración | S | §5 |
| RNF-06 id, semillas, versiones, commit y SHA-256 | M | §3 (`experimento.reproducibilidad`) |
| RNF-07 navegador, sin instalar nada el usuario | M | API HTTP/JSON; la instalación es del operador |
| RNF-08 cualquier tabla con la estructura de RF-01 | S | D10: nada de OULAD en `api/` |
| RE-01/RE-02/RE-03 | M | §4.5, §7 |

Dos flujos (decisión 1 del estudiante):

- **Genérico (D10):** subir CSV → configurar → entrenar en segundo plano → evaluar → predecir → explicar. Presupuesto por
  defecto = el del experimento (`completo`: 7 familias × 50 ensayos, apilamiento, 2000 réplicas *bootstrap*; RM-01).
- **Modelo OULAD exp-2026-10-29-03:** se importa con el mecanismo genérico de paquetes desplegados (§8). Aparece en el
  historial; su evaluación muestra los resultados OOF de su experimento origen (exp-2026-10-27-01).

Invariantes que el `backend` no puede romper:

1. Ninguna ruta calcula métricas con filas de predicción: `POST /predicciones` ignora la columna objetivo si viene.
   La única ruta que calcula métricas fuera de la validación cruzada es la de la cohorte de prueba reservada (§4.7, si el
   estudiante la aprueba), que no existe para modelos importados.
2. Solo se cargan paquetes con `origen["desplegado"] is True` (identidad, no veracidad), nunca por nombre de archivo.
3. `api/` no reimplementa nada de `ml/`: toda la lógica de modelado, umbral, calibración, comparación y SHAP está en
   `ml/automl/` (§6). `api/` hace E/S, validación de la petición, persistencia y textos.
4. `joblib.load` solo sobre rutas registradas por el trabajador o el importador; nunca sobre un archivo subido.

## 2. Estructura de archivos nuevos

```
docker-compose.yml               # PostgreSQL 16.15 (imagen fijada); puerto del host ${PG_PUERTO:-5433}
docker/initdb/01_pruebas.sql     # CREATE DATABASE plataforma_pruebas (BD de las pruebas funcionales)
.env.example                     # Variables del §9 con valores de ejemplo (el .env real no se versiona)
api/
├── __init__.py                  # crear_app(configuracion=None): factoría; añade ml/ a sys.path; registra rutas, errores y comandos
├── configuracion.py             # Desarrollo (desde el entorno) y Pruebas (SQLite en memoria o DATABASE_URL_PRUEBAS)
├── bd.py                        # engine, sessionmaker, sesión por petición (teardown) y Base declarativa (SQLAlchemy 2)
├── tablas.py                    # las 6 tablas del §3
├── textos.py                    # TODOS los textos visibles (avisos, lecturas, errores fijos) y coma decimal
├── errores.py                   # ErrorPlataforma(codigo, mensaje) y manejadores → {"error": "..."}
├── rutas/
│   ├── estado.py                # GET /api/estado
│   ├── conjuntos.py             # §4.1
│   ├── experimentos.py          # §4.2, §4.3, §4.7
│   ├── modelos.py               # GET /api/modelos…, explicación global
│   └── predicciones.py          # §4.4, §4.5 local, §4.6
├── servicios/
│   ├── tablas_csv.py            # leer CSV (UTF-8, «,» o «;»), resumen de columnas, coerción de tipos para predecir
│   ├── configuracion_exp.py     # petición → configuración efectiva (llama a automl.validacion); usado por /validacion y POST
│   ├── entrenamiento.py         # ejecutar(id): datos → motor.modelar → modelo final → paquete → evaluación → BD
│   ├── paquetes.py              # cargar_paquete(modelo) con SHA-256 y desplegado is True; caché en memoria (8)
│   ├── evaluacion.py            # resumen de ml (web o importado) → JSON de la ruta §4.3, con textos
│   └── explicaciones.py         # top-5 por signo, extremos (|φ| > 5), «sin contribución», avisos
├── trabajador.py                # comando `flask trabajador`: bucle, latido, bloqueo consultivo (§5)
├── importar.py                  # comando `flask importar-paquetes` (§8)
├── alembic.ini
├── migraciones/                 # env.py + versions/0001_inicial.py (las 6 tablas)
└── tests/
    ├── conftest.py              # app de pruebas; marcador `postgres`; tabla sintética; paquetes sintéticos
    ├── test_textos.py           # vocabulario prohibido de guardarrailes-interfaz en textos.py y en respuestas
    ├── test_conjuntos.py  test_configuracion.py  test_paquetes.py  test_importar.py
    ├── test_predicciones.py  test_explicaciones.py  test_trabajador.py
    └── funcionales/             # test_rf01…test_rf09 contra PostgreSQL (§10)
ml/
├── automl/validacion.py         # NUEVO: cohorte de prueba y pliegues estratificados/agrupados genéricos (§6.1)
├── automl/motor.py              # NUEVO: parte genérica de experimento.momento + modelo final + curva (§6.2)
├── automl/explicacion.py        # NUEVO: paquete genérico, predicción y SHAP por familia (§6.3)
├── referencia_oulad.py          # NUEVO, script OULAD: filas de entrenamiento por momento para la explicación global (§8)
└── tests/test_validacion.py  test_motor.py  test_explicacion.py
data/plataforma/                 # NO versionada (.gitignore): conjuntos/, experimentos/<id>/, predicciones/
```

`api/` se ejecuta desde la raíz del repositorio: `flask --app api run --port 5000` y `flask --app api trabajador`
(`api/__init__.py` expone `create_app = crear_app`, el nombre de factoría que busca Flask). Migraciones:
`alembic -c api/alembic.ini upgrade head` (URL desde `DATABASE_URL`).
`api/__init__.py` inserta `RAIZ / "ml"` en `sys.path` **antes** de cualquier `joblib.load`: los paquetes serializan las
clases como `automl.busqueda.MLPPonderado`, `automl.preprocesado.DescartarVacias`, etc. (módulo de primer nivel `automl`).

## 3. Modelo de datos

PostgreSQL 16; JSON como `JSON().with_variant(JSONB, "postgresql")`; fechas `timestamptz` en UTC.

| Tabla | Columnas (clave primaria en negrita) | Notas |
|---|---|---|
| `conjunto_datos` | **id** serial · nombre_archivo · momento (texto libre, opcional: «semana 4») · ruta · sha256 · n_filas · n_columnas · columnas JSON (`[{nombre, tipo, faltantes, proporcion_faltantes, valores_distintos, valores_frecuentes[≤20]}]`) · avisos JSON · creado_en | El CSV se guarda tal cual en `data/plataforma/conjuntos/<sha256>.csv` (`ruta` relativa a `PLATAFORMA_DATOS`; por hash y no por id porque `ruta` no cambia tras el INSERT, y el mismo contenido comparte archivo) |
| `experimento` | **id** texto (`web-AAAA-MM-DD-NN` o el id del experimento importado) · origen (`web`/`importado`) · conjunto_id FK nulo · sha256_datos nulo (copia de `conjunto_datos.sha256` al crearlo) · cohorte_prueba_clave nulo (SHA-256 de la definición canónica de la cohorte de prueba, `tablas.clave_cohorte`; nulo sin cohorte) · descripcion · configuracion JSON (§6.4) · estado (`en_cola`, `en_curso`, `completado`, `fallido`, `interrumpido`) · etapa texto · progreso JSON `{completadas, total}` · error texto · latido_en · creado_en · iniciado_en · terminado_en · duracion_s · reproducibilidad JSON · procedencia JSON (importados) · evaluacion_prueba JSON nulo (§4.7) · reintento_de FK nulo | `UNIQUE(id)`; el id nunca se reutiliza ni cambia (disparador) |
| `modelo` | **id** serial · experimento_id FK · momento texto nulo · familia · ruta_paquete · sha256_paquete · umbral (float exacto) · metodo_calibracion nulo · columnas JSON · explicador (`lineal`/`arbol`/`permutacion`) · evaluacion JSON (§4.3) · explicacion_global JSON nulo · creado_en | Solo modelos desplegados; los candidatos viven en `evaluacion` |
| `lote_prediccion` | **id** serial · modelo_id FK · nombre_archivo · ruta · sha256 · n_filas · columna_id nulo · columnas_ignoradas JSON · umbral · n_alertas · creado_en | |
| `prediccion` | **(lote_id, fila)** · identificador texto nulo · probabilidad · alerta bool · log_odds · base_log_odds · valores JSON (valores de las columnas del modelo) | `fila` = posición 1..n en el CSV |
| `explicacion` | **(lote_id, fila)** FK → prediccion · contribuciones JSON `{variable: φ}` · explicador · error_aditividad · creado_en | Lineal y árbol: se crea al predecir; permutación: al pedirla (§4.5) |

Evaluación única en la cohorte de prueba (matiz D-2), impuesta en la base de datos desde `0001_inicial`:

- `CHECK (evaluacion_prueba IS NULL OR (origen = 'web' AND estado = 'completado' AND conjunto_id IS NOT NULL AND
  sha256_datos IS NOT NULL AND cohorte_prueba_clave IS NOT NULL))`.
- `CHECK` de formato en `conjunto_datos.sha256` y `experimento.sha256_datos`: 64 caracteres hexadecimales en minúsculas
  (`length(x) = 64 AND trim(x, '0123456789abcdef') = ''`, la misma expresión en PostgreSQL y SQLite).
- Índice único parcial `uq_experimento_evaluacion_prueba` sobre `(sha256_datos, cohorte_prueba_clave)
  WHERE evaluacion_prueba IS NOT NULL`: una sola evaluación por datos y definición de cohorte, no por experimento
  (decisión del estudiante, 2026-10-30). Volver a subir el mismo CSV (otro `conjunto_datos`, mismo SHA-256) y entrenar
  otro experimento con la misma cohorte no permite una segunda evaluación. Como un índice no cruza tablas, el SHA-256 se
  copia en `experimento` al crearlo.
- `clave_cohorte` es canónica (decisión del estudiante, 2026-10-30): en modo «valores», columna y conjunto de valores
  como texto, sin repetidos y ordenados (`sorted(set(map(str, valores)))`), sin semilla; en modo «aleatoria», solo el
  modo (ni semilla ni nada más): una sola evaluación con cohorte aleatoria por datos, porque otra semilla da una cohorte
  que comparte filas con la ya evaluada. «semilla», «filas» y «metodo» no forman parte de la clave.
- Disparador `evaluacion_prueba_unica` (`BEFORE INSERT OR UPDATE OR DELETE` en `experimento`): rechaza siempre cambiar
  `id` (si no, renombrar el experimento saltaría lo demás); si ya hay `evaluacion_prueba`, cambiarla o anularla, borrar
  el experimento y cambiar `configuracion` (contiene la definición de la cohorte), `conjunto_id`, `sha256_datos` o
  `cohorte_prueba_clave`; y, al evaluar (o crear el experimento ya evaluado), que `sha256_datos` no sea el
  `conjunto_datos.sha256` de su `conjunto_id`.
- Disparador `modelo_evaluado_congelado` (`BEFORE INSERT OR UPDATE OR DELETE` en `modelo`): rechaza cambiar o borrar
  los modelos de un experimento con `evaluacion_prueba` (`OLD.experimento_id`) y añadirle uno o traérselo de otro
  experimento (`NEW.experimento_id`).
- Disparador `conjunto_datos_inmutable` (`BEFORE UPDATE` en `conjunto_datos`): la `ruta` y el `sha256` de un conjunto
  no cambian nunca (si no, se podría alterar el hash del conjunto para que coincidiera con otro `sha256_datos`).
- Los disparadores responden con `check_violation`. `TRUNCATE` no los dispara (solo lo usan las pruebas en
  `plataforma_pruebas`). `api/tablas.py` crea el equivalente en SQLite para las pruebas unitarias. Las columnas JSON
  guardan `None` como `NULL` de SQL (`none_as_null=True`), para que la comprobación sea fiable.

Limitaciones (se declaran en la memoria): un archivo modificado (otro SHA-256) u otra definición de cohorte, aunque se
solape con la anterior, sí permiten otra evaluación; en particular, los solapamientos parciales entre conjuntos de
valores distintos (p. ej. `["2014J"]` y `["2014J", "2014B"]`, o una cohorte por valores y otra aleatoria sobre los mismos
datos) no se impiden y permitirían otra evaluación que comparte filas con la primera; y D-2 protege frente a errores de la aplicación, no frente a un
administrador de la base de datos (un superusuario puede desactivar los disparadores o borrar el índice).

`experimento.reproducibilidad` (RNF-06): `{id, commit, arbol_limpio, semillas, versiones (versiones_entorno de
ml/evidencias.py: python, pandas, numpy, scikit-learn, xgboost, lightgbm, catboost, optuna, shap, joblib, flask,
sqlalchemy, psycopg), sha256_datos, sha256_oof, hardware, optuna: busqueda.DESCRIPCION_OPTUNA, n_jobs:
{valor, nivel: busqueda.NIVEL_N_JOBS}}`. `commit` y `arbol_limpio` con `evidencias.git`; un árbol sucio **no** aborta
(no es una exportación a `evidencias/`), pero queda registrado y la vista lo muestra.

En disco (`PLATAFORMA_DATOS`, por defecto `data/plataforma/`): `conjuntos/<sha256>.csv`; `experimentos/<id>/paquete.joblib`,
`oof.parquet` (predicciones *out-of-fold* `p_<modelo>` y `etiqueta`, para reproducir la evaluación), `prueba.parquet`
(índices de la cohorte reservada) y `error.log`; `predicciones/<lote>.csv`. Los paquetes importados se quedan en su ruta
(`data/procesado/modelos/`) y la BD guarda ruta y SHA-256.

## 4. Contrato de rutas

Convenciones: prefijo `/api`; JSON UTF-8; error = `{"error": "<mensaje en español>"}` y, si hay varios,
`{"error": "...", "detalles": ["..."]}`. Probabilidades en [0, 1] como números (la interfaz las muestra en % entero); los
textos que genera la API usan coma decimal. Códigos comunes: 400 cuerpo mal formado («La petición no es JSON válido.»,
«Falta el campo «x».»), 404 («No existe el <recurso> <id>.»; ruta desconocida: «No existe la ruta solicitada.»), 405
(«Esta ruta no admite el método solicitado.»), 409 conflicto de estado, 413 («El archivo supera el tamaño
máximo de 50 MB.»), 415, 422 validación, 500 («Error interno de la plataforma. Inténtelo de nuevo; si persiste, consulte
el registro del servidor.»), 503 («La base de datos no está disponible.»).
Toda respuesta de resultados (evaluación, predicciones, explicaciones) incluye `aviso_decision` = pie fijo de
`guardarrailes-interfaz` («Herramienta de apoyo a la decisión…»).

`GET /api/estado` → 200 `{motor_bd: "postgresql 16.15" | "sqlite", trabajador_activo: bool | null, commit}`.
`trabajador_activo` consulta `pg_locks` por el bloqueo consultivo del §5 (null en SQLite).

### 4.1 Conjuntos de datos (RF-01, M)

`POST /api/conjuntos` — multipart: `archivo` (CSV), `momento` (opcional). → **201**
`{id, nombre_archivo, momento, sha256, n_filas, n_columnas, columnas: [...], avisos: [...], aviso_privacidad}`.

- Lectura: UTF-8 (con o sin BOM), separador «,» o «;» detectado en los primeros 64 KB (`csv.Sniffer` restringido a esos
  dos), decimal «.», vacíos estándar de pandas. Tipo: numérica si pandas la lee como número; categórica en otro caso
  (texto y booleanos, como `str`).
- `avisos`: columna categórica con > 50 % de valores distintos («La columna «x» parece un identificador; excluirla de las
  variables protege la privacidad y evita que el modelo memorice filas.»); columna sin ningún valor; columna constante.
- `aviso_privacidad` = mensaje fijo de carga de `guardarrailes-interfaz`.
- Errores: 400 «No se ha recibido ningún archivo.»; 415 «El archivo debe ser un CSV en UTF-8 separado por comas o por punto
  y coma.»; 413; 422 «El archivo no tiene filas de datos.», «Hay columnas con el mismo nombre: a, b.», «Se necesitan al
  menos 2 columnas.».

`GET /api/conjuntos` → 200 lista resumida. `GET /api/conjuntos/{id}` → 200 el resumen anterior; 404.

La comprobación «presencia de ambas clases» de RF-01 se hace al elegir el objetivo (§4.2, `/validacion`).

### 4.2 Experimentos: configuración, lanzamiento, estado e historial (RF-02, RF-03 M; RF-08 S)

Cuerpo de configuración (solo `conjunto_id`, `objetivo` y `clase_positiva` son obligatorios; RF-03):

```json
{"conjunto_id": 3, "objetivo": "final_result", "clase_positiva": "Withdrawn",
 "excluidas": ["id_student"], "sensibles": ["gender", "disability"], "columna_grupo": "presentacion",
 "cohorte_prueba": {"modo": "valores", "columna": "code_presentation", "valores": ["2014J"]},
 "presupuesto": "completo", "descripcion": "texto libre"}
```

- `cohorte_prueba`: `null` (por defecto), `{"modo": "valores", "columna", "valores"}` o `{"modo": "aleatoria"}`
  (20 % estratificado, semilla de modelos; solo sin columna de grupo).
- `presupuesto`: `completo` (por defecto) o `demostracion` (5 ensayos por familia, 200 réplicas). `prueba` (1 ensayo, 20
  réplicas) solo se acepta con la configuración `Pruebas`; en otro caso, 422.
- Clase positiva: `y = (objetivo.astype(str) == str(clase_positiva))`; el resto de valores es negativo (como D2). Las filas
  sin objetivo se descartan y se cuentan.

`POST /api/experimentos/validacion` — mismo cuerpo, no crea nada. → **200**
`{filas_entrenamiento, filas_prueba, filas_sin_objetivo, positivos_entrenamiento, prevalencia_entrenamiento, variables:
{numericas, categoricas}, excluidas_automaticamente: [{columna, motivo}], validacion: {tipo, k, semilla, columna_grupo,
n_grupos}, cohorte_prueba: {...efectiva}, presupuesto: {modo, familias, n_trials_por_familia, n_bootstrap}, avisos: [...]}`.
La interfaz la llama antes de «Entrenar» para mostrar el esquema efectivo y los avisos.

`POST /api/experimentos` — mismo cuerpo → **202** `{id, estado: "en_cola", ...}` + cabecera `Location`. Repite la
validación; guarda la configuración efectiva completa (§6.4).

Errores de validación (422; los marcados con † salen tal cual del `ValueError` de `automl.validacion`):
«La columna objetivo «x» no existe en el conjunto.» · «La clase positiva «x» no aparece en la columna objetivo.» ·
«Columnas desconocidas: a, b.» · «La columna objetivo no puede ser también de grupo, excluida ni sensible.» ·
«No queda ninguna variable para entrenar tras las exclusiones.» · «La columna objetivo solo tiene una clase en las filas
de entrenamiento; se necesitan ambas.» · †«La clase «x» tiene N filas de entrenamiento; la validación cruzada de 5
pliegues necesita al menos 5 por clase.» · †«La columna de grupo «x» tiene N valores distintos; la validación agrupada
necesita al menos 5. Indique otra columna de grupo o ninguna.» · †«La columna de grupo «x» tiene valores vacíos en N
filas.» · †«Con esta columna de grupo, el pliegue N queda sin filas de una de las clases; indique otra columna.» ·
†«Con columna de grupo, la cohorte de prueba se elige por valores (cohortes completas), no al azar, para que filas
relacionadas no queden a ambos lados.» · †«Ningún valor de la cohorte de prueba aparece en «x».» · †«Los valores «…» de la cohorte de prueba no aparecen en «x».» · †«La cohorte de prueba
comparte grupos con el entrenamiento (N grupos); elija cohortes completas.» · «El presupuesto debe ser «completo» o
«demostracion».».

Avisos (200, se guardan en la configuración): sin columna de grupo → «Sin columna de grupo, los pliegues se forman al azar
(estratificados). Si hay filas relacionadas, como el mismo estudiante en varias cohortes o estudiantes de una misma
cohorte, las métricas pueden sobreestimar el rendimiento en una cohorte nueva.»; presupuesto `demostracion` → «Presupuesto
reducido de demostración: los resultados no son comparables con los de un entrenamiento completo.»; filas sin objetivo;
columnas excluidas automáticamente (grupo y columna de la cohorte de prueba).

`GET /api/experimentos` (RF-08) → 200 `[{id, origen, estado, creado_en, duracion_s, conjunto: {id, nombre_archivo,
momento} | null, objetivo, presupuesto, modelos: [{id, momento, familia}]}]`, del más reciente al más antiguo.

`GET /api/experimentos/{id}` → 200 `{id, origen, estado, etapa, progreso: {completadas, total}, latido_en, sin_respuesta,
error, creado_en, iniciado_en, terminado_en, duracion_s, configuracion, reproducibilidad, procedencia, modelos}`.
`sin_respuesta = estado == "en_curso" y latido_en hace > 120 s` (texto: «El proceso de entrenamiento no responde.
Compruebe que está en marcha.»).

`POST /api/experimentos/{id}/reintentar` → 202 experimento **nuevo** con la misma configuración y `reintento_de = id`; 409
«Solo se puede reintentar un experimento fallido o interrumpido.».

### 4.3 Evaluación (RF-04, M)

`GET /api/experimentos/{id}/evaluacion` → 200; 409 «El experimento aún no ha terminado (estado: en curso).».

```json
{"experimento": "web-2026-11-03-01", "origen": "web",
 "fuente": "validacion_cruzada",
 "aviso_fuente": "Métricas de validación cruzada sobre los datos de entrenamiento (predicciones out-of-fold), no de una cohorte de prueba.",
 "presupuesto": {"modo": "completo", "...": "..."},
 "validacion": {"tipo": "agrupada_estratificada", "k": 5, "semilla": 42, "columna_grupo": "presentacion", "aviso": null},
 "modelos": [{
   "modelo_id": 7, "momento": "semana 4", "n": 18000, "positivos": 3900,
   "candidatos": [{"modelo": "rl", "papel": "candidato", "roc_auc_oof": 0.68, "roc_auc_media": 0.67, "roc_auc_desv": 0.03,
                   "pr_auc_oof": 0.4, "brier_oof": 0.15, "calibracion": "isotonica"}],
   "referencias": [{"modelo": "mayoritaria", "...": "..."}, {"modelo": "rl_defecto", "...": "..."}],
   "contraste": {"modelo_a": "apilamiento", "modelo_b": "rl_optimizada", "diferencia": 0.005, "ic95_bootstrap": [0.001, 0.009],
                 "delong_p": 0.019, "delong_p_holm": 0.057, "holm_sobre": 4, "lectura": "equivalencia_practica", "lectura_texto": "..."},
   "parsimonia": {"mejor": "apilamiento", "margen": 0.02, "candidatos": ["..."]},
   "desplegado": {"modelo": "rl", "motivo_texto": "..."},
   "punto_operacion": {"umbral": 0.2136, "sensibilidad": 0.70, "precision": 0.28, "tasa_alerta": 0.53,
                       "tasa_falsos_positivos": 0.49, "matriz_confusion": [[7624, 7288], [1223, 2888]], "textos": {"...": "..."}},
   "calibracion": {"metodo": "isotonica", "brier_sin_calibrar": 0.16, "brier_calibrado": 0.16,
                   "curva": {"calibrada": [{"predicha": 0.1, "observada": 0.09}], "sin_calibrar": ["..."]}, "texto": "..."},
   "equidad": null,
   "textos": {"roc_auc": "...", "pr_auc": "..."}}],
 "aviso_decision": "Herramienta de apoyo a la decisión. ..."}
```

- **Web:** `candidatos`, `referencias`, `contraste`, `parsimonia`, `desplegado`, `punto_operacion` y `calibracion` salen
  del `resumen` de `motor.modelar` (mismas claves que `momentos[]` de exp-2026-10-27-01). Con un solo momento, Holm sobre
  1 contraste = *p* sin corregir (`holm_sobre: 1`, se declara). `equidad` sale de `motor.auditar_equidad` si hay sensibles.
- **Importado:** las mismas claves desde `momentos[semana == paquete["semana"]]` del JSON origen (exp-2026-10-27-01), con
  `delong_p_holm` sobre los 4 momentos (`holm_sobre: 4`) y `equidad` = `equidad_oof`. `apilamiento` se añade a
  `candidatos` como un candidato más. `curva` se calcula al importar desde el parquet OOF registrado en el JSON origen
  (verificando su SHA-256); si no está, `null` con `motivo`.
- `textos` (de `api/textos.py`, sin códigos de decisión, coma decimal):
  - ROC-AUC: «Capacidad del modelo para ordenar a quien tiene el resultado positivo por encima de quien no (0,5 = azar;
    1 = perfecta).»
  - Punto de operación: «De cada 10 casos positivos, el modelo marca a 7.» · «De cada 10 marcados, 3 son positivos.» ·
    «Se marcaría al 53 % de los casos.»
  - Calibración: «Cuando el modelo estima un 30 %, aproximadamente 3 de cada 10 casos son positivos.» (frase genérica).
  - `lectura_texto`: `ventaja_relevante` → «El mejor modelo AutoML ordena mejor que la regresión logística optimizada, con
    una diferencia relevante (al menos 0,02).»; `detectable_sin_relevancia` → «Hay una diferencia detectable, pero menor
    que 0,02: sin relevancia práctica.»; `equivalencia_practica` → «El intervalo de la diferencia queda dentro de ±0,02:
    rendimiento equivalente en la práctica.»; `no_concluyente` → «Los datos no permiten concluir si hay diferencia.»;
    `desventaja_relevante` → «La regresión logística optimizada ordena mejor que el mejor modelo AutoML, con una diferencia
    relevante (al menos 0,02).».
  - `motivo_texto`: «Se despliega <nombre llano>: es el modelo más simple cuya pérdida de ROC-AUC frente al mejor
    (<nombre>) tiene un límite superior del intervalo del 95 % (0,009) por debajo de 0,02.». Nunca se reenvía el `motivo`
    técnico de `parsimonia` (lleva códigos D).
  - Nombres llanos: rl «regresión logística», rf «bosque aleatorio», gb «potenciación de gradiente (scikit-learn)», xgb
    «XGBoost», lgbm «LightGBM», catboost «CatBoost», mlp «red neuronal (perceptrón multicapa)», apilamiento «apilamiento
    de modelos», rl_defecto «regresión logística por defecto», mayoritaria «clase mayoritaria».
  - Si hay sensibles: «Las variables sensibles (…) no se usan para predecir; se muestran las métricas por subgrupo.»

### 4.4 Predicción (RF-05, M)

`GET /api/modelos` → 200 `[{id, experimento_id, origen, momento, familia, umbral, explicador, creado_en}]`.
`GET /api/modelos/{id}` → 200 lo anterior + `columnas` (numéricas y categóricas que el CSV debe traer).

`POST /api/modelos/{id}/predicciones` — multipart: `archivo` (CSV), `columna_id` (opcional; solo se muestra, nunca entra
al modelo). → **201** `{lote_id, modelo_id, n_filas, n_alertas, tasa_alerta, umbral, columnas_ignoradas,
explicaciones: "completas" | "bajo_demanda", aviso_decision}`.

- Se leen con `tablas_csv.leer`; se exigen todas las columnas del paquete; se coaccionan a su tipo (numéricas con
  `pd.to_numeric`; categóricas a `str` conservando vacíos). Las columnas sobrantes (incluida la objetivo) se ignoran y se
  listan. **Nunca se calculan métricas.**
- `explicacion.predecir(paquete, X)` da probabilidad calibrada, alerta, log-odds y valor base; con explicador `lineal` o
  `arbol` también `explicacion.explicar(paquete, X)` para todas las filas (OE4: 100 %); con `permutacion`, bajo demanda.
- Máximo `PLATAFORMA_MAX_FILAS_PREDICCION` (20 000) filas: 422 «El archivo tiene N filas; el máximo por lote es 20 000.».
- Errores: 404 modelo; 409 «Este modelo no está desplegado y no puede usarse para predecir.» (si el paquete no cumple
  `desplegado is True` o su SHA-256 no coincide: «El archivo del modelo no coincide con el registrado.»); 422 «Faltan
  columnas que el modelo necesita: a, b.»; 422 «La columna «x» debe ser numérica (fila N: «abc»).»; 422 «La columna
  identificadora «x» no existe.».

`GET /api/predicciones/{lote_id}` → 200 `{lote: {...}, filas: [{fila, identificador, probabilidad, alerta, sugerencia}],
textos: {probabilidad: "Probabilidad estimada por el modelo", sugerencia: "Sugerencia: priorizar contacto de apoyo"},
aviso_decision}`. Se devuelven todas las filas (≤ 20 000); ordenar y filtrar (por probabilidad, alerta, identificador) lo
hace la interfaz. `sugerencia` solo si `alerta`.

### 4.5 Explicaciones (RF-06, M)

`GET /api/modelos/{id}/explicacion-global` → 200

```json
{"modelo_id": 7, "explicador": "lineal", "escala": "log-odds sin calibrar",
 "fuente": "filas de entrenamiento (n = 19 023)",
 "variables": [{"variable": "tipo_presentacion", "importancia_media_abs": 0.59}],
 "sin_contribucion": [{"variable": "antelacion_media", "motivo": "Sin valores en los datos de entrenamiento: no interviene en la estimación."}],
 "avisos": {"escala": "...RE-02...", "causalidad": "...RE-03...", "decision": "..."}}
```

`null` en `variables` con 200 y `motivo` si el modelo importado no tiene filas de referencia (§8).

`GET /api/predicciones/{lote_id}/filas/{fila}/explicacion` → 200

```json
{"fila": 12, "identificador": "A-123", "probabilidad": 0.34, "alerta": true, "sugerencia": "Sugerencia: priorizar contacto de apoyo",
 "escala": "log-odds sin calibrar", "valor_base": -1.2, "log_odds": -0.4, "explicador": "lineal",
 "aumentan": [{"variable": "dias_desde_ultima_conexion", "valor": "12", "contribucion": 0.8, "extrema": false}],
 "reducen": [{"variable": "n_cma_calificadas", "valor": "2", "contribucion": -10.8, "extrema": true}],
 "resto": {"n_variables": 40, "suma": 0.1},
 "todas": [{"variable": "...", "valor": "...", "contribucion": 0.0}],
 "sin_contribucion": [{"variable": "antelacion_media", "motivo": "..."}],
 "hay_extremas": true,
 "avisos": {"escala": "...", "extrema": "...", "causalidad": "...", "decision": "..."}}
```

- Top-5 por |φ| entre las variables con contribución, repartidas por signo (`guardarrailes-interfaz`); `todas` para la
  vista detallada (RF-07). `valor` en texto llano; vacío → «sin dato».
- **Extremos** (O1 de 29-02, O3 de 29-03): `extrema = |φ| > explicacion.LIMITE_EXTREMO` (5 log-odds, el de
  exp-2026-10-29-05). Aviso: «Algunas contribuciones son inusualmente grandes (más de 5 unidades en la escala del modelo).
  Suelen deberse a un valor poco habitual de la variable en comparación con los datos de entrenamiento; interprételas con
  cautela. La probabilidad mostrada no cambia.» No se recorta ningún valor.
- **Sin contribución** (O4): variables sin valores en las filas de entrenamiento (descartadas por el preprocesado; φ = 0
  por construcción) → `sin_contribucion`, nunca en `aumentan`/`reducen`/`todas` ni en la explicación global.
- Avisos fijos (`textos.py`):
  - RE-02: «Las contribuciones están en la escala interna del modelo (log-odds, antes de calibrar). Indican cuánto empuja
    cada variable la estimación hacia arriba o hacia abajo; no suman la probabilidad mostrada, que está calibrada.»
  - RE-03: «Estos factores describen cómo llegó el modelo a su estimación. No son causas comprobadas ni sustituyen el
    conocimiento del equipo docente sobre el estudiante. La probabilidad es una estimación, no una certeza, y la decisión
    corresponde siempre a las personas.»
- Con explicador `permutacion`, la primera petición calcula y guarda la fila (≈ 1-2 s); 404 si la fila no existe.

### 4.6 Exportación (RF-09, C; último incremento)

`GET /api/predicciones/{lote_id}/exportar` → `text/csv; charset=utf-8`, adjunto: primera línea `# <aviso_decision>`,
columnas `fila, identificador, probabilidad_estimada_pct, alerta, sugerencia`.
`GET /api/experimentos/{id}/evaluacion/exportar` → `application/json`, adjunto: la respuesta de §4.3 + `configuracion` y
`reproducibilidad`.

### 4.7 Cohorte de prueba reservada (pendiente de D-2)

`POST /api/experimentos/{id}/evaluacion-prueba` con `{"confirmar": true}` → 201 con métricas del modelo desplegado en las
filas reservadas con el umbral ya fijado (`punto_operacion` + ROC-AUC, PR-AUC, Brier; `calibracion.punto_operacion` y
`roc_auc_score` de ml); se guarda en `experimento.evaluacion_prueba`, junto con `modelo_id` y `sha256_paquete` del modelo
evaluado, y no se recalcula nunca. 409 «La evaluación en la
cohorte de prueba ya se hizo (fecha); se usa una sola vez.»; 409 «Este experimento no tiene cohorte de prueba reservada.»
(siempre para importados); 409 si el índice único parcial del §3 la rechaza (los mismos datos ya se evaluaron con
esta cohorte en otro experimento); 400 sin `confirmar`. Texto previo obligatorio en la interfaz: «Esta evaluación se hace una sola
vez y no cambia el modelo ni el umbral.».

## 5. Ejecución en segundo plano (RNF-03)

- **Mecanismo:** la cola es la tabla `experimento`. Un proceso aparte, `flask --app api trabajador`, que lanza el operador en
  su propia terminal (como las ejecuciones largas de `ml/`), toma los trabajos de uno en uno. El servidor web solo inserta
  filas `en_cola` y lee estados, así que un entrenamiento de horas no bloquea ninguna consulta (proceso distinto, sin GIL
  compartido) y un reinicio del servidor web no lo interrumpe.
- **Exclusión:** al arrancar, el trabajador toma `pg_try_advisory_lock(727301)`; si ya está tomado, termina con «Ya hay un
  proceso de entrenamiento en marcha.». Un solo trabajador evita sobresuscribir la CPU (`n_jobs` ya usa los núcleos).
- **Recuperación al arrancar:** con el bloqueo tomado, todo experimento `en_curso` es huérfano de un trabajador anterior →
  `interrumpido`, con error «El proceso de entrenamiento se detuvo antes de terminar (cierre o reinicio). Puede
  reintentarlo: se creará un experimento nuevo con la misma configuración.». No se reanuda a medias (cada familia tarda
  hasta ~1 h y la reanudación exigiría cambiar `busqueda`); limitación declarada.
- **Bucle:** cada 5 s, `SELECT … WHERE estado = 'en_cola' ORDER BY creado_en LIMIT 1 FOR UPDATE SKIP LOCKED` → `en_curso`,
  `iniciado_en`; ejecuta `servicios.entrenamiento.ejecutar(id)`.
- **Latido:** un hilo actualiza `latido_en` cada 30 s mientras corre el trabajo (sesión propia). La API marca
  `sin_respuesta` si pasan > 120 s.
- **Progreso:** `motor.modelar(..., progreso=f)` llama a `f(etapa)` al empezar cada etapa; el servicio guarda `etapa` y
  `progreso`. Etapas (total 12, 13 con sensibles): 7 familias («Optimizando XGBoost (familia 4 de 7)»), «Referencias»,
  «Apilamiento», «Comparación y elección del modelo», «Modelo final», «Explicación global», [«Equidad»]. Granularidad por
  familia: `busqueda.buscar` no expone *callbacks* y no se cambia.
- **Fallo:** cualquier excepción → `fallido`; `error` = mensaje del `ValueError` de `ml/` (ya en español) o «El
  entrenamiento ha fallado por un error interno.»; traza completa en `experimentos/<id>/error.log`. Nada a medias en BD: el
  `modelo` y la `evaluacion` se escriben en una única transacción al final; los archivos parciales se borran.
- **Duración:** `duracion_s = terminado_en − iniciado_en` (RNF-03), también en el historial.

`servicios.entrenamiento.ejecutar(id)`, en orden:
1. Lee el CSV y comprueba `sha256 == conjunto_datos.sha256` (si no: `fallido`, «El archivo del conjunto ha cambiado
   desde que se cargó.»).
2. Reconstruye `y`, `X`, grupos y la máscara de prueba con la configuración efectiva guardada (`validacion.reservar_prueba`,
   `validacion.asignar_pliegues`; mismas semillas → mismos pliegues que en `/validacion`, se comprueba con
   `pliegues_sha256` de la configuración).
3. `motor.modelar(X, y, pliegue, columnas, config, progreso)` sobre las filas de entrenamiento.
4. `motor.entrenar_desplegado(...)`, `explicacion.preparar_paquete(...)`, `joblib.dump` → `paquete.joblib` y su SHA-256.
5. `explicacion.explicacion_global(paquete, X)`; `motor.curva_calibracion(...)`; `motor.auditar_equidad(...)` si hay
   sensibles.
6. Guarda `oof.parquet`, `reproducibilidad`, `modelo` (+ `evaluacion`) y `completado` en una transacción.

## 6. Funciones nuevas en `ml/` (primero, con sus pruebas)

Regla: búsqueda, calibración anidada, umbral, comparación y apilamiento se reutilizan **sin cambios**
(`busqueda.buscar`/`construir`, `calibracion.oof_anidado`/`elegir_metodo`/`umbral`/`punto_operacion`,
`comparacion.*`, `apilamiento.*`, `particion.divisiones`, `equidad.auditar`). `k = 5` fijo: `particion.PLIEGUES = {1..5}`.

### 6.1 `ml/automl/validacion.py`

```python
K = len(PLIEGUES)  # 5
MINIMO_POR_CLASE = K
FRACCION_PRUEBA = 0.2

def reservar_prueba(datos: pd.DataFrame, y: pd.Series, cohorte: dict | None, grupos: pd.Series | None,
                    semilla: int) -> pd.Series:
    """Máscara booleana (índice de datos) de las filas reservadas como cohorte de prueba; False en todas si cohorte es None.
    {"modo": "valores", "columna", "valores"}: filas con datos[columna] ∈ valores (comparación como str); con grupos,
    falla si algún grupo tiene filas a ambos lados. {"modo": "aleatoria"}: train_test_split estratificado por y,
    test_size=FRACCION_PRUEBA, random_state=semilla; falla si grupos no es None."""

def asignar_pliegues(y: pd.Series, grupos: pd.Series | None, semilla: int) -> pd.Series:
    """Pliegue 1..K (Int64, mismo índice que y) de las filas de entrenamiento.
    Sin grupos: StratifiedKFold(K, shuffle=True, random_state=semilla).
    Con grupos: StratifiedGroupKFold(K, shuffle=True, random_state=semilla); falla si hay vacíos en grupos, si hay menos
    de K grupos o si algún pliegue queda sin una de las clases. Nunca cambia de esquema en silencio.
    En ambos casos falla si una clase tiene menos de MINIMO_POR_CLASE filas."""
```

Mensajes: los del §4.2 marcados con †, con `ValueError`. La API añade el nombre de la columna (la función recibe series;
se le pasa `grupos.rename(columna)` y usa `grupos.name` en el mensaje).
Comprobaciones añadidas al implementar (incremento 1): `asignar_pliegues` también falla con el mensaje (sin †) de «solo
una clase» si `y` tiene una única clase y si `grupos` no tiene el mismo índice que `y`; `reservar_prueba` falla con un modo
distinto de `valores` o `aleatoria`. En el mensaje de la clase, «x» es el valor de `y` (`True`/`False` si la API pasa `y`
booleana). `StratifiedGroupKFold(shuffle=True, random_state=...)` funciona tal cual con scikit-learn 1.9.1.

Pruebas (`ml/tests/test_validacion.py`, datos sintéticos):
`test_pliegues_estratificados_reproducibles_con_semilla` (misma semilla → misma serie; otra → distinta) ·
`test_pliegues_en_1_a_5_y_compatibles_con_divisiones` (`divisiones(pliegue)` no falla y da 5 divisiones) ·
`test_prevalencia_por_pliegue_estratificada` (±0,02 de la global en 1000 filas) ·
`test_ningun_grupo_en_dos_pliegues` · `test_menos_de_5_grupos_falla_sin_cambiar_de_esquema` (4 grupos → `ValueError`, aunque
estratificado funcionaría) · `test_grupos_con_vacios_falla` · `test_pliegue_sin_una_clase_falla` ·
`test_clase_con_menos_de_5_filas_falla` · `test_prueba_por_valores_reserva_exactamente_esas_filas` ·
`test_prueba_por_valores_que_comparte_grupos_falla` · `test_prueba_aleatoria_estratificada_20_por_ciento_con_semilla` ·
`test_prueba_aleatoria_con_grupos_falla` · `test_sin_cohorte_no_reserva_nada`.

### 6.2 `ml/automl/motor.py` (extracción de `ml/experimento.py`)

Se **mueven sin cambios** desde `experimento.py`: `metricas`, `rl_defecto`, `calcular_referencias`; y desde
`modelo_final.py`: `entrenar_final`. `experimento.py` y `modelo_final.py` los importan de `automl.motor`, así que
`ex.calcular_referencias`, `ex.rl_defecto`, `ex.metricas` (usado por `variante.py`) y `mf.entrenar_final` siguen existiendo
con el mismo nombre (las pruebas actuales no cambian).

```python
def modelar(X: pd.DataFrame, y: pd.Series, pliegue: pd.Series, columnas: dict, config: dict,
            progreso: Callable[[str], None] | None = None
            ) -> tuple[dict, dict[str, np.ndarray], dict[str, np.ndarray], dict[str, Pipeline]]:
    """Parte genérica de experimento.momento, en el mismo orden y con el mismo código: búsqueda por familia → OOF con
    calibración anidada y método por Brier → referencias → apilamiento → mejor AutoML (D44) y contraste con la RL
    optimizada → parsimonia (D49-rev) → umbral (D45) → punto de operación OOF.
    Devuelve (resumen, predicciones, otras, modelos). resumen tiene las claves de momentos[] de exp-2026-10-27-01 salvo
    semana, desglose, equidad_oof, shap y tiempo_s: n, retiros, familias, referencias, apilamiento, mejor_automl,
    contraste_central (sin Holm), parsimonia, modelo_desplegado, calibracion, punto_operacion_oof.
    config: familias, n_trials_por_familia, semillas {optuna, modelos, bootstrap}, n_jobs, apilamiento, n_bootstrap,
    sensibilidad_minima. Exige "rl" en familias."""

def entrenar_desplegado(resumen: dict, modelos: dict[str, Pipeline], X, y, pliegue, columnas: dict, config: dict):
    """Modelo final (D41/D54): familia desplegada ≠ apilamiento → entrenar_final(familia, hiperparámetros, método de su
    calibración, …) con los 5 pliegues; apilamiento → apilamiento(modelos, pliegue, semilla).fit(X, y), sin calibración
    adicional (D52)."""

def curva_calibracion(y, p, n_intervalos: int = 10) -> list[dict]:
    """[{predicha, observada}] con sklearn calibration_curve(strategy="quantile"), como figura_calibracion."""

def auditar_equidad(y, p, corte, atributos: pd.DataFrame, y_ref, atributos_ref: pd.DataFrame, n_bootstrap, semilla) -> dict:
    """equidad.auditar con retiros_prueba = positivos por subgrupo en las filas de referencia (la cohorte de prueba si
    existe —recuento descriptivo, sin predicciones—; si no, el entrenamiento). Añade "recuentos_de"."""
```

`experimento.momento` pasa a: cargar datos → `modelar(X, y, pliegue, columnas, config, progreso=lambda e:
print(f"  semana {semana}: {e}", flush=True))` → añadir `semana`, `desglose` (CCC), `equidad_oof` (con
`retiros_prueba`), `shap: None` y construir el `DataFrame` OOF, con el mismo orden de claves que hoy.

Condición de la extracción (requisito del estudiante): (a) las pruebas de `ml/tests` (hoy 155) pasan sin tocarlas; (b)
**prueba de no regresión manual antes del commit:** ejecutar
`python ml/experimento.py ml/configs/principal.json --ensayo --n-trials 2 --semanas 0 --n-bootstrap 50 --salida <tmp>`
en 82a6f9e y tras el cambio, y comparar `momentos` del JSON (sin las claves `tiempo*`) y el parquet OOF (`assert_frame_equal`):
deben ser idénticos (las predicciones, dentro de atol=1e-9: RandomForest con `n_jobs` > 1 no es reproducible bit a bit
entre ejecuciones del mismo código; véase el esquema `no_regresion` de CONTRATO.md). Los experimentos exportados siguen siendo reproducibles desde su propio commit, y desde el nuevo con
los mismos números.

Pruebas (`ml/tests/test_motor.py`): `test_modelar_despliega_un_candidato_y_fija_el_umbral_sobre_sus_oof` (umbral ==
`umbral(y, predicciones[desplegado])`) · `test_modelar_exige_rl` · `test_modelar_informa_cada_etapa` (espía de
`progreso`: 7 familias + referencias + apilamiento + comparación) · `test_modelar_no_vuelve_a_buscar_en_el_modelo_final`
(monkeypatch de `buscar` tras `modelar`) · `test_entrenar_desplegado_apilamiento_sin_calibracion` ·
`test_entrenar_desplegado_familia_calibrada_con_5_pliegues_ensemble_false` · `test_curva_calibracion_10_intervalos` ·
`test_auditar_equidad_con_recuentos_de_referencia`.

Al implementar (incremento 2):
- `modelar` sin `rl` → `ValueError`. Etapas de `progreso`: el nombre de cada familia, `"referencias"`, `"apilamiento"`
  (si se pide) y `"comparacion"`; `experimento.py` las imprime (dos líneas más en consola que antes, sin efecto numérico).
  `momento` toma el corte de `punto_operacion_oof["umbral_exacto"]` (el mismo `float`).
- `auditar_equidad` lleva un argumento nombrado obligatorio, `recuentos_de` (`"cohorte de prueba"` o
  `"entrenamiento"`): la función no puede saber de dónde vienen las filas de referencia. Devuelve
  `{"recuentos_de": …, <atributo>: …}`. Un subgrupo con predicciones que no aparece en la referencia cuenta 0 positivos
  (es un recuento de esas filas, no un dato que falte).
- `curva_calibracion` redondea a 4 decimales.
- `test_motor.py` reduce los predeterminados de rf, gb, xgb, lgbm, catboost y mlp con `monkeypatch` (solo el primer
  ensayo encolado) para que las 7 familias y el apilamiento tarden unos 35 s.
- La no regresión es el script `ml/no_regresion.py` (matiz (a)): comando, comparación y exportación en el esquema
  `analisis: "no_regresion"` de `evidencias/CONTRATO.md`, con su prueba `test_no_regresion.py`. Base: 3395ab4 (desde
  82a6f9e solo cambiaron `api/` y `validacion.py`). Las pruebas de `ml/tests` eran 169 antes del incremento (201 después).

### 6.3 `ml/automl/explicacion.py`

Se **mueven sin cambios** desde `shap_estabilidad.py`: `variable_original` y `agregar`; `shap_estabilidad.py` los importa
de aquí (`modelo_final`, que hace `from shap_estabilidad import agregar`, no cambia).

```python
LIMITE_EXTREMO = 5.0     # |φ| en log-odds; el de shap_analisis.LIMITE (exp-2026-10-29-05)
FAMILIAS_ARBOL = {"gb", "xgb", "lgbm", "catboost"}   # TreeSHAP en salida bruta = log-odds sin calibrar
FAMILIAS_PERMUTACION = {"rf", "mlp", "apilamiento"}  # RF: TreeSHAP daría probabilidad, no log-odds (D32)
N_FONDO = 50
MAX_FILAS_GLOBAL_PERMUTACION = 500

def tipo_explicador(paquete: dict) -> str:            # "lineal" (coef_), "arbol" o "permutacion"
def modelo_base(paquete: dict):                       # calibrated_classifiers_[0].estimator, o el StackingClassifier
def variables_sin_valores(paquete: dict) -> list[str]:
    """Variables de columnas sin ninguna columna transformada en el preprocesado ajustado (descartadas por no tener valores
    en el entrenamiento; O4). Funciona con los paquetes de modelo_final (sin claves nuevas)."""
def preparar_paquete(modelo, familia: str, corte: float, columnas: dict, X: pd.DataFrame, origen: dict, semilla: int,
                     momento: str | None = None) -> dict:
    """Mismo formato que modelo_final.paquete (semana, modelo, umbral, columnas, fondo, origen) + familia, explicador,
    momento. fondo: lineal = media de X transformada (como paquete); árbol = None; permutación = N_FONDO filas de X
    originales (muestra con semilla). origen debe traer desplegado=True."""
def predecir(paquete: dict, X: pd.DataFrame) -> pd.DataFrame:
    """probabilidad (calibrada), alerta (≥ umbral), log_odds (salida sin calibrar) y base_log_odds."""
def explicar(paquete: dict, X: pd.DataFrame) -> tuple[pd.DataFrame, float]:
    """φ por variable original en log-odds sin calibrar (D32) y error máximo de aditividad.
    lineal: la fórmula de modelo_final.predecir_y_explicar (coef · (x − fondo)) + agregar.
    árbol: shap.TreeExplainer(estimador) sobre X transformada + agregar.
    permutación: shap.PermutationExplainer sobre f(X) = logit(clip(p_sin_calibrar, 1e-6, 1 − 1e-6)) en el espacio de las
    variables originales (categóricas codificadas como enteros para el enmascarador y decodificadas dentro de f), fondo =
    paquete["fondo"], max_evals = 2·p + 1, seed = semilla del origen."""
def explicacion_global(paquete: dict, X: pd.DataFrame, semilla: int = 42) -> dict:
    """{variables: [{variable, importancia_media_abs}] ordenadas, sin_contribucion, n_filas, explicador,
    aditividad_error_max}; con permutación, muestra de MAX_FILAS_GLOBAL_PERMUTACION filas con semilla."""
```

Comprobado en el entorno (shap 0.54.1, sondeo en datos sintéticos): TreeSHAP es aditivo frente a `logit(predict_proba)` en
`HistGradientBoostingClassifier`, LightGBM y CatBoost (error ~1e-14) y en XGBoost (~3e-5, float32); permutación con
`max_evals = 2p + 1` es aditiva (~1e-14) y tarda ≈ 1 s/100 filas en MLP y ≈ 6,5 s/100 filas en RF de 100 árboles; por eso
las explicaciones locales de permutación son bajo demanda.

Pruebas (`ml/tests/test_explicacion.py`): `test_lineal_reproduce_predecir_y_explicar_de_modelo_final` (paquete de
`modelo_final.paquete` sintético: mismas probabilidades, alertas y φ) · `test_aditividad_por_familia` (rl, gb, xgb, lgbm,
catboost, rf, mlp, apilamiento: |Σφ + base − log_odds| < 1e-4) · `test_variables_sin_valores_son_las_descartadas`
(columna toda vacía → listada y φ = 0) · `test_limite_extremo_igual_que_shap_analisis` · `test_permutacion_reproducible_con_semilla`
· `test_categorias_nuevas_no_rompen_la_explicacion` · `test_preparar_paquete_exige_desplegado_true`.

Al implementar (incremento 2):
- **`variables_sin_valores`:** el criterio «sin ninguna columna transformada» no sirve para la RL ni la MLP: en ellas el
  indicador de faltante sobrevive aunque la variable esté vacía (en el paquete de la semana 0 de exp-2026-10-29-03 queda
  `missingindicator_antelacion_media`, con coeficiente 0). Criterio implementado: sin ningún valor observado al ajustar
  el preprocesado (mediana NaN en el `SimpleImputer`, descartada por `DescartarVacias` o, en una categórica, solo la
  categoría de relleno «faltante»); en el apilamiento, las que no tienen valores para ninguno de sus modelos base. En la
  semana 0 de 29-03 da `proporcion_entregadas` y `antelacion_media`, ambas con φ = 0 en todas las filas.
- **TreeSHAP en XGBoost:** con shap 0.54.1, `TreeExplainer(...).expected_value` es una aproximación hasta que se calcula
  algún SHAP (error de aditividad 0,099 en el sondeo); el valor base se toma después de explicar una fila y el error
  queda en ~5e-7. `log_odds` de los árboles es la salida bruta nativa (`decision_function`, `output_margin`, `raw_score`,
  `RawFormulaVal`), que coincide con el logit de la probabilidad sin calibrar (< 1e-5).
- `preparar_paquete`: sin la clave `semana` (es de OULAD) y con `semilla` (la de la muestra de fondo y la del
  explicador de permutación). `tipo_explicador` acepta los paquetes de `modelo_final` (sin `familia` ni `explicador`):
  lineal si el estimador tiene `coef_`. Función auxiliar `explicador_de_familia`.
- `explicacion_global` no redondea (identidad exacta del matiz D-3) y `sin_contribucion` es una lista de nombres (el
  motivo es texto de `api/textos.py`).
- Prueba añadida `test_oulad_paquetes_de_29_03_siguen_funcionando`: los paquetes reales se cargan sin regenerarse y
  `predecir`/`explicar` dan lo mismo que `modelo_final.predecir_y_explicar` (`assert_frame_equal`).
- `shap_estabilidad.explicar` (SHAP *out-of-fold* con fondo = filas de ajuste del pliegue) se queda en su script: no es
  el explicador del modelo desplegado.

### 6.4 Configuración efectiva guardada (RF-02 f, RNF-06)

```json
{"objetivo": "final_result", "clase_positiva": "Withdrawn", "excluidas": ["id_student"], "sensibles": ["gender"],
 "excluidas_automaticamente": [{"columna": "presentacion", "motivo": "columna de grupo"},
                               {"columna": "code_presentation", "motivo": "define la cohorte de prueba"}],
 "variables": {"numericas": ["..."], "categoricas": ["..."], "imputar_mediana": []},
 "validacion": {"tipo": "agrupada_estratificada", "k": 5, "semilla": 42, "columna_grupo": "presentacion", "n_grupos": 15,
                "metodo": "StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=42)", "aviso": null,
                "pliegues_sha256": "..."},
 "cohorte_prueba": {"modo": "valores", "columna": "code_presentation", "valores": ["2014J"], "filas": 0,
                    "metodo": "filas cuyo valor está en la lista", "semilla": null},
 "filas_sin_objetivo": 0,
 "presupuesto": {"modo": "completo", "familias": ["rl", "rf", "gb", "xgb", "lgbm", "catboost", "mlp"],
                 "n_trials_por_familia": 50, "apilamiento": true, "n_bootstrap": 2000},
 "sensibilidad_minima": 0.70, "semillas": {"optuna": 42, "modelos": 42, "bootstrap": 42}, "n_jobs": 8,
 "avisos": ["..."]}
```

`imputar_mediana = []` en el flujo genérico: los árboles tratan los vacíos de forma nativa y RL/MLP imputan todas las
numéricas (`preprocesado.codificador`); D28 es específico de OULAD. La columna de grupo y la que define la cohorte de
prueba nunca son predictores. Las sensibles se excluyen de los predictores (D8, variante «sin») y solo se usan en la
auditoría de equidad.

## 7. Textos y guardarraíles

- `api/textos.py` concentra todos los textos (constantes y funciones `texto_lectura`, `texto_motivo`,
  `textos_punto_operacion`, `coma`). Ninguna ruta escribe texto visible fuera de él, salvo los `ValueError` de `ml/`.
- `test_textos.py` recorre todas las constantes y una respuesta de cada ruta y falla si aparece algún término de la columna
  «No usar» de `guardarrailes-interfaz` («va a abandonar», «abandonará», «causa», «motivo», «porque», «debido a»,
  «provoca», «alto riesgo», «en riesgo», «predicción de fracaso») o un código de decisión (`\bD\d+`, `P-\d+`).
  Excepciones documentadas: las claves JSON (`motivo_texto`, `motivo`) no son texto visible, y las notas fijas que niegan
  la causalidad («No son causas comprobadas…», RE-03) se comprueban por igualdad exacta con `guardarrailes-interfaz`.
- La interfaz no muestra «riesgo» como hecho: «probabilidad estimada por el modelo», «marcados para seguimiento».

## 8. Importación de paquetes desplegados (flujo OULAD, sin código de OULAD en `api/`)

`flask --app api importar-paquetes --modelos data/procesado/modelos --experimentos evidencias/experimentos
[--referencia data/procesado/referencia]`:

1. Para cada `*.joblib` de `--modelos` (orden alfabético): `joblib.load`; si `paquete.get("origen", {}).get("desplegado")
   is not True` → se omite e informa («omitido: no desplegado»). El nombre del archivo no interviene (auditoría O2).
2. Verifica `sha256(archivo) == <origen.id>.json["modelos_sha256"][nombre]`; si no coincide o falta, aborta sin escribir.
3. Crea (una vez) `experimento` con `id = origen["id"]`, `origen = "importado"`, `estado = "completado"`, `configuracion`
   y `reproducibilidad` (commit, entorno, hardware, `dataset.sha256`) desde ese JSON, y `procedencia = {experimento,
   evaluacion_de: origen["experimento"], archivo_json_sha256}`.
4. Crea un `modelo` por paquete: `momento = f"semana {paquete['semana']}"` si existe la clave; `evaluacion` desde
   `<origen.experimento>.json` (§4.3); `explicacion_global` con `explicacion.explicacion_global(paquete, X_ref)` si
   `--referencia/<nombre>.parquet` existe (si no, `null` con motivo).
5. Idempotente: un id ya importado con los mismos SHA-256 se omite; con otros, error.

`ml/referencia_oulad.py` (script OULAD, en `ml/`): para cada paquete desplegado de `exp-2026-10-29-03`, escribe
`data/procesado/referencia/<nombre>.parquet` con las filas de `experimento.cargar_entrenamiento(semana, cortes)` (solo
las 15 presentaciones de entrenamiento, con verificación de SHA-256) y solo las columnas del paquete. No lee 2014J.
Opción `--demo <presentación>`: escribe además `data/procesado/demo/semana_<k>_<presentación>.csv` de una presentación
anterior a 2014J **sin** `etiqueta` (para las capturas de predicción; D-4).

Pruebas (`api/tests/test_importar.py`, paquetes sintéticos con `modelo_final.paquete`):
`test_importador_solo_carga_paquetes_desplegados` (un paquete llamado `x_semana_0.joblib` con `desplegado=False` se omite y
uno llamado `x_con_sensibles_semana_0.joblib` con `desplegado=True` se importa; `desplegado` = `"True"`, `1` o ausente →
omitido) · `test_importador_rechaza_sha256_distinto` · `test_importador_es_idempotente` ·
`test_evaluacion_importada_sale_del_experimento_origen` · `test_prediccion_rechaza_paquete_no_desplegado` (defensa en
`servicios.paquetes`, aunque esté en BD).

## 9. Dependencias, base de datos y configuración

Nuevas en `requirements.txt` (versiones exactas, como el resto; comprobadas con `pip index versions` el 2026-10-30):

| Biblioteca | Versión | Por qué |
|---|---|---|
| Flask | 3.1.3 | API REST (stack del TFM) |
| SQLAlchemy | 2.1.6 | ORM y consultas; ya instalada en el entorno |
| psycopg[binary] | 3.3.6 | Controlador de PostgreSQL para SQLAlchemy (`postgresql+psycopg://`); binario, sin compilar en Windows |
| alembic | 1.20.1 | Migraciones: el esquema cambiará entre incrementos y la BD guardará experimentos de horas que no conviene perder; ya instalada |
| python-dotenv | 1.2.4 | Flask carga `.env` automáticamente; el mismo `.env` lo usa Docker Compose |
| pytest-cov | 7.1.0 | Cobertura para `evidencias/pruebas/` (punto 34) |

Descartadas: Flask-SQLAlchemy (una capa más sin necesidad), Celery/RQ/Redis (§5), flask-cors (en desarrollo, el proxy de
Angular reenvía `/api` a `localhost:5000`; mismo origen), waitress (el servidor de Flask, con hilos, basta en local),
Marshmallow/Pydantic (validación a mano en `servicios/configuracion_exp.py`).

`docker-compose.yml`: servicio `bd`, imagen `postgres:16.15`, `ports: ["127.0.0.1:${PG_PUERTO:-5433}:5432"]`,
`environment` desde `.env` (`POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB=plataforma`), volumen con nombre
`datos_pg`, `docker/initdb/` montado en `/docker-entrypoint-initdb.d`, `healthcheck` con `pg_isready`.

`.env.example`:

```
POSTGRES_USER=plataforma
POSTGRES_PASSWORD=cambiar
POSTGRES_DB=plataforma
PG_PUERTO=5433
DATABASE_URL=postgresql+psycopg://plataforma:cambiar@127.0.0.1:5433/plataforma
DATABASE_URL_PRUEBAS=postgresql+psycopg://plataforma:cambiar@127.0.0.1:5433/plataforma_pruebas
PLATAFORMA_DATOS=data/plataforma
PLATAFORMA_N_JOBS=8
PLATAFORMA_MAX_MB=50
PLATAFORMA_MAX_FILAS_PREDICCION=20000
```

`.gitignore`: añadir `.env` y `data/plataforma/`. `configuracion.Desarrollo` exige `DATABASE_URL` (sin valor por defecto:
«Falta DATABASE_URL: copie .env.example a .env.»). `configuracion.Pruebas`: `sqlite+pysqlite:///:memory:` con
`StaticPool` y `create_all` (sin Alembic), o `DATABASE_URL_PRUEBAS` con el marcador `postgres` (allí se aplica
`alembic upgrade head` y se vacían las tablas entre pruebas). El servidor escucha solo en `127.0.0.1`.

## 10. Plan de pruebas por capa (las ejecuta `tester`)

| Capa | Dónde | Motor | Qué |
|---|---|---|---|
| Núcleo ML | `ml/tests/test_validacion.py`, `test_motor.py`, `test_explicacion.py` + las 155 actuales | — | §6; anti-fuga: la cohorte de prueba nunca llega a `modelar` (espía) |
| Servicios y rutas | `api/tests/test_*.py` | SQLite en memoria | lectura CSV (separadores, BOM, duplicadas, vacío), configuración (cada 422 del §4.2), importador (§8), paquetes, explicaciones (top-5, extremos, sin contribución), textos (§7), trabajador (`ejecutar` síncrono con presupuesto `prueba`; huérfanos → `interrumpido`; fallo → `fallido` sin `modelo`) |
| Funcionales | `api/tests/funcionales/test_rf01…rf09.py` (`@pytest.mark.postgres`) | **PostgreSQL 16.15 del contenedor** | Un caso por requisito con el cliente de Flask, tabla sintética (300 filas, 10 grupos) y presupuesto `prueba`; RF-03 con el trabajador en otro hilo y `GET /experimentos/{id}` respondiendo mientras entrena (RNF-03); RF-04/05/06 también con un paquete importado sintético |

- Cada caso funcional registra su requisito con `record_property("requisito", "RF-0x")`; el JUnit lleva
  `record_testsuite_property("motor_bd", "postgresql 16.15")` (se lee de `SELECT version()`).
- Exportación (punto 34): `pytest api/tests -m postgres --junitxml=evidencias/pruebas/<id>_api_funcionales.xml
  --cov=api --cov=ml/automl --cov-report=json:evidencias/pruebas/<id>_cobertura.json`, desde árbol limpio y con el
  procedimiento de `contrato-evidencias` (sin `hostname`). El informe indica el motor usado.
- Ninguna prueba usa 2014J ni los CSV reales de OULAD.

## 11. Orden de implementación (incrementos pequeños, cada uno verificable)

| # | Incremento | Verificación |
|---|---|---|
| 0 | Infraestructura: dependencias, `docker-compose.yml`, `.env.example`, `.gitignore`, factoría, `bd.py`, `tablas.py`, Alembic `0001_inicial`, `GET /api/estado`, `conftest.py` | `docker compose up -d`; `alembic upgrade head`; `GET /api/estado` → `postgresql 16.15`; `pytest api/tests` y `pytest ml/tests` verdes |
| 1 | `ml/automl/validacion.py` + pruebas | `pytest ml/tests` |
| 2 | Extracción a `ml/automl/motor.py` y `explicacion.py` (movimientos + funciones nuevas) + pruebas | `pytest ml/tests` sin tocar las existentes; no regresión del §6.2 idéntica |
| 3 | RF-01: conjuntos | `test_conjuntos.py` |
| 4 | Importador + `ml/referencia_oulad.py` + `GET /modelos`, evaluación de importados (RF-04 sobre exp-2026-10-29-03) | `test_importar.py` (O2); importar los 4 paquetes reales: 4 modelos, 0 con sensibles |
| 5 | RF-05 y RF-06 (predicción, explicación global y local) → **primer flujo de punta a punta** con el modelo OULAD y el CSV de demostración | `test_predicciones.py`, `test_explicaciones.py`; φ del lineal = `predecir_y_explicar` |
| 6 | RF-02/RF-03: `/validacion`, `POST /experimentos`, trabajador, `servicios.entrenamiento`, evaluación web (RF-04), RNF-06 | `test_configuracion.py`, `test_trabajador.py`; un entrenamiento `demostracion` real de punta a punta |
| 7 | RF-08: historial y reintento | pruebas de rutas |
| 8 | Suite funcional contra PostgreSQL + exportación de JUnit y cobertura | `pytest -m postgres` verde; contrato de evidencias |
| 9 | RF-09 exportación; §4.7 si D-2 = sí | pruebas de rutas |

Los incrementos 0-6 cubren todos los Must de la plataforma; 7-9 son S/C.

## 12. Decisiones del estudiante (confirmadas el 2026-10-30, con los matices del §0)

| Id | Decisión | Recomendación |
|---|---|---|
| D-1 | **RNF-02 (S) en la Entrega 2.** (a) Sin autenticación: uso local, servidor solo en `127.0.0.1`, declarado como S pendiente; (b) un token compartido por variable de entorno (no cumple «perfiles»); (c) usuarios con dos perfiles (docente: predecir y explicar; analista: además entrenar y evaluar) con `werkzeug.security`, sin dependencias nuevas | **(a)** en la E2 y (c) en la E3 si el director exige el requisito; (b) no aporta lo que pide RNF-02 |
| D-2 | **Evaluar una vez en la cohorte de prueba reservada** (§4.7) en el flujo web | Incluirla como último incremento, solo para experimentos web, nunca en las demos con OULAD; si no, la cohorte reservada solo se aparta y se cuenta |
| D-3 | **Explicación global del modelo OULAD** con filas de referencia de entrenamiento (`ml/referencia_oulad.py`) | Sí: es la importancia del modelo final sobre las 15 presentaciones de entrenamiento, sin 2014J. Alternativa: ninguna explicación global hasta predecir una cohorte |
| D-4 | **Datos de demostración de predicción** | Una presentación anterior a 2014J sin `etiqueta` (el script no lee 2014J). Alternativa permitida: 2014J sin la columna objetivo |
| D-5 | **Columna que define la cohorte de prueba** fuera de los predictores (como la de grupo) | Sí: en prueba tendría valores nunca vistos al entrenar |
| D-6 | **Presupuesto `demostracion`** = 5 ensayos por familia y 200 réplicas *bootstrap* | Aceptar; las capturas de evaluación para la memoria, con el modelo importado (resultados reales de 27-01) y no con una demostración |
| D-7 | **Pliegues agrupados genéricos** con `StratifiedGroupKFold` (equilibra la prevalencia entre pliegues), distinto del reparto de D29-rev (3 presentaciones por pliegue, permutación con semilla), que sigue siendo el de OULAD | Aceptar y declararlo en 5.6 de la memoria |
| D-8 | **Extraer** `motor.py` y `explicacion.py` de `experimento.py`, `modelo_final.py` y `shap_estabilidad.py` (movimientos con reexportación) en vez de duplicar | Extraer, con la no regresión del §6.2 antes del commit |

## 13. Pendientes

**Obligatorios antes de la congelación del 06/11** (no son menores; el estudiante pidió vigilar que no se aplacen):

- **Incremento 6:** `clave_cohorte` normaliza los valores con `automl.validacion.normalizar_valor` (la misma que usa
  `reservar_prueba`) antes de que se guarde la primera evaluación (incremento 9). Si no, "2014" y 2014.0 reservarían las
  mismas filas con claves distintas y se reabriría el hueco I-4. Con su prueba.
- **Incremento 6:** prueba de API `cohorte_prueba_clave == clave_cohorte(configuracion["cohorte_prueba"])` al crear el
  experimento.

Las cifras que den las revisiones de código (p. ej. la prevalencia por pliegue de la revisión del incremento 1) son
comprobaciones internas, no citables: si la memoria las quiere, deben llegar como evidencia exportada con su commit.

### Menores (para después de la congelación del 06/11)

Hallazgos menores de las revisiones de código, anotados por decisión del estudiante (solo se corrigen bloqueantes e
importantes antes de la congelación).

| Origen | Pendiente |
|---|---|
| Revisión 2 del incremento 0 | Congelar también `experimento.reproducibilidad` tras evaluar |
| Revisión 2 del incremento 0 | La prueba del catálogo comprueba nombres de disparadores, no las columnas que vigila cada uno |
| Revisión 2 del incremento 0 | Instalar `ruff` en el entorno para pasar el linter |
| Revisión 3 del incremento 0 | El hook que oculta la contraseña solo actúa en informes fallidos (`-rA` mostraría la salida de pruebas superadas) |
| Revisión 3 del incremento 0 | `modelo_evaluado_congelado` lee `experimento` sin `FOR SHARE`: un INSERT concurrente con la evaluación podría colarse (no ocurre con un solo trabajador) |
| Incremento 8 | Exportar el JUnit de `-m postgres` con `--tb=short` |
| Revisión del incremento 1 | `reservar_prueba` no comprueba que `grupos` tenga el índice de `datos` (si no, la salvaguarda de grupos compartidos se desactiva en silencio) |
| Revisión del incremento 1 | En modo `aleatoria`, una clase con 1 fila da un `ValueError` de sklearn en inglés; la API no debe devolverlo tal cual |
| Revisión del incremento 1 | `asignar_pliegues` acepta `y` con 3 clases o con NaN (la API construye `y` binaria sin vacíos) |
| Revisión del incremento 1 | Pliegue vacío: el mensaje dice «sin filas de una de las clases» aunque no tenga filas |
| Revisión del incremento 1 | `cohorte` sin la clave `modo` da `KeyError` (lo valida la API) |
| Revisión del incremento 1 | Pruebas que faltan: prevalencia por pliegue con grupos (distingue `StratifiedGroupKFold` de `GroupKFold`, D-7), índice de grupos distinto, modo desconocido, `y` de una clase |
| Revisión del incremento 2 | `variables_sin_valores`: en una fila nueva con valor, φ puede no ser 0 (MLP, categórica toda «faltante»); el texto de la API dirá «sin valores en el entrenamiento», no «no contribuye» |
| Revisión del incremento 2 | Permutación con `max_evals = 2p+1`: una sola permutación antitética, aditiva pero aproximada y dependiente de la semilla; declararlo en la memoria (D33) |
| Revisión del incremento 2 | Para `decisiones.md` (lo registra el estudiante): RF con permutación (D33 dice «TreeSHAP para árboles») y `auditar_equidad` cuenta 0 en un subgrupo ausente (D50 dice «falla») |
| Revisión del incremento 2 | `no_regresion.py`: si la copia de `data/` falla, el worktree se elimina igualmente en el `finally`; `--salida evidencias/sub` pasa el filtro de `--arbol-de-trabajo` (usar `is_relative_to`); JUnit huérfano si un ensayo falla |
| Revisión del incremento 2 | Pruebas que faltan: salvaguardas de base = HEAD y comparación vacía, `proporcion_entregadas` en `variables_sin_valores` de la semana 0 |
| Revisión del incremento 2 | `explicacion.py`: `calibrated_classifiers_[0]` sin comprobar que haya uno; muestra de `explicacion_global` con `semilla=42` y no `paquete["semilla"]`; guarda `if len(X)` inútil |
| Revisión del incremento 3 | Prueba del 413: fija `MAX_CONTENT_LENGTH` a mano, así que no comprueba la traducción de `PLATAFORMA_MAX_MB` y afirma «50 MB» con un límite de 1 KB |
| Revisión del incremento 3 | `tablas_csv.py`: con una línea en blanco inicial, la cabecera de `csv.reader` es `[]` y el archivo se rechaza con 415 sin explicar la causa (saltar las filas vacías iniciales: `next((f for f in lector if f), [])`); varias cabeceras vacías dan «Hay columnas con el mismo nombre: .»; con «;» y un separador al final de cada fila, el Sniffer no detecta el separador y el mensaje es «Se necesitan al menos 2 columnas.» en lugar del 415 |
| Revisión del incremento 3 | Un NUL (`\u0000`) en un valor, en un nombre de columna o en el nombre del archivo hace fallar el INSERT en PostgreSQL con 500 en lugar de 415/422; con «;» y coma decimal, la columna sale categórica sin aviso |
| Revisión del incremento 3 | `conjuntos.py`: si falla la escritura, el `.tmp` queda huérfano (`try/finally` con `unlink(missing_ok=True)`); en Windows, `os.replace` da 500 si otra subida simultánea tiene abierto el destino |
