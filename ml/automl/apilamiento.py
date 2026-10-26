"""Apilamiento sin fuga (D48): paso posterior a la búsqueda, con los hiperparámetros de cada familia ya fijados.

El metamodelo (RL regularizada) se entrena con predicciones out-of-fold de una validación cruzada interna agrupada por
presentación sobre las filas de ajuste; nunca ve predicciones de los datos con que se evalúa (wolpert1992).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.ensemble import StackingClassifier
from sklearn.linear_model import LogisticRegression

from automl.particion import divisiones

METAMODELO = "LogisticRegression(C=1.0, L2) sobre predict_proba de los modelos base"


def apilamiento(base: dict[str, object], pliegue_ajuste: pd.Series, semilla: int = 42) -> StackingClassifier:
    """Apilamiento para ajustar con las filas cuyo pliegue es pliegue_ajuste (en ese orden).

    En la validación cruzada externa, pliegue_ajuste son los 4 pliegues de ajuste; en el modelo final, los 5.
    StackingClassifier no recibe grupos: las divisiones internas se le pasan precalculadas.
    """
    return StackingClassifier(
        estimators=list(base.items()),
        final_estimator=LogisticRegression(random_state=semilla),
        cv=divisiones(pliegue_ajuste),
        stack_method="predict_proba",
    )


def oof_apilamiento(base: dict[str, object], X: pd.DataFrame, y: pd.Series, pliegue: pd.Series,
                    semilla: int = 42) -> np.ndarray:
    """Probabilidades out-of-fold del apilamiento: para cada pliegue externo, todo (modelos base y metamodelo) se
    ajusta con los otros pliegues. La salida es la del metamodelo logístico, sin calibración adicional."""
    salida = np.full(len(y), np.nan)
    for ajuste, validacion in divisiones(pliegue):
        modelo = apilamiento(base, pliegue.iloc[ajuste], semilla).fit(X.iloc[ajuste], y.iloc[ajuste])
        salida[validacion] = modelo.predict_proba(X.iloc[validacion])[:, 1]
    return salida
