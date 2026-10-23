---
description: Ejecuta las pruebas del núcleo ML, de la API y del flujo, y opcionalmente exporta el informe
argument-hint: "[ml|api|web|todo] [--exportar]"
---

Ejecuta las pruebas de `$ARGUMENTS` (por defecto `todo`) con el subagente **tester**:

1. `ml`: `python -m pytest ml/tests`; `api`: `python -m pytest api/tests`; `web`: pruebas de Angular en `web/`.
   Omite las partes que aún no existan y dilo.
2. Muéstrame el resumen (superadas, fallidas, omitidas) y, para cada fallo, la salida relevante y la causa probable.
3. Con `--exportar` y árbol limpio: guarda el informe (JUnit XML y resumen JSON) en `evidencias/pruebas/` y añádelo al manifiesto.
