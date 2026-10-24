"""Divisiones de validación cruzada a partir de una columna de pliegue precalculada (D29-rev)."""

from __future__ import annotations

import numpy as np
import pandas as pd


def divisiones(pliegue: pd.Series) -> list[tuple[np.ndarray, np.ndarray]]:
    """Una división (índices de ajuste, índices de validación) por pliegue, en orden de pliegue.

    Solo admite filas de entrenamiento: un pliegue vacío delataría filas de prueba mezcladas.
    """
    if pliegue.isna().any():
        raise ValueError("Hay filas sin pliegue: las divisiones solo se construyen con el entrenamiento")
    valores = pliegue.to_numpy()
    return [(np.flatnonzero(valores != p), np.flatnonzero(valores == p)) for p in sorted(pliegue.unique())]
