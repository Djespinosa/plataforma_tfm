---
name: guardarrailes-interfaz
description: Textos y presentación del riesgo, la probabilidad, el umbral y las explicaciones SHAP para personal académico sin formación en ciencia de datos. Usar SIEMPRE al escribir o revisar cualquier texto visible de la plataforma (etiquetas, ayudas, mensajes, informes exportados), respuestas de la API que se muestren al usuario, o capturas para la memoria.
---

# Guardarraíles de la interfaz

Regla 4 de CLAUDE.md, en la práctica. Cuatro ideas que todo texto debe respetar:

1. **SHAP = contribución a la predicción del modelo**, no causa del abandono.
2. **Riesgo = probabilidad estimada**, no certeza ni diagnóstico.
3. **La plataforma apoya; la decisión es humana.**
4. **La predicción sirve para ofrecer apoyo, nunca para excluir o sancionar.**

## Vocabulario

| Usar | No usar |
|---|---|
| "probabilidad estimada de retiro: 34 %" | "va a abandonar", "abandonará", "34 % de riesgo seguro" |
| "el modelo sugiere priorizar el seguimiento" | "estudiante de alto riesgo" como etiqueta de la persona |
| "factores que más contribuyen a esta estimación" | "causas", "motivos", "porque", "debido a" |
| "aumenta / reduce la estimación del modelo" | "provoca", "explica por qué abandona" |
| "estudiantes marcados para seguimiento" | "estudiantes en riesgo" (como hecho) |
| "alerta" | "predicción de fracaso" |

## Presentación de una predicción individual

- Probabilidad **calibrada** en porcentaje entero, con la frase "estimada por el modelo".
- Si supera el umbral: "Sugerencia: priorizar contacto de apoyo". Nunca rojo como único indicador.
- Factores SHAP locales: los 5 de mayor magnitud, separados en "aumentan la estimación" y "reducen la estimación",
  con el valor de la variable en lenguaje llano ("Días desde la última conexión: 12").
- Nota fija bajo la explicación: "Estos factores describen cómo llegó el modelo a su estimación. No son causas
  comprobadas ni sustituyen el conocimiento del equipo docente sobre el estudiante."

## Presentación de la evaluación del modelo

- ROC-AUC con una frase: "capacidad del modelo para ordenar a quien se retira por encima de quien no (0,5 = azar; 1 = perfecta)".
- Punto de operación siempre junto: sensibilidad ("de cada 10 estudiantes que se retiran, el modelo marca a 7"),
  precisión ("de cada 10 marcados, N se retiran") y **tasa de alerta** ("se marcaría al X % de los estudiantes").
- Calibración: "cuando el modelo estima un 30 %, aproximadamente 3 de cada 10 se retiran".
- Si se usan variables sensibles (`gender`, `disability`, `age_band`, `imd_band`), indicarlo y mostrar las métricas por subgrupo.

## Mensajes fijos

- Pie de cada vista de resultados: "Herramienta de apoyo a la decisión. Las estimaciones pueden equivocarse; la
  decisión corresponde siempre al personal académico y debe orientarse a ofrecer apoyo."
- Al cargar datos: "No suba datos personales identificables sin autorización. La plataforma no envía datos a servicios externos."

## Revisión

Ante cualquier texto nuevo, buscar las palabras de la columna "No usar" y comprobar las cuatro ideas. Un texto que
lo incumpla es un defecto, igual que un error de código.
