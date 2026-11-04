# Plataforma AutoML explicable — detección temprana del riesgo de deserción

Repositorio del **código** del TFM. Será público y se enlaza en el Anexo A de la memoria.
La memoria vive en `../memoria` y solo consume la carpeta `evidencias/` de este repositorio.

## Stack
Angular + TypeScript (frontend) · Flask + Python (API REST) · PostgreSQL · scikit-learn, XGBoost,
LightGBM, Optuna, SHAP (pipeline ML).

## Reglas
1. **Autoría:** el estudiante es el único autor del repositorio. Los commits los hace el estudiante con su
   identidad; no se añaden líneas de coautoría en los mensajes de commit.
2. **Evidencias:** todo experimento, figura, captura, informe de pruebas o resultado de usabilidad que vaya a
   aparecer en la memoria se exporta a `evidencias/` siguiendo `evidencias/CONTRATO.md`, desde un estado
   del código confirmado en un commit.
3. **Rigor experimental:** partición entrenamiento/prueba fija y con semilla; optimización (Optuna) solo con
   validación cruzada sobre entrenamiento; el conjunto de prueba solo para la evaluación final; ninguna
   variable con información posterior al momento de predicción (fuga de información).
4. **Guardarraíles en la interfaz:** los textos de la plataforma presentan SHAP como contribución a la
   predicción del modelo (no causa) y el riesgo como probabilidad estimada (no certeza), y recuerdan que la
   decisión es humana.
5. **Privacidad:** no subir datos personales reales. Los datos públicos (OULAD) se documentan con su licencia.
6. **Prueba intocable:** el conjunto de prueba (2014J) no interviene en ninguna decisión de modelado; solo evalúa,
   una vez, configuraciones declaradas en un commit anterior (principal y análisis de sensibilidad).
7. **Prioridad del ML sobre la web:** el flujo de ML se construye y valida primero, en scripts; la API y la interfaz
   lo envuelven sin reescribirlo.
8. **Reproducibilidad:** semillas fijas, versiones de bibliotecas y SHA-256 de entradas registrados, un identificador
   por experimento.
9. **Memoria de solo lectura:** `../memoria/` se puede leer (en especial `plan/decisiones.md`, fuente de verdad de las
   decisiones), pero nunca se escribe en ella. No se envían datos del estudiante a servicios externos sin autorización.

## Mapa del repositorio

```
ml/                  Núcleo ML y scripts (cortes, experimento, variantes, ablación, fuga, SHAP, modelo final; automl/, configs/, tests/)
api/                 API Flask + PostgreSQL (rutas/, servicios/, trabajador, importador, migraciones Alembic, tests/)
scripts/             Evidencias que cruzan api/ y ml/ con datos de OULAD (evidencia_global_api.py, D-3) y registro de capturas (registrar_capturas.py)
web/                 Interfaz Angular 21 (src/app: api/, vistas/, pruebas/, textos.ts)
data/raw/oulad/      7 CSV de OULAD, CC-BY 4.0 (no versionados)
evidencias/          Lo único que consume la memoria (ver CONTRATO.md)
.claude/             Skills, agentes y comandos de Claude Code (abajo)
```

Detalle de capas, convenciones, API y modelo de datos: skill `arquitectura`.

## Infraestructura de Claude Code

| Tipo | Nombre | Para qué |
|---|---|---|
| Skill | `rigor-ml` | Decisiones metodológicas cerradas como checklist (fuga, cortes, partición, CV, calibración, umbral, DeLong, SHAP, equidad) |
| Skill | `contrato-evidencias` | Cómo exportar a `evidencias/` |
| Skill | `arquitectura` | Estructura, capas, convenciones, API REST, modelo de datos |
| Skill | `guardarrailes-interfaz` | Textos de riesgo, probabilidad y explicaciones para no expertos |
| Agente | `ingeniero-datos` | Cortes de OULAD, población, variables (OE2) |
| Agente | `ingeniero-ml` | AutoML, referencias, calibración, umbral, comparación, SHAP, equidad (OE3, OE4) |
| Agente | `revisor-fuga` | Auditoría independiente de fugas y del uso de la prueba (solo lectura) |
| Agente | `arquitecto` | Diseño de `api/` y `web/` antes de implementar: módulos, contrato de la API, modelo de datos, decisiones técnicas |
| Agente | `revisor-codigo` | Revisión independiente de calidad antes de cada commit: corrección, capas, simplicidad, seguridad, pruebas (solo lectura) |
| Agente | `backend` / `frontend` | API Flask + PostgreSQL / interfaz Angular (OE5) |
| Agente | `tester` | Pruebas del núcleo, de la API y del flujo; Lighthouse y axe (OE5, OE6) |
| Comando | `/cortes`, `/experimento`, `/comparar` | Construir cortes, ejecutar un experimento, comparar modelos |
| Comando | `/auditar-fuga`, `/revisar-codigo`, `/exportar-evidencias`, `/test`, `/estado` | Auditar fugas, revisar código, validar evidencias, probar, ver el avance |

## Estado actual (2026-11-03)

- Hecho, flujo de ML (F0-F3), todo solo *out-of-fold* y sin tocar 2014J:
  - Cortes (exp-2026-10-23-02), núcleo `ml/automl/` con D52-D54 y experimento principal exp-2026-10-27-01 (RL desplegada
    en los 4 momentos; ROC-AUC OOF 0,646-0,708, por debajo de 0,75 de D4).
  - F3: D8 con sensibles (exp-2026-10-28-01, salvaguarda D38 no activada, máx. 0,0181) y su equidad descriptiva
    (28-02); ablación D46-rev (28-03); sensibilidad a la fuga D20/D39 (29-01); SHAP y estabilidad (29-02; 29-05 sustituye
    a 29-04); diagnóstico del umbral transferido (29-06). Todas con auditoría de fuga apta con observaciones.
  - Modelo final D41 preparado sin evaluar en 2014J (exp-2026-10-29-03), con la variante con sensibles sin desplegar
    (P-13). Paquetes `.joblib` en `data/procesado/modelos/` (no versionados).
  - 207 pruebas en `ml/tests` y `scripts/tests` (2026-11-03, todas pasan).
- Hecho, bloque E (API y web; diseño en `docs/diseno-api.md` y `docs/diseno-web.md`):
  - API Flask + PostgreSQL 16 (pasos 0-9): conjuntos, validación y creación de experimentos con trabajador en segundo
    plano, historial, importación de paquetes, predicciones y explicaciones, exportaciones y evaluación única en la
    cohorte de prueba (§4.7, nunca con OULAD). Pruebas unitarias y funcionales (RF-01..RF-06, RF-08, RF-09); exportación
    intermedia api-2026-10-31-01. Explicación global de la API idéntica a la de `ml/` (exp-2026-11-03-01).
  - Web Angular 21 (I-0..I-10): las 11 vistas del flujo carga → configuración → seguimiento → evaluación → modelos →
    predicción → explicaciones, historial y descargas; 70 pruebas Vitest con barrido de vocabulario prohibido.
  - Capturas de la interfaz (9) registradas en `evidencias/capturas/` (148d259, código 9945a8c; flujo web con
    web-2026-11-03-02).
- Pendiente para la Entrega 2:
  - Diagrama de arquitectura para el capítulo 5 (`evidencias/arquitectura/` está vacía).
  - Congelación el 06/11: exportación final única de las pruebas de la API (y de la web si se decide, sin `hostname`).
- Después del 06/11: hallazgos menores de las revisiones (§13 de `docs/diseno-api.md`); en la Entrega 3, evaluación en
  2014J, explicador del apilamiento (permutación), usabilidad y auditoría de accesibilidad.
- Pendiente de registrar en `decisiones.md`: la etiqueta `desventaja_relevante` (lectura con signo).
- Entorno: `~/.venvs/plataforma_tfm` (fuera de OneDrive), versiones exactas en `requirements.txt`. Ejecutar con
  `~/.venvs/plataforma_tfm/Scripts/python`. Las ejecuciones largas las lanza el estudiante en PowerShell.

## Plan hacia la Entrega 2 (09/11/2026, D17)

Mínimo: flujo de ML completo para los 4 momentos con evidencias exportadas; flujo web mínimo de punta a punta
(cargar CSV → entrenar → resultados → explicaciones); capturas y diagrama de arquitectura para el capítulo 5.
Según el cronograma de la memoria, el apartado 5.7.2 de la Entrega 2 lleva **resultados de validación, no de prueba**.

1. **Semana 1:** `/cortes`; referencias; primer experimento AutoML; calibración y umbral; exportación.
2. **Semana 2:** ingeniería de variables; comparación con DeLong e IC; ablación; sensibilidad a la fuga; SHAP y
   estabilidad; equidad; API Flask.
3. **Semana 3:** interfaz mínima en Angular; pruebas; capturas y diagramas; exportación final para la memoria.

Usabilidad por inspección, auditoría de accesibilidad y pulido de la interfaz: Entrega 3.
