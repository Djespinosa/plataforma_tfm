"""Pruebas de ml/shap_estabilidad.py (D9, D32, D33): variable original de cada columna transformada, SHAP en log-odds
sin calibrar (aditividad; el lineal coincide con shap.LinearExplainer), estabilidad entre pliegues y figura."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
import shap

import shap_estabilidad as se
from automl import busqueda
from automl.calibracion import oof_anidado
from test_automl import COLUMNAS, datos

RL = {"C": 0.3, "l1_ratio": 0.0, "class_weight": "balanced"}


def test_variable_original_y_agregacion_por_variable():
    assert se.variable_original("a", COLUMNAS) == "a"
    assert se.variable_original("missingindicator_b", COLUMNAS) == "b"
    assert se.variable_original("c_faltante", COLUMNAS) == "c"
    columnas = {"numericas": ["x"], "categoricas": ["code", "code_module"]}
    assert se.variable_original("code_module_AAA", columnas) == "code_module"  # prefijo más largo
    with pytest.raises(ValueError):
        se.variable_original("desconocida", COLUMNAS)
    phi = pd.DataFrame({"a": [1.0, -1.0], "missingindicator_b": [0.5, 0.0], "c_x": [0.2, 0.1], "c_y": [-0.1, 0.3]})
    agregado = se.agregar(phi, COLUMNAS)
    assert list(agregado.columns) == ["a", "b", "date_registration", "c"]
    np.testing.assert_allclose(agregado["c"], [0.1, 0.4])
    assert agregado["date_registration"].eq(0).all()  # descartada por el pliegue: 0


def test_rl_lineal_exacto_aditivo_e_igual_a_linear_explainer():
    X, y, pliegue = datos()
    ajuste = (pliegue != 1).to_numpy()
    modelo = busqueda.construir("rl", RL, **COLUMNAS).fit(X[ajuste], y[ajuste])
    phi, error, _ = se.explicar(modelo, X[ajuste], X[~ajuste])
    assert error.max() < 1e-10
    Xa = modelo.named_steps["preprocesado"].transform(X[ajuste])
    Xv = modelo.named_steps["preprocesado"].transform(X[~ajuste])
    masker = shap.maskers.Independent(Xa, max_samples=len(Xa))
    referencia = shap.LinearExplainer(modelo.named_steps["modelo"], masker).shap_values(Xv)
    np.testing.assert_allclose(phi.to_numpy(), referencia, atol=1e-10)


def test_catboost_treeshap_aditivo_en_log_odds():
    X, y, pliegue = datos()
    ajuste = (pliegue != 1).to_numpy()
    params = busqueda.PREDETERMINADOS["catboost"] | {"iterations": 50}
    modelo = busqueda.construir("catboost", params, **COLUMNAS).fit(X[ajuste], y[ajuste])
    phi, error, explicador = se.explicar(modelo, X[ajuste], X[~ajuste])
    assert error.max() < 1e-6 and "TreeSHAP" in explicador
    # log-odds: la sigmoide de la salida bruta es la probabilidad sin calibrar
    bruta = modelo.named_steps["modelo"].predict(modelo.named_steps["preprocesado"].transform(X[~ajuste]),
                                                 prediction_type="RawFormulaVal")
    np.testing.assert_allclose(1 / (1 + np.exp(-bruta)), modelo.predict_proba(X[~ajuste])[:, 1], atol=1e-9)


def test_estabilidad_spearman_y_top10():
    rng = np.random.default_rng(0)
    base = pd.Series(np.arange(20, 0, -1.0), index=[f"v{i}" for i in range(20)])
    iguales = pd.DataFrame([base] * 5, index=range(1, 6))
    e = se.estabilidad(iguales)
    assert e["pares"] == 10 and e["spearman_media"] == 1 and e["top10_solape_media"] == 1
    distintos = pd.DataFrame([base.sample(frac=1, random_state=i).to_numpy() for i in range(5)], index=range(1, 6),
                             columns=base.index)
    e = se.estabilidad(distintos + rng.random((5, 20)) * 1e-3)
    assert e["spearman_rango"][0] <= e["spearman_media"] <= e["spearman_rango"][1] < 1


def test_shap_oof_explica_el_modelo_base_del_principal():
    """El orden de la salida sin calibrar coincide con el de las OOF calibradas con Platt (monótono, D32)."""
    X, y, pliegue = datos()
    p = oof_anidado(busqueda.construir("rl", RL, **COLUMNAS), X, y, pliegue)["platt"]
    resumen, valores = se.shap_oof("rl", {"hiperparametros": RL}, X, y, pliegue, p, COLUMNAS, 42, 1)
    assert resumen["concordancia_con_oof_principal_spearman_min"] == 1.0
    assert resumen["aditividad_error_max"] < 1e-10 and resumen["estabilidad"]["pares"] == 10
    assert list(valores.columns) == COLUMNAS["numericas"] + COLUMNAS["categoricas"] and len(valores) == len(X)
    assert valores.index.equals(X.index)
    assert [v["variable"] for v in resumen["importancia_global"]][0] == "a"


def test_figura_con_un_panel_por_momento_y_eje_x_comun(tmp_path, monkeypatch):
    capturadas = []
    monkeypatch.setattr(se.plt, "close", capturadas.append)
    importancia = lambda k: [{"variable": f"v{i}", "media_abs": k / (i + 1), "rango_pliegues": [0.8 * k / (i + 1),  # noqa: E731
                                                                                              1.2 * k / (i + 1)]}
                             for i in range(20)]
    estable = {"spearman_media": 0.8, "top10_solape_media": 0.7}
    momentos = [{"semana": s, "modelos": [{"papel": "rl_desplegada", "modelo": "rl", "explicador": "lineal",
                                           "importancia_global": importancia(k), "estabilidad": estable},
                                          {"papel": "mejor_automl", "modelo": "apilamiento", "explicador": None}]}
                for s, k in ((0, 0.2), (4, 0.5))]
    se.figura_importancia(momentos, "rl_desplegada", tmp_path / "figura.png")
    ejes = capturadas[0].axes
    assert (tmp_path / "figura.png").exists() and len(ejes) == 2 and len({ax.get_xlim() for ax in ejes}) == 1
    assert len(ejes[0].get_yticklabels()) == 15
