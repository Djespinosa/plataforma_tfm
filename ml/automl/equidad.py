"""Auditoría de equidad (D50): probabilidades igualadas (hardt2016) en el umbral de decisión.

Indicador principal: sensibilidad por subgrupo (igualdad de oportunidades); secundario: tasa de falsos positivos.
Diferencia entre subgrupos = máxima − mínima. IC bootstrap del 95 % remuestreando matrículas.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

MINIMO_RETIROS_PRUEBA = 30
FALTANTE = "faltante"


def _tasas(y: np.ndarray, alerta: np.ndarray, grupos: np.ndarray, valores: list) -> tuple[dict, dict]:
    sensibilidad, falsos_positivos = {}, {}
    for valor in valores:
        en = grupos == valor
        positivos, negativos = en & (y == 1), en & (y == 0)
        sensibilidad[valor] = alerta[positivos].mean() if positivos.any() else np.nan
        falsos_positivos[valor] = alerta[negativos].mean() if negativos.any() else np.nan
    return sensibilidad, falsos_positivos


def _diferencia(tasas: dict) -> float:
    valores = [v for v in tasas.values() if not np.isnan(v)]
    return max(valores) - min(valores) if len(valores) > 1 else np.nan


def _redondear(v: float) -> float | None:
    return None if np.isnan(v) else round(float(v), 4)


def _ic(muestras: list[float]) -> list[float | None]:
    validas = np.asarray([m for m in muestras if not np.isnan(m)])
    if not len(validas):
        return [None, None]
    return [round(float(np.percentile(validas, 2.5)), 4), round(float(np.percentile(validas, 97.5)), 4)]


def auditar(y: np.ndarray, p: np.ndarray, corte: float, atributos: pd.DataFrame, retiros_prueba: dict[str, dict],
            n_bootstrap: int, semilla: int) -> dict:
    """atributos: una columna por atributo sensible, alineada con y; retiros_prueba: {atributo: {valor: retiros}}
    en 2014J (recuento descriptivo, sin predicciones)."""
    y, alerta = np.asarray(y), (np.asarray(p) >= corte).astype(int)
    rng = np.random.default_rng(semilla)
    remuestreos = [rng.integers(0, len(y), len(y)) for _ in range(n_bootstrap)]
    salida = {}
    for atributo in atributos.columns:
        grupos = atributos[atributo].astype(object).where(atributos[atributo].notna(), FALTANTE).to_numpy()
        valores = sorted(pd.unique(grupos), key=str)
        sens, fpr = _tasas(y, alerta, grupos, valores)
        muestras = [_tasas(y[i], alerta[i], grupos[i], valores) for i in remuestreos]
        subgrupos = {}
        for valor in valores:
            en = grupos == valor
            retiros = int(retiros_prueba.get(atributo, {}).get(valor, 0))
            subgrupos[str(valor)] = {
                "n": int(en.sum()), "retiros": int(y[en].sum()), "retiros_prueba": retiros,
                "sensibilidad": _redondear(sens[valor]), "sensibilidad_ic95": _ic([m[0][valor] for m in muestras]),
                "tasa_falsos_positivos": _redondear(fpr[valor]),
                "tasa_falsos_positivos_ic95": _ic([m[1][valor] for m in muestras]),
                "solo_descriptiva": retiros < MINIMO_RETIROS_PRUEBA,
            }
        salida[atributo] = {
            "subgrupos": subgrupos,
            "diferencia_sensibilidad": _redondear(_diferencia(sens)),
            "diferencia_sensibilidad_ic95": _ic([_diferencia(m[0]) for m in muestras]),
            "diferencia_tasa_falsos_positivos": _redondear(_diferencia(fpr)),
            "diferencia_tasa_falsos_positivos_ic95": _ic([_diferencia(m[1]) for m in muestras]),
        }
    return salida
