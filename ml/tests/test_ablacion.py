"""Pruebas de ml/ablacion.py (D46, D38): columnas por grupo, reentrenamiento sin búsqueda, ruta abreviada del
apilamiento y pérdida; con OULAD, que la ruta abreviada reproduce las predicciones del principal en la semana 8."""

from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest
from scipy.stats import rankdata
from sklearn.metrics import roc_auc_score

import ablacion as ab
import variante as va
from automl import busqueda
from evidencias import EVIDENCIAS, sha256
from experimento import OOF, cargar_cortes, cargar_entrenamiento, columnas_modelo
from test_automl import COLUMNAS, datos

FAMILIAS = [{"modelo": "rl", "hiperparametros": {"C": 0.3, "l1_ratio": 1.0, "class_weight": "balanced"},
             "calibracion": {"metodo": "platt"}},
            {"modelo": "lgbm", "hiperparametros": busqueda.PREDETERMINADOS["lgbm"] | {"n_estimators": 20},
             "calibracion": {"metodo": "isotonica"}}]


def test_columnas_sin_grupo_quita_solo_las_del_grupo():
    catalogo = pd.DataFrame({"nombre": ["a", "b", "date_registration", "c"],
                             "grupo_ablacion": ["g1", "g2", "g1", "g2"]})
    assert ab.columnas_sin_grupo(COLUMNAS, catalogo, "g1") == {"numericas": ["b"], "categoricas": ["c"],
                                                               "imputar_mediana": []}
    assert ab.columnas_sin_grupo(COLUMNAS, catalogo, "otro") == COLUMNAS


def test_sin_busqueda_y_con_el_metodo_de_calibracion_del_principal(monkeypatch):
    def prohibida(*args, **kwargs):
        raise AssertionError("la ablación no puede lanzar una búsqueda (D38)")

    monkeypatch.setattr(busqueda, "buscar", prohibida)
    X, y, pliegue = datos()
    p = ab.predecir_sin_grupo("lgbm", {"familias": FAMILIAS}, X, y, pliegue, COLUMNAS, 42, 1)
    _, _, otras = va.reentrenar(FAMILIAS[1:], X, y, pliegue, COLUMNAS, 42, 1, apilar=False)
    np.testing.assert_array_equal(p, otras["lgbm_isotonica"])  # el del principal, no el que elegiría el Brier


def test_ruta_abreviada_del_apilamiento_igual_a_la_completa():
    X, y, pliegue = datos()
    abreviada = ab.predecir_sin_grupo("apilamiento", {"familias": FAMILIAS}, X, y, pliegue, COLUMNAS, 42, 1)
    _, completa, _ = va.reentrenar(FAMILIAS, X, y, pliegue, COLUMNAS, 42, 1, apilar=True)
    np.testing.assert_array_equal(abreviada, completa["apilamiento"])


def test_perdida_es_completo_menos_sin_grupo():
    X, y, _ = datos()
    p_sin_grupo = X["a"].to_numpy()
    p_completo = p_sin_grupo + 0.5 * X["b"].fillna(0).to_numpy()
    r = ab.perdida(y, p_completo, p_sin_grupo, 200, 42)
    assert r["perdida"] == round(roc_auc_score(y, p_completo) - roc_auc_score(y, p_sin_grupo), 4) > 0
    assert r["ic95_bootstrap"][0] < r["perdida"] < r["ic95_bootstrap"][1]


def test_figura_con_eje_x_comun_y_los_dos_modelos(tmp_path, monkeypatch):
    capturadas = []
    monkeypatch.setattr(ab.plt, "close", capturadas.append)
    grupos = lambda d: [{"grupo": g, "perdida": d * i, "ic95_bootstrap": [d * i - 0.003, d * i + 0.003]}  # noqa: E731
                        for i, g in enumerate(ab.GRUPOS)]
    momentos = [{"semana": s, "modelos": [{"papel": "mejor_automl", "modelo": "catboost", "grupos": grupos(d)},
                                          {"papel": "rl_desplegada", "modelo": "rl", "grupos": grupos(-d)}]}
                for s, d in ((0, 0.002), (4, 0.01))]
    ab.figura_perdidas(momentos, tmp_path / "figura.png")
    ejes = capturadas[0].axes
    assert (tmp_path / "figura.png").exists() and len({ax.get_xlim() for ax in ejes}) == 1
    assert [t.get_text() for t in ejes[0].get_yticklabels()] == [ab.NOMBRE_GRUPO[g] for g in ab.GRUPOS]


def test_oulad_ruta_abreviada_reproduce_el_principal_en_la_semana_8():
    """Con todas las variables, la ruta abreviada del apilamiento (sin calibración por familia) y la RL con el método
    del principal reproducen sus predicciones out-of-fold: ROC-AUC idéntica y mismo orden de las filas. Con n_jobs > 1
    el apilamiento difiere en el orden de 1e-12 (sumas en coma flotante en paralelo), por lo que no se exige la
    igualdad bit a bit."""
    ruta_json = EVIDENCIAS / "experimentos" / "exp-2026-10-27-01.json"
    ruta_oof = OOF / "exp-2026-10-27-01_semana_8.parquet"
    if not ruta_oof.exists():
        pytest.skip("Sin las predicciones out-of-fold de exp-2026-10-27-01 en data/procesado/oof")
    principal = json.loads(ruta_json.read_text(encoding="utf-8"))
    assert sha256(ruta_oof) == principal["predicciones_oof_sha256"][ruta_oof.name]
    resumen = next(m for m in principal["momentos"] if m["semana"] == 8)
    assert resumen["mejor_automl"] == "apilamiento"
    cortes, catalogo = cargar_cortes(principal["experimento_cortes"])
    columnas = columnas_modelo(catalogo, sin_sensibles=principal["configuracion"]["sin_sensibles"])
    corte = cargar_entrenamiento(8, cortes)
    X, y, pliegue = corte[columnas["numericas"] + columnas["categoricas"]], corte["etiqueta"], corte["pliegue"]
    referencia = va.predicciones_principal(pd.read_parquet(ruta_oof), corte)
    semilla, n_jobs = principal["particion"]["semillas"]["modelos"], principal["configuracion"]["n_jobs"]
    for modelo in ("apilamiento", "rl"):
        p = ab.predecir_sin_grupo(modelo, resumen, X, y, pliegue, columnas, semilla, n_jobs)
        esperado = referencia[f"p_{modelo}"].to_numpy()
        assert roc_auc_score(y, p) == roc_auc_score(y, esperado), modelo
        np.testing.assert_array_equal(rankdata(p), rankdata(esperado), err_msg=modelo)
        np.testing.assert_allclose(p, esperado, rtol=0, atol=1e-9, err_msg=modelo)
