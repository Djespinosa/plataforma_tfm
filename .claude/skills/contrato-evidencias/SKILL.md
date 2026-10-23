---
name: contrato-evidencias
description: Cómo exportar a evidencias/ cualquier resultado que vaya a usar la memoria (experimentos JSON, figuras, capturas, diagramas, informes de pruebas): árbol limpio, commit, identificador, esquema por tipo, figuras a 300 ppp y actualización de manifest.json. Usar SIEMPRE que un script escriba en evidencias/ o se revise una exportación.
---

# Contrato de evidencias

La norma es `evidencias/CONTRATO.md`. Esta skill dice **cómo** cumplirla.
La memoria (`../memoria`) solo lee `evidencias/` con `/importar-evidencias`; su agente `analista-resultados`
rechaza como bloqueante cualquier experimento sin partición, semilla o control de fuga verificables.

## Procedimiento de exportación

1. Ensayo primero: todo script que exporte acepta `--salida <carpeta>` y se prueba fuera de `evidencias/`
   (en la carpeta temporal de la sesión).
2. Commit del código. El script aborta si `--salida` es `evidencias/` y `git status --porcelain` no está vacío.
3. Ejecución real hacia `evidencias/`. El JSON registra `commit` (corto) y `fecha` ISO.
4. Revisión: `/exportar-evidencias` valida el contrato; antes de exportar resultados de modelos, `/auditar-fuga`.
5. El estudiante confirma las evidencias en un commit propio (mensaje `Evidencias: <qué> (<id>)`, como en el historial).

## Identificadores y nombres

- Experimento: `exp-AAAA-MM-DD-NN` (NN correlativo del día, desde 01). Nunca se reutiliza ni se sobrescribe un id:
  un experimento citado en la memoria no se borra; se añade otro.
- Figuras: `figuras/<id>_<nombre>.png`, 300 ppp, títulos y ejes en español, legibles en escala de grises.
- Capturas: `capturas/<vista>.png` con nombre descriptivo. Diagramas: `arquitectura/<nombre>.png|svg` + fuente
  (`.mmd`, `.puml` o `.drawio`). Pruebas: `pruebas/<id>_<suite>.xml|json`.

## Código reutilizable

`ml/exploracion_oulad.py` ya implementa: `git`, `comprobar_arbol_limpio`, `siguiente_id`, `sha256`,
`versiones_entorno` y `actualizar_manifest`. Cuando se escriba el **segundo** script que exporte, se extraen a un
módulo común (`ml/evidencias.py`) y ambos scripts lo importan; no se copian. `versiones_entorno` debe ampliarse con
cada biblioteca que use el script (scikit-learn, xgboost, lightgbm, catboost, optuna, shap…).

## Campos obligatorios por tipo

Todos: `id`, `tipo`, `fecha`, `commit`, `descripcion`, `entorno`, `tiempo_ejecucion_s`, `figuras`, y en `dataset`
el `sha256` de cada archivo de entrada. Los campos de cada tipo están en `CONTRATO.md`.

## Comprobaciones antes de dar una exportación por buena

- [ ] El JSON es válido, UTF-8, `ensure_ascii=False`, con sangría 2.
- [ ] Ningún valor se ha escrito a mano: todo sale del script.
- [ ] Toda figura citada en `figuras` existe y está en `manifest.json` con descripción y experimento.
- [ ] `manifest.json` lista el experimento y su `commit` coincide con el del JSON más reciente.
- [ ] Ningún dato personal real; OULAD está anonimizado (CC-BY 4.0, Kuzilek et al., 2017).
- [ ] Si el experimento evalúa en prueba: la configuración estaba declarada en un commit anterior (skill `rigor-ml`, §2).
