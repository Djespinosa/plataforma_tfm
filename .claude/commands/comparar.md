---
description: Compara modelos por momento con DeLong e IC bootstrap de la diferencia de ROC-AUC
argument-hint: "<ids de experimentos a comparar>"
---

Compara los experimentos `$ARGUMENTS` con el subagente **ingeniero-ml**:

1. Comprueba que todos usan el mismo corte, población y partición (si no, no son comparables: dímelo y para).
2. Por momento: ROC-AUC de cada modelo, diferencia frente a la RL optimizada, p-valor de DeLong e IC 95 % *bootstrap*
   (semilla registrada). Indica si las predicciones son *out-of-fold* o de prueba.
3. Aplica la regla de parsimonia (D33) solo si las decisiones `[DECIDIR]` de `rigor-ml` §5 están resueltas.
4. Exporta la comparación como experimento de tipo `comparacion` (con figura de diferencias por semana) y muéstrame la tabla.
