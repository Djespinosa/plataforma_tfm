"""Pruebas de ml/variante.py (D8, D38): reentrenamiento sin búsqueda, alineación con el principal y salvaguarda."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from sklearn.metrics import roc_auc_score

import variante as va
from automl import busqueda
from test_automl import COLUMNAS, datos


def test_variante_reutiliza_los_hiperparametros_sin_buscar(monkeypatch):
    def prohibida(*args, **kwargs):
        raise AssertionError("una variante no puede lanzar una búsqueda (D38)")

    construidos = []
    original = busqueda.construir

    def espia(familia, params, **kwargs):
        construidos.append((familia, params))
        return original(familia, params, **kwargs)

    monkeypatch.setattr(busqueda, "buscar", prohibida)
    monkeypatch.setattr(busqueda, "construir", espia)
    X, y, pliegue = datos()
    familias = [{"modelo": "rl", "hiperparametros": {"C": 0.3, "l1_ratio": 1.0, "class_weight": "balanced"}},
                {"modelo": "lgbm", "hiperparametros": busqueda.PREDETERMINADOS["lgbm"] | {"n_estimators": 20}}]
    filas, predicciones, otras = va.reentrenar(familias, X, y, pliegue, COLUMNAS, 42, 1, apilar=True)
    assert construidos == [(f["modelo"], f["hiperparametros"]) for f in familias]
    assert [f["modelo"] for f in filas] == ["rl", "lgbm", "apilamiento"]
    assert all(not np.isnan(p).any() for p in predicciones.values())
    assert set(otras) == {f"{f}_{m}" for f in ("rl", "lgbm") for m in ("sin_calibrar", "platt", "isotonica")}
    metodo = filas[0]["calibracion"]["metodo"]
    np.testing.assert_array_equal(predicciones["rl"], otras[f"rl_{metodo}"])


def test_predicciones_del_principal_alineadas_fila_a_fila():
    corte = pd.DataFrame({"code_module": ["AAA", "BBB"], "code_presentation": ["2013J", "2014B"],
                          "id_student": [1, 2], "pliegue": [1, 2], "etiqueta": [0, 1]})
    oof = corte.assign(p_rl=[0.2, 0.7])
    assert va.predicciones_principal(oof, corte) is oof
    with pytest.raises(ValueError):
        va.predicciones_principal(oof.iloc[::-1], corte)
    with pytest.raises(ValueError):
        va.predicciones_principal(oof.iloc[:1], corte)


def test_contraste_con_menos_sin_y_margen():
    X, y, _ = datos()
    p_sin = X["a"].to_numpy()
    p_con = p_sin + 0.5 * X["b"].fillna(0).to_numpy()
    c = va.contraste(y, p_con, p_sin, 200, 42)
    assert c["diferencia"] == round(roc_auc_score(y, p_con) - roc_auc_score(y, p_sin), 4)
    assert c["ic95_bootstrap"][0] < c["diferencia"] < c["ic95_bootstrap"][1]
    assert c["diferencia"] > 0 and c["alcanza_margen"] == (c["diferencia"] >= va.MARGEN)
    assert va.contraste(y, p_sin, p_sin, 50, 42)["diferencia"] == 0


def _momento(semana, diferencias, mejores):
    return {"semana": semana, "por_modelo": [{"modelo": m, "diferencia": d, "alcanza_margen": d >= va.MARGEN}
                                             for m, d in diferencias.items()],
            "mejores": {"diferencia": mejores, "alcanza_margen": mejores >= va.MARGEN}}


def test_salvaguarda_d38_se_activa_desde_el_margen():
    tranquilos = [_momento(0, {"rl": 0.0199, "lgbm": -0.01}, 0.015), _momento(4, {"rl": 0.0}, 0.0)]
    assert not va.salvaguarda(tranquilos)["activada"]
    regla = va.salvaguarda(tranquilos + [_momento(8, {"rl": 0.005, "apilamiento": 0.02}, 0.01)])
    assert regla["activada"]
    assert regla["activadores"] == [{"semana": 8, "comparacion": "apilamiento", "diferencia": 0.02}]
    assert va.salvaguarda([_momento(12, {"rl": 0.01}, 0.021)])["activadores"][0]["comparacion"] == "mejor con − mejor sin"


def test_figura_con_eje_x_comun_margen_visible_y_fila_de_mejores(tmp_path, monkeypatch):
    capturadas = []
    monkeypatch.setattr(va.plt, "close", capturadas.append)
    momentos = [
        {"semana": s, "por_modelo": [{"modelo": "rl", "diferencia": d, "ic95_bootstrap": [d - 0.004, d + 0.004]},
                                     {"modelo": "mlp", "diferencia": -d, "ic95_bootstrap": [-d - 0.006, -d + 0.006]}],
         "mejores": {"diferencia": d / 2, "ic95_bootstrap": [d / 2 - 0.003, d / 2 + 0.003]}}
        for s, d in ((0, 0.003), (4, 0.012))
    ]
    ruta = tmp_path / "figura.png"
    va.figura_diferencias(momentos, ruta)
    assert ruta.exists()
    ejes = capturadas[0].axes
    assert len({ax.get_xlim() for ax in ejes}) == 1
    izquierda, derecha = ejes[0].get_xlim()
    assert izquierda < -0.018 and derecha > va.MARGEN
    assert [t.get_text() for t in ejes[0].get_yticklabels()] == ["rl", "mlp", "mejor con − mejor sin"]
