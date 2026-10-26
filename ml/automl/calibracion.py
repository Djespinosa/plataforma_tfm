"""Predicciones out-of-fold con calibración anidada (D37), elección del método y umbral (D6, D31, D45).

Para cada pliegue externo f, el modelo se ajusta solo con los otros pliegues y se predice f sin calibrar; el
calibrador (Platt o isotónica) es un CalibratedClassifierCV cuyas divisiones internas son esos otros pliegues
(agrupadas por presentación), así que ninguna probabilidad calibrada de f procede de un calibrador que vio f.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import brier_score_loss, confusion_matrix, precision_recall_curve

from automl.particion import divisiones

METODOS = {"platt": "sigmoid", "isotonica": "isotonic"}


def oof_anidado(modelo, X: pd.DataFrame, y: pd.Series, pliegue: pd.Series, calibrar: bool = True) -> dict[str, np.ndarray]:
    """Probabilidades out-of-fold sin calibrar y, si calibrar, con cada método de METODOS."""
    nombres = ["sin_calibrar", *(METODOS if calibrar else [])]
    salida = {nombre: np.full(len(y), np.nan) for nombre in nombres}
    for ajuste, validacion in divisiones(pliegue):
        Xa, ya, Xv = X.iloc[ajuste], y.iloc[ajuste], X.iloc[validacion]
        salida["sin_calibrar"][validacion] = clone(modelo).fit(Xa, ya).predict_proba(Xv)[:, 1]
        if calibrar:
            internas = divisiones(pliegue.iloc[ajuste])
            for nombre, metodo in METODOS.items():
                calibrado = CalibratedClassifierCV(clone(modelo), method=metodo, cv=internas).fit(Xa, ya)
                salida[nombre][validacion] = calibrado.predict_proba(Xv)[:, 1]
    return salida


def elegir_metodo(y: pd.Series, oof: dict[str, np.ndarray]) -> dict:
    brier = {nombre: float(brier_score_loss(y, oof[nombre])) for nombre in ["sin_calibrar", *METODOS]}
    metodo = min(METODOS, key=lambda nombre: brier[nombre])
    return {"metodo": metodo, "brier_sin_calibrar": round(brier["sin_calibrar"], 4),
            "brier_calibrado": round(brier[metodo], 4),
            "brier_por_metodo": {nombre: round(brier[nombre], 4) for nombre in METODOS}, "anidada": True}


def umbral(y: pd.Series, p: np.ndarray, sensibilidad_minima: float = 0.70) -> float:
    """Máxima precisión con sensibilidad ≥ mínima, sin margen (D45); a igual precisión, el umbral más alto."""
    precision, sensibilidad, umbrales = precision_recall_curve(y, p)
    precision, sensibilidad = precision[:-1], sensibilidad[:-1]  # el último punto no tiene umbral
    validos = np.flatnonzero(sensibilidad >= sensibilidad_minima)
    mejor = precision[validos].max()
    return float(umbrales[validos[precision[validos] == mejor]].max())


def punto_operacion(y: pd.Series, p: np.ndarray, corte: float) -> dict:
    alerta = (p >= corte).astype(int)
    tn, fp, fn, tp = confusion_matrix(y, alerta, labels=[0, 1]).ravel()
    return {
        "umbral": round(corte, 6),
        "sensibilidad": round(tp / (tp + fn), 4),
        "precision": round(tp / (tp + fp), 4) if tp + fp else None,
        "tasa_alerta": round(float(alerta.mean()), 4),
        "tasa_falsos_positivos": round(fp / (fp + tn), 4),
        "matriz_confusion": [[int(tn), int(fp)], [int(fn), int(tp)]],
    }
