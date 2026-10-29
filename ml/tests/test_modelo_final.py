"""Pruebas de ml/modelo_final.py (D41, D31-rev, D54, D32): modelo base con todo el entrenamiento, calibrador sobre los
pliegues agrupados, umbral transferido, SHAP aditivo e igual al de la validación, persistencia y rechazo de filas sin
pliegue; con OULAD, que el umbral recalculado es el del principal en los 4 momentos."""

from __future__ import annotations

import json

import joblib
import numpy as np
import pandas as pd
import pytest

import modelo_final as mf
import shap_estabilidad as se
from automl import busqueda
from automl.calibracion import umbral
from evidencias import EVIDENCIAS, sha256
from experimento import OOF, cargar_cortes, cargar_entrenamiento
from test_automl import COLUMNAS, datos
from variante import predicciones_principal

RL = {"C": 0.3, "l1_ratio": 0.0, "class_weight": "balanced"}


def final(metodo: str = "platt"):
    X, y, pliegue = datos()
    calibrado = mf.entrenar_final("rl", RL, metodo, X, y, pliegue, COLUMNAS, 42, 1)
    return X, y, pliegue, calibrado, mf.paquete(calibrado, 0.4, COLUMNAS, X, 4, {"experimento": "prueba"})


def test_base_con_todo_el_entrenamiento_y_calibrador_sobre_los_pliegues():
    X, y, _, calibrado, _ = final()
    assert len(calibrado.calibrated_classifiers_) == 1 and calibrado.ensemble is False
    base = calibrado.calibrated_classifiers_[0].estimator
    todo = busqueda.construir("rl", RL, **COLUMNAS, semilla=42).fit(X, y)
    np.testing.assert_array_equal(base.named_steps["modelo"].coef_, todo.named_steps["modelo"].coef_)
    assert len(calibrado.cv) == 5  # 5 pliegues agrupados


def test_umbral_transferido_y_alerta():
    X, _, _, _, paquete = final()
    prediccion, _ = mf.predecir_y_explicar(paquete, X)
    assert paquete["umbral"] == 0.4
    np.testing.assert_array_equal(prediccion["alerta"], prediccion["probabilidad"] >= 0.4)
    assert prediccion["probabilidad"].between(0, 1).all()


@pytest.mark.parametrize("metodo", ["platt", "isotonica"])
def test_shap_final_aditivo_e_igual_al_de_la_validacion(metodo):
    X, _, _, calibrado, paquete = final(metodo)
    prediccion, valores = mf.predecir_y_explicar(paquete, X.iloc[:40])
    suma = valores.sum(axis=1) + prediccion["base_log_odds"]
    np.testing.assert_allclose(suma, prediccion["log_odds"], atol=1e-10)
    phi, _, _ = se.explicar(calibrado.calibrated_classifiers_[0].estimator, X, X.iloc[:40])
    np.testing.assert_allclose(valores.to_numpy(), se.agregar(phi, COLUMNAS).to_numpy(), atol=1e-12)
    assert list(valores.columns) == COLUMNAS["numericas"] + COLUMNAS["categoricas"]


def test_paquete_se_guarda_y_carga_con_las_mismas_predicciones(tmp_path):
    X, _, _, _, paquete = final()
    ruta = tmp_path / "modelo.joblib"
    joblib.dump(paquete, ruta)
    cargado = joblib.load(ruta)
    pd.testing.assert_frame_equal(mf.predecir_y_explicar(cargado, X)[0], mf.predecir_y_explicar(paquete, X)[0])
    assert len(sha256(ruta)) == 64


def test_rechaza_filas_sin_pliegue():
    X, y, pliegue = datos()
    pliegue = pliegue.astype("Float64")
    pliegue.iloc[:10] = pd.NA  # filas de 2014J: sin pliegue
    with pytest.raises(ValueError, match="sin pliegue"):
        mf.entrenar_final("rl", RL, "platt", X, y, pliegue, COLUMNAS, 42, 1)


def test_oulad_umbral_recalculado_es_el_del_principal():
    """D41: el umbral que se transfiere sale de las predicciones out-of-fold calibradas de la RL desplegada del principal
    y coincide con su JSON en los 4 momentos."""
    ruta_oof = OOF / "exp-2026-10-27-01_semana_0.parquet"
    if not ruta_oof.exists():
        pytest.skip("Sin las predicciones out-of-fold de exp-2026-10-27-01 en data/procesado/oof")
    principal = json.loads((EVIDENCIAS / "experimentos" / "exp-2026-10-27-01.json").read_text(encoding="utf-8"))
    cortes, _ = cargar_cortes(principal["experimento_cortes"])
    for resumen in principal["momentos"]:
        semana = resumen["semana"]
        assert resumen["modelo_desplegado"]["modelo"] == "rl"
        datos_ = cargar_entrenamiento(semana, cortes)
        oof = predicciones_principal(pd.read_parquet(OOF / f"exp-2026-10-27-01_semana_{semana}.parquet"), datos_)
        corte = umbral(datos_["etiqueta"], oof["p_rl"].to_numpy(), principal["configuracion"]["sensibilidad_minima"])
        assert round(corte, 6) == resumen["punto_operacion_oof"]["umbral"]
