"""Prueba anti-fuga de D28: la mediana de date_registration se ajusta solo con el entrenamiento de cada pliegue.

Datos sintéticos: cada pliegue tiene fechas de matrícula de magnitud distinta, de modo que la mediana de un pliegue,
la de todo el entrenamiento y la que incluye 2014J son distintas y una imputación global se detectaría.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from sklearn.base import clone
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import cross_validate
from sklearn.pipeline import Pipeline

import cortes_oulad as co
from automl.particion import divisiones
from automl.preprocesado import imputador_mediana


def datos() -> pd.DataFrame:
    filas = []
    for pliegue in range(1, 6):
        for i in range(10):
            fecha = np.nan if i < 2 else -10.0 * pliegue ** 2 - i
            filas.append({"pliegue": pliegue, "particion": "entrenamiento", "date_registration": fecha,
                          "clics_total": float(i), "etiqueta": i % 2})
    for i in range(10):  # 2014J: fechas extremas que moverían la mediana si entraran en el ajuste
        filas.append({"pliegue": pd.NA, "particion": "prueba", "date_registration": np.nan if i < 2 else 500.0 + i,
                      "clics_total": float(i), "etiqueta": i % 2})
    tabla = pd.DataFrame(filas)
    tabla["pliegue"] = tabla["pliegue"].astype("Int64")
    tabla["falta_date_registration"] = tabla["date_registration"].isna().astype(int)
    return tabla


def tuberia() -> Pipeline:
    return Pipeline([("imputar", imputador_mediana(co.IMPUTAR_MEDIANA)), ("modelo", LogisticRegression())])


def entrada(tabla: pd.DataFrame) -> pd.DataFrame:
    return tabla[["date_registration", "falta_date_registration", "clics_total"]]


def mediana_aprendida(modelo: Pipeline) -> float:
    return float(modelo.named_steps["imputar"].named_transformers_["mediana"].statistics_[0])


def test_mediana_por_pliegue_solo_con_su_entrenamiento():
    tabla = datos()
    entrenamiento = tabla[tabla["particion"] == "entrenamiento"].reset_index(drop=True)
    cv = divisiones(entrenamiento["pliegue"])
    resultado = cross_validate(tuberia(), entrada(entrenamiento), entrenamiento["etiqueta"], cv=cv,
                               return_estimator=True)
    global_ = entrenamiento["date_registration"].median()
    for (ajuste, _), modelo in zip(cv, resultado["estimator"]):
        esperada = entrenamiento.loc[ajuste, "date_registration"].median()
        assert mediana_aprendida(modelo) == pytest.approx(esperada)
        assert esperada != pytest.approx(global_)


def test_la_imputacion_de_validacion_no_depende_de_la_validacion():
    tabla = datos()
    entrenamiento = tabla[tabla["particion"] == "entrenamiento"].reset_index(drop=True)
    ajuste, validacion = divisiones(entrenamiento["pliegue"])[0]
    alterada = entrenamiento.copy()
    observadas = alterada.index.isin(validacion) & alterada["date_registration"].notna()
    alterada.loc[observadas, "date_registration"] = 9999.0

    imputadas = []
    for tabla_ in (entrenamiento, alterada):
        modelo = clone(tuberia()).fit(entrada(tabla_.loc[ajuste]), tabla_.loc[ajuste, "etiqueta"])
        transformadas = modelo.named_steps["imputar"].transform(entrada(tabla_.loc[validacion]))
        faltantes = tabla_.loc[validacion, "falta_date_registration"].to_numpy() == 1
        imputadas.append(transformadas.loc[faltantes, "date_registration"].to_numpy())
    np.testing.assert_array_equal(imputadas[0], imputadas[1])


def test_modelo_final_mediana_de_todo_el_entrenamiento_sin_2014J():
    tabla = datos()
    entrenamiento = tabla[tabla["particion"] == "entrenamiento"]
    modelo = tuberia().fit(entrada(entrenamiento), entrenamiento["etiqueta"])
    assert mediana_aprendida(modelo) == pytest.approx(entrenamiento["date_registration"].median())
    assert mediana_aprendida(modelo) != pytest.approx(tabla["date_registration"].median())


def test_el_indicador_de_faltante_se_conserva_y_no_quedan_vacios():
    tabla = datos()
    entrenamiento = tabla[tabla["particion"] == "entrenamiento"]
    transformadas = imputador_mediana(co.IMPUTAR_MEDIANA).fit_transform(entrada(entrenamiento))
    assert not transformadas["date_registration"].isna().any()
    np.testing.assert_array_equal(transformadas["falta_date_registration"], entrenamiento["falta_date_registration"])


def test_divisiones_rechazan_filas_sin_pliegue():
    with pytest.raises(ValueError):
        divisiones(datos()["pliegue"])
