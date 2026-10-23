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
ml/                  Núcleo ML y scripts (exploracion_oulad.py; próximos: cortes_oulad.py, automl/, configs/, tests/)
api/                 API Flask + PostgreSQL (semana 2)
web/                 Interfaz Angular (semana 3)
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
| Agente | `backend` / `frontend` | API Flask + PostgreSQL / interfaz Angular (OE5) |
| Agente | `tester` | Pruebas del núcleo, de la API y del flujo; Lighthouse y axe (OE5, OE6) |
| Comando | `/cortes`, `/experimento`, `/comparar` | Construir cortes, ejecutar un experimento, comparar modelos |
| Comando | `/auditar-fuga`, `/exportar-evidencias`, `/test`, `/estado` | Auditar, validar evidencias, probar, ver el avance |

## Estado actual (2026-10-17)

- Hecho: exploración de OULAD con calidad de datos, versiones y SHA-256 (exp-2026-10-05-02); infraestructura de Claude Code.
- Pendiente para la memoria (`decisiones.md`, 2026-10-05): bajas en el día 0 exacto; población y prevalencia por corte
  y partición; definición de `n_variables`. Se resuelve con `/cortes`.
- Decisiones abiertas que bloquean código: parsimonia D33 (orden de complejidad y si se compara con *out-of-fold* o
  con prueba), `rigor-ml` §5.
- **Pendiente de registrar en `../memoria/plan/decisiones.md`** (la próxima vez que se trabaje en la memoria; desde aquí
  no se escribe allí): matrícula tardía (a) y evaluaciones (b), confirmadas el 2026-10-17, con el tratamiento de
  `is_banked`; texto en `rigor-ml` §1.
- Entorno: faltan xgboost, lightgbm, catboost, optuna, shap y pytest.

## Plan hacia la Entrega 2 (09/11/2026, D17)

Mínimo: flujo de ML completo para los 4 momentos con evidencias exportadas; flujo web mínimo de punta a punta
(cargar CSV → entrenar → resultados → explicaciones); capturas y diagrama de arquitectura para el capítulo 5.
Según el cronograma de la memoria, el apartado 5.7.2 de la Entrega 2 lleva **resultados de validación, no de prueba**.

1. **Semana 1:** `/cortes`; referencias; primer experimento AutoML; calibración y umbral; exportación.
2. **Semana 2:** ingeniería de variables; comparación con DeLong e IC; ablación; sensibilidad a la fuga; SHAP y
   estabilidad; equidad; API Flask.
3. **Semana 3:** interfaz mínima en Angular; pruebas; capturas y diagramas; exportación final para la memoria.

Usabilidad por inspección, auditoría de accesibilidad y pulido de la interfaz: Entrega 3.
