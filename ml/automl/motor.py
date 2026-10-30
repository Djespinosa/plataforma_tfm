"""Parte genérica del experimento y del modelo final, agnóstica al conjunto de datos (docs/diseno-api.md §6.2).

Extraída de ml/experimento.py (metricas, rl_defecto, calcular_referencias y el cuerpo de momento) y de ml/modelo_final.py
(entrenar_final) sin cambiar el código ni el orden de las operaciones: los scripts de OULAD la reimportan y la API la
llama con cualquier tabla (D10). Recibe X, y y la columna de pliegue (1..5) ya calculada; no lee archivos.

Orden de modelar (D31-rev, D37, D44, D48, D49-rev, D45):
  búsqueda por familia → OOF con calibración anidada y método por Brier → referencias → apilamiento →
  mejor AutoML y contraste con la RL optimizada → parsimonia → umbral → punto de operación OOF.
"""

from __future__ import annotations

import time
from typing import Callable

import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV, calibration_curve
from sklearn.dummy import DummyClassifier
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score
from sklearn.pipeline import Pipeline

from automl import busqueda
from automl.apilamiento import apilamiento, oof_apilamiento
from automl.calibracion import METODOS, elegir_metodo, oof_anidado, punto_operacion, umbral
from automl.comparacion import auc_bootstrap, delong, intervalo, parsimonia
from automl.equidad import FALTANTE, auditar
from automl.particion import divisiones


# --- Métricas y referencias (movidas sin cambios desde experimento.py) -----------------------------------------------

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


# --- Modelado de un momento (cuerpo genérico de experimento.momento) ---------------------------------------------------

def modelar(X: pd.DataFrame, y: pd.Series, pliegue: pd.Series, columnas: dict, config: dict,
            progreso: Callable[[str], None] | None = None
            ) -> tuple[dict, dict[str, np.ndarray], dict[str, np.ndarray], dict[str, Pipeline]]:
    """Búsqueda por familia → OOF con calibración anidada y método por Brier → referencias → apilamiento → mejor AutoML
    (D44) y contraste con la RL optimizada → parsimonia (D49-rev) → umbral (D45) → punto de operación OOF.

    Devuelve (resumen, predicciones, otras, modelos): resumen con las claves de momentos[] de exp-2026-10-27-01 salvo
    semana, desglose, equidad_oof, shap y tiempo_s; predicciones = OOF calibradas de cada candidato y referencia; otras
    = OOF sin calibrar y con cada método (para reproducir el resumen); modelos = Pipeline sin ajustar de cada familia
    con sus hiperparámetros. progreso recibe el nombre de cada etapa al empezarla: cada familia, "referencias",
    "apilamiento" (si se pide) y "comparacion".
    config: familias, n_trials_por_familia, semillas {optuna, modelos, bootstrap}, n_jobs, apilamiento, n_bootstrap,
    sensibilidad_minima. Exige "rl" en familias (es la referencia optimizada del contraste central).
    """
    if "rl" not in config["familias"]:
        raise ValueError("La regresión logística (rl) debe estar entre las familias: es la referencia optimizada con "
                         "el mismo presupuesto con la que se compara el mejor modelo AutoML.")
    avisar = progreso or (lambda etapa: None)
    cv = divisiones(pliegue)
    semillas, n_jobs = config["semillas"], config["n_jobs"]
    predicciones: dict[str, np.ndarray] = {}
    otras: dict[str, np.ndarray] = {}  # sin calibrar y con cada método, para reproducir el JSON desde el parquet
    familias, modelos = [], {}

    for familia in config["familias"]:
        avisar(familia)
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

    avisar("referencias")
    referencias, p_referencias = calcular_referencias(X, y, pliegue, columnas, semillas["modelos"])
    predicciones |= p_referencias
    rl = next(f for f in familias if f["modelo"] == "rl")
    referencias.append(rl | {"modelo": "rl_optimizada", "igual_que": "familia rl (mismo nº de ensayos que cada familia)"})

    candidatos = list(config["familias"])
    resultado_apilamiento = None
    if config["apilamiento"]:
        avisar("apilamiento")
        inicio = time.perf_counter()
        predicciones["apilamiento"] = oof_apilamiento(modelos, X, y, pliegue, semilla=semillas["modelos"])
        resultado_apilamiento = {"base": list(modelos), **metricas(y, predicciones["apilamiento"], pliegue),
                                 "calibracion": "salida del metamodelo logístico, sin calibración adicional",
                                 "tiempo_s": round(time.perf_counter() - inicio, 1)}
        candidatos.append("apilamiento")

    avisar("comparacion")
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

    resumen = {
        "n": int(len(y)), "retiros": int(y.sum()),
        "familias": familias, "referencias": referencias, "apilamiento": resultado_apilamiento,
        "mejor_automl": mejor_automl, "contraste_central": contraste,
        "parsimonia": {k: v for k, v in regla.items() if k not in ("desplegado", "motivo")},
        "modelo_desplegado": {"modelo": desplegado, "motivo": regla["motivo"]},
        "calibracion": next((f["calibracion"] for f in familias if f["modelo"] == desplegado),
                            {"metodo": None, "motivo": "apilamiento: salida del metamodelo"}),
        "punto_operacion_oof": punto_operacion(y, p_desplegado, corte),
    }
    return resumen, predicciones, otras, modelos


# --- Modelo final (D41, D54) -------------------------------------------------------------------------------------------

def entrenar_final(familia: str, hiperparametros: dict, metodo: str, X: pd.DataFrame, y: pd.Series,
                   pliegue: pd.Series, columnas: dict, semilla: int, n_jobs: int) -> CalibratedClassifierCV:
    """Modelo base con todo el entrenamiento y calibrador con las predicciones out-of-fold de los 5 pliegues agrupados
    (ensemble=False). `divisiones` falla si hay filas sin pliegue (las de la cohorte de prueba)."""
    base = busqueda.construir(familia, hiperparametros, **columnas, semilla=semilla, n_jobs=n_jobs)
    return CalibratedClassifierCV(base, method=METODOS[metodo], cv=divisiones(pliegue), ensemble=False).fit(X, y)


def entrenar_desplegado(resumen: dict, modelos: dict[str, Pipeline], X: pd.DataFrame, y: pd.Series,
                        pliegue: pd.Series, columnas: dict, config: dict):
    """Modelo final del desplegado de `resumen`, sin nueva búsqueda (D38). Una familia: entrenar_final con sus
    hiperparámetros y el método de su calibración sobre los 5 pliegues (D41, D54). Apilamiento: el de los modelos de
    cada familia con todos los pliegues, sin calibración adicional (D48, D52)."""
    desplegado = resumen["modelo_desplegado"]["modelo"]
    semilla = config["semillas"]["modelos"]
    if desplegado == "apilamiento":
        return apilamiento(modelos, pliegue, semilla).fit(X, y)
    familia = next(f for f in resumen["familias"] if f["modelo"] == desplegado)
    return entrenar_final(desplegado, familia["hiperparametros"], familia["calibracion"]["metodo"], X, y, pliegue,
                          columnas, semilla, config["n_jobs"])


# --- Calibración y equidad para la evaluación ------------------------------------------------------------------------

def curva_calibracion(y, p, n_intervalos: int = 10) -> list[dict]:
    """[{predicha, observada}] por intervalos de cuantiles, como la figura de calibración de experimento.py."""
    observada, predicha = calibration_curve(y, p, n_bins=n_intervalos, strategy="quantile")
    return [{"predicha": round(float(a), 4), "observada": round(float(b), 4)} for a, b in zip(predicha, observada)]


def auditar_equidad(y, p, corte: float, atributos: pd.DataFrame, y_ref, atributos_ref: pd.DataFrame,
                    n_bootstrap: int, semilla: int, *, recuentos_de: str) -> dict:
    """equidad.auditar (D50) con retiros_prueba = positivos por subgrupo en las filas de referencia: la cohorte de prueba
    si existe (recuento descriptivo, sin predicciones) o, si no, el entrenamiento. Los subgrupos con predicciones que
    no aparecen en la referencia cuentan 0 positivos (es un recuento de esas filas, no un dato que falte).
    recuentos_de describe la referencia ("cohorte de prueba" o "entrenamiento") y se añade como "recuentos_de"."""
    y_ref = np.asarray(y_ref)
    retiros: dict[str, dict] = {}
    for atributo in atributos.columns:
        grupos = atributos_ref[atributo].astype(object).where(atributos_ref[atributo].notna(), FALTANTE).to_numpy()
        valores = atributos[atributo].astype(object).where(atributos[atributo].notna(), FALTANTE).unique()
        retiros[atributo] = {valor: int(y_ref[grupos == valor].sum()) for valor in valores}
    return {"recuentos_de": recuentos_de} | auditar(y, p, corte, atributos, retiros, n_bootstrap, semilla)
