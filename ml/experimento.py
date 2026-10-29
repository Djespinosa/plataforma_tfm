"""Experimento de modelado (OE3) desde una configuración de ml/configs/, exportado según CONTRATO.md (tipo "modelado").

Solo validación cruzada (Entrega 2): se leen las filas de entrenamiento de cada corte y 2014J no se predice. Las
predicciones out-of-fold se guardan en data/procesado/oof/ (no versionado) para la comparación y las variantes.

Orden por momento (D31-rev, D37, D44, D48, D49-rev, D45, D50):
  búsqueda por familia → OOF con calibración anidada y método por Brier → referencias → apilamiento →
  mejor AutoML y contraste con la RL optimizada → parsimonia → umbral → desglose CCC/resto → equidad.
Holm se aplica al terminar los 4 momentos.

Uso:
    python ml/experimento.py ml/configs/principal.json
    python ml/experimento.py ml/configs/principal.json --ensayo --n-trials 3 --semanas 0   # cronometrado, fuera de evidencias/
"""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib import ticker  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from sklearn.calibration import calibration_curve  # noqa: E402
from sklearn.dummy import DummyClassifier  # noqa: E402
from sklearn.metrics import average_precision_score, brier_score_loss, precision_recall_curve, roc_auc_score, roc_curve  # noqa: E402
from sklearn.pipeline import Pipeline  # noqa: E402

from automl import busqueda  # noqa: E402
from automl.apilamiento import METAMODELO, oof_apilamiento  # noqa: E402
from automl.calibracion import elegir_metodo, oof_anidado, punto_operacion, umbral  # noqa: E402
from automl.comparacion import auc_bootstrap, delong, holm, intervalo, lectura, parsimonia  # noqa: E402
from automl.equidad import auditar  # noqa: E402
from automl.particion import divisiones  # noqa: E402
from cortes_oulad import IMPUTAR_MEDIANA, PROCESADO, SENSIBLES, ejecutar_pruebas  # noqa: E402
from evidencias import (  # noqa: E402
    EVIDENCIAS,
    RAIZ,
    actualizar_manifest,
    comprobar_arbol_limpio,
    escribir_json,
    hardware,
    sha256,
    siguiente_id,
    versiones_entorno,
)

OOF = RAIZ / "data" / "procesado" / "oof"
DPI = 300
# Paleta categórica de referencia (skill dataviz): los 3 primeros puestos son seguros para daltonismo entre todos
# los pares; cada serie lleva además su propio estilo de línea (impresión en escala de grises).
SERIES = [("#2a78d6", "-"), ("#eb6834", "--"), ("#1baf7a", ":")]
TINTA, TINTA_SECUNDARIA, REJILLA = "#0b0b0b", "#52514e", "#e4e3df"
NOMBRE_METODO = {"platt": "Platt", "isotonica": "isotónica"}
CALIBRACION_DEFINICION = ("D37/D54: para cada pliegue externo, CalibratedClassifierCV (sigmoid = Platt, isotonic) con "
                          "los otros 4 pliegues como divisiones internas y ensemble=False: el calibrador se ajusta con "
                          "las predicciones out-of-fold de esas divisiones y el modelo base se reentrena con los 4 "
                          "pliegues; método por Brier out-of-fold; métricas por pliegue y out-of-fold sobre las "
                          "probabilidades calibradas")
BRIER_SIN_CALIBRAR_DEFINICION = ("Brier de predict_proba del modelo base tal como sale, sin corregir la prevalencia: "
                                 "con class_weight 'balanced' (pesos por muestra en xgb y mlp, auto_class_weights en "
                                 "catboost) el modelo se entrena con las clases reponderadas y sus probabilidades sin "
                                 "calibrar están desplazadas hacia la clase minoritaria, así que su Brier es mayor que "
                                 "el de un modelo sin pesos. Se informa; el método se elige solo entre Platt e isotónica")


# --- Datos ----------------------------------------------------------------------------------------------------------

def cargar_cortes(experimento_cortes: str) -> tuple[dict, pd.DataFrame]:
    ruta = EVIDENCIAS / "experimentos" / f"{experimento_cortes}.json"
    cortes = json.loads(ruta.read_text(encoding="utf-8"))
    catalogo = pd.read_csv(EVIDENCIAS / cortes["catalogo_variables"], keep_default_na=False)
    return cortes, catalogo


def columnas_modelo(catalogo: pd.DataFrame, sin_sensibles: bool) -> dict:
    variables = catalogo[catalogo["motivo_exclusion"] == ""]
    if sin_sensibles:
        variables = variables[~variables["nombre"].isin(SENSIBLES)]
    categoricas = variables.loc[variables["tipo"] == "categórica", "nombre"].tolist()
    numericas = variables.loc[variables["tipo"] != "categórica", "nombre"].tolist()
    return {"numericas": numericas, "categoricas": categoricas,
            "imputar_mediana": [c for c in IMPUTAR_MEDIANA if c in numericas]}


def cargar_entrenamiento(semana: int, cortes: dict, sufijo: str = "") -> pd.DataFrame:
    """Filas de entrenamiento del corte (sufijo "_sin_exclusion_retirados" para D20); comprueba el SHA-256 registrado en
    el experimento de cortes."""
    nombre = f"semana_{semana}{sufijo}.parquet"
    ruta = PROCESADO / nombre
    if sha256(ruta) != cortes["salidas_sha256"][nombre]:
        raise ValueError(f"{nombre} no coincide con el SHA-256 de {cortes['id']}: regenera los cortes")
    # 2014J no se usa para modelar en la Entrega 2: el filtro se aplica al leer y sus filas no llegan a cargarse.
    return pd.read_parquet(ruta, filters=[("particion", "==", "entrenamiento")]).reset_index(drop=True)


def retiros_prueba(cortes: dict, semana: int) -> dict[str, dict]:
    """Retiros por subgrupo en 2014J, del experimento de cortes (recuento descriptivo; no se leen filas de 2014J)."""
    salida: dict[str, dict] = {}
    for fila in cortes["subgrupos"]:
        if fila["semana"] == semana and fila["particion"] == "prueba":
            salida.setdefault(fila["variable"], {})[fila["valor"]] = fila["desercion"]
    return salida


# --- Métricas ---------------------------------------------------------------------------------------------------------

def metricas(y: pd.Series, p: np.ndarray, pliegue: pd.Series) -> dict:
    por_pliegue = []
    for f in sorted(pliegue.unique()):
        en = (pliegue == f).to_numpy()
        por_pliegue.append({"pliegue": int(f), "roc_auc": round(roc_auc_score(y[en], p[en]), 4),
                            "pr_auc": round(average_precision_score(y[en], p[en]), 4),
                            "brier": round(brier_score_loss(y[en], p[en]), 4)})
    auc = [f["roc_auc"] for f in por_pliegue]
    return {"por_pliegue": por_pliegue, "roc_auc_media": round(float(np.mean(auc)), 4),
            "roc_auc_desv": round(float(np.std(auc, ddof=1)), 4), "roc_auc_oof": round(roc_auc_score(y, p), 4),
            "pr_auc_oof": round(average_precision_score(y, p), 4), "brier_oof": round(brier_score_loss(y, p), 4)}


def rl_defecto(columnas: dict, semilla: int = 42) -> Pipeline:
    """Referencia: regresión logística por defecto (C = 1, L2, sin pesos de clase) con el solver de la familia RL
    (liblinear) y la misma entrada; es exactamente el primer ensayo de la búsqueda de la RL optimizada."""
    return busqueda.construir("rl", busqueda.PREDETERMINADOS["rl"], **columnas, semilla=semilla)


def calcular_referencias(X: pd.DataFrame, y: pd.Series, pliegue: pd.Series, columnas: dict,
                         semilla: int) -> tuple[list[dict], dict[str, np.ndarray]]:
    """Mayoritaria sin calibrar; rl_defecto con la misma calibración anidada y elección por Brier que los candidatos
    (D53), para comparar con la RL optimizada en igualdad de condiciones."""
    referencias, predicciones = [], {}
    inicio = time.perf_counter()
    p = oof_anidado(DummyClassifier(strategy="prior"), X, y, pliegue, calibrar=False)["sin_calibrar"]
    referencias.append({"modelo": "mayoritaria", "calibracion": None, **metricas(y, p, pliegue),
                        "tiempo_s": round(time.perf_counter() - inicio, 1),
                        "nota": "predice en cada pliegue la prevalencia de sus pliegues de ajuste: ROC-AUC 0,5 en cada "
                                "pliegue; la ROC-AUC out-of-fold agrupada se aparta de 0,5 solo porque esa constante "
                                "cambia entre pliegues (limitación de agrupar predicciones de 5 modelos, D40)"})
    predicciones["ref_mayoritaria"] = p

    inicio = time.perf_counter()
    oof = oof_anidado(rl_defecto(columnas, semilla), X, y, pliegue)
    calibracion = elegir_metodo(y, oof)
    predicciones["ref_rl_defecto"] = oof[calibracion["metodo"]]
    predicciones |= {f"ref_rl_defecto_{nombre}": p for nombre, p in oof.items()}  # todas, para reproducir el JSON
    referencias.append({"modelo": "rl_defecto", "hiperparametros": busqueda.PREDETERMINADOS["rl"],
                        "calibracion": calibracion,
                        "roc_auc_oof_sin_calibrar": round(roc_auc_score(y, oof["sin_calibrar"]), 4),
                        **metricas(y, predicciones["ref_rl_defecto"], pliegue),
                        "tiempo_s": round(time.perf_counter() - inicio, 1)})
    return referencias, predicciones


# --- Un momento -------------------------------------------------------------------------------------------------------

def momento(semana: int, config: dict, cortes: dict, columnas: dict) -> tuple[dict, dict]:
    datos = cargar_entrenamiento(semana, cortes)
    X = datos[columnas["numericas"] + columnas["categoricas"]]
    y, pliegue = datos["etiqueta"], datos["pliegue"]
    cv = divisiones(pliegue)
    semillas, n_jobs = config["semillas"], config["n_jobs"]
    predicciones: dict[str, np.ndarray] = {}
    otras: dict[str, np.ndarray] = {}  # sin calibrar y con cada método, para reproducir el JSON desde el parquet
    familias, modelos = [], {}

    for familia in config["familias"]:
        print(f"  semana {semana}: {familia}", flush=True)
        resultado = busqueda.buscar(familia, X, y, cv, config["n_trials_por_familia"], columnas,
                                    semilla=semillas["optuna"], n_jobs=n_jobs, semilla_modelos=semillas["modelos"])
        modelo = busqueda.construir(familia, resultado["hiperparametros"], **columnas, semilla=semillas["modelos"],
                                    n_jobs=n_jobs)
        inicio = time.perf_counter()
        oof = oof_anidado(modelo, X, y, pliegue)
        calibracion = elegir_metodo(y, oof)
        predicciones[familia] = oof[calibracion["metodo"]]
        otras |= {f"{familia}_{nombre}": p for nombre, p in oof.items()}
        modelos[familia] = modelo
        familias.append({"modelo": familia, **resultado, "calibracion": calibracion,
                         "roc_auc_oof_sin_calibrar": round(roc_auc_score(y, oof["sin_calibrar"]), 4),
                         **metricas(y, predicciones[familia], pliegue),
                         "tiempo_oof_calibrado_s": round(time.perf_counter() - inicio, 1)})
        familias[-1]["tiempo_s"] = round(familias[-1]["tiempo_busqueda_s"] + familias[-1]["tiempo_oof_calibrado_s"], 1)

    referencias, p_referencias = calcular_referencias(X, y, pliegue, columnas, semillas["modelos"])
    predicciones |= p_referencias
    if "rl" in predicciones:
        rl = next(f for f in familias if f["modelo"] == "rl")
        referencias.append(rl | {"modelo": "rl_optimizada",
                                 "igual_que": "familia rl (mismo nº de ensayos que cada familia)"})

    candidatos = list(config["familias"])
    resultado_apilamiento = None
    if config["apilamiento"]:
        print(f"  semana {semana}: apilamiento", flush=True)
        inicio = time.perf_counter()
        predicciones["apilamiento"] = oof_apilamiento(modelos, X, y, pliegue, semilla=semillas["modelos"])
        resultado_apilamiento = {"base": list(modelos), **metricas(y, predicciones["apilamiento"], pliegue),
                                 "calibracion": "salida del metamodelo logístico, sin calibración adicional",
                                 "tiempo_s": round(time.perf_counter() - inicio, 1)}
        candidatos.append("apilamiento")

    no_rl = [c for c in candidatos if c != "rl"]
    auc_oof = {c: roc_auc_score(y, predicciones[c]) for c in candidatos}
    mejor_automl = max(no_rl, key=auc_oof.get)
    central = delong(y, predicciones[mejor_automl], predicciones["rl"])
    muestras = auc_bootstrap(y, {"a": predicciones[mejor_automl], "b": predicciones["rl"]},
                             config["n_bootstrap"], semillas["bootstrap"])
    contraste = {"modelo_a": mejor_automl, "modelo_b": "rl_optimizada", "roc_auc_a": round(central["roc_auc_a"], 4),
                 "roc_auc_b": round(central["roc_auc_b"], 4), "diferencia": round(central["diferencia"], 4),
                 "ic95_bootstrap": [round(v, 4) for v in intervalo(muestras["a"] - muestras["b"])],
                 "delong_p": central["delong_p"], "n_bootstrap": config["n_bootstrap"], "semilla": semillas["bootstrap"]}

    regla = parsimonia(y, {c: predicciones[c] for c in candidatos}, busqueda.COMPLEJIDAD,
                       config["n_bootstrap"], semillas["bootstrap"])
    desplegado = regla["desplegado"]
    p_desplegado = predicciones[desplegado]
    corte = umbral(y, p_desplegado, config["sensibilidad_minima"])
    ccc = (datos["code_module"] == "CCC").to_numpy()
    desglose = {
        nombre: {"n": int(en.sum()), "roc_auc": round(roc_auc_score(y[en], p_desplegado[en]), 4),
                 **punto_operacion(y[en], p_desplegado[en], corte)}
        for nombre, en in (("CCC", ccc), ("resto", ~ccc))
    }
    equidad = auditar(y, p_desplegado, corte, datos[SENSIBLES], retiros_prueba(cortes, semana),
                      config["n_bootstrap"], semillas["bootstrap"])

    resumen = {
        "semana": semana, "n": int(len(y)), "retiros": int(y.sum()),
        "familias": familias, "referencias": referencias, "apilamiento": resultado_apilamiento,
        "mejor_automl": mejor_automl, "contraste_central": contraste,
        "parsimonia": {k: v for k, v in regla.items() if k not in ("desplegado", "motivo")},
        "modelo_desplegado": {"modelo": desplegado, "motivo": regla["motivo"]},
        "calibracion": next((f["calibracion"] for f in familias if f["modelo"] == desplegado),
                            {"metodo": None, "motivo": "apilamiento: salida del metamodelo"}),
        "punto_operacion_oof": punto_operacion(y, p_desplegado, corte),
        "desglose": desglose,
        "equidad_oof": equidad,
        "shap": None,
    }
    oof = pd.DataFrame({"code_module": datos["code_module"], "code_presentation": datos["code_presentation"],
                        "id_student": datos["id_student"], "pliegue": pliegue, "etiqueta": y} |
                       {f"p_{nombre}": p for nombre, p in predicciones.items()} |
                       {f"p_{nombre}": p for nombre, p in otras.items()})
    return resumen, oof


# --- Figuras ----------------------------------------------------------------------------------------------------------

class FormatoComa(ticker.ScalarFormatter):
    """Marcas de los ejes con coma decimal (la memoria está en español)."""

    def __call__(self, x, pos=None):
        return super().__call__(x, pos).replace(".", ",")


def coma(valor: float, decimales: int = 3) -> str:
    return f"{valor:.{decimales}f}".replace(".", ",")


def _estilo(ax) -> None:
    for eje in (ax.xaxis, ax.yaxis):
        if type(eje.get_major_formatter()) is ticker.ScalarFormatter:  # no toca las etiquetas de categorías
            eje.set_major_formatter(FormatoComa())
    ax.grid(color=REJILLA, linewidth=0.8)
    ax.set_axisbelow(True)
    for lado in ("top", "right"):
        ax.spines[lado].set_visible(False)
    for lado in ("left", "bottom"):
        ax.spines[lado].set_color(TINTA_SECUNDARIA)
    ax.tick_params(colors=TINTA_SECUNDARIA, labelcolor=TINTA)


def series_figura(resumen: dict) -> list[tuple[str, str]]:
    """Como máximo 3 series: modelo desplegado, mejor AutoML y RL optimizada (sin repetir)."""
    nombres = []
    for nombre, etiqueta in ((resumen["modelo_desplegado"]["modelo"], "desplegado"),
                             (resumen["mejor_automl"], "mejor AutoML"), ("rl", "RL optimizada")):
        if nombre not in [n for n, _ in nombres]:
            nombres.append((nombre, etiqueta))
    return nombres


def figura_roc_pr(resumenes: list[dict], salidas: dict, ruta: Path) -> None:
    fig, ejes = plt.subplots(2, len(resumenes), figsize=(3.6 * len(resumenes), 7), squeeze=False)
    for j, resumen in enumerate(resumenes):
        oof = salidas[resumen["semana"]]
        y = oof["etiqueta"]
        ax_roc, ax_pr = ejes[0, j], ejes[1, j]
        for (nombre, etiqueta), (color, linea) in zip(series_figura(resumen), SERIES):
            p = oof[f"p_{nombre}"]
            fpr, tpr, _ = roc_curve(y, p)
            precision, sensibilidad, _ = precision_recall_curve(y, p)
            texto = f"{nombre} ({etiqueta}), AUC {coma(roc_auc_score(y, p))}"
            ax_roc.plot(fpr, tpr, linea, color=color, linewidth=2, label=texto)
            ax_pr.plot(sensibilidad, precision, linea, color=color, linewidth=2,
                       label=f"{nombre}, PR-AUC {coma(average_precision_score(y, p))}")
        ax_roc.plot([0, 1], [0, 1], color=TINTA_SECUNDARIA, linewidth=0.8)
        ax_pr.axhline(y.mean(), color=TINTA_SECUNDARIA, linewidth=0.8)
        ax_roc.set(title=f"Semana {resumen['semana']}", xlabel="Tasa de falsos positivos", ylabel="Sensibilidad")
        ax_pr.set(xlabel="Sensibilidad", ylabel="Precisión", ylim=(0, 1))
        for ax in (ax_roc, ax_pr):
            _estilo(ax)
            ax.legend(fontsize=6.5, frameon=False, loc="lower right" if ax is ax_roc else "upper right")
    fig.suptitle("Curvas ROC y precisión-sensibilidad out-of-fold por momento (OULAD, entrenamiento)", color=TINTA, fontsize=10)
    fig.tight_layout()
    fig.savefig(ruta, dpi=DPI)
    plt.close(fig)


def figura_calibracion(resumenes: list[dict], salidas: dict, ruta: Path) -> None:
    fig, ejes = plt.subplots(1, len(resumenes), figsize=(3.6 * len(resumenes), 3.8), squeeze=False)
    for ax, resumen in zip(ejes[0], resumenes):
        oof = salidas[resumen["semana"]]
        desplegado = resumen["modelo_desplegado"]["modelo"]
        metodo = NOMBRE_METODO.get(resumen["calibracion"].get("metodo"), "metamodelo")
        curvas = [(f"calibrado ({metodo})", oof[f"p_{desplegado}"])]
        if f"p_{desplegado}_sin_calibrar" in oof:
            curvas.insert(0, ("sin calibrar", oof[f"p_{desplegado}_sin_calibrar"]))
        for (etiqueta, p), (color, linea) in zip(curvas, SERIES):
            observada, predicha = calibration_curve(oof["etiqueta"], p, n_bins=10, strategy="quantile")
            ax.plot(predicha, observada, linea, marker="o", markersize=4, color=color, linewidth=2, label=etiqueta)
        ax.plot([0, 1], [0, 1], color=TINTA_SECUNDARIA, linewidth=0.8)
        ax.set(title=f"Semana {resumen['semana']}: {desplegado}", xlabel="Probabilidad predicha",
               ylabel="Proporción observada de retiros", xlim=(0, 1), ylim=(0, 1))
        _estilo(ax)
        ax.legend(fontsize=7, frameon=False, loc="upper left")
    fig.suptitle("Calibración out-of-fold del modelo desplegado (10 intervalos por cuantiles)", color=TINTA, fontsize=10)
    fig.tight_layout()
    fig.savefig(ruta, dpi=DPI)
    plt.close(fig)


ETIQUETA_FAMILIA = {"rl": "rl (RL optimizada)", "rl_defecto": "rl_defecto (RL por defecto)",
                    "mayoritaria": "mayoritaria (prevalencia)"}


def figura_familias(resumenes: list[dict], ruta: Path) -> None:
    """Candidatos (familias y apilamiento) y referencias con marcas distintas; rl_optimizada no se repite."""
    fig, ejes = plt.subplots(1, len(resumenes), figsize=(3.6 * len(resumenes), 4.4), sharey=True, squeeze=False)
    for ax, resumen in zip(ejes[0], resumenes):
        candidatos = list(resumen["familias"]) + ([resumen["apilamiento"] | {"modelo": "apilamiento"}]
                                                  if resumen["apilamiento"] else [])
        referencias = [r for r in resumen["referencias"] if "igual_que" not in r]
        filas = candidatos + referencias
        posiciones = np.arange(len(filas))
        for grupo, inicio, (color, _), marca in ((candidatos, 0, SERIES[0], "o"),
                                                 (referencias, len(candidatos), SERIES[1], "s")):
            ax.errorbar([f["roc_auc_oof"] for f in grupo], posiciones[inicio:inicio + len(grupo)],
                        xerr=[f["roc_auc_desv"] for f in grupo], fmt=marca, markersize=6, color=color,
                        ecolor=TINTA_SECUNDARIA, elinewidth=1, capsize=0)
        ax.axhline(len(candidatos) - 0.5, color=TINTA_SECUNDARIA, linewidth=0.8, linestyle=":")
        mayoritaria = next((i for i, f in enumerate(filas) if f["modelo"] == "mayoritaria"), None)
        if mayoritaria is not None:
            f = filas[mayoritaria]
            ax.annotate(f"{coma(f['roc_auc_oof'])} agrupada; {coma(f['roc_auc_media'], 2)} en cada pliegue (D40)",
                        (f["roc_auc_oof"], mayoritaria), xytext=(8, 0), textcoords="offset points", va="center",
                        fontsize=6.5, color=TINTA_SECUNDARIA)
        ax.set_yticks(posiciones, [ETIQUETA_FAMILIA.get(f["modelo"], f["modelo"]) for f in filas])
        ax.invert_yaxis()
        ax.set(title=f"Semana {resumen['semana']}", xlabel="ROC-AUC out-of-fold")
        _estilo(ax)
    leyenda = [Line2D([], [], marker="o", linestyle="", color=SERIES[0][0], label="candidato del motor AutoML"),
               Line2D([], [], marker="s", linestyle="", color=SERIES[1][0], label="referencia")]
    fig.legend(handles=leyenda, loc="lower center", ncol=2, frameon=False, fontsize=8)
    fig.suptitle("ROC-AUC out-of-fold por familia y referencia (barra: ± desviación entre pliegues)", color=TINTA, fontsize=10)
    fig.tight_layout(rect=(0, 0.05, 1, 1))
    fig.savefig(ruta, dpi=DPI)
    plt.close(fig)


def lista_figuras(id_exp: str, sufijo: str = "") -> list[tuple[str, str]]:
    return [
        (f"figuras/{id_exp}_roc_pr_oof{sufijo}.png", "Curvas ROC y PR out-of-fold por momento: desplegado, mejor AutoML y RL optimizada"),
        (f"figuras/{id_exp}_calibracion_oof{sufijo}.png", "Curva de calibración out-of-fold del modelo desplegado por momento"),
        (f"figuras/{id_exp}_familias_roc_auc{sufijo}.png", "ROC-AUC out-of-fold por familia y referencia, por momento"),
    ]


def dibujar_figuras(resumenes: list[dict], salidas: dict, salida: Path, figuras: list[tuple[str, str]]) -> None:
    figura_roc_pr(resumenes, salidas, salida / figuras[0][0])
    figura_calibracion(resumenes, salidas, salida / figuras[1][0])
    figura_familias(resumenes, salida / figuras[2][0])


# --- Principal --------------------------------------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("configuracion", type=Path)
    parser.add_argument("--salida", type=Path, default=EVIDENCIAS, help="Carpeta de evidencias (por defecto evidencias/)")
    parser.add_argument("--ensayo", action="store_true", help="Ensayo cronometrado: exige --salida fuera de evidencias/")
    parser.add_argument("--n-trials", type=int, help="Sustituye n_trials_por_familia (solo con --ensayo)")
    parser.add_argument("--semanas", type=int, nargs="+", help="Sustituye las semanas (solo con --ensayo)")
    parser.add_argument("--n-bootstrap", type=int, help="Sustituye n_bootstrap (solo con --ensayo)")
    args = parser.parse_args()

    config = json.loads(args.configuracion.read_text(encoding="utf-8"))
    sustituciones = {"n_trials_por_familia": args.n_trials, "semanas": args.semanas, "n_bootstrap": args.n_bootstrap}
    if any(v is not None for v in sustituciones.values()) or args.ensayo:
        if not args.ensayo or args.salida.resolve() == EVIDENCIAS.resolve():
            parser.error("Las sustituciones solo valen en un --ensayo con --salida fuera de evidencias/")
        config |= {k: v for k, v in sustituciones.items() if v is not None}

    inicio = time.perf_counter()
    salida: Path = args.salida
    commit = comprobar_arbol_limpio(salida)
    fecha = datetime.now()
    for carpeta in ("experimentos", "figuras"):
        (salida / carpeta).mkdir(parents=True, exist_ok=True)
    id_exp = siguiente_id(salida / "experimentos", fecha)
    # Pruebas antes de modelar: si falla alguna, no se gastan horas de cómputo ni se exporta nada.
    (salida / "pruebas").mkdir(parents=True, exist_ok=True)
    archivo_pruebas = f"pruebas/{id_exp}_pruebas.xml"
    resultado_pruebas = ejecutar_pruebas(salida / archivo_pruebas)
    carpeta_oof = OOF if salida.resolve() == EVIDENCIAS.resolve() else salida / "oof"
    carpeta_oof.mkdir(parents=True, exist_ok=True)

    cortes, catalogo = cargar_cortes(config["experimento_cortes"])
    columnas = columnas_modelo(catalogo, config["sin_sensibles"])
    resumenes, salidas, oof_sha256 = [], {}, {}
    for semana in config["semanas"]:
        inicio_momento = time.perf_counter()
        resumen, salidas[semana] = momento(semana, config, cortes, columnas)
        resumen["tiempo_s"] = round(time.perf_counter() - inicio_momento, 1)
        ruta_oof = carpeta_oof / f"{id_exp}_semana_{semana}.parquet"
        salidas[semana].to_parquet(ruta_oof, index=False)
        oof_sha256[ruta_oof.name] = sha256(ruta_oof)
        resumenes.append(resumen)
        print(f"semana {semana}: {resumen['tiempo_s']} s", flush=True)

    corregidos = holm([r["contraste_central"]["delong_p"] for r in resumenes])
    for resumen, p_holm in zip(resumenes, corregidos):
        contraste = resumen["contraste_central"]
        contraste["delong_p_holm"] = p_holm
        contraste["lectura"] = lectura(contraste["diferencia"], contraste["ic95_bootstrap"], p_holm)

    figuras = lista_figuras(id_exp)
    dibujar_figuras(resumenes, salidas, salida, figuras)

    experimento = {
        "id": id_exp,
        "tipo": "modelado",
        "fecha": fecha.isoformat(timespec="seconds"),
        "commit": commit,
        "descripcion": f"{config['descripcion']} Configuración: {args.configuracion.as_posix()}.",
        "variante": config["variante"],
        "configuracion": config,
        "experimento_cortes": config["experimento_cortes"],
        "dataset": {"nombre": "OULAD", "version": "2017", "licencia": "CC BY 4.0 (Kuzilek et al., 2017)",
                    "tablas_usadas": cortes["dataset"]["tablas_usadas"], "sha256": cortes["dataset"]["sha256"],
                    "cortes_sha256": {f"semana_{s}.parquet": cortes["salidas_sha256"][f"semana_{s}.parquet"]
                                      for s in config["semanas"]}},
        "variables": columnas | {"sensibles_excluidas": SENSIBLES if config["sin_sensibles"] else []},
        "particion": {"estrategia": "temporal", "entrenamiento": "presentaciones anteriores a 2014J (15)",
                      "prueba": "2014J (7)", "validacion": "5 pliegues agrupados por presentación (D29-rev)",
                      "semillas": config["semillas"]},
        "automl": busqueda.DESCRIPCION_OPTUNA | {
            "n_trials_por_familia": config["n_trials_por_familia"],
            "espacios_busqueda": busqueda.ESPACIOS,
            "predeterminados": {"valores": busqueda.PREDETERMINADOS, "nota": busqueda.PREDETERMINADOS_NOTA},
            "configuracion_fija": busqueda.CONFIGURACION_FIJA,
            "n_jobs": {"valor": config["n_jobs"], "nivel": busqueda.NIVEL_N_JOBS},
            "apilamiento": {"en_busqueda": False, "base": "mejor configuración de cada familia (D48)",
                            "metamodelo": METAMODELO, "cv_interna": "divisiones agrupadas por presentación dentro de "
                            "cada pliegue externo (StackingClassifier con cv precalculado)"},
        },
        "tratamiento_desbalance": "class_weight como hiperparámetro (D30); sin sobremuestreo",
        "calibracion_definicion": CALIBRACION_DEFINICION,
        "brier_sin_calibrar_definicion": BRIER_SIN_CALIBRAR_DEFINICION,
        "evaluado_en_prueba": False,
        "momentos": resumenes,
        "metricas_test": None,
        "motivos_null": {"metricas_test": "Entrega 2: solo validación cruzada; 2014J se evalúa una vez en la Entrega 3",
                         "momentos.shap": "SHAP y su estabilidad se calculan en la F3, sobre la configuración principal "
                                          "ya fijada tras la salvaguarda de D38"},
        "predicciones_oof_sha256": {"carpeta": OOF.relative_to(RAIZ).as_posix()} | oof_sha256,
        "entorno": versiones_entorno("pandas", "numpy", "pyarrow", "sklearn", "optuna", "xgboost", "lightgbm",
                                     "catboost", "scipy", "matplotlib", "pytest"),
        "hardware": hardware(),
        "pruebas": {"informe": archivo_pruebas} | resultado_pruebas,
        "tiempo_ejecucion_s": round(time.perf_counter() - inicio, 1),
        "figuras": [archivo for archivo, _ in figuras],
    }
    escribir_json(salida / "experimentos" / f"{id_exp}.json", experimento)
    actualizar_manifest(salida, fecha, commit, id_exp,
                        [{"archivo": a, "descripcion": d, "experimento": id_exp} for a, d in figuras],
                        [{"archivo": archivo_pruebas, "descripcion": "JUnit de todas las pruebas de ml/tests (núcleo "
                          "de modelado, anti-fuga y cortes) en el commit del experimento", "experimento": id_exp}])
    print(f"Exportado {id_exp} en {salida} (commit {commit})")


if __name__ == "__main__":
    main()
