---
description: Comprueba que evidencias/ cumple el contrato y regenera el manifiesto si hace falta
---

Valida `evidencias/` con la skill `contrato-evidencias`:

1. Comprueba `git status --porcelain` y el commit actual.
2. Para cada `experimentos/*.json`: JSON válido, campos obligatorios de su tipo según `CONTRATO.md`, figuras existentes.
3. Comprueba que `manifest.json` lista todos los experimentos y figuras, sin entradas huérfanas ni archivos sin listar.
4. Si el manifiesto está desfasado, propón la corrección y aplícala solo si te lo confirmo (sin tocar los experimentos).
5. Resume: qué está listo para `/importar-evidencias` en la memoria, qué falla y qué falta confirmar en un commit.
