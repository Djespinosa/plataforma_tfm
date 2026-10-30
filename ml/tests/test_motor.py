"""Pruebas de ml/automl/motor.py (docs/diseno-api.md §6.2): modelado genérico, modelo final, curva de calibración y
equidad con recuentos de referencia. Datos sintéticos; la no regresión frente a experimento.py la da ml/no_regresion.py."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import StackingClassifier

from automl import busqueda, motor
from automl.calibracion import METODOS, umbral
from automl.equidad import FALTANTE
from test_automl import COLUMNAS, datos

# Primer ensayo de cada familia, más pequeño que el predeterminado, para que las 7 familias entren en segundos.
RAPIDOS = {"rf": {"n_estimators": 20}, "gb": {"max_iter": 20}, "xgb": {"n_estimators": 20},
           "lgbm": {"n_estimators": 20}, "catboost": {"iterations": 30}, "mlp": {"hidden_layer_sizes": "64"}}
CONFIG = {"familias": busqueda.FAMILIAS, "n_trials_por_familia": 1, "n_jobs": 1, "apilamiento": True,
          "n_bootstrap": 20, "sensibilidad_minima": 0.7, "semillas": {"optuna": 42, "modelos": 42, "bootstrap": 42}}
CLAVES_RESUMEN = ["n", "retiros", "familias", "referencias", "apilamiento", "mejor_automl", "contraste_central",
                  "parsimonia", "modelo_desplegado", "calibracion", "punto_operacion_oof"]


@pytest.fixture(scope="module")
def modelado():
    X, y, pliegue = datos(400)
    etapas: list[str] = []
    with pytest.MonkeyPatch.context() as mp:
        for familia, cambios in RAPIDOS.items():
            mp.setitem(busqueda.PREDETERMINADOS, familia, busqueda.PREDETERMINADOS[familia] | cambios)
        resultado = motor.modelar(X, y, pliegue, COLUMNAS, CONFIG, progreso=etapas.append)
    return X, y, pliegue, etapas, resultado


def test_modelar_despliega_un_candidato_y_fija_el_umbral_sobre_sus_oof(modelado):
    _, y, _, _, (resumen, predicciones, otras, modelos) = modelado
    assert list(resumen) == CLAVES_RESUMEN
    desplegado = resumen["modelo_desplegado"]["modelo"]
    assert desplegado in busqueda.FAMILIAS + ["apilamiento"]
    corte = umbral(y, predicciones[desplegado], CONFIG["sensibilidad_minima"])
    assert resumen["punto_operacion_oof"]["umbral_exacto"] == corte
    assert resumen["punto_operacion_oof"]["sensibilidad"] >= 0.7
    assert resumen["mejor_automl"] != "rl" and resumen["contraste_central"]["modelo_b"] == "rl_optimizada"
    assert [r["modelo"] for r in resumen["referencias"]] == ["mayoritaria", "rl_defecto", "rl_optimizada"]
    assert list(modelos) == busqueda.FAMILIAS
    assert set(otras) == {f"{f}_{m}" for f in busqueda.FAMILIAS for m in ["sin_calibrar", *METODOS]}
    assert all(not np.isnan(p).any() for p in predicciones.values())


def test_modelar_exige_rl():
    X, y, pliegue = datos(100)
    with pytest.raises(ValueError, match="regresión logística"):
        motor.modelar(X, y, pliegue, COLUMNAS, CONFIG | {"familias": ["gb", "lgbm"]})


def test_modelar_informa_cada_etapa(modelado):
    _, _, _, etapas, _ = modelado
    assert etapas == busqueda.FAMILIAS + ["referencias", "apilamiento", "comparacion"]


def test_modelar_no_vuelve_a_buscar_en_el_modelo_final(modelado, monkeypatch):
    X, y, pliegue, _, (resumen, _, _, modelos) = modelado

    def prohibida(*args, **kwargs):
        raise AssertionError("el modelo final no debe repetir la búsqueda (D38)")

    monkeypatch.setattr(busqueda, "buscar", prohibida)
    modelo = motor.entrenar_desplegado(resumen, modelos, X, y, pliegue, COLUMNAS, CONFIG)
    assert modelo.predict_proba(X).shape == (len(X), 2)


def test_entrenar_desplegado_apilamiento_sin_calibracion(modelado):
    X, y, pliegue, _, (resumen, _, _, modelos) = modelado
    base = {k: modelos[k] for k in ("rl", "lgbm")}
    forzado = resumen | {"modelo_desplegado": {"modelo": "apilamiento", "motivo": ""}}
    modelo = motor.entrenar_desplegado(forzado, base, X, y, pliegue, COLUMNAS, CONFIG)
    assert isinstance(modelo, StackingClassifier) and not isinstance(modelo, CalibratedClassifierCV)
    assert [nombre for nombre, _ in modelo.estimators] == ["rl", "lgbm"]
    assert len(modelo.cv) == 5  # divisiones agrupadas precalculadas con los 5 pliegues (D48)


def test_entrenar_desplegado_familia_calibrada_con_5_pliegues_ensemble_false(modelado):
    X, y, pliegue, _, (resumen, _, _, modelos) = modelado
    forzado = resumen | {"modelo_desplegado": {"modelo": "rl", "motivo": ""}}
    rl = next(f for f in resumen["familias"] if f["modelo"] == "rl")
    modelo = motor.entrenar_desplegado(forzado, modelos, X, y, pliegue, COLUMNAS, CONFIG)
    assert isinstance(modelo, CalibratedClassifierCV) and modelo.ensemble is False
    assert modelo.method == METODOS[rl["calibracion"]["metodo"]]
    assert len(modelo.cv) == 5 and len(modelo.calibrated_classifiers_) == 1
    todo = busqueda.construir("rl", rl["hiperparametros"], **COLUMNAS, semilla=42).fit(X, y)
    np.testing.assert_array_equal(modelo.calibrated_classifiers_[0].estimator.named_steps["modelo"].coef_,
                                  todo.named_steps["modelo"].coef_)


def test_curva_calibracion_10_intervalos():
    rng = np.random.default_rng(0)
    p = rng.random(2000)
    y = (rng.random(2000) < p).astype(int)
    curva = motor.curva_calibracion(y, p)
    assert len(curva) == 10 and list(curva[0]) == ["predicha", "observada"]
    predichas = [c["predicha"] for c in curva]
    assert predichas == sorted(predichas)
    assert max(abs(c["predicha"] - c["observada"]) for c in curva) < 0.1  # bien calibrada por construcción


def test_auditar_equidad_con_recuentos_de_referencia():
    rng = np.random.default_rng(1)
    n = 400
    atributos = pd.DataFrame({"genero": rng.choice(["F", "M", None], n)})
    y = pd.Series(rng.integers(0, 2, n))
    p = rng.random(n)
    # Referencia (p. ej. la cohorte de prueba): solo F y M, con recuentos conocidos; el vacío no aparece.
    atributos_ref = pd.DataFrame({"genero": ["F"] * 50 + ["M"] * 20})
    y_ref = pd.Series([1] * 35 + [0] * 15 + [1] * 5 + [0] * 15)
    salida = motor.auditar_equidad(y, p, 0.5, atributos, y_ref, atributos_ref, 50, 42, recuentos_de="cohorte de prueba")
    assert salida["recuentos_de"] == "cohorte de prueba"
    subgrupos = salida["genero"]["subgrupos"]
    assert {k: v["retiros_prueba"] for k, v in subgrupos.items()} == {"F": 35, "M": 5, FALTANTE: 0}
    assert [k for k, v in subgrupos.items() if v["solo_descriptiva"]] == ["M", FALTANTE]
    assert subgrupos["F"]["retiros"] == int(y[atributos["genero"] == "F"].sum())
