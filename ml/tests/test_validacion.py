"""Pruebas de ml/automl/validacion.py (docs/diseno-api.md §6.1): cohorte de prueba y pliegues genéricos, con datos
sintéticos."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from automl.particion import divisiones
from automl.validacion import FRACCION_PRUEBA, K, asignar_pliegues, reservar_prueba


def objetivo(n: int = 1000, prevalencia: float = 0.3, semilla: int = 0) -> pd.Series:
    rng = np.random.default_rng(semilla)
    return pd.Series(rng.random(n) < prevalencia, index=pd.RangeIndex(100, 100 + n), name="y")


def grupos_de(y: pd.Series, n_grupos: int, nombre: str = "grupo") -> pd.Series:
    return pd.Series([f"g{i % n_grupos}" for i in range(len(y))], index=y.index, name=nombre)


def test_pliegues_estratificados_reproducibles_con_semilla():
    y = objetivo()
    for grupos in (None, grupos_de(y, 12)):
        a, b, c = (asignar_pliegues(y, grupos, s) for s in (42, 42, 7))
        pd.testing.assert_series_equal(a, b)
        assert not a.equals(c)


def test_pliegues_en_1_a_5_y_compatibles_con_divisiones():
    y = objetivo()
    for grupos in (None, grupos_de(y, 12)):
        pliegue = asignar_pliegues(y, grupos, 42)
        assert str(pliegue.dtype) == "Int64" and pliegue.index.equals(y.index)
        assert set(pliegue.unique()) == set(range(1, K + 1))
        assert len(divisiones(pliegue)) == K


def test_prevalencia_por_pliegue_estratificada():
    y = objetivo(1000)
    pliegue = asignar_pliegues(y, None, 42)
    por_pliegue = y.groupby(pliegue).mean()
    assert (por_pliegue - y.mean()).abs().max() <= 0.02


def test_ningun_grupo_en_dos_pliegues():
    y = objetivo()
    grupos = grupos_de(y, 20)
    pliegue = asignar_pliegues(y, grupos, 42)
    assert (pliegue.groupby(grupos).nunique() == 1).all()


def test_menos_de_5_grupos_falla_sin_cambiar_de_esquema():
    y = objetivo()
    assert set(asignar_pliegues(y, None, 42).unique()) == set(range(1, K + 1))  # estratificado funcionaría
    with pytest.raises(ValueError, match=r"La columna de grupo «cohorte» tiene 4 valores distintos; .* al menos 5"):
        asignar_pliegues(y, grupos_de(y, 4, "cohorte"), 42)


def test_grupos_con_vacios_falla():
    y = objetivo()
    grupos = grupos_de(y, 12, "cohorte")
    grupos.iloc[[0, 5, 9]] = None
    with pytest.raises(ValueError, match="La columna de grupo «cohorte» tiene valores vacíos en 3 filas"):
        asignar_pliegues(y, grupos, 42)


def test_pliegue_sin_una_clase_falla():
    # 6 grupos puros: un solo grupo con todos los positivos, así que 4 pliegues quedan sin positivos.
    y = pd.Series([True] * 50 + [False] * 250)
    grupos = pd.Series(["pos"] * 50 + [f"neg{i % 5}" for i in range(250)], name="cohorte")
    with pytest.raises(ValueError, match=r"Con esta columna de grupo, el pliegue \d queda sin filas de una de las clases"):
        asignar_pliegues(y, grupos, 42)


def test_clase_con_menos_de_5_filas_falla():
    y = pd.Series([True] * 4 + [False] * 100)
    for grupos in (None, grupos_de(y, 10)):
        with pytest.raises(ValueError, match="La clase «True» tiene 4 filas de entrenamiento; .* al menos 5 por clase"):
            asignar_pliegues(y, grupos, 42)


def test_prueba_por_valores_reserva_exactamente_esas_filas():
    y = objetivo(300)
    datos = pd.DataFrame({"anio": [2013, 2014, 2015] * 100, "x": np.arange(300)}, index=y.index)
    cohorte = {"modo": "valores", "columna": "anio", "valores": ["2014", 2015]}
    mascara = reservar_prueba(datos, y, cohorte, None, 42)
    assert mascara.dtype == bool and mascara.index.equals(datos.index)
    assert mascara.equals((datos["anio"] >= 2014).rename("prueba"))
    with pytest.raises(ValueError, match="Ningún valor de la cohorte de prueba aparece en «anio»"):
        reservar_prueba(datos, y, {"modo": "valores", "columna": "anio", "valores": ["2020"]}, None, 42)


def test_prueba_por_valores_columna_con_vacios_y_valores_ausentes():
    """Una columna entera con vacíos se lee como float (2014.0): "2014" y 2014.0 la seleccionan igual; si alguno de los
    valores pedidos no aparece, falla en vez de reservar menos filas de las declaradas."""
    y = objetivo(300)
    anio = pd.Series([2013, 2014, 2015] * 100, index=y.index, dtype=float)
    anio.iloc[::7] = np.nan
    datos = pd.DataFrame({"anio": anio})
    esperada = (anio == 2014).rename("prueba")
    for valores in (["2014"], [2014], [2014.0], ["2014", 2014.0]):
        assert reservar_prueba(datos, y, {"modo": "valores", "columna": "anio", "valores": valores}, None, 42).equals(esperada)
    with pytest.raises(ValueError, match="Los valores «2020» de la cohorte de prueba no aparecen en «anio»"):
        reservar_prueba(datos, y, {"modo": "valores", "columna": "anio", "valores": [2014, "2020"]}, None, 42)


def test_prueba_por_valores_que_comparte_grupos_falla():
    y = objetivo(300)
    datos = pd.DataFrame({"anio": [2013, 2014, 2015] * 100}, index=y.index)
    cohorte = {"modo": "valores", "columna": "anio", "valores": ["2015"]}
    por_anio = datos["anio"].astype(str).rename("grupo")
    assert reservar_prueba(datos, y, cohorte, por_anio, 42).sum() == 100  # cohortes completas: válida
    mezclados = grupos_de(y, 10)  # cada grupo tiene filas de los tres años
    with pytest.raises(ValueError, match=r"La cohorte de prueba comparte grupos con el entrenamiento \(10 grupos\)"):
        reservar_prueba(datos, y, cohorte, mezclados, 42)


def test_prueba_aleatoria_estratificada_20_por_ciento_con_semilla():
    y = objetivo(1000)
    datos = pd.DataFrame({"x": np.arange(1000)}, index=y.index)
    cohorte = {"modo": "aleatoria"}
    a, b, c = (reservar_prueba(datos, y, cohorte, None, s) for s in (42, 42, 7))
    assert a.index.equals(datos.index) and a.dtype == bool
    assert a.sum() == int(FRACCION_PRUEBA * len(y))
    assert abs(y[a].mean() - y.mean()) <= 0.01 and abs(y[~a].mean() - y.mean()) <= 0.01
    assert a.equals(b) and not a.equals(c)


def test_prueba_aleatoria_con_grupos_falla():
    y = objetivo(300)
    datos = pd.DataFrame({"x": np.arange(300)}, index=y.index)
    with pytest.raises(ValueError, match="Con columna de grupo, la cohorte de prueba se elige por valores"):
        reservar_prueba(datos, y, {"modo": "aleatoria"}, grupos_de(y, 10), 42)


def test_sin_cohorte_no_reserva_nada():
    y = objetivo(300)
    datos = pd.DataFrame({"x": np.arange(300)}, index=y.index)
    mascara = reservar_prueba(datos, y, None, None, 42)
    assert mascara.dtype == bool and mascara.index.equals(datos.index) and not mascara.any()
