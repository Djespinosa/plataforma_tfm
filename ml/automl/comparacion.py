"""Comparación de modelos sobre las mismas predicciones out-of-fold (D5, D40, D44, D49, D49-rev).

- DeLong pareado (DeLong et al., 1988) con el algoritmo de rangos medios de Sun y Xu (2014).
- IC bootstrap del 95 % pareado (se remuestrean matrículas con reemplazo, las mismas para todos los modelos).
- Holm sobre los 4 momentos.
- Parsimonia por no inferioridad: el más simple cuya pérdida frente al mejor tenga límite superior del IC < margen.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.stats import norm, rankdata

MARGEN = 0.02
ALFA = 0.05


def _componentes(y: np.ndarray, p: np.ndarray) -> tuple[float, np.ndarray, np.ndarray]:
    """ROC-AUC y componentes estructurales V10 (por positivo) y V01 (por negativo)."""
    positivos, negativos = p[y == 1], p[y == 0]
    m, n = len(positivos), len(negativos)
    rango_total = rankdata(np.concatenate([positivos, negativos]))
    rango_pos, rango_neg = rankdata(positivos), rankdata(negativos)
    auc = (rango_total[:m].sum() - m * (m + 1) / 2) / (m * n)
    v10 = (rango_total[:m] - rango_pos) / n
    v01 = 1 - (rango_total[m:] - rango_neg) / m
    return auc, v10, v01


def delong(y: np.ndarray, p_a: np.ndarray, p_b: np.ndarray) -> dict:
    """Contraste bilateral de H0: AUC_a = AUC_b sobre las mismas observaciones."""
    y = np.asarray(y)
    auc_a, v10_a, v01_a = _componentes(y, np.asarray(p_a))
    auc_b, v10_b, v01_b = _componentes(y, np.asarray(p_b))
    s10 = np.cov(np.vstack([v10_a, v10_b]))
    s01 = np.cov(np.vstack([v01_a, v01_b]))
    varianza = (s10[0, 0] + s10[1, 1] - 2 * s10[0, 1]) / len(v10_a) + (s01[0, 0] + s01[1, 1] - 2 * s01[0, 1]) / len(v01_a)
    diferencia = auc_a - auc_b
    if varianza <= 0:
        p = 1.0 if diferencia == 0 else 0.0
    else:
        p = float(2 * norm.sf(abs(diferencia) / np.sqrt(varianza)))
    return {"roc_auc_a": float(auc_a), "roc_auc_b": float(auc_b), "diferencia": float(diferencia), "delong_p": p}


def auc_rapida(y: np.ndarray, p: np.ndarray) -> float:
    return _componentes(y, p)[0]


def auc_bootstrap(y: np.ndarray, predicciones: dict[str, np.ndarray], n_bootstrap: int, semilla: int) -> pd.DataFrame:
    """ROC-AUC de cada modelo en cada remuestreo; las mismas matrículas remuestreadas para todos (pareado)."""
    y = np.asarray(y)
    rng = np.random.default_rng(semilla)
    filas = []
    while len(filas) < n_bootstrap:
        indices = rng.integers(0, len(y), len(y))
        if y[indices].min() == y[indices].max():  # remuestreo sin las dos clases: se descarta
            continue
        filas.append({nombre: auc_rapida(y[indices], np.asarray(p)[indices]) for nombre, p in predicciones.items()})
    return pd.DataFrame(filas)


def intervalo(valores: pd.Series | np.ndarray) -> list[float]:
    return [float(np.percentile(valores, 2.5)), float(np.percentile(valores, 97.5))]


def holm(p: list[float]) -> list[float]:
    """p corregidos por Holm-Bonferroni (monótonos y truncados en 1)."""
    orden = np.argsort(p)
    k = len(p)
    corregidos = np.empty(k)
    acumulado = 0.0
    for posicion, i in enumerate(orden):
        acumulado = max(acumulado, min(1.0, (k - posicion) * p[i]))
        corregidos[i] = acumulado
    return corregidos.tolist()


def lectura(diferencia: float, ic: list[float], p_holm: float, margen: float = MARGEN, alfa: float = ALFA) -> str:
    """Lectura en cuatro casos de D49, con signo: diferencia = AutoML − RL optimizada. Una desventaja significativa
    de AutoML ≥ margen es "desventaja_relevante", nunca una ventaja."""
    if p_holm < alfa:
        if diferencia >= margen:
            return "ventaja_relevante"
        return "desventaja_relevante" if diferencia <= -margen else "detectable_sin_relevancia"
    if -margen < ic[0] and ic[1] < margen:
        return "equivalencia_practica"
    return "no_concluyente"


def parsimonia(y: np.ndarray, predicciones: dict[str, np.ndarray], complejidad: dict[str, int],
               n_bootstrap: int, semilla: int, margen: float = MARGEN) -> dict:
    """D33/D49-rev. El mejor es el de mayor ROC-AUC; se despliega el más simple no inferior (límite superior de la
    pérdida < margen); a igual complejidad, el de mayor ROC-AUC. El p de DeLong solo se informa."""
    auc = {nombre: auc_rapida(np.asarray(y), np.asarray(p)) for nombre, p in predicciones.items()}
    mejor = max(auc, key=auc.get)
    muestras = auc_bootstrap(y, predicciones, n_bootstrap, semilla)
    candidatos = []
    for nombre in predicciones:
        ic = intervalo(muestras[mejor] - muestras[nombre])
        candidatos.append({
            "modelo": nombre, "complejidad": complejidad[nombre], "roc_auc_oof": round(auc[nombre], 4),
            "perdida": round(auc[mejor] - auc[nombre], 4), "ic95_bootstrap": [round(v, 4) for v in ic],
            "delong_p": None if nombre == mejor else delong(y, predicciones[mejor], predicciones[nombre])["delong_p"],
            "cumple": bool(ic[1] < margen),
        })
    elegibles = [c for c in candidatos if c["cumple"]]
    desplegado = min(elegibles, key=lambda c: (c["complejidad"], -c["roc_auc_oof"]))
    return {
        "regla": "no inferioridad (D49-rev)", "mejor": mejor, "margen": margen, "n_bootstrap": n_bootstrap,
        "semilla": semilla, "candidatos": candidatos, "desplegado": desplegado["modelo"],
        "motivo": (f"D33/D49-rev: {desplegado['modelo']} es el candidato más simple cuya pérdida de ROC-AUC "
                   f"out-of-fold frente a {mejor} tiene límite superior del IC 95 % "
                   f"({desplegado['ic95_bootstrap'][1]:.4f}) por debajo de {margen}"),
    }
