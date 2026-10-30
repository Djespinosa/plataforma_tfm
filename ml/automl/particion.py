"""Divisiones de validación cruzada a partir de una columna de pliegue precalculada (D29-rev)."""

from __future__ import annotations

import numpy as np
import pandas as pd

PLIEGUES = {1, 2, 3, 4, 5}  # los de cortes_oulad.N_PLIEGUES; 2014J no tiene pliegue


def divisiones(pliegue: pd.Series) -> list[tuple[np.ndarray, np.ndarray]]:
    """Una división (índices de ajuste, índices de validación) por pliegue, en orden de pliegue.

    Solo admite filas de entrenamiento: un pliegue vacío o fuera de 1-5 delataría filas de prueba mezcladas.
    """
    if pliegue.isna().any():
        raise ValueError("Hay filas sin pliegue: las divisiones solo se construyen con el entrenamiento")
    if not set(pliegue.unique()) <= PLIEGUES:
        raise ValueError(f"Pliegues fuera de {sorted(PLIEGUES)}: las divisiones solo se construyen con el entrenamiento")
    valores = pliegue.to_numpy()
    return [(np.flatnonzero(valores != p), np.flatnonzero(valores == p)) for p in sorted(pliegue.unique())]
