"""Paquete de un modelo desplegado, predicción y SHAP por familia, agnóstico al conjunto de datos (docs/diseno-api.md §6.3).

SHAP siempre en la escala sin calibrar, log-odds (D32); la probabilidad que se muestra es la calibrada. Explicador por
familia (D33): RL, lineal exacto (la fórmula de modelo_final.predecir_y_explicar); gb, xgb, lgbm y catboost, TreeSHAP
sobre la salida bruta; rf, mlp y apilamiento, permutación sobre logit(probabilidad sin calibrar) con una muestra de
fondo (en RF, TreeSHAP daría probabilidad, no log-odds). Los valores de las columnas transformadas se suman por variable
original (one-hot e indicador de faltante). SHAP es contribución a la predicción del modelo, no causa.

variable_original y agregar se movieron sin cambios desde ml/shap_estabilidad.py, que los reimporta.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import shap
from sklearn.calibration import CalibratedClassifierCV
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline

from automl.preprocesado import DescartarVacias

LIMITE_EXTREMO = 5.0  # |φ| en log-odds; el de shap_analisis.LIMITE (exp-2026-10-29-05)
FAMILIAS_ARBOL = {"gb", "xgb", "lgbm", "catboost"}  # TreeSHAP en salida bruta = log-odds sin calibrar
FAMILIAS_PERMUTACION = {"rf", "mlp", "apilamiento"}  # RF: TreeSHAP daría probabilidad, no log-odds (D32)
N_FONDO = 50
MAX_FILAS_GLOBAL_PERMUTACION = 500
RECORTE = 1e-6  # logit(clip(p, RECORTE, 1 − RECORTE)) en el explicador de permutación


# --- Variables originales (movidas sin cambios desde shap_estabilidad.py) --------------------------------------------

def variable_original(columna: str, columnas: dict) -> str:
    """Variable de la que procede una columna transformada (numérica, indicador de faltante o one-hot)."""
    if columna in columnas["numericas"]:
        return columna
    if columna.startswith("missingindicator_"):
        return columna.removeprefix("missingindicator_")
    candidatas = [c for c in columnas["categoricas"] if columna.startswith(f"{c}_")]
    if not candidatas:
        raise ValueError(f"No se reconoce la variable de la columna {columna}")
    return max(candidatas, key=len)


def agregar(phi: pd.DataFrame, columnas: dict) -> pd.DataFrame:
    """Suma los SHAP de las columnas transformadas por variable original; las variables que el pliegue descartó (sin
    valores) reciben 0."""
    variables = columnas["numericas"] + columnas["categoricas"]
    return phi.T.groupby([variable_original(c, columnas) for c in phi.columns]).sum().T.reindex(columns=variables,
                                                                                                 fill_value=0.0)


# --- Paquete ---------------------------------------------------------------------------------------------------------

def explicador_de_familia(familia: str) -> str:
    if familia == "rl":
        return "lineal"
    if familia in FAMILIAS_ARBOL:
        return "arbol"
    if familia in FAMILIAS_PERMUTACION:
        return "permutacion"
    raise ValueError(f"Familia desconocida: {familia}")


def modelo_base(paquete: dict):
    """Modelo sin calibrar: el Pipeline base del calibrador (ensemble=False, uno solo) o el apilamiento tal cual (D52)."""
    modelo = paquete["modelo"]
    if isinstance(modelo, CalibratedClassifierCV):
        return modelo.calibrated_classifiers_[0].estimator
    return modelo


def tipo_explicador(paquete: dict) -> str:
    """"lineal", "arbol" o "permutacion". Los paquetes de modelo_final (sin las claves familia ni explicador) son de
    la RL desplegada: lineal si su estimador tiene coef_."""
    if "explicador" in paquete:
        return paquete["explicador"]
    if "familia" in paquete:
        return explicador_de_familia(paquete["familia"])
    if hasattr(modelo_base(paquete).named_steps["modelo"], "coef_"):
        return "lineal"
    raise ValueError("El paquete no indica su familia y su modelo no es lineal: no se puede elegir el explicador")


def _vacias(preprocesado) -> set[str]:
    """Variables sin ningún valor en las filas con que se ajustó un ColumnTransformer de preprocesado.codificador:
    mediana NaN en un SimpleImputer, descartadas por DescartarVacias o, en las categóricas, solo la categoría de relleno."""
    vacias: set[str] = set()
    for _, transformador, columnas in preprocesado.transformers_:
        if isinstance(transformador, str) or not len(columnas):
            continue
        pasos = [p for _, p in transformador.steps] if isinstance(transformador, Pipeline) else [transformador]
        primero = pasos[0]
        if isinstance(primero, DescartarVacias):
            vacias |= set(columnas) - set(primero.columnas_)
        elif isinstance(primero, SimpleImputer) and primero.strategy == "constant":
            vacias |= {c for c, categorias in zip(columnas, pasos[-1].categories_)
                       if list(categorias) == [primero.fill_value]}
        elif isinstance(primero, SimpleImputer):
            vacias |= {c for c, s in zip(columnas, primero.statistics_) if pd.isna(s)}
    return vacias


def variables_sin_valores(paquete: dict) -> list[str]:
    """Variables sin ningún valor en las filas de entrenamiento (auditoría O4): el preprocesado ajustado las descarta
    (en la RL y la MLP queda su indicador de faltante, constante en el entrenamiento). En el apilamiento, las que no
    tienen valores para ninguno de sus modelos base. Funciona con los paquetes de modelo_final (sin claves nuevas)."""
    base = modelo_base(paquete)
    if isinstance(base, Pipeline):
        vacias = _vacias(base.named_steps["preprocesado"])
    else:
        vacias = set.intersection(*(_vacias(m.named_steps["preprocesado"]) for m in base.estimators_))
    columnas = paquete["columnas"]
    return [v for v in columnas["numericas"] + columnas["categoricas"] if v in vacias]


def preparar_paquete(modelo, familia: str, corte: float, columnas: dict, X: pd.DataFrame, origen: dict, semilla: int,
                     momento: str | None = None) -> dict:
    """Mismo formato que modelo_final.paquete (modelo, umbral, columnas, fondo, origen) más familia, explicador,
    momento y semilla (la de la muestra de fondo y del explicador de permutación). Sin "semana", que es de OULAD.
    fondo: lineal = media de X transformada (como modelo_final.paquete); árbol = None; permutación = N_FONDO filas de
    X originales (muestra con la semilla). X son las filas de entrenamiento. Exige origen["desplegado"] is True."""
    if origen.get("desplegado") is not True:
        raise ValueError("Solo se prepara el paquete de un modelo desplegado (origen['desplegado'] debe ser True).")
    explicador = explicador_de_familia(familia)
    paquete = {"modelo": modelo, "umbral": corte, "columnas": columnas, "fondo": None, "origen": origen,
               "familia": familia, "explicador": explicador, "momento": momento, "semilla": semilla}
    variables = columnas["numericas"] + columnas["categoricas"]
    if explicador == "lineal":
        paquete["fondo"] = modelo_base(paquete).named_steps["preprocesado"].transform(X[variables]).mean()
    elif explicador == "permutacion":
        paquete["fondo"] = X[variables].sample(n=min(N_FONDO, len(X)), random_state=semilla)
    return paquete


# --- Predicción y explicación ------------------------------------------------------------------------------------------

def _salida_bruta(familia: str, estimador, Xt: pd.DataFrame) -> np.ndarray:
    """Salida sin calibrar en log-odds del estimador de árboles, la que explica TreeSHAP."""
    if familia == "gb":
        return estimador.decision_function(Xt)
    if familia == "xgb":
        return estimador.predict(Xt, output_margin=True)
    if familia == "lgbm":
        return estimador.predict(Xt, raw_score=True)
    return estimador.predict(Xt, prediction_type="RawFormulaVal")  # catboost


def _logit_sin_calibrar(paquete: dict, X: pd.DataFrame) -> np.ndarray:
    p = np.clip(modelo_base(paquete).predict_proba(X)[:, 1], RECORTE, 1 - RECORTE)
    return np.log(p / (1 - p))


def _partes(paquete: dict, X: pd.DataFrame) -> tuple[np.ndarray, float]:
    """(log_odds sin calibrar por fila, valor base) según el explicador."""
    tipo = tipo_explicador(paquete)
    if tipo == "permutacion":
        return _logit_sin_calibrar(paquete, X), float(np.mean(_logit_sin_calibrar(paquete, paquete["fondo"])))
    base = modelo_base(paquete)
    estimador = base.named_steps["modelo"]
    Xt = base.named_steps["preprocesado"].transform(X)
    if tipo == "lineal":
        coef = estimador.coef_[0]
        return estimador.decision_function(Xt), float(estimador.intercept_[0] + paquete["fondo"].to_numpy() @ coef)
    arbol = shap.TreeExplainer(estimador)
    arbol.shap_values(Xt.iloc[:1])  # en XGBoost (shap 0.54), expected_value solo es el exacto tras calcular un SHAP
    valor_base = float(np.ravel(arbol.expected_value)[0])
    return np.asarray(_salida_bruta(paquete["familia"], estimador, Xt), dtype=float), valor_base


def predecir(paquete: dict, X: pd.DataFrame) -> pd.DataFrame:
    """probabilidad (calibrada), alerta (probabilidad ≥ umbral), log_odds (salida sin calibrar) y base_log_odds."""
    columnas = paquete["columnas"]
    X = X[columnas["numericas"] + columnas["categoricas"]]
    probabilidad = paquete["modelo"].predict_proba(X)[:, 1]
    log_odds, valor_base = _partes(paquete, X)
    return pd.DataFrame({"probabilidad": probabilidad, "alerta": probabilidad >= paquete["umbral"],
                         "log_odds": log_odds, "base_log_odds": valor_base}, index=X.index)


def _codificar(fondo: pd.DataFrame, X: pd.DataFrame, columnas: dict):
    """Matrices numéricas para el enmascarador (categóricas como enteros; −1 = vacío) y la función que las decodifica."""
    categoricas = columnas["categoricas"]
    unidas = pd.concat([fondo, X])
    codigos, niveles = {}, {}
    for c in categoricas:
        codigos[c], niveles[c] = pd.factorize(unidas[c], use_na_sentinel=True)
    vacio = {c: next((v for v in unidas[c] if pd.isna(v)), np.nan) for c in categoricas}
    matriz = unidas.astype({c: float for c in columnas["numericas"]}).assign(
        **{c: codigos[c].astype(float) for c in categoricas}).to_numpy(dtype=float)
    orden = list(unidas.columns)

    def decodificar(Z: np.ndarray) -> pd.DataFrame:
        tabla = pd.DataFrame(Z, columns=orden)
        for c in categoricas:
            enteros = np.rint(tabla[c].to_numpy()).astype(int)
            validos = enteros >= 0
            valores = np.full(len(enteros), vacio[c], dtype=object)
            valores[validos] = np.asarray(niveles[c], dtype=object)[enteros[validos]]
            tabla[c] = valores
        return tabla

    return matriz[:len(fondo)], matriz[len(fondo):], decodificar


def explicar(paquete: dict, X: pd.DataFrame) -> tuple[pd.DataFrame, float]:
    """φ por variable original en log-odds sin calibrar (D32), con las columnas numericas + categoricas del paquete, y
    error máximo de aditividad |Σφ + base_log_odds − log_odds| frente a predecir."""
    columnas = paquete["columnas"]
    variables = columnas["numericas"] + columnas["categoricas"]
    X = X[variables]
    tipo = tipo_explicador(paquete)
    if tipo == "permutacion":
        fondo, filas, decodificar = _codificar(paquete["fondo"], X, columnas)
        f = lambda Z: _logit_sin_calibrar(paquete, decodificar(Z))  # noqa: E731
        explicador = shap.PermutationExplainer(f, shap.maskers.Independent(fondo, max_samples=len(fondo)),
                                               seed=paquete["semilla"])
        valores = explicador(filas, max_evals=2 * len(variables) + 1, silent=True).values
        phi = pd.DataFrame(valores, index=X.index, columns=variables)
    else:
        base = modelo_base(paquete)
        estimador = base.named_steps["modelo"]
        Xt = base.named_steps["preprocesado"].transform(X)
        if tipo == "lineal":  # la fórmula de modelo_final.predecir_y_explicar
            phi_t = (Xt - paquete["fondo"]) * estimador.coef_[0]
        else:
            phi_t = pd.DataFrame(shap.TreeExplainer(estimador).shap_values(Xt), index=Xt.index, columns=Xt.columns)
        phi = agregar(phi_t, columnas)
    log_odds, valor_base = _partes(paquete, X)
    error = float(np.abs(phi.sum(axis=1).to_numpy() + valor_base - log_odds).max()) if len(X) else 0.0
    return phi, error


def explicacion_global(paquete: dict, X: pd.DataFrame, semilla: int = 42) -> dict:
    """Media de |φ| por variable sobre las filas de X (con permutación, una muestra de MAX_FILAS_GLOBAL_PERMUTACION filas
    con la semilla), ordenada de mayor a menor y sin las variables sin valores en el entrenamiento, que van aparte."""
    explicador = tipo_explicador(paquete)
    if explicador == "permutacion" and len(X) > MAX_FILAS_GLOBAL_PERMUTACION:
        X = X.sample(n=MAX_FILAS_GLOBAL_PERMUTACION, random_state=semilla)
    phi, error = explicar(paquete, X)
    sin_valores = variables_sin_valores(paquete)
    importancia = phi.drop(columns=sin_valores).abs().mean().sort_values(ascending=False, kind="stable")
    return {"variables": [{"variable": v, "importancia_media_abs": float(m)} for v, m in importancia.items()],
            "sin_contribucion": sin_valores, "n_filas": int(len(X)), "explicador": explicador,
            "aditividad_error_max": error}
