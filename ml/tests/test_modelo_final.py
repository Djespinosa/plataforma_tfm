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
from evidencias import EVIDENCIAS, RAIZ, sha256
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


def test_ajustar_exige_el_umbral_registrado():
    X, y, pliegue = datos()
    tabla = X.assign(etiqueta=y, pliegue=pliegue)
    p = np.random.default_rng(0).random(len(y))
    corte = round(umbral(y, p, 0.7), 6)
    origen = {"semana": 4, "umbral_de": "prueba"}
    resumen, paquete = mf.ajustar(tabla, COLUMNAS, RL, "platt", p, corte, 0.7, 42, 1, origen)
    assert resumen["umbral"]["valor"] == corte == round(paquete["umbral"], 6)
    with pytest.raises(ValueError, match="no coincide"):
        mf.ajustar(tabla, COLUMNAS, RL, "platt", p, corte + 0.01, 0.7, 42, 1, origen)


def test_oulad_umbral_de_la_variante_con_sensibles_es_el_registrado():
    """P-13: el umbral de la variante con sensibles se recalcula desde sus OOF (exp-2026-10-28-01) y coincide con el
    registrado en su análisis de equidad (exp-2026-10-28-02) en los 4 momentos."""
    if not (OOF / "exp-2026-10-28-01_semana_0.parquet").exists():
        pytest.skip("Sin las predicciones out-of-fold de exp-2026-10-28-01 en data/procesado/oof")
    leer = lambda i: json.loads((EVIDENCIAS / "experimentos" / f"{i}.json").read_text(encoding="utf-8"))  # noqa: E731
    con, equidad = leer("exp-2026-10-28-01"), leer("exp-2026-10-28-02")
    cortes, _ = cargar_cortes(con["experimento_cortes"])
    for m in equidad["momentos"]:
        datos_ = cargar_entrenamiento(m["semana"], cortes)
        p = mf.leer_oof(con, m["semana"], datos_)["p_rl"].to_numpy()
        assert round(umbral(datos_["etiqueta"], p, 0.7), 6) == m["con"]["punto_operacion_oof"]["umbral"]


def test_diagnostico_d41_dentro_de_la_muestra():
    d = mf.diagnostico_d41(pd.Series([1, 1, 1, 0, 0]), pd.Series([True, True, False, True, False]))
    assert d["sensibilidad_en_entrenamiento"] == 0.6667 and d["tasa_alerta_en_entrenamiento"] == 0.6
    assert "no es rendimiento" in d["lectura"]


def test_oulad_paquetes_usan_el_umbral_exacto():
    """P-18: los paquetes del modelo final guardan el umbral exacto (sin redondear) y, aplicado a las predicciones
    out-of-fold de su variante, reproduce la sensibilidad y las alertas registradas (0,7025 en la semana 0 del
    desplegado)."""
    leer = lambda i: json.loads((EVIDENCIAS / "experimentos" / f"{i}.json").read_text(encoding="utf-8"))  # noqa: E731
    carpeta = RAIZ / leer("exp-2026-10-29-03")["modelos_sha256"]["carpeta"]
    if not (carpeta / "exp-2026-10-29-03_semana_0.joblib").exists() or not (OOF / "exp-2026-10-27-01_semana_0.parquet").exists():
        pytest.skip("Sin los paquetes de exp-2026-10-29-03 o las predicciones out-of-fold")
    principal, con, equidad = leer("exp-2026-10-27-01"), leer("exp-2026-10-28-01"), leer("exp-2026-10-28-02")
    cortes, _ = cargar_cortes(principal["experimento_cortes"])
    for m in principal["momentos"]:
        semana = m["semana"]
        datos_ = cargar_entrenamiento(semana, cortes)
        y = datos_["etiqueta"].to_numpy()
        punto_con = next(e for e in equidad["momentos"] if e["semana"] == semana)["con"]["punto_operacion_oof"]
        for sufijo, origen, punto in (("", principal, m["punto_operacion_oof"]), ("_con_sensibles", con, punto_con)):
            p = mf.leer_oof(origen, semana, datos_)["p_rl"].to_numpy()
            corte = joblib.load(carpeta / f"exp-2026-10-29-03{sufijo}_semana_{semana}.joblib")["umbral"]
            assert corte == umbral(datos_["etiqueta"], p, 0.7)  # exacto, no el redondeado del JSON
            alerta = p >= corte
            (_, fp), (_, tp) = punto["matriz_confusion"]
            assert alerta.sum() == fp + tp and round(alerta[y == 1].mean(), 4) == punto["sensibilidad"]
    assert principal["momentos"][0]["punto_operacion_oof"]["sensibilidad"] == 0.7025


def test_diagnostico_d41_desde_un_paquete_comprueba_el_umbral_registrado():
    """P-19: el análisis aparte usa el paquete tal cual y exige que su umbral sea el registrado en el modelo final."""
    import diagnostico_d41 as dg

    X, y, _, _, paquete_ = final()
    datos_ = X.assign(etiqueta=y)
    registrado = {"umbral": {"valor": 0.4, "punto_operacion_oof": {"sensibilidad": 0.7, "tasa_alerta": 0.5}}}
    d = dg.diagnostico_momento(paquete_, datos_, registrado)
    alerta = mf.predecir_y_explicar(paquete_, X)[0]["alerta"]
    assert d["umbral_exacto"] == 0.4 and d["sensibilidad_oof"] == 0.7
    assert d["sensibilidad_en_entrenamiento"] == round(float(alerta[y == 1].mean()), 4)
    assert d["lectura"] == mf.LECTURA_DIAGNOSTICO
    with pytest.raises(ValueError, match="no es el registrado"):
        dg.diagnostico_momento(paquete_, datos_, registrado | {"umbral": registrado["umbral"] | {"valor": 0.41}})
