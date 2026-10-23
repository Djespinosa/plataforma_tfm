"""Conjuntos de OULAD por momento de predicción (OE2, D10) exportados a evidencias/ según CONTRATO.md.

Reglas (skill rigor-ml §1-2): etiqueta Withdrawn (D2); corte k = día 7k inclusive (D3, D25); población sin
bajas ≤ 7k (D24-D25) ni matrícula tardía (date_registration > 7k); eliminación de D26 y D27; clics y entregas
solo con fecha ≤ 7k; notas solo de CMA; sin notas de TMA ni exámenes; is_banked en variables propias.
La imputación de date_registration (D28) no se hace aquí: va dentro del Pipeline de cada pliegue (ml/automl).

Genera:
  - data/procesado/cortes/semana_<k>.parquet y semana_<k>_sin_exclusion_retirados.parquet (D20), no versionados.
  - Experimento de tipo "cortes": población, prevalencia y exclusiones por corte y partición, pliegues,
    solapamiento, subgrupos sensibles, recuentos de evaluaciones, catálogo de variables y pruebas anti-fuga.

Uso:
    python ml/cortes_oulad.py
    python ml/cortes_oulad.py --salida /tmp/prueba   # ensayo fuera de evidencias/
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import matplotlib.ticker  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from evidencias import (  # noqa: E402
    DATOS,
    EVIDENCIAS,
    RAIZ,
    actualizar_manifest,
    comprobar_arbol_limpio,
    escribir_json,
    sha256,
    siguiente_id,
    versiones_entorno,
)

SEMANAS = [0, 4, 8, 12]
PRESENTACION_PRUEBA = "2014J"
N_PLIEGUES = 5
SEMILLA_PLIEGUES = 42
PROCESADO = RAIZ / "data" / "procesado" / "cortes"
EXPLORACION_REFERENCIA = EVIDENCIAS / "experimentos" / "exp-2026-10-05-02.json"
ARCHIVOS_ENTRADA = [
    "courses.csv", "studentInfo.csv", "studentRegistration.csv", "assessments.csv",
    "studentAssessment.csv", "vle.csv", "studentVle.csv",
]
CLAVES = ["code_module", "code_presentation", "id_student"]
# Columnas del corte que no son entrada del modelo (code_module es clave y también variable).
NO_VARIABLES = ["code_presentation", "id_student", "presentacion", "particion", "pliegue", "etiqueta"]
SENSIBLES = ["gender", "disability", "age_band", "imd_band"]
DPI = 300

GRUPOS = ["demograficas_matricula", "aula_virtual", "evaluaciones", "contexto_modulo"]
EXCLUIDAS = [
    ("id_student", "studentInfo", "identificador"),
    ("code_presentation", "studentInfo", "identificador (la información útil está en tipo_presentacion)"),
    ("final_result", "studentInfo", "etiqueta (D2)"),
    ("date_unregistration", "studentRegistration", "fuga: fecha de baja (D3)"),
    ("score de TMA", "studentAssessment", "fuga: corrección por tutor con retraso; OULAD no registra la publicación"),
    ("evaluaciones de tipo Exam", "assessments", "posteriores a la semana 12"),
    ("weight", "assessments", "no usado"),
    ("week_from, week_to", "vle", "no usado"),
]


def cargar_tablas(datos: Path = DATOS) -> dict[str, pd.DataFrame]:
    tablas = {
        archivo.removesuffix(".csv"): pd.read_csv(datos / archivo, na_values="?")
        for archivo in ARCHIVOS_ENTRADA
    }
    # Único tramo de imd_band escrito sin "%" en OULAD.
    tablas["studentInfo"]["imd_band"] = tablas["studentInfo"]["imd_band"].replace({"10-20": "10-20%"})
    return tablas


def matriculas(tablas: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Unión 1:1 de studentInfo y studentRegistration con la duración del módulo, sin eliminaciones."""
    union = tablas["studentInfo"].merge(tablas["studentRegistration"], on=CLAVES, validate="1:1").merge(
        tablas["courses"], on=["code_module", "code_presentation"], validate="m:1"
    )
    union["presentacion"] = union["code_module"] + "_" + union["code_presentation"]
    union["tipo_presentacion"] = union["code_presentation"].str[-1]
    union["particion"] = np.where(
        union["code_presentation"] == PRESENTACION_PRUEBA, "prueba", "entrenamiento"
    )
    union["etiqueta"] = (union["final_result"] == "Withdrawn").astype(int)
    return union


def reglas_eliminacion(union: pd.DataFrame) -> dict[str, pd.Series]:
    con_baja = union["date_unregistration"].notna()
    return {
        "D26_withdrawn_sin_fecha_baja": (union["final_result"] == "Withdrawn") & ~con_baja,
        "D27_fail_con_fecha_baja": (union["final_result"] == "Fail") & con_baja,
    }


def poblacion_base(union: pd.DataFrame) -> pd.DataFrame:
    eliminar = np.logical_or.reduce(list(reglas_eliminacion(union).values()))
    return union[~eliminar].reset_index(drop=True)


def asignar_pliegues(base: pd.DataFrame) -> dict[str, int]:
    """D29-rev: permutación con semilla de las presentaciones de entrenamiento, 3 por pliegue."""
    presentaciones = sorted(base.loc[base["particion"] == "entrenamiento", "presentacion"].unique())
    if len(presentaciones) % N_PLIEGUES:
        raise ValueError(f"{len(presentaciones)} presentaciones no se reparten en {N_PLIEGUES} pliegues iguales")
    orden = np.random.default_rng(SEMILLA_PLIEGUES).permutation(presentaciones)
    tamano = len(presentaciones) // N_PLIEGUES
    return {p: i // tamano + 1 for i, p in enumerate(orden)}


def exclusiones(base: pd.DataFrame, dia: int, excluir_retirados: bool = True) -> tuple[pd.Series, pd.Series]:
    """Máscaras disjuntas: baja (≤ día del corte, o < 0 en D20) y, entre el resto, matrícula tardía.

    Sin date_registration se considera matriculado antes del inicio (comparación con NaN es falsa).
    """
    baja_fecha = base["date_unregistration"]
    baja = baja_fecha <= dia if excluir_retirados else baja_fecha < 0
    tardia = ~baja & (base["date_registration"] > dia)
    return baja, tardia


def tipos_actividad(vle: pd.DataFrame) -> list[str]:
    """Tipos de actividad de las presentaciones de entrenamiento: 2014J no decide qué columnas existen.

    Los clics de 2014J en tipos que no existen en entrenamiento cuentan igualmente en clics_total.
    """
    return sorted(vle.loc[vle["code_presentation"] != PRESENTACION_PRUEBA, "activity_type"].unique())


def preparar_clics(tablas: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Clics diarios por matrícula y tipo de actividad (sin filtrar por fecha: se filtra en cada corte)."""
    clics = tablas["studentVle"].merge(
        tablas["vle"][["id_site", "activity_type"]], on="id_site", validate="m:1"
    )
    return clics.groupby([*CLAVES, "date", "activity_type"], as_index=False)["sum_click"].sum()


def preparar_entregas(tablas: dict[str, pd.DataFrame]) -> pd.DataFrame:
    entregas = tablas["studentAssessment"].merge(tablas["assessments"], on="id_assessment", validate="m:1")
    return entregas[entregas["assessment_type"] != "Exam"]


def variables_estaticas(pob: pd.DataFrame) -> pd.DataFrame:
    estaticas = pob[[
        "code_module", "tipo_presentacion", "module_presentation_length", "gender", "region",
        "highest_education", "imd_band", "age_band", "num_of_prev_attempts", "studied_credits",
        "disability", "date_registration",
    ]].copy()
    estaticas["falta_date_registration"] = pob["date_registration"].isna().astype(int)
    return estaticas


def variables_aula_virtual(pob: pd.DataFrame, clics: pd.DataFrame, dia: int, tipos: list[str]) -> pd.DataFrame:
    filtrados = clics[clics["date"] <= dia]
    por_matricula = filtrados.groupby(CLAVES)
    salida = pd.DataFrame({
        "clics_total": por_matricula["sum_click"].sum(),
        "dias_activos": por_matricula["date"].nunique(),
        "ultima_actividad": por_matricula["date"].max(),
    })
    por_tipo = filtrados.pivot_table(
        index=CLAVES, columns="activity_type", values="sum_click", aggfunc="sum", fill_value=0
    ).reindex(columns=tipos, fill_value=0)
    por_tipo.columns = [f"clics_{t}" for t in por_tipo.columns]
    ventanas = {}
    for j in range(1, 5):  # ventana 1 = días (7k-6 .. 7k); ventana 4 = la más antigua
        en_ventana = filtrados[filtrados["date"] > dia - 7 * j]
        en_ventana = en_ventana[en_ventana["date"] <= dia - 7 * (j - 1)]
        ventanas[f"clics_ventana_{j}"] = en_ventana.groupby(CLAVES)["sum_click"].sum()
    recientes = filtrados[filtrados["date"] > dia - 28]
    salida = salida.join(por_tipo).join(pd.DataFrame(ventanas)).join(
        (recientes.groupby(CLAVES)["date"].nunique() / 28).rename("proporcion_dias_activos_28d")
    )
    salida = pob[CLAVES].join(salida, on=CLAVES).drop(columns=CLAVES)
    columnas_conteo = [c for c in salida.columns if c.startswith("clics_") or c in ("dias_activos", "proporcion_dias_activos_28d")]
    salida[columnas_conteo] = salida[columnas_conteo].fillna(0)
    salida["sin_actividad"] = (salida["clics_total"] == 0).astype(int)
    salida["dias_desde_ultima_actividad"] = dia - salida.pop("ultima_actividad")

    serie = salida[[f"clics_ventana_{j}" for j in (4, 3, 2, 1)]].to_numpy(dtype=float)
    x = np.arange(4) - 1.5
    salida["tendencia_4s"] = (serie - serie.mean(axis=1, keepdims=True)) @ x / (x @ x)
    media = serie.mean(axis=1)
    with np.errstate(invalid="ignore", divide="ignore"):
        salida["cv_clics_4s"] = np.where(media > 0, serie.std(axis=1) / media, np.nan)

    # Cohorte: la población elegible de la misma presentación en este corte, con datos ≤ día del corte.
    grupo = pob["presentacion"].to_numpy()
    for columna in ("clics_total", "dias_activos", "clics_ventana_1"):
        salida[f"percentil_{columna}_cohorte"] = salida[columna].groupby(grupo).rank(pct=True)
    return salida


def variables_evaluaciones(pob: pd.DataFrame, entregas: pd.DataFrame, assessments: pd.DataFrame, dia: int) -> pd.DataFrame:
    convalidadas = entregas[entregas["is_banked"] == 1]
    propias = entregas[entregas["is_banked"] == 0]

    vencidas = assessments[(assessments["assessment_type"] != "Exam") & (assessments["date"] <= dia)]
    n_vencidas_presentacion = vencidas.groupby(["code_module", "code_presentation"]).size()
    # Una evaluación convalidada no se entrega en esta presentación: no cuenta como pendiente.
    convalidadas_vencidas = convalidadas[convalidadas["date"] <= dia].groupby(CLAVES).size()

    entregadas = propias[(propias["date"] <= dia) & (propias["date_submitted"] <= dia)]
    por_matricula = entregadas.assign(
        antelacion=entregadas["date"] - entregadas["date_submitted"],
        tardia=(entregadas["date_submitted"] > entregadas["date"]).astype(int),
    ).groupby(CLAVES)
    cma = propias[(propias["assessment_type"] == "CMA") & (propias["date_submitted"] <= dia)].groupby(CLAVES)

    salida = pd.DataFrame({
        "n_entregadas": por_matricula.size(),
        "antelacion_media": por_matricula["antelacion"].mean(),
        "n_entregas_tardias": por_matricula["tardia"].sum(),
        "n_cma_calificadas": cma["score"].count(),
        "nota_media_cma": cma["score"].mean(),
        "n_convalidadas": convalidadas.groupby(CLAVES).size(),
        "nota_media_convalidada": convalidadas.groupby(CLAVES)["score"].mean(),
        "_convalidadas_vencidas": convalidadas_vencidas,
    })
    salida = pob[CLAVES].join(salida, on=CLAVES)
    conteos = ["n_entregadas", "n_entregas_tardias", "n_cma_calificadas", "n_convalidadas", "_convalidadas_vencidas"]
    salida[conteos] = salida[conteos].fillna(0)
    salida["n_evaluaciones_vencidas"] = (
        salida[["code_module", "code_presentation"]].join(
            n_vencidas_presentacion.rename("n"), on=["code_module", "code_presentation"]
        )["n"].fillna(0)
        - salida.pop("_convalidadas_vencidas")
    )
    with np.errstate(invalid="ignore", divide="ignore"):
        salida["proporcion_entregadas"] = np.where(
            salida["n_evaluaciones_vencidas"] > 0,
            salida["n_entregadas"] / salida["n_evaluaciones_vencidas"],
            np.nan,
        )
    return salida.drop(columns=CLAVES)


def construir_corte(
    union: pd.DataFrame,
    pliegues: dict[str, int],
    clics: pd.DataFrame,
    entregas: pd.DataFrame,
    assessments: pd.DataFrame,
    tipos: list[str],
    semana: int,
    excluir_retirados: bool = True,
) -> pd.DataFrame:
    """Recibe las matrículas sin eliminaciones: la cohorte de los percentiles incluye las que D26/D27 eliminan
    después, porque en despliegue estarían (eliminarlas antes usaría final_result)."""
    dia = 7 * semana
    baja, tardia = exclusiones(union, dia, excluir_retirados)
    pob = union[~baja & ~tardia].sort_values(CLAVES).reset_index(drop=True)
    corte = pd.concat(
        [
            pob[[*CLAVES, "presentacion", "particion", "etiqueta"]],
            pob["presentacion"].map(pliegues).astype("Int64").rename("pliegue"),
            variables_estaticas(pob),
            variables_aula_virtual(pob, clics, dia, tipos),
            variables_evaluaciones(pob, entregas, assessments, dia),
        ],
        axis=1,
    )
    corte = corte.loc[:, ~corte.columns.duplicated()]
    eliminar = np.logical_or.reduce(list(reglas_eliminacion(pob).values()))
    return corte[~eliminar].reset_index(drop=True)


def catalogo_variables(tipos: list[str]) -> pd.DataFrame:
    def fila(nombre, origen, tipo, calculo, grupo, desde=0):
        return {"nombre": nombre, "tabla_origen": origen, "tipo": tipo, "desde_semana": desde,
                "calculo": calculo, "grupo_ablacion": grupo, "sensible": nombre in SENSIBLES, "motivo_exclusion": ""}

    filas = [
        fila("code_module", "studentInfo", "categórica", "módulo", "contexto_modulo"),
        fila("tipo_presentacion", "studentInfo", "categórica", "B o J (último carácter de code_presentation)", "contexto_modulo"),
        fila("module_presentation_length", "courses", "numérica", "duración planificada en días", "contexto_modulo"),
        *[fila(c, "studentInfo", "categórica", "valor declarado en la matrícula", "demograficas_matricula")
          for c in ["gender", "region", "highest_education", "imd_band", "age_band", "disability"]],
        fila("num_of_prev_attempts", "studentInfo", "numérica", "intentos previos del módulo", "demograficas_matricula"),
        fila("studied_credits", "studentInfo", "numérica", "créditos matriculados", "demograficas_matricula"),
        fila("date_registration", "studentRegistration", "numérica",
             "día de matrícula relativo al inicio; faltantes imputados por la mediana del pliegue (D28, en el Pipeline)",
             "demograficas_matricula"),
        fila("falta_date_registration", "studentRegistration", "binaria", "1 si date_registration falta (D28)", "demograficas_matricula"),
        fila("clics_total", "studentVle", "numérica", "suma de sum_click con date ≤ 7k (incluye días previos al inicio)", "aula_virtual"),
        fila("dias_activos", "studentVle", "numérica", "días distintos con clics y date ≤ 7k", "aula_virtual"),
        *[fila(f"clics_{t}", "studentVle + vle", "numérica", f"suma de sum_click en actividades {t} con date ≤ 7k", "aula_virtual")
          for t in tipos],
        *[fila(f"clics_ventana_{j}", "studentVle", "numérica",
               f"suma de sum_click con date en ({7}k − {7 * j}, 7k − {7 * (j - 1)}]", "aula_virtual") for j in range(1, 5)],
        fila("proporcion_dias_activos_28d", "studentVle", "numérica", "días activos en (7k − 28, 7k] / 28 (regularidad)", "aula_virtual"),
        fila("sin_actividad", "studentVle", "binaria", "1 si no hay clics con date ≤ 7k", "aula_virtual"),
        fila("dias_desde_ultima_actividad", "studentVle", "numérica", "7k − última date con clics ≤ 7k; vacía si no hay", "aula_virtual"),
        fila("tendencia_4s", "studentVle", "numérica", "pendiente MCO de clics_ventana_4..1 (tendencia semanal)", "aula_virtual"),
        fila("cv_clics_4s", "studentVle", "numérica", "desviación / media de las 4 ventanas (regularidad); vacía si media 0", "aula_virtual"),
        *[fila(f"percentil_{c}_cohorte", "studentVle", "numérica",
               f"percentil de {c} en la población elegible de la misma presentación en el corte (datos ≤ 7k)", "aula_virtual")
          for c in ("clics_total", "dias_activos", "clics_ventana_1")],
        fila("n_evaluaciones_vencidas", "assessments", "numérica",
             "evaluaciones no Exam con date ≤ 7k, sin contar las convalidadas del estudiante", "evaluaciones"),
        fila("n_entregadas", "studentAssessment", "numérica",
             "entregas no convalidadas con date ≤ 7k y date_submitted ≤ 7k", "evaluaciones"),
        fila("proporcion_entregadas", "studentAssessment", "numérica", "n_entregadas / n_evaluaciones_vencidas; vacía si 0 vencidas", "evaluaciones"),
        fila("antelacion_media", "studentAssessment", "numérica", "media de date − date_submitted de las entregadas", "evaluaciones"),
        fila("n_entregas_tardias", "studentAssessment", "numérica", "entregadas con date_submitted > date", "evaluaciones"),
        fila("n_cma_calificadas", "studentAssessment", "numérica",
             "CMA no convalidadas con date_submitted ≤ 7k y nota (supuesto: nota disponible al entregar)", "evaluaciones"),
        fila("nota_media_cma", "studentAssessment", "numérica", "media de score de esas CMA", "evaluaciones"),
        fila("n_convalidadas", "studentAssessment", "numérica",
             "filas is_banked = 1 (intento previo, date_submitted = −1; disponibles desde la semana 0)", "evaluaciones"),
        fila("nota_media_convalidada", "studentAssessment", "numérica", "media de score de las convalidadas (CMA y TMA)", "evaluaciones"),
    ]
    excluidas = [
        {"nombre": n, "tabla_origen": o, "tipo": "", "desde_semana": "", "calculo": "", "grupo_ablacion": "",
         "sensible": False, "motivo_exclusion": m}
        for n, o, m in EXCLUIDAS
    ]
    return pd.DataFrame(filas + excluidas)


def resumen_poblacion(pob: pd.DataFrame) -> dict:
    n = len(pob)
    desercion = int(pob["etiqueta"].sum())
    return {"n": n, "desercion": desercion, "no_desercion": n - desercion,
            "prevalencia": round(desercion / n, 4) if n else None}


def resumen_corte(base: pd.DataFrame, dia: int, excluir_retirados: bool) -> dict:
    baja, tardia = exclusiones(base, dia, excluir_retirados)
    pob = base[~baja & ~tardia]
    salida = {}
    for particion in ("entrenamiento", "prueba"):
        en = base["particion"] == particion
        bloque = resumen_poblacion(pob[pob["particion"] == particion]) | {
            "excluidos_baja": int((baja & en).sum()),
            "excluidos_matricula_tardia": int((tardia & en).sum()),
        }
        for nombre, mascara in (("CCC", base["code_module"] == "CCC"), ("resto", base["code_module"] != "CCC")):
            sub = en & mascara
            bloque[nombre] = resumen_poblacion(pob[(pob["particion"] == particion) & mascara[pob.index]]) | {
                "excluidos_baja": int((baja & sub).sum()),
                "excluidos_matricula_tardia": int((tardia & sub).sum()),
            }
        salida[particion] = bloque
    return salida


def proporcion_curso(cursos: pd.DataFrame, dia: int) -> dict:
    proporcion = dia / cursos["module_presentation_length"]
    tipo = cursos["code_presentation"].str[-1]
    return {
        t: {"media": round(float(proporcion[tipo == t].mean()), 4), "min": round(float(proporcion[tipo == t].min()), 4),
            "max": round(float(proporcion[tipo == t].max()), 4)}
        for t in ("B", "J")
    }


def subgrupos(corte: pd.DataFrame) -> list[dict]:
    filas = []
    for particion, datos in corte.groupby("particion"):
        for variable in SENSIBLES:
            for valor, grupo in datos.groupby(datos[variable].fillna("faltante")):
                filas.append({"particion": particion, "variable": variable, "valor": valor} | resumen_poblacion(grupo))
    return filas


def recuentos_evaluaciones(tablas: dict[str, pd.DataFrame]) -> dict:
    todas = tablas["studentAssessment"].merge(tablas["assessments"], on="id_assessment", validate="m:1")
    convalidadas = todas[todas["is_banked"] == 1]
    tma_propias = todas[(todas["is_banked"] == 0) & (todas["assessment_type"] == "TMA") & todas["score"].notna()]
    return {
        "filas_is_banked": int(len(convalidadas)),
        "matriculas_is_banked": int(convalidadas[CLAVES].drop_duplicates().shape[0]),
        "date_submitted_is_banked": sorted(int(v) for v in convalidadas["date_submitted"].unique()),
        "filas_examen_excluidas": int((todas["assessment_type"] == "Exam").sum()),
        "notas_tma_descartadas_total": int(len(tma_propias)),
        "notas_tma_descartadas_por_corte": {
            str(s): int((tma_propias["date_submitted"] <= 7 * s).sum()) for s in SEMANAS
        },
    }


def comprobar_calidad(union: pd.DataFrame) -> None:
    """Los recuentos de calidad deben coincidir con los de la exploración de referencia."""
    referencia = json.loads(EXPLORACION_REFERENCIA.read_text(encoding="utf-8"))["calidad_datos"]
    reglas = reglas_eliminacion(union)
    antes_dia_0 = union["date_unregistration"] < 0
    comprobaciones = {
        "D26_withdrawn_sin_fecha_baja": (int(reglas["D26_withdrawn_sin_fecha_baja"].sum()), referencia["withdrawn_sin_fecha_baja"]),
        "D27_fail_con_fecha_baja": (int(reglas["D27_fail_con_fecha_baja"].sum()), referencia["fail_con_fecha_baja"]),
        "matriculas_sin_fecha_registro": (int(union["date_registration"].isna().sum()), referencia["matriculas_sin_fecha_registro"]),
        "bajas_antes_dia_0": (int(antes_dia_0.sum()), referencia["bajas_antes_dia_0"]["total"]),
        f"bajas_antes_dia_0_{PRESENTACION_PRUEBA}": (
            int((antes_dia_0 & (union["code_presentation"] == PRESENTACION_PRUEBA)).sum()),
            referencia["bajas_antes_dia_0"][PRESENTACION_PRUEBA],
        ),
    }
    for nombre, (obtenido, esperado) in comprobaciones.items():
        if obtenido != esperado:
            raise ValueError(f"{nombre}: {obtenido}, la exploración de referencia registró {esperado}")


def ejecutar_pruebas(ruta_xml: Path) -> dict:
    import pytest

    codigo = pytest.main([str(RAIZ / "ml" / "tests"), "-q", f"--junitxml={ruta_xml}"])
    arbol = ET.parse(ruta_xml)
    raiz = arbol.getroot()
    # El nombre del equipo no debe llegar al repositorio público.
    for elemento in raiz.iter("testsuite"):
        elemento.attrib.pop("hostname", None)
    arbol.write(ruta_xml, encoding="utf-8", xml_declaration=True)
    suite = raiz if raiz.tag == "testsuite" else raiz.find("testsuite")
    total, fallos, errores, omitidas = (int(suite.get(k, 0)) for k in ("tests", "failures", "errors", "skipped"))
    if codigo != 0 or omitidas:
        sys.exit(f"Pruebas fallidas u omitidas (código {codigo}, omitidas {omitidas}); no se exporta. Informe: {ruta_xml}")
    return {"superadas": total - fallos - errores - omitidas, "fallidas": fallos + errores, "omitidas": omitidas}


def figura_poblacion(cortes: list[dict], ruta: Path) -> None:
    fig, (ax_n, ax_p) = plt.subplots(1, 2, figsize=(11, 4.5))
    semanas = [c["semana"] for c in cortes]
    for particion, estilo in (("entrenamiento", "o-"), ("prueba", "s--")):
        ax_n.plot(semanas, [c["por_particion"][particion]["n"] for c in cortes], estilo, color="black", label=particion)
        ax_p.plot(semanas, [c["por_particion"][particion]["prevalencia"] for c in cortes], estilo, color="black", label=particion)
    ax_n.set_ylabel("Matrículas en la población en riesgo")
    ax_p.set_ylabel("Prevalencia de Withdrawn")
    ax_p.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0))
    for ax in (ax_n, ax_p):
        ax.set_xlabel("Semana del corte (día 7k)")
        ax.set_xticks(semanas)
        ax.grid(alpha=0.3)
        ax.legend(title="Partición")
    fig.suptitle("Población en riesgo y prevalencia por corte (OULAD)")
    fig.tight_layout()
    fig.savefig(ruta, dpi=DPI)
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--salida", type=Path, default=EVIDENCIAS, help="Carpeta de evidencias (por defecto evidencias/)")
    args = parser.parse_args()

    inicio = time.perf_counter()
    salida: Path = args.salida
    commit = comprobar_arbol_limpio(salida)
    fecha = datetime.now()
    for carpeta in ("experimentos", "figuras", "pruebas"):
        (salida / carpeta).mkdir(parents=True, exist_ok=True)
    id_exp = siguiente_id(salida / "experimentos", fecha)

    archivo_pruebas = f"pruebas/{id_exp}_antifuga.xml"
    resultado_pruebas = ejecutar_pruebas(salida / archivo_pruebas)

    tablas = cargar_tablas()
    union = matriculas(tablas)
    comprobar_calidad(union)
    base = poblacion_base(union)
    pliegues = asignar_pliegues(base)
    clics = preparar_clics(tablas)
    entregas = preparar_entregas(tablas)
    tipos = tipos_actividad(tablas["vle"])
    catalogo = catalogo_variables(tipos)
    variables = catalogo.loc[catalogo["motivo_exclusion"] == "", "nombre"].tolist()

    # Un ensayo no sobrescribe los cortes que usará el modelado.
    procesado = PROCESADO if salida.resolve() == EVIDENCIAS.resolve() else salida / "procesado"
    procesado.mkdir(parents=True, exist_ok=True)
    salidas_sha256 = {}
    resumen_cortes, resumen_d20, tabla_subgrupos, tamano_pliegues = [], [], [], []
    for semana in SEMANAS:
        dia = 7 * semana
        for excluir, sufijo in ((True, ""), (False, "_sin_exclusion_retirados")):
            corte = construir_corte(union, pliegues, clics, entregas, tablas["assessments"], tipos, semana, excluir)
            if sorted(set(corte.columns) - set(NO_VARIABLES)) != sorted(variables):
                raise ValueError("Las columnas del corte no coinciden con el catálogo de variables")
            ruta_corte = procesado / f"semana_{semana}{sufijo}.parquet"
            corte.to_parquet(ruta_corte, index=False)
            salidas_sha256[ruta_corte.name] = sha256(ruta_corte)
            if excluir:
                tabla_subgrupos += [{"semana": semana} | f for f in subgrupos(corte)]
                entrenamiento = corte[corte["particion"] == "entrenamiento"]
                tamano_pliegues += [
                    {"semana": semana, "pliegue": int(p)} | resumen_poblacion(g)
                    for p, g in entrenamiento.groupby("pliegue")
                ]
        comun = {"semana": semana, "dia_corte": dia}
        resumen_cortes.append(comun | {
            "proporcion_curso": proporcion_curso(tablas["courses"], dia),
            "n_variables": len(variables),
            "variables_por_grupo": catalogo[catalogo["motivo_exclusion"] == ""].groupby("grupo_ablacion").size().astype(int).to_dict(),
            "por_particion": resumen_corte(base, dia, excluir_retirados=True),
        })
        resumen_d20.append(comun | {"por_particion": resumen_corte(base, dia, excluir_retirados=False)})

    archivo_catalogo = f"experimentos/{id_exp}_catalogo_variables.csv"
    catalogo.to_csv(salida / archivo_catalogo, index=False, encoding="utf-8")
    figuras = [(f"figuras/{id_exp}_poblacion_prevalencia_por_corte.png",
                "Población en riesgo y prevalencia de Withdrawn por corte y partición en OULAD")]
    figura_poblacion(resumen_cortes, salida / figuras[0][0])

    entrenamiento = base[base["particion"] == "entrenamiento"]
    pliegue_estudiante = entrenamiento.assign(pliegue=entrenamiento["presentacion"].map(pliegues))
    estudiantes_por_pliegues = pliegue_estudiante.groupby("id_student")["pliegue"].nunique()
    reglas = reglas_eliminacion(union)

    experimento = {
        "id": id_exp,
        "tipo": "cortes",
        "fecha": fecha.isoformat(timespec="seconds"),
        "commit": commit,
        "descripcion": (
            "Preparación de los conjuntos de OULAD por momento de predicción (semanas 0, 4, 8 y 12): población en "
            "riesgo, prevalencia y exclusiones por corte y partición, pliegues, solapamiento, subgrupos sensibles, "
            "recuentos de evaluaciones, catálogo de variables y pruebas anti-fuga. Sin modelos."
        ),
        "dataset": {
            "nombre": "OULAD",
            "version": "2017",
            "licencia": "CC BY 4.0 (Kuzilek et al., 2017)",
            "tablas_usadas": ARCHIVOS_ENTRADA,
            "sha256": {archivo: sha256(DATOS / archivo) for archivo in ARCHIVOS_ENTRADA},
        },
        "reglas": {
            "etiqueta": "D2: final_result == Withdrawn es positivo; Fail, Pass y Distinction negativos",
            "corte": "D3/D25: corte k = día 7k; información hasta ese día inclusive",
            "exclusion_baja": "D24/D25: se excluye date_unregistration ≤ 7k (incluye bajas antes del día 0)",
            "exclusion_matricula_tardia": "se excluye date_registration > 7k; sin date_registration = matriculado antes del inicio",
            "orden_exclusiones": "disjuntas: primero baja; la matrícula tardía se cuenta entre los no excluidos por baja",
            "eliminaciones": "D26: Withdrawn sin date_unregistration; D27: Fail con date_unregistration",
            "imputacion": "D28: date_registration se imputa dentro del Pipeline de cada pliegue (ml/automl), no aquí",
            "evaluaciones": "entrega solo de evaluaciones con date ≤ 7k y date_submitted ≤ 7k; notas solo de CMA "
                            "entregadas hasta el corte; ninguna nota de TMA; exámenes fuera por tipo",
            "is_banked": "filas convalidadas fuera de entrega y notas CMA; variables propias desde la semana 0",
            "supuesto_notas": "OULAD no registra la publicación de las notas; CMA (automática) / TMA (tutor) según "
                              "kuzilek2017; la disponibilidad inmediata de las CMA es una suposición",
            "d20": "sensibilidad a la fuga: solo se excluye date_unregistration < 0; se mantienen matrícula tardía y D26/D27",
            "imd_band": "el tramo '10-20' se normaliza a '10-20%'",
        },
        "eliminaciones": {
            regla: {"total": int(m.sum()), **{p: int((m & (union["particion"] == p)).sum()) for p in ("entrenamiento", "prueba")}}
            for regla, m in reglas.items()
        },
        "bajas_dia_0": {
            momento: {
                "total": int(datos["date_unregistration"].eq(0).sum()),
                **{p: int((datos["date_unregistration"].eq(0) & (datos["particion"] == p)).sum())
                   for p in ("entrenamiento", "prueba")},
            }
            for momento, datos in (("antes_de_eliminaciones", union), ("tras_eliminaciones", base))
        },
        "particion": {
            p: {
                "presentaciones": sorted(base.loc[base["particion"] == p, "presentacion"].unique()),
                "n_matriculas": int((base["particion"] == p).sum()),
                "n_estudiantes_unicos": int(base.loc[base["particion"] == p, "id_student"].nunique()),
            }
            for p in ("entrenamiento", "prueba")
        },
        "pliegues": {
            "estrategia": f"permutación con semilla {SEMILLA_PLIEGUES} de las presentaciones de entrenamiento, "
                          f"{len(pliegues) // N_PLIEGUES} por pliegue (D29-rev)",
            "composicion": {str(k): sorted(p for p, f in pliegues.items() if f == k) for k in range(1, N_PLIEGUES + 1)},
            "por_corte": tamano_pliegues,
        },
        "solapamiento": {
            "estudiantes_en_mas_de_un_pliegue": int((estudiantes_por_pliegues > 1).sum()),
            "estudiantes_en_entrenamiento_y_prueba": int(
                len(set(entrenamiento["id_student"]) & set(base.loc[base["particion"] == "prueba", "id_student"]))
            ),
        },
        "cortes": resumen_cortes,
        "cortes_sin_exclusion_retirados": resumen_d20,
        "subgrupos": tabla_subgrupos,
        "evaluaciones": recuentos_evaluaciones(tablas),
        "n_variables_definicion": "columnas de entrada del modelo (catálogo sin motivo de exclusión), sin "
                                  "identificadores, partición, pliegue ni etiqueta",
        "catalogo_variables": archivo_catalogo,
        "pruebas_antifuga": {"informe": archivo_pruebas} | resultado_pruebas | {
            "pendiente": "imputación de date_registration (D28) ajustada dentro de cada pliegue: se implementa y "
                         "prueba en F2 (Pipeline de ml/automl), no en este experimento",
        },
        "salidas_sha256": {"carpeta": PROCESADO.relative_to(RAIZ).as_posix()} | salidas_sha256,
        "referencia_calidad": {
            "experimento": EXPLORACION_REFERENCIA.stem, "sha256": sha256(EXPLORACION_REFERENCIA),
        },
        "entorno": versiones_entorno("pandas", "numpy", "matplotlib", "pyarrow", "pytest"),
        "tiempo_ejecucion_s": round(time.perf_counter() - inicio, 2),
        "figuras": [archivo for archivo, _ in figuras],
    }
    escribir_json(salida / "experimentos" / f"{id_exp}.json", experimento)
    actualizar_manifest(
        salida, fecha, commit, id_exp,
        [{"archivo": a, "descripcion": d, "experimento": id_exp} for a, d in figuras],
        [{"archivo": archivo_pruebas, "descripcion": "Pruebas automatizadas anti-fuga de los cortes", "experimento": id_exp}],
    )
    print(f"Exportado {id_exp} en {salida} (commit {commit})")


if __name__ == "__main__":
    main()
