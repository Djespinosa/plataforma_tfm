"""Pruebas de ml/automl/explicacion.py (docs/diseno-api.md §6.3): explicador por familia en log-odds sin calibrar (D32,
D33), aditividad, variables sin valores (auditoría O4), extremos y compatibilidad con los paquetes de modelo_final."""

from __future__ import annotations

import json

import joblib
import numpy as np
import pandas as pd
import pytest

import modelo_final as mf
import shap_analisis
from automl import busqueda, explicacion, motor
from evidencias import EVIDENCIAS, RAIZ
from test_automl import COLUMNAS, datos

RAPIDOS = {"rf": {"n_estimators": 20}, "gb": {"max_iter": 20}, "xgb": {"n_estimators": 20},
           "lgbm": {"n_estimators": 20}, "catboost": {"iterations": 30}, "mlp": {"hidden_layer_sizes": "64"}}
DESPLEGADO = {"experimento": "prueba", "desplegado": True}


def entrenar(familia: str, X, y, pliegue, columnas=COLUMNAS):
    """Modelo final de una familia (o apilamiento de rl y lgbm) con hiperparámetros pequeños."""
    if familia == "apilamiento":
        base = {f: busqueda.construir(f, busqueda.PREDETERMINADOS[f] | RAPIDOS.get(f, {}), **columnas, semilla=42)
                for f in ("rl", "lgbm")}
        return motor.entrenar_desplegado({"modelo_desplegado": {"modelo": "apilamiento"}}, base, X, y, pliegue,
                                         columnas, {"semillas": {"modelos": 42}, "n_jobs": 1})
    return motor.entrenar_final(familia, busqueda.PREDETERMINADOS[familia] | RAPIDOS.get(familia, {}), "platt", X, y,
                                pliegue, columnas, 42, 1)


def paquete_de(familia: str, X, y, pliegue, columnas=COLUMNAS, semilla: int = 42) -> dict:
    return explicacion.preparar_paquete(entrenar(familia, X, y, pliegue, columnas), familia, 0.4, columnas, X,
                                        DESPLEGADO, semilla)


def test_lineal_reproduce_predecir_y_explicar_de_modelo_final():
    X, y, pliegue = datos()
    calibrado = mf.entrenar_final("rl", {"C": 0.5, "l1_ratio": 0.0, "class_weight": "balanced"}, "platt", X, y,
                                  pliegue, COLUMNAS, 42, 1)
    paquete = mf.paquete(calibrado, 0.4, COLUMNAS, X, 4, DESPLEGADO)  # formato de exp-2026-10-29-03, sin claves nuevas
    prediccion, valores = mf.predecir_y_explicar(paquete, X)
    assert explicacion.tipo_explicador(paquete) == "lineal"
    pd.testing.assert_frame_equal(explicacion.predecir(paquete, X), prediccion)
    phi, error = explicacion.explicar(paquete, X)
    pd.testing.assert_frame_equal(phi, valores)
    assert error < 1e-12
    nuevo = explicacion.preparar_paquete(calibrado, "rl", 0.4, COLUMNAS, X, DESPLEGADO, 42)
    pd.testing.assert_series_equal(nuevo["fondo"], paquete["fondo"])


@pytest.mark.parametrize("familia", busqueda.FAMILIAS + ["apilamiento"])
def test_aditividad_por_familia(familia):
    X, y, pliegue = datos(400)
    paquete = paquete_de(familia, X, y, pliegue)
    assert paquete["explicador"] == explicacion.explicador_de_familia(familia)
    filas = X.iloc[:25]
    prediccion = explicacion.predecir(paquete, filas)
    phi, error = explicacion.explicar(paquete, filas)
    assert list(phi.columns) == COLUMNAS["numericas"] + COLUMNAS["categoricas"]
    suma = phi.sum(axis=1) + prediccion["base_log_odds"]
    assert np.abs(suma - prediccion["log_odds"]).max() < 1e-4 and error < 1e-4
    np.testing.assert_allclose(prediccion["probabilidad"], paquete["modelo"].predict_proba(filas)[:, 1])
    assert (prediccion["alerta"] == (prediccion["probabilidad"] >= 0.4)).all()
    if familia in explicacion.FAMILIAS_ARBOL:  # la salida bruta es el logit de la probabilidad sin calibrar (D32)
        p = explicacion.modelo_base(paquete).predict_proba(filas)[:, 1]
        np.testing.assert_allclose(prediccion["log_odds"], np.log(p / (1 - p)), atol=1e-5)


@pytest.mark.parametrize("familia", ["rl", "gb", "mlp"])
def test_variables_sin_valores_son_las_descartadas(familia):
    X, y, pliegue = datos(400)
    X = X.assign(vacia=np.nan)
    columnas = COLUMNAS | {"numericas": COLUMNAS["numericas"] + ["vacia"]}
    paquete = paquete_de(familia, X, y, pliegue, columnas)
    assert explicacion.variables_sin_valores(paquete) == ["vacia"]
    phi, _ = explicacion.explicar(paquete, X.iloc[:25])
    assert (phi["vacia"] == 0).all()
    global_ = explicacion.explicacion_global(paquete, X.iloc[:25])
    assert global_["sin_contribucion"] == ["vacia"]
    assert "vacia" not in [v["variable"] for v in global_["variables"]]
    assert global_["n_filas"] == 25 and global_["aditividad_error_max"] < 1e-4


def test_limite_extremo_igual_que_shap_analisis():
    assert explicacion.LIMITE_EXTREMO == shap_analisis.LIMITE == 5.0


def test_permutacion_reproducible_con_semilla():
    X, y, pliegue = datos(400)
    paquete = paquete_de("mlp", X, y, pliegue)
    filas = X.iloc[:20]
    phi, _ = explicacion.explicar(paquete, filas)
    pd.testing.assert_frame_equal(explicacion.explicar(paquete, filas)[0], phi)
    otra = paquete | {"semilla": 7}  # mismo fondo, otro orden de permutación
    phi_otra, error = explicacion.explicar(otra, filas)
    assert error < 1e-4 and not np.allclose(phi_otra.to_numpy(), phi.to_numpy())


@pytest.mark.parametrize("familia", ["rl", "lgbm", "rf"])
def test_categorias_nuevas_no_rompen_la_explicacion(familia):
    X, y, pliegue = datos(400)
    paquete = paquete_de(familia, X, y, pliegue)
    nuevas = X.iloc[:10].assign(c=["z"] * 5 + [None] * 5)  # "z" no aparece en el entrenamiento
    prediccion = explicacion.predecir(paquete, nuevas)
    phi, error = explicacion.explicar(paquete, nuevas)
    assert not phi.isna().any().any() and not prediccion.isna().any().any() and error < 1e-4


@pytest.mark.parametrize("desplegado", [False, "True", 1, None])
def test_preparar_paquete_exige_desplegado_true(desplegado):
    X, y, pliegue = datos()
    modelo = entrenar("rl", X, y, pliegue)
    origen = {"experimento": "prueba"} if desplegado is None else {"experimento": "prueba", "desplegado": desplegado}
    with pytest.raises(ValueError, match="desplegado"):
        explicacion.preparar_paquete(modelo, "rl", 0.4, COLUMNAS, X, origen, 42)


def test_oulad_paquetes_de_29_03_siguen_funcionando():
    """Los paquetes exportados de exp-2026-10-29-03 se cargan (clases en automl.*) y dan lo mismo que
    modelo_final.predecir_y_explicar; en la semana 0, las variables sin valores son las que el preprocesado descarta."""
    from experimento import cargar_cortes, cargar_entrenamiento

    registro = json.loads((EVIDENCIAS / "experimentos" / "exp-2026-10-29-03.json").read_text(encoding="utf-8"))
    carpeta = RAIZ / registro["modelos_sha256"]["carpeta"]
    if not (carpeta / "exp-2026-10-29-03_semana_0.joblib").exists():
        pytest.skip("Sin los paquetes de exp-2026-10-29-03 en data/procesado/modelos")
    cortes, _ = cargar_cortes(registro["experimento_cortes"])
    for semana in (0, 4):
        paquete = joblib.load(carpeta / f"exp-2026-10-29-03_semana_{semana}.joblib")
        X = cargar_entrenamiento(semana, cortes).iloc[:2000]
        prediccion, valores = mf.predecir_y_explicar(paquete, X)
        pd.testing.assert_frame_equal(explicacion.predecir(paquete, X), prediccion)
        phi, _ = explicacion.explicar(paquete, X)
        pd.testing.assert_frame_equal(phi, valores)
        sin_valores = explicacion.variables_sin_valores(paquete)
        assert "antelacion_media" in sin_valores if semana == 0 else sin_valores == []
        assert (phi[sin_valores] == 0).all().all()
