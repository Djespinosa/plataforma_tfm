# Diseño de la interfaz Angular (bloque E, Entrega 2)

Estado: aprobado por el estudiante el 2026-11-03 (W-1 a W-12 del §14, tal como están; W-9: generar el CSV de
entrenamiento con `ml/referencia_oulad.py`; W-10: capturas manuales con `datos` en el manifest).
Destinatarios: agente `frontend` (implementación) y `tester` (§9). Congelación de la plataforma: **06/11/2026**.
Fuentes: `docs/diseno-api.md` (contrato del §4, que prevalece en cuerpos y errores; matices D-4 y D-6 del §0), código de
`api/rutas/` y `api/textos.py` en 7a7c663, skills `arquitectura` y `guardarrailes-interfaz`, `evidencias/CONTRATO.md`.

## 1. Alcance

| Prioridad | Requisito | Vista (§3) |
|---|---|---|
| 1 (Must; flujo del modelo importado, para las capturas) | RF-05 predicción · RF-06 explicación global y local · RF-04 evaluación | `modelos`, `prediccion`, `lote`, `explicacion-*`, `evaluacion` |
| 2 (Must; flujo genérico) | RF-01 carga · RF-02 configuración con validación previa · RF-03 seguimiento | `carga`, `configuracion`, `seguimiento` |
| 3 (Should, sin ruta propia) | RF-07 vista resumida y detallada | dentro de `evaluacion`, `lote` y `explicacion-*` (§6) |
| 4 (si da tiempo, en este orden) | RF-08 historial y reintento · §4.7 evaluación única · RF-09 exportación | `historial`, `evaluacion`, `lote` |

Recorte si hay retraso: RF-09, RF-08, RF-07 (en ese orden). Fuera de la E2: autenticación (D-1 a), auditoría formal de
accesibilidad, Lighthouse y usabilidad; WCAG 2.1 AA se aplica desde el primer incremento (§7).

Invariantes del `frontend`:
1. Solo habla con `/api` por HTTP/JSON. No calcula métricas, umbrales ni contribuciones: ordenar, filtrar, paginar y
   formatear números (porcentaje, coma decimal) no son cálculos de modelado.
2. Nada de OULAD en `web/` (D10): ni nombres de columnas, ni presentaciones, ni «retiro». El dominio se nombra con el
   vocabulario genérico de la API: «casos», «clase positiva», «marcados para seguimiento».
3. Ninguna petición sale del equipo: sin CDN, fuentes externas ni analítica (`"cli": {"analytics": false}`).
4. Ningún texto de la API se reescribe: avisos, lecturas, `motivo_texto`, textos del punto de operación y mensajes de
   error se muestran tal cual. Interpolación normal de Angular; nunca `[innerHTML]` ni `bypassSecurityTrust*`.

## 2. Versiones y andamiaje

Node instalado: **20.19.1** (npm 10.8.2). Angular 22 (actual `latest`, 22.2.5) exige Node `^22.22.3 || ^24.15.0`, así
que queda descartado. Rama 21 (LTS), con `engines.node` `^20.19.0 || ^22.12.0 || >=24.0.0`:

| Paquete | Versión exacta | Publicada |
|---|---|---|
| `@angular/{core,common,compiler,forms,platform-browser,router,compiler-cli}` | 21.2.25 | 2026-09-30 |
| `@angular/cli`, `@angular/build` | 21.2.27 | 2026-10-15 |
| `typescript` | 5.9.3 | 2025-09-30 |
| `rxjs` / `tslib` | 7.8.2 / 2.8.1 | 2025-02-22 / 2024-10-31 (tslib 2.9.1 tiene 4 días) |
| `vitest` / `jsdom` | 4.1.12 / 28.1.0 | 2026-10-15 / 2026-02-15 |

Comprobado el 2026-11-03 en una carpeta temporal (fuera del repositorio) con Node 20.19.1: `npm install` de estas
versiones exactas, `ng test --watch=false` (Vitest + jsdom) y `ng build` sin errores. Con `vitest` 4.1.11, npm 10.8.2
falla al resolver el árbol (`Cannot read properties of null (reading 'edgesOut')`); por eso 4.1.12.

Andamiaje (desde la raíz, una vez):

```
set NG_CLI_ANALYTICS=false
npx -y @angular/cli@21.2.27 new plataforma --directory web --defaults --style=css --routing --ssr=false --skip-git --zoneless --skip-install
```

Después: fijar las versiones de la tabla en `web/package.json` sin `^` ni `~`; `web/.npmrc` con `save-exact=true`;
quitar `prettier` y `web/.vscode/` (no se usan); `"cli": {"analytics": false}` en `angular.json`; `npm install` y
versionar `package-lock.json` (el operador usa `npm ci`). `index.html` con `lang="es"` y título propio; `app.html` sin la
plantilla de bienvenida (enlaza a angular.dev).

Modelo de programación: componentes *standalone* (el predeterminado), **signals** para el estado de cada vista
(`signal`, `computed`), sin zone.js (`--zoneless`, predeterminado en la 21), `HttpClient` con observables en los
servicios y `ReactiveFormsModule` solo en la configuración. Sin NgRx ni almacén global: el contexto del flujo viaja en la
URL (ids de conjunto, experimento, modelo y lote), lo que además permite reabrir cualquier vista (RF-08).

## 3. Estructura de `web/`

```
web/
├── package.json, package-lock.json, .npmrc     # versiones exactas (§2)
├── angular.json                                 # serve.options.proxyConfig = proxy.conf.json; test = @angular/build:unit-test
├── proxy.conf.json                              # /api → http://127.0.0.1:5000 (§4)
├── tsconfig.json, tsconfig.app.json, tsconfig.spec.json
├── public/favicon.ico
└── src/
    ├── index.html                               # lang="es"
    ├── main.ts
    ├── styles.css                               # paleta con contraste AA, foco visible, tablas, botones, avisos (§7)
    └── app/
        ├── app.ts / app.html                    # cabecera, enlace «Saltar al contenido», <app-pasos>, <router-outlet>, foco al h1 tras navegar
        ├── app.config.ts                        # provideRouter(rutas, withComponentInputBinding()), provideHttpClient()
        ├── app.routes.ts                        # tabla del §3.1; cada ruta con title y data.paso
        ├── textos.ts                            # TODOS los textos propios de la interfaz (§8)
        ├── formato.ts                           # porcentaje, decimal con coma, miles, intervalo, p-valor, fecha (§8)
        ├── api/
        │   ├── tipos.ts                         # interfaces TypeScript de cada respuesta del §4 de diseno-api
        │   ├── errores.ts                       # leerError(e) → {mensaje, detalles[]} (§5)
        │   ├── estado.service.ts                # GET /api/estado
        │   ├── conjuntos.service.ts             # POST/GET /api/conjuntos[/id]
        │   ├── experimentos.service.ts          # validación, crear, historial, detalle, reintentar, evaluación, evaluación-prueba
        │   ├── modelos.service.ts               # GET /api/modelos[/id], explicación global
        │   └── predicciones.service.ts          # POST predicciones, GET lote, explicación local; URLs de exportación
        ├── comun/
        │   ├── pasos.ts                         # los seis pasos (<nav><ol>, aria-current="step")
        │   ├── aviso.ts                         # aviso informativo / de cautela / error: icono + título de texto + role
        │   ├── pie-decision.ts                  # aviso_decision de la respuesta, al pie de cada vista de resultados
        │   ├── grafico-barras.ts                # barras horizontales en SVG (con signo o sin él) + tabla equivalente
        │   └── grafico-calibracion.ts           # curva de calibración en SVG + tabla equivalente
        ├── vistas/                              # una carpeta por vista: <vista>.ts + <vista>.html (+ .css si hace falta)
        │   ├── inicio/  carga/  configuracion/  seguimiento/  historial/  evaluacion/
        │   ├── modelos/  prediccion/  lote/ (lista.ts: ordenar y filtrar, funciones puras)
        │   └── explicacion-global/  explicacion-local/  no-encontrada/
        └── pruebas/fixtures.ts                  # respuestas sintéticas con la forma del §4 (sin datos de OULAD)
```

### 3.1 Rutas

| Ruta | Vista | Paso | Llamadas a la API |
|---|---|---|---|
| `/` | inicio: dos entradas («Usar un modelo ya entrenado», «Entrenar con mis datos»), estado del servidor | — | `GET /estado` |
| `/datos` | carga (RF-01) y conjuntos ya cargados | 1 | `POST /conjuntos`, `GET /conjuntos` |
| `/datos/:conjunto/configuracion` | configuración (RF-02) | 2 | `GET /conjuntos/{id}`, `POST /experimentos/validacion`, `POST /experimentos` |
| `/experimentos` | historial (RF-08) | — | `GET /experimentos` |
| `/experimentos/:id` | seguimiento y resumen del experimento (RF-03) | 3 | `GET /experimentos/{id}` (sondeo, §5), `GET /estado`, `POST …/reintentar` |
| `/experimentos/:id/evaluacion?modelo=` | evaluación (RF-04, §4.7) | 4 | `GET /experimentos/{id}`, `GET …/evaluacion`, `POST …/evaluacion-prueba` |
| `/modelos` | modelos desplegados (entrada del flujo importado) | 5 | `GET /modelos` |
| `/modelos/:modelo/prediccion` | subir el CSV que se va a estimar (RF-05) | 5 | `GET /modelos/{id}`, `GET /experimentos/{exp}`, `POST /modelos/{id}/predicciones` |
| `/predicciones/:lote` | lista ordenable y filtrable (RF-05) | 5 | `GET /predicciones/{lote}` |
| `/modelos/:modelo/explicacion` | explicación global (RF-06) | 6 | `GET /modelos/{id}/explicacion-global` |
| `/predicciones/:lote/filas/:fila` | explicación local (RF-06) | 6 | `GET …/filas/{fila}/explicacion` |
| `**` | no encontrada | — | — |

Los parámetros llegan como `input()` (`withComponentInputBinding`). El paso de un experimento importado muestra los pasos
1-3 como «No aplica: modelo ya entrenado» (texto, no enlace).

## 4. Conexión con la API y arranque local

`web/proxy.conf.json` (sin CORS, como fija `arquitectura`; mismo origen para el navegador):

```json
{ "/api": { "target": "http://127.0.0.1:5000", "secure": false } }
```

Las descargas de RF-09 son enlaces normales (`<a href="/api/predicciones/7/exportar" download>`): el navegador las pide
por el proxy y la API pone el nombre del archivo. Arranque (cuatro terminales, desde la raíz; `python` = el del entorno
`~/.venvs/plataforma_tfm`):

| # | Orden | Para qué |
|---|---|---|
| 1 | `docker compose up -d` y, la primera vez, `python -m alembic -c api/alembic.ini upgrade head` | PostgreSQL 16.15 en 127.0.0.1:5433 |
| — | Una vez: `python -m flask --app api importar-paquetes --modelos data/procesado/modelos --experimentos evidencias/experimentos --referencia data/procesado/referencia` | Modelos de exp-2026-10-29-03 |
| 2 | `python -m flask --app api run --host 127.0.0.1 --port 5000` | API |
| 3 | `python -m flask --app api trabajador` | Entrenamiento en segundo plano (solo para RF-03) |
| 4 | `cd web`, `npm ci` (la primera vez) y `npm start` (`ng serve`, http://localhost:4200) | Interfaz |

## 5. Servicios, tipos y errores

- **Un servicio por recurso** (§3), `providedIn: 'root'`, métodos finos que devuelven `Observable<T>` con la ruta y el
  cuerpo exactos del §4 de diseno-api; las subidas usan `FormData` con los campos `archivo`, `momento` y `columna_id`.
  Sin interceptores ni caché. Las vistas se suscriben, guardan el resultado en un `signal` y desactivan el botón que
  lanzó la petición hasta que responde (evita el doble POST y el doble reintento de las revisiones de los incrementos 6
  y 7 de la API).
- **Tipos** (`api/tipos.ts`): una interfaz por respuesta, con los nombres de campo de la API tal cual (`roc_auc_oof`,
  `aviso_sin_respuesta`…), los nulos declarados (`curva: … | null`, `precision: number | null`, `variables: … | null`,
  `evaluacion_prueba: … | null`) y uniones cerradas para los estados (`'en_cola' | 'en_curso' | 'completado' | 'fallido'
  | 'interrumpido'`), el explicador y `explicaciones: 'completas' | 'bajo_demanda'`. En la equidad, la clave `retiros`
  de cada subgrupo se etiqueta como «positivos».
- **Errores** (`api/errores.ts`): `leerError(e: unknown): {mensaje: string; detalles: string[]}`. Cuerpo `{"error",
  "detalles"?}` → tal cual; estado 0, 502 o 504, o cuerpo sin `error` (el proxy responde con texto si Flask no está en
  marcha) → `TEXTOS.errores.sinConexion`; cualquier otro → `TEXTOS.errores.inesperado`. Se muestra con
  `<app-aviso tipo="error">` (`role="alert"`, mensaje y detalles) junto al control que lo causó; el foco no se mueve.

## 6. Vistas

Cada vista de resultados termina con `<app-pie-decision>` (el `aviso_decision` de la respuesta). La vista **resumida**
(RF-07) es lo visible al abrir; la **detallada** va en `<details>`/`<summary>` con su título («Ver el detalle técnico»).

**Carga (RF-01).** Antes del campo de archivo, el aviso de privacidad (§8, copia literal). Campo `archivo`
(`accept=".csv,text/csv"`) y `momento` opcional; al responder, resumen (filas, columnas), `avisos` de la API y tabla de
columnas (nombre, tipo, % de faltantes, valores distintos). Botón «Configurar el entrenamiento» → paso 2. Debajo, los
conjuntos ya cargados (`GET /conjuntos`) con el mismo botón.

**Configuración (RF-02).** Formulario reactivo con `fieldset`/`legend` por grupo:
- objetivo (`select` de columnas); clase positiva (`select` con los `valores_frecuentes` del objetivo; con más de 20
  valores, campo de texto); columna de grupo (opcional);
- cohorte de prueba (radio «ninguna», «por valores» con columna y casillas de sus `valores_frecuentes`, o «al azar
  (20 %)»);
- excluidas y sensibles (casillas); descripción;
- presupuesto (radio «completo», predeterminado, o «demostración», con su aviso visible al elegirlo, D-6).

«Comprobar la configuración» llama a `/validacion` y muestra el esquema efectivo:
- filas de entrenamiento y de prueba, filas sin objetivo, positivos y prevalencia en %;
- variables numéricas y categóricas, y excluidas automáticamente con su motivo;
- validación (tipo en lenguaje llano, k, columna de grupo, n.º de grupos), cohorte y presupuesto;
- `avisos`, tal cual.

«Entrenar» solo se activa si el cuerpo actual es idéntico al último validado sin error (se compara el JSON); `202` →
`/experimentos/{id}`.

**Seguimiento (RF-03).** Estado en lenguaje llano, `etapa` (ya llega en texto llano), `<progress max=total
value=completadas>` con el texto «N de M etapas», último latido y duración. Si el presupuesto es `demostracion`, una
etiqueta de texto «Entrenamiento de demostración» y los `configuracion.avisos` (D-6). Sondeo: §10. Si `GET /estado`
dice `trabajador_activo: false` y el experimento está `en_cola`, aviso propio: el experimento esperará hasta que se
inicie el proceso de entrenamiento. Al completar: enlaces a la evaluación y, por modelo, a predecir y a la explicación
global. Con `fallido`/`interrumpido`: `error` tal cual y, si da tiempo (RF-08), «Reintentar» → nuevo id.
Reproducibilidad (commit, árbol limpio, semillas, versiones, SHA-256) en la vista detallada.

**Evaluación (RF-04).** Con varios modelos (los 4 momentos de 29-03), un grupo de botones por `momento`
(`aria-pressed`) que actualiza `?modelo=`. Por encima de todo, `aviso_fuente` y, si el presupuesto es de demostración,
la etiqueta y el aviso de D-6 (de `configuracion.avisos` del detalle).
- Resumen:
  - modelo desplegado (nombre llano) con `motivo_texto`;
  - punto de operación: umbral en % con 1 decimal y los tres `punto_operacion.textos` (sensibilidad, precisión, tasa de
    alerta), siempre juntos;
  - ROC-AUC del desplegado con `textos.roc_auc`;
  - `contraste.lectura_texto`;
  - curva de calibración (`grafico-calibracion`) con `calibracion.texto`, o `calibracion.motivo` si `curva` es `null`.
- Detalle:
  - tabla de candidatos y referencias (ROC-AUC OOF, media ± desv., PR-AUC con `textos.pr_auc`, Brier, calibración;
    fila del desplegado marcada con texto «desplegado»);
  - contraste (diferencia, IC 95 %, *p* de DeLong y corregido, «Holm sobre N»);
  - parsimonia (pérdida, IC, cumple sí/no);
  - matriz de confusión como tabla con encabezados (filas «positivo real / negativo real», columnas «marcado / no
    marcado»; la API da `[[VN, FP], [FN, VP]]`);
  - Brier sin calibrar y calibrado;
  - equidad (`equidad.texto` y una tabla por atributo; subgrupos `solo_descriptiva` con la nota «solo descriptiva»);
  - validación y presupuesto.
- §4.7, solo si `origen == "web"`, hay `configuracion.cohorte_prueba` y `evaluacion_prueba` es `null`: el texto previo
  obligatorio (§8), una casilla «He leído que esta evaluación se hace una sola vez» y el botón «Evaluar en la cohorte de
  prueba», activo solo con la casilla marcada y desactivado durante la petición. Con `evaluacion_prueba`, sus métricas
  (solo lectura) con su `aviso_fuente`, separadas de las de validación cruzada. Nunca se ofrece en importados.

**Modelos.** Tabla: experimento, momento, familia (nombre llano), origen, umbral en %. Acciones por fila: «Ver
evaluación», «Ver explicación global», «Estimar una cohorte».

**Predicción (RF-05).** Aviso de privacidad (copia literal), columnas que debe traer el CSV (`GET /modelos/{id}`),
campo `archivo` y campo de texto «Columna identificadora (opcional)» con ayuda: solo se muestra y nunca entra al modelo.
Si el experimento del modelo es de demostración, la etiqueta de D-6. `201` → `/predicciones/{lote}`.

**Lote (RF-05).** Arriba, `aviso_rendimiento` (D-4) como aviso de cautela. Resumen:
- archivo, filas y marcados, con la tasa de alerta en % (texto propio: «Se marcan para seguimiento N de M casos
  (X %)»);
- umbral en % con 1 decimal y columnas ignoradas;
- con `bajo_demanda`, la ayuda «la explicación de cada fila se calcula al abrirla (unos segundos)».

Lista:
- columnas: fila, identificador, `textos.probabilidad` (en %), alerta y sugerencia;
- la alerta va como texto («Marcado para seguimiento» + `sugerencia`) con borde e icono, nunca solo con color;
- orden por probabilidad descendente (predeterminado), fila o identificador, con botones en los `th` y `aria-sort`;
- filtros: «todos / solo marcados», búsqueda por identificador (contiene, sin distinguir mayúsculas) y probabilidad
  mínima en %;
- 50 filas por página; «Mostrando X-Y de Z»;
- cada fila enlaza a su explicación local.

`ordenar`, `filtrar` y `paginar` son funciones puras de `lista.ts` aplicadas en un `computed`. Con RF-09, enlace «Descargar
CSV».

**Explicación global (RF-06).** `fuente` (o `motivo` si `variables` es `null`), barras de `importancia_media_abs` de las
15 primeras (resumen) y tabla completa (detalle), `sin_contribucion` en una lista aparte con su motivo, y `avisos.escala`,
`avisos.causalidad`. Encabezado: «Variables que más contribuyen a las estimaciones del modelo».

**Explicación local (RF-06).**
- Resumen:
  - probabilidad en % con «estimada por el modelo» y `sugerencia` si hay alerta;
  - dos listas, «Aumentan la estimación» (`aumentan`) y «Reducen la estimación» (`reducen`), con «variable: valor» y la
    contribución con signo y coma decimal; las barras con signo de `grafico-barras` hacia la derecha o la izquierda del
    eje;
  - las `extrema` llevan el texto «(inusualmente grande)» y `avisos.extrema`;
  - `resto` como frase («Otras N variables suman ±x»);
  - `sin_contribucion` aparte;
  - `avisos.escala` y `avisos.causalidad` (la nota fija), siempre visibles.
- Detalle: tabla `todas`, valor base y log-odds con `escala`.
- La vista también muestra `aviso_rendimiento` (D-4; ajuste A-1 del §11).
- Los nombres de variable se muestran como vienen en el CSV: la plataforma es genérica (D10) y no tiene etiquetas
  llanas por columna (limitación para la memoria).

## 7. Accesibilidad (WCAG 2.1 AA desde el principio)

- HTML semántico: `header`, `nav`, `main` con un único `h1` por vista, jerarquía de encabezados, `table` con `caption`
  y `th scope`, listas reales. `lang="es"`. Título de documento por ruta (`title` en `app.routes.ts`).
- Formularios: todo control con `label` visible; grupos con `fieldset`/`legend`; ayudas y errores enlazados con
  `aria-describedby`; nada se envía al cambiar un campo.
- Foco: `:focus-visible` con contorno de 3 px y contraste ≥ 3:1; enlace «Saltar al contenido»; tras navegar, foco al `h1`
  (`tabindex="-1"`); orden de tabulación natural, sin `tabindex` positivo.
- Color: paleta en variables CSS con texto ≥ 4,5:1 (comprobada al definirla, anotando las razones en `styles.css`). La
  alerta, el estado, el modelo desplegado y las curvas llevan siempre texto, icono o trazo distinto además del color
  (calibrada: línea continua con círculos; sin calibrar: discontinua con cuadrados; diagonal: punteada).
- Gráficos: `<svg role="img" aria-labelledby>` con `title` y `desc`, y la misma información en una tabla dentro de un
  `details` contiguo.
- Estado dinámico: el bloque de estado del seguimiento con `aria-live="polite"`; los errores con `role="alert"`.
- Tipografía del sistema (`system-ui, "Segoe UI", Roboto, sans-serif`), sin fuentes descargadas; tamaño base 1rem;
  tablas anchas en un contenedor con desplazamiento, `tabindex="0"` y `aria-label`.

## 8. Textos y formato

- **De la API, tal cual:** errores, `avisos`, `aviso_*`, `lectura_texto`, `motivo_texto`, `punto_operacion.textos`,
  `calibracion.texto|motivo`, `equidad.texto`, `textos.*`, `etapa`, `error`, `sugerencia` y `motivo` de
  `sin_contribucion`.
- **Propios, solo en `textos.ts`:** un objeto `TEXTOS` agrupado por vista (etiquetas, botones, ayudas, encabezados de
  tabla, títulos de ruta, errores de conexión) más funciones para las frases con cifras. Las plantillas no llevan texto
  literal: todo `{{ t.… }}`.
  - Incluye mapas cerrados: estado → llano («en cola», «en curso»…), tipo de validación → frase («validación cruzada de
    5 pliegues, agrupada y estratificada»…), familia → nombre llano.
  - También copias literales de cuatro textos de `api/textos.py` que hacen falta antes de llamar a la API:
    `AVISO_PRIVACIDAD_CARGA`, `AVISO_DEMOSTRACION`, `TEXTO_PREVIO_PRUEBA` y `NOMBRES_MODELOS`.
  - Cada copia lleva el comentario `// copia literal de api/textos.py: <CONSTANTE>` y la revisa `revisor-codigo` si
    cambia la API (decisión W-6).
- **Vocabulario:** el de `guardarrailes-interfaz`. «Probabilidad estimada por el modelo», «marcado para seguimiento»,
  «aumentan/reducen la estimación», «factores que más contribuyen». Nunca «riesgo» como etiqueta de una persona.
- **Formato (`formato.ts`, sin `Intl` para coincidir con la API):**
  - `porcentaje(p)`: % entero con espacio («34 %»); si redondea a 0 o a 100 sin serlo, «< 1 %» o «> 99 %», para no
    sugerir certeza;
  - `porcentaje1(p)`: 1 decimal (umbral, tasa);
  - `decimal(x, d = 3)`: coma decimal y signo «−» tipográfico en las contribuciones;
  - `miles(n)`: espacio desde 10 000, como `textos.miles`;
  - `intervalo([a, b])`: «[0,001; 0,009]», con punto y coma porque la coma es decimal;
  - `pValor(p)`: «< 0,001» si p < 0,001;
  - `fecha(iso)`: «dd/mm/aaaa hh:mm».

## 9. Pruebas (Vitest + jsdom, `ng test --watch=false`; las ejecuta `tester`)

| Archivo | Qué comprueba |
|---|---|
| `formato.spec.ts` | coma decimal, % entero, «< 1 %» y «> 99 %», miles, intervalo, p-valor |
| `api/errores.spec.ts` | `{error}`, `{error, detalles}`, estado 0, 504 con cuerpo de texto, 500 sin cuerpo JSON |
| `api/servicios.spec.ts` | con `provideHttpClientTesting`: método, URL y cuerpo de cada llamada; `FormData` con `archivo`, `momento`, `columna_id` |
| `textos.spec.ts` | recorre `TEXTOS` (cadenas y funciones con valores de ejemplo): ningún término de «No usar» (la misma lista que `api/tests/test_textos.py`) ni códigos `\bD-?\d+` o `P-\d+` |
| `pruebas/vocabulario.spec.ts` | renderiza seguimiento, evaluación, lote, explicación global y local con `fixtures.ts` (textos de la API sustituidos por «texto de la API») y busca la misma lista en `textContent`: cubre el texto literal que se cuele en una plantilla |
| `vistas/lote/lista.spec.ts` | orden por probabilidad, fila e identificador; filtros por alerta, identificador y mínimo; paginación |
| `vistas/seguimiento/seguimiento.spec.ts` | con temporizadores falsos: el sondeo sigue en `en_cola`/`en_curso`, para en `completado`/`fallido`, muestra `aviso_sin_respuesta` |
| `vistas/configuracion/configuracion.spec.ts` | «Entrenar» desactivado hasta validar y otra vez tras cambiar un campo |

Verificación manual por incremento: el flujo en el navegador contra la API real (§11) y navegación solo con teclado. Sin
cobertura en la E2: necesitaría `@vitest/coverage-v8`, una dependencia más.

Exportación (la decide el estudiante en la congelación): `npx --no ng test --watch=false --reporters=junit
--output-file=<tmp>/web_pruebas.xml` desde un árbol limpio. Vitest escribe `hostname` en cada `testsuite`, que el
contrato prohíbe: hay que quitarlo antes de copiar el informe a
`evidencias/pruebas/interfaz-AAAA-MM-DD-NN_pruebas.xml` (no `web-`, que es el prefijo de los experimentos web) y añadirlo a `manifest.json`. Se puede hacer con el mismo
procedimiento de `api/exportar_pruebas.py`: `python -m scripts.exportar_pruebas_web`.

## 10. Seguimiento del entrenamiento

`timer(0, 3000).pipe(exhaustMap(() => experimentos.detalle(id)), takeWhile(e => e.estado === 'en_cola' || e.estado ===
'en_curso', true), takeUntilDestroyed())`. Cada respuesta actualiza el `signal` del experimento. Un error de red no corta
el sondeo (`catchError` dentro del `exhaustMap` muestra `leerError` y sigue: la API puede reiniciarse sin afectar al
trabajador). `sin_respuesta: true` → `aviso_sin_respuesta` como aviso de cautela. Al llegar a `completado` se ofrecen
los enlaces; no se navega solo. Una lectura de una fila cada 3 s no carga la API.

## 11. Ajustes del contrato de la API

| Id | Ajuste | Motivo | Coste |
|---|---|---|---|
| A-1 (recomendado) | `GET /api/predicciones/{lote}/filas/{fila}/explicacion` añade `aviso_rendimiento` (`textos.AVISO_RENDIMIENTO`) | D-4 pide etiquetar las predicciones de demostración en la interfaz; la vista local muestra la probabilidad y se puede abrir por URL sin cargar el lote (hasta 20 000 filas) | 1 línea en `rutas/predicciones.py` y una aserción en `test_predicciones.py`; `test_textos.py` ya recorre esa respuesta |
| A-2 (no recomendado antes del 06/11) | `GET /api/textos` con los cuatro textos copiados (§8) y `nombre` llano en `candidatos`, `referencias`, `contraste` y `/modelos` | Una sola fuente de textos | Ruta, pruebas y revisión: no compensa con 3 días; queda como menor |

El resto de lo que necesita la interfaz ya está en el contrato. Limitaciones de la E2, para la memoria: no hay listado
de lotes (un lote se reabre por su URL; RF-08 cubre los experimentos); los nombres de variable se muestran tal cual; la
clave `retiros` de la equidad es terminología de OULAD en una clave JSON (no visible; anotarla en los menores del §13 de
diseno-api).

## 12. Capturas para la memoria (`evidencias/capturas/`)

- **Datos:**
  - modelo importado exp-2026-10-29-03, con la evaluación de sus OOF de exp-2026-10-27-01;
  - CSV de demostración `data/procesado/demo/semana_4_2014B.csv` (generado por `ml/referencia_oulad.py --demo`), con
    `columna_id = id_student` (anonimizado en OULAD, CC-BY 4.0).
- **Prohibido:** nunca 2014J, ni la evaluación única §4.7 con datos de OULAD, ni métricas de prueba.
- **Lista** (semana 4 salvo indicación; vistas en `capturas/web-<vista>.png`):

| Archivo | Vista |
|---|---|
| `web-modelos.png` | modelos desplegados de 29-03 (4 momentos) |
| `web-evaluacion-resumen.png` | resumen con `aviso_fuente`, desplegado y motivo, punto de operación, lectura del contraste y calibración |
| `web-evaluacion-detalle.png` | candidatos y referencias, contraste, matriz de confusión |
| `web-prediccion-lista.png` | lote de 2014B ordenado por probabilidad, con `aviso_rendimiento` y resumen |
| `web-explicacion-local.png` | una fila marcada: aumentan/reducen, avisos de escala y causalidad |
| `web-explicacion-extrema.png` | regla de las contribuciones extremas (valor absoluto de SHAP > 5 log-odds): marcadas, sin recortar y con su aviso; semana 12, `semana_12_2014B.csv`, fila 3261 (632215, `clics_glossary` −7,61) |
| `web-explicacion-global.png` | importancia global y variables sin contribución |
| `web-carga.png`, `web-configuracion.png`, `web-seguimiento.png` | flujo genérico (datos: decisión W-9) |

- **Toma:** Chrome a 1440 × 900, zoom 100 %, DevTools → «Capture full size screenshot», con `web/` y `api/` confirmados
  en un commit (árbol limpio) y la base de datos solo con los importados y los lotes de las capturas.
- **Registro:** cada PNG en `manifest.json` → `capturas` con `{archivo, descripcion, commit, datos}` (`datos`: experimento
  y CSV con su SHA-256; amplía el esquema de CONTRATO.md, W-10); el estudiante las confirma en un commit propio.

## 13. Orden de implementación

Cada incremento termina con `ng test` y `ng build` en verde, la verificación de la tabla, `/revisar-codigo` (solo
bloqueantes e importantes hasta el 06/11) y el commit del estudiante. El flujo del modelo importado va primero (I-1 a
I-3) porque las capturas tienen prioridad.

| # | Incremento (≈ h) | Verificación |
|---|---|---|
| I-0 | Andamiaje (§2), proxy, `styles.css`, `app` con pasos y salto al contenido, `textos.ts`, `formato.ts`, `tipos.ts`, `errores.ts`, `estado.service`, vista inicio, `no-encontrada` (2) | `formato`, `errores` y `textos` en verde; con la API en marcha, inicio muestra el motor y el trabajador; sin la API, el mensaje de sin conexión; `grep -rE "https?://" web/src` sin URL externas |
| I-1 | RF-05: `modelos.service`, `predicciones.service`, vistas modelos, predicción y lote con `lista.ts` (3) | Subir `semana_4_2014B.csv` con `id_student` al modelo de la semana 4: el número de filas y de marcados coincide con la respuesta del POST; ordenar y filtrar con teclado; `servicios` y `lista` en verde |
| I-2 | RF-06: `grafico-barras`, explicación local y global; A-1 si se aprueba (3) | Una fila marcada muestra top-5 por signo, nota fija y aviso de escala; semana 0: `sin_contribucion` con dos variables; global con 15 barras y tabla |
| I-3 | RF-04: evaluación de importados con selector de momento, `grafico-calibracion`, resumen/detalle (3) | Las 4 semanas de 29-03: textos idénticos a los de la respuesta JSON; matriz con encabezados; curva y tabla equivalente. **Primer flujo completo: capturas provisionales** |
| I-4 | RF-01: carga y lista de conjuntos (1,5) | CSV con «;» y con BOM; 415 y 422 de la API visibles con sus detalles |
| I-5 | RF-02: configuración, validación y esquema efectivo (3) | Cada error 422 del §4.2 se muestra; «Entrenar» solo tras validar; aviso de demostración al elegirla |
| I-6 | RF-03: seguimiento con sondeo y resumen del experimento (2) | Entrenamiento de demostración real con el trabajador: etapas y progreso avanzan; parar el trabajador → `aviso_sin_respuesta` a los 2 min; `seguimiento.spec` en verde |
| I-7 | `vocabulario.spec.ts`, `configuracion.spec.ts`, repaso de accesibilidad con teclado y de contraste; **capturas definitivas** (2) | Todas las pruebas en verde; recorrido completo solo con teclado |
| I-8 | RF-08: historial y reintento (1,5) | Reabrir un experimento y un importado desde el historial; reintentar un interrumpido → nuevo id |
| I-9 | §4.7: evaluación única (1,5) | Con datos sintéticos: botón solo con la casilla; 201 y después solo lectura; segundo intento → 409 visible |
| I-10 | RF-09: enlaces de descarga (0,5) | El CSV se abre con tildes; el JSON lleva la configuración |

Total ≈ 23 h. Si el 05/11 por la tarde no está I-7, se recortan I-10, I-8 y RF-07 (el `details` de detalle) en ese
orden; I-9 solo entra si están I-0 a I-8.

## 14. Decisiones para confirmar

| Id | Decisión | Alternativa descartada | Motivo / recomendación |
|---|---|---|---|
| W-1 | Angular 21.2.25 (CLI y build 21.2.27), TypeScript 5.9.3, versiones exactas y `package-lock.json` | Angular 22.2.x | 22 exige Node ≥ 22.22.3; 21 es LTS, con Node 20.19.1 verificado (§2) |
| W-2 | *Standalone*, signals, *zoneless*, estado en la URL, formularios reactivos solo en la configuración | NgRx o un servicio de estado global; *signal forms* (experimental) | Lo mínimo que cubre el flujo; la URL permite reabrir (RF-08) |
| W-3 | CSS propio con elementos nativos (`table`, `fieldset`, `details`, `progress`) | Angular Material | Los controles del flujo son nativos y ya accesibles; Material añade CDK, tema y curva de aprendizaje en 3 días |
| W-4 | Gráficos en SVG propio (barras y calibración), con tabla equivalente | Chart.js, ngx-charts | Dos gráficos sencillos; sin dependencias y con control del texto alternativo |
| W-5 | Proxy de desarrollo `/api` → 127.0.0.1:5000; descargas por enlace | CORS en Flask | Lo que fija `arquitectura`; mismo origen |
| W-6 | Textos propios en `textos.ts`; 4 textos de la API copiados literalmente con comentario de origen | Ruta `GET /api/textos` (A-2) | Sin cambios en la API antes de la congelación; A-2 como menor |
| W-7 | Sondeo cada 3 s mientras `en_cola`/`en_curso`; los errores de red no lo cortan | WebSocket o SSE | La API ya expone el detalle; sin dependencias |
| W-8 | Vitest + jsdom (predeterminados de la 21): formato, errores, servicios, textos, vocabulario renderizado, lista, sondeo, configuración; JUnit sin `hostname`; sin cobertura en la E2 | Karma/Jasmine; Playwright E2E | Predeterminado, rápido; E2E no cabe en 3 días |
| W-9 | Capturas del flujo genérico (carga, configuración, seguimiento) con un CSV de entrenamiento generado por un script confirmado | `data/procesado/demo/entrenamiento_semana_4.csv` actual | Ese archivo (2013B, 2013J y 2014B, con `etiqueta`, sin 2014J) no tiene script versionado que lo genere: no sería trazable. **Decide el estudiante**; recomiendo añadir su generación a `ml/referencia_oulad.py` (tarea de `ingeniero-datos`, ≈ 30 min) o usar una tabla sintética |
| W-10 | Capturas manuales a 1440 × 900 y entradas `{archivo, descripcion, commit, datos}` en `manifest.json` | Capturas automáticas con Playwright | Sin dependencias ni navegadores descargados. **Decide el estudiante**: amplía el esquema de capturas de CONTRATO.md |
| W-11 | Ajuste A-1 (`aviso_rendimiento` en la explicación local) | Copiar el aviso en la web; cargar el lote entero | D-4 en todas las vistas con probabilidades; cambio de una línea |
| W-12 | Probabilidades extremas como «< 1 %» y «> 99 %» | Mostrar «0 %» y «100 %» | Un 0 % o un 100 % se leería como certeza (regla 4) |

Tras confirmarlas, se resumen en «Decisiones técnicas» de la skill `arquitectura` y en su sección «Interfaz Angular»;
este documento no las escribe allí, por indicación del encargo.
