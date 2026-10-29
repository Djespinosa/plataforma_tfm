"""Pruebas de ml/shap_analisis.py: estabilidad sin las variables nulas, percentil, equivalencia de la alerta con un umbral
en la suma de SHAP por pliegue y contrafactual con los SHAP acotados."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

import shap_analisis as sa


def test_estabilidad_sin_nulas_quita_las_variables_siempre_cero():
    rng = np.random.default_rng(0)
    phi = pd.DataFrame(rng.normal(size=(100, 12)), columns=[f"v{i}" for i in range(12)]).assign(cero=0.0, nada=0.0)
    pliegue = pd.Series(np.repeat(np.arange(1, 6), 20))
    e = sa.estabilidad_dos_versiones(phi, pliegue)
    assert e["variables_nulas"] == ["cero", "nada"]
    assert e["todas"]["variables"] == 14 and e["sin_nulas"]["variables"] == 12 and e["todas"]["pares"] == 10
    assert e["todas"]["spearman_media"] > e["sin_nulas"]["spearman_media"]  # los ceros empatados inflan Spearman


def test_percentil_en_el_entrenamiento():
    valores = pd.Series([1.0, 2.0, 3.0, 4.0, np.nan])
    assert sa.percentil(valores, 4.0) == 100.0 and sa.percentil(valores, 2.0) == 50.0
    assert sa.percentil(valores, np.nan) is None


def test_extremos_alerta_equivalente_y_contrafactual_acotado():
    phi = pd.DataFrame({"a": [0.5, -0.2, 8.0, -9.0, 0.1, 0.3], "b": [0.1, 0.0, -1.0, 0.0, 0.2, -0.4]})
    datos = pd.DataFrame({"a": [1.0, 2.0, 50.0, 60.0, 3.0, 4.0], "b": [0.0, 1.0, 1.0, 0.0, 1.0, 0.0],
                          "pliegue": [1, 1, 1, 2, 2, 2]})
    suma = phi.sum(axis=1).to_numpy()  # [0.6, -0.2, 7.0, -9.0, 0.3, -0.1]
    alerta = np.array([True, False, True, False, True, False])  # pliegue 1: s_f = 0.6; pliegue 2: s_f = 0.3
    np.testing.assert_allclose(sa.umbral_en_suma(suma, alerta, datos["pliegue"].to_numpy()), [0.6] * 3 + [0.3] * 3)
    r = sa.extremos(phi, datos, alerta)
    assert r["filas_con_extremo"] == 2 and r["shap_abs_max"] == 9.0
    assert [v["variable"] for v in r["variables"]] == ["a"] and r["variables"][0]["percentil_min"] == 83.33
    assert r["alerta"]["cambian_al_acotar"] == 0  # 7 → 4 sigue ≥ 0,6; −9 → −5 sigue < 0,3
    with pytest.raises(ValueError, match="no cumplen"):
        sa.extremos(phi, datos, np.array([True, True, False, False, True, False]))
