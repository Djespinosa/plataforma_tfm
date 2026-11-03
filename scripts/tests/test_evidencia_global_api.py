"""Comparación descriptiva de la evidencia D-3 (scripts/evidencia_global_api.py): Spearman con todas las variables y sin las
nulas, y cambios en el top-10."""

import pandas as pd
import pytest

from scripts.evidencia_global_api import comparar


def test_comparar_top10_y_spearman():
    variables = [f"v{i:02d}" for i in range(12)]
    oof = pd.Series(range(12, 0, -1), index=variables, dtype=float)  # v00 la más importante
    api = oof.copy()
    api["v00"], api["v01"] = oof["v01"], oof["v00"]  # intercambian las posiciones 1 y 2
    api["v09"], api["v10"] = oof["v10"], oof["v09"]  # v10 entra en el top-10 y v09 sale
    api["v11"] = 0.0  # sin contribución en la API
    c = comparar(api, oof, ["v11"])
    assert c["todas"]["variables"] == 12 and c["sin_nulas"]["variables"] == 11
    assert c["todas"]["spearman"] == pytest.approx(0.986, abs=1e-3) and c["sin_nulas"]["spearman"] < 1
    assert c["top10"] == {"solape": 0.9, "entran": ["v10"], "salen": ["v09"],
                          "cambian_posicion": [{"variable": "v01", "posicion_api": 1, "posicion_oof": 2},
                                               {"variable": "v00", "posicion_api": 2, "posicion_oof": 1}]}
    assert c["variables_nulas"] == ["v11"]
