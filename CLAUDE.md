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

> La infraestructura de agentes para el desarrollo (requisitos, backend, frontend, ML, pruebas) se definirá
> en una fase posterior, antes de la Entrega 2.
