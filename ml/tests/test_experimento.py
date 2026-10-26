"""Pruebas de ml/experimento.py: columnas de entrada (D38) y uso exclusivo del entrenamiento."""

from __future__ import annotations

import pandas as pd

import cortes_oulad as co
import experimento as ex
from test_cortes_oulad import tablas_sinteticas


def catalogo() -> pd.DataFrame:
    tablas = tablas_sinteticas()
    return co.catalogo_variables(co.tipos_actividad(tablas["vle"]))


def test_busqueda_principal_sin_variables_sensibles():
    columnas = ex.columnas_modelo(catalogo(), sin_sensibles=True)
    entrada = set(columnas["numericas"]) | set(columnas["categoricas"])
    assert not entrada & set(co.SENSIBLES)
    assert not entrada & set(co.NO_VARIABLES) - {"code_module"}
    assert columnas["imputar_mediana"] == ["date_registration"]
    con = ex.columnas_modelo(catalogo(), sin_sensibles=False)
    assert set(co.SENSIBLES) <= set(con["categoricas"])


def test_identificadores_y_etiqueta_nunca_son_entrada():
    columnas = ex.columnas_modelo(catalogo(), sin_sensibles=False)
    entrada = set(columnas["numericas"]) | set(columnas["categoricas"])
    assert not entrada & {"id_student", "code_presentation", "presentacion", "particion", "pliegue", "etiqueta",
                          "final_result", "date_unregistration"}


def test_retiros_de_prueba_salen_del_experimento_de_cortes():
    cortes = {"subgrupos": [
        {"semana": 4, "particion": "prueba", "variable": "gender", "valor": "F", "desercion": 31},
        {"semana": 4, "particion": "entrenamiento", "variable": "gender", "valor": "F", "desercion": 99},
        {"semana": 8, "particion": "prueba", "variable": "gender", "valor": "F", "desercion": 7},
    ]}
    assert ex.retiros_prueba(cortes, 4) == {"gender": {"F": 31}}


def test_rl_defecto_con_la_misma_calibracion_anidada_que_los_candidatos():
    """D53: la referencia rl_defecto pasa por la calibración anidada y la elección por Brier de las familias."""
    import numpy as np
    from sklearn.metrics import roc_auc_score

    from automl.calibracion import elegir_metodo, oof_anidado
    from test_automl import COLUMNAS, datos

    X, y, pliegue = datos()
    referencias, predicciones = ex.calcular_referencias(X, y, pliegue, COLUMNAS, 42)
    mayoritaria, rl = referencias
    assert mayoritaria["calibracion"] is None
    oof = oof_anidado(ex.rl_defecto(COLUMNAS, 42), X, y, pliegue)  # anti-fuga probada en test_automl
    metodo = elegir_metodo(y, oof)["metodo"]
    assert rl["calibracion"]["metodo"] == metodo
    np.testing.assert_allclose(predicciones["ref_rl_defecto"], oof[metodo])
    assert not np.allclose(predicciones["ref_rl_defecto"], oof["sin_calibrar"])
    assert rl["roc_auc_oof_sin_calibrar"] == round(roc_auc_score(y, oof["sin_calibrar"]), 4)
