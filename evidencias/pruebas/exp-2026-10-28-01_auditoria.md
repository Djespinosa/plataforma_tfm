# Auditoría de fugas del experimento exp-2026-10-28-01

**Fecha:** 2026-10-28
**Auditor:** agente `revisor-fuga` (solo lectura; no escribió el código y no modificó ningún archivo del repositorio)
**Commit auditado:** `20ebcfa` (código registrado en el JSON), con las salidas de la exportación todavía sin confirmar
**Veredicto:** **apto con observaciones.** No hay hallazgos críticos ni mayores.

## Alcance

- Experimento: variante D8 con variables sensibles y sin nueva búsqueda (D38): `evidencias/experimentos/exp-2026-10-28-01.json`, `evidencias/figuras/exp-2026-10-28-01_coste_excluir_sensibles.png`, `evidencias/pruebas/exp-2026-10-28-01_pruebas.xml` y `evidencias/manifest.json`.
- Código: `ml/variante.py`, `ml/configs/con_sensibles.json`, `ml/experimento.py` y `ml/automl/{calibracion,apilamiento,particion,preprocesado,comparacion,busqueda}.py`.
- Datos no versionados, solo lectura: los 4 parquet OOF de exp-2026-10-27-01 («sin») y los 4 de exp-2026-10-28-01 («con») en `data/procesado/oof/`, y los cortes en `data/procesado/cortes/`.
- Referencias normativas: `decisiones.md` de la memoria (D8, D8-concreción-rev, D38, D48, D49, D52, D54), `.claude/skills/rigor-ml/SKILL.md` y `evidencias/CONTRATO.md`.

**Cómo se trabajó.** En `HEAD` = `20ebcfa`, las únicas diferencias del árbol son las salidas de la exportación. La RL de la semana 0 se reprodujo con un script temporal fuera del repositorio.

## Comprobaciones realizadas y resultado

| # | Comprobación | Resultado |
|---|---|---|
| 1 | 2014J fuera de toda decisión | Se cumple. `cargar_entrenamiento` (`ml/experimento.py:101`) lee con `filters=[("particion","==","entrenamiento")]`. Los cortes contienen filas de prueba (por ejemplo, 10 147 en la semana 0, todas con `pliegue` NA), pero ninguna llega a los OOF, que solo contienen 2013B, 2013J y 2014B, sin `pliegue` NA. `divisiones()` (`ml/automl/particion.py:14`) falla si hay filas con `pliegue` NA. `variante.py` no usa `retiros_prueba`, así que no usa recuentos de 2014J. `evaluado_en_prueba: false` y `metricas_test: null`, con su motivo. La configuración se confirmó en `193340c` (2026-10-27 20:06), antes de la ejecución (2026-10-28 09:38). |
| 2 | Variables y codificación | Correctas. Son las columnas del principal más `gender`, `disability`, `age_band` e `imd_band`, todas estáticas (`studentInfo`, `desde_semana` 0). No entra ninguna variable prohibida (`final_result`, `date_unregistration`, notas de TMA, `code_presentation`). La imputación constante «faltante» (`imd_band` tiene 670 vacíos en la semana 0) y `OneHotEncoder(handle_unknown="ignore")` van dentro del `Pipeline` y se ajustan por pliegue (`ml/automl/preprocesado.py:60-72`). Entre `e49f339` y `20ebcfa` el único cambio del modelado es el nombre de las columnas one-hot (`nombre_columna`), que no cambia los valores. |
| 3 | Mismos pliegues, filas, semillas e hiperparámetros; predicciones «sin» del principal | Se cumple. El script comprueba el SHA-256 de los OOF del principal antes de entrenar (`ml/variante.py:201-206`). Recalculados, coinciden los 4 parquet «sin» y los 4 «con». La alineación fila a fila incluye `pliegue` y `etiqueta` (`variante.py:98-103`) y es idéntica en los 4 momentos. Hay 5 pliegues de 3 presentaciones cada uno, sin presentaciones repetidas. `n` y `retiros` (19 023/4 111, 18 304/3 320, 17 629/2 641, 17 146/2 154) coinciden con el principal y con exp-2026-10-23-02. Las semillas son 42/42/42 y los hiperparámetros de las 7 familias en los 4 momentos son idénticos a los del principal. |
| 4 | Reproducción independiente | **Exacta.** La RL de la semana 0, reentrenada con el código actual, reproduce `p_rl` de exp-2026-10-27-01 (sin sensibles) y de exp-2026-10-28-01 (con sensibles) con diferencia máxima 0,0, tanto calibradas como sin calibrar. Por tanto, «con − sin» solo mide el cambio de entrada. |
| 5 | Calibración anidada D54 | Sin fugas. `oof_anidado` (`ml/automl/calibracion.py:46-54`) ajusta el modelo y `CalibratedClassifierCV(cv=divisiones internas agrupadas, ensemble=False)` solo con los 4 pliegues de ajuste, y predice el pliegue externo. El método se elige por Brier OOF, solo con validación. |
| 6 | Apilamiento D48/D52 | Sin fugas. `oof_apilamiento` (`ml/automl/apilamiento.py:123-125`) ajusta los modelos base y el metamodelo solo con los pliegues de ajuste, con divisiones internas agrupadas que se pasan como `cv`. Los modelos base van sin calibrar y la salida no recibe calibración adicional (D52). |
| 7 | Bootstrap pareado y DeLong | Correctos. El bootstrap usa los mismos índices para «con» y «sin» (`ml/automl/comparacion.py:56-60`), 2000 réplicas y semilla 42. DeLong es pareado y usa la implementación ya probada. Se recalcularon las 32 ROC-AUC con/sin y todas coinciden con el JSON. En la MLP coinciden además la diferencia, el IC y el *p* en los 4 momentos (por ejemplo, en la semana 4: +0,0181 [0,0123; 0,0242], *p* = 5,26e-9). |
| 8 | Salvaguarda D38 | Bien calculada y **no activada**. `salvaguarda()` (`variante.py:116-127`) compara la estimación puntual con 0,02 en cada candidato (8 por momento) y entre los mejores de cada variante, en cualquier momento, con la diferencia sin redondear (`variante.py:113`). Para elegir los mejores se redondea la AUC (`variante.py:145-147`), pero eso no cambia nada: en la semana 8 la RL (0,69573) supera de verdad al apilamiento (0,69569). La diferencia máxima es +0,0181 (MLP, semana 4). Entre los mejores, las diferencias son 0,0007, 0,0054, 0,0016 y 0,0026. |
| 9 | Contrato y manifiesto | Se cumplen. El JSON incluye `id`, `tipo`, `fecha`, `commit` `20ebcfa`, `dataset` (SHA-256 de las 7 tablas y de los 4 cortes, iguales a los de exp-2026-10-23-02), `variante`, `hiperparametros_de`, `reentrenamiento`, `comparacion`, por momento `{semana, n, retiros, mejor_automl_principal, desplegado_principal, por_modelo, mejores, tiempo_s}`, `salvaguarda_d38`, `entorno` (11 bibliotecas y Python), `hardware` sin nombre del equipo, `n_jobs` con su nivel, `pruebas` (115/0/0) y `motivos_null`. Los únicos `null` son `metricas_test` (con motivo) y valores `class_weight` de hiperparámetros. El manifiesto solo añade el experimento, la figura y el JUnit, y actualiza la fecha y el commit. |
| 10 | `pytest ml/tests` en `20ebcfa` | **115 superadas, 0 fallidas, 0 omitidas** (JUnit `pruebas/exp-2026-10-28-01_pruebas.xml`). |
| 11 | Datos personales | Se cumple. El JSON, el manifiesto y el JUnit no contienen `hostname`, nombres de usuario ni de equipo, ni correos. |

## Hallazgos

### Críticos
Ninguno.

### Mayores
Ninguno.

### Menores

**m1. Figura: escala del eje x distinta en cada panel y marcas solapadas** (`ml/variante.py:162`, `sharey=True` sin `sharex`; `evidencias/figuras/exp-2026-10-28-01_coste_excluir_sensibles.png`).
- Evidencia: cada semana tiene su propio rango (de −0,025 a 0,02 en la semana 0 y de −0,005 a 0,025 en la semana 4). En el borde entre las semanas 4 y 8 se lee «0,025−0,010». La comparación «mejor con − mejor sin», que también forma parte de la regla D38, no aparece en la figura.
- Riesgo: no se pueden comparar las magnitudes entre momentos a simple vista. No es una fuga.
- Corrección propuesta: `sharex=True` (o un rango común que incluya 0,02) y una fila «mejores», redibujando desde los OOF con el sufijo `_v2`, como en exp-2026-10-27-01.

**m2. `predicciones_oof_sha256.carpeta` siempre vale lo mismo** (`ml/variante.py:267`).
- Evidencia: siempre registra `data/procesado/oof`, aunque en un `--ensayo` los OOF se escriben en `<salida>/oof` (`variante.py:217`).
- Riesgo: ninguno en esta exportación, que se hizo a `evidencias/`. Solo afecta a los ensayos.
- Corrección propuesta: registrar `carpeta_oof`.

### Observaciones (para declarar en la memoria; no bloquean)

**O1. `decisiones.md` no recoge cómo se aplica D38.** D38 solo dice «si excluirlas cuesta ≥ 0,02 de ROC-AUC». Lo de «estimación puntual, por candidato o entre los mejores, en algún momento» está en la skill `rigor-ml` §2 y en el código confirmado en `193340c`, antes de la ejecución, así que no se fijó a la vista de los resultados. Conviene registrarlo en `decisiones.md` junto con I1-I8 de la auditoría de exp-2026-10-27-01.

**O2. El IC de la MLP en la semana 4 supera el margen.** La estimación puntual es +0,0181 y el IC llega a +0,0242. Con la regla puntual la salvaguarda no se activa, pero no se puede descartar un coste ≥ 0,02 en esa familia, así que no debe presentarse como «el coste es < 0,02 con seguridad». La MLP no es ni el mejor modelo ni el desplegado. La RL, desplegada en los 4 momentos, tiene un coste de +0,0058, +0,0042, +0,0020 y +0,0076. Entre los mejores, el límite superior más alto es 0,0095.

**O3. Ruido de reentrenamiento en la MLP.** Su diferencia cambia de signo con una magnitud parecida (−0,0179 en la semana 0, +0,0181 en la semana 4). Lo más probable es que sea ruido de reentrenamiento y no un efecto de las sensibles: al añadir columnas cambian la dimensión de entrada, la inicialización de los pesos y la partición interna de `early_stopping`, y en los árboles cambia el muestreo de columnas. Ese ruido entra en «con − sin», el IC bootstrap sobre filas no lo recoge, y hace que la regla puntual por candidato dependa del azar en la MLP. Se declara como limitación de D38. Lo de la cota inferior (la búsqueda se hizo sin sensibles) ya está declarado en el JSON.

**O4. El bootstrap remuestrea matrículas de forma independiente.** No tiene en cuenta presentaciones, estudiantes repetidos ni la variabilidad de los 5 modelos (D40), así que los IC pueden ser algo estrechos. Es la misma limitación que en el principal.

**O5. La variante «con» no tiene auditoría por subgrupo.** D8 pide sensibilidad y tasa de falsos positivos por subgrupo, y la variante no exporta `equidad_oof`. El CONTRATO no lo exige para `con_sensibles`, y la equidad de la configuración vigente («sin») está en exp-2026-10-27-01. Si la memoria compara la equidad con y sin sensibles, habrá que calcularla después desde los OOF, con su propio umbral OOF y sin usar 2014J.

**O6. Los parquet OOF no están versionados** (`data/procesado/` está en `.gitignore`), igual que en el principal. La trazabilidad depende de los SHA-256 del JSON, que están completos y se verificaron.

## Veredicto

**Apto con observaciones.**
- No entra información posterior al corte: las variables sensibles son estáticas y se codifican dentro del pipeline de cada pliegue.
- No hay fuga entre pliegues: la calibración D54 y el apilamiento D48 se ajustan solo con los pliegues de ajuste y con divisiones internas agrupadas.
- 2014J no se lee ni interviene en ninguna decisión.
- Pliegues, filas, semillas e hiperparámetros son los del principal, y las predicciones «sin» son las suyas (SHA-256 comprobado y reproducción exacta de la RL).
- La salvaguarda D38 está bien calculada y no se activa (máximo +0,0181).
- El JSON y el manifiesto cumplen el CONTRATO.

m1 y m2 son de presentación y se pueden corregir en otro commit sin reentrenar. O1-O6 se declaran en la memoria, sobre todo O2 y O1.
