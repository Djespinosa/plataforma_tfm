"""Pruebas de la comparación de ml/no_regresion.py (sin ejecutar los ensayos)."""

from __future__ import annotations

import pandas as pd

import no_regresion as nr


def test_comparacion_exacta_sin_tiempos():
    base = {"momentos": [{"semana": 0, "familias": [{"modelo": "rl", "roc_auc_oof": 0.7, "tiempo_s": 1.0,
                                                      "p": float("nan")}], "tiempo_s": 9.0}]}
    igual = {"momentos": [{"semana": 0, "familias": [{"modelo": "rl", "roc_auc_oof": 0.7, "tiempo_s": 2.0,
                                                       "p": float("nan")}], "tiempo_s": 3.0}]}
    resultado = nr.comparar_momentos(base, igual)
    assert resultado["igual"] and resultado["claves_excluidas"] == ["tiempo_s"] and resultado["valores_comparados"] == 4
    distinto = {"momentos": [{"semana": 0, "familias": [{"modelo": "rl", "roc_auc_oof": 0.7000001, "p": float("nan")}]}]}
    resultado = nr.comparar_momentos(base, distinto)
    assert not resultado["igual"]
    assert resultado["diferencias"] == [{"ruta": "momentos[0].familias[0].roc_auc_oof", "base": 0.7, "nuevo": 0.7000001}]


def test_orden_de_claves_y_tipos_cuentan():
    diferencias, _ = nr.diferencias({"a": 1, "b": 2}, {"b": 2, "a": 1}, "m")
    assert [d["ruta"] for d in diferencias] == ["m (orden de claves)"]
    diferencias, _ = nr.diferencias({"a": 1}, {"a": 1.0}, "m")
    assert [d["ruta"] for d in diferencias] == ["m.a"]


def test_oof_con_tolerancia_absoluta_y_diferencia_maxima(tmp_path):
    base = pd.DataFrame({"id": ["a", "b"], "pliegue": [1, 2], "p_rf": [0.1, 0.2]})
    rutas = {}
    for nombre, p, id_ in (("ruido", [0.1 + 3e-16, 0.2], ["a", "b"]), ("lejos", [0.1 + 1e-6, 0.2], ["a", "b"]),
                           ("texto", [0.1, 0.2], ["a", "c"])):
        rutas[nombre] = tmp_path / f"{nombre}.parquet"
        base.assign(p_rf=p, id=id_).to_parquet(rutas[nombre])
    base.to_parquet(tmp_path / "base.parquet")

    def comparar(nombre):
        return nr.comparar_oof({0: (tmp_path / "base.parquet", "x")}, {0: (rutas[nombre], "y")})[0]

    ruido = comparar("ruido")
    assert ruido["igual"] and ruido["diferencia"] is None and 0 < ruido["diferencia_maxima"]["p_rf"] < 1e-15
    assert not comparar("lejos")["igual"]
    texto = comparar("texto")
    assert not texto["igual"] and texto["diferencia_maxima"] == {}
