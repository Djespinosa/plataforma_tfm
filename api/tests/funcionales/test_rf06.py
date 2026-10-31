"""RF-06 y RE-01/02/03: explicación global y local con los avisos de escala, causalidad y decisión (§4.5)."""

import pytest

from api import textos
from test_configuracion import tabla
from test_predicciones import subir

REQUISITO = "RF-06, RE-01, RE-02, RE-03"
pytestmark = pytest.mark.postgres


def test_explicacion_global_y_local(cliente, entrenado):
    modelo_id = entrenado["modelos"][0]["id"]
    global_ = cliente.get(f"/api/modelos/{modelo_id}/explicacion-global").get_json()
    assert global_["variables"] and global_["fuente"].startswith("filas de entrenamiento")
    assert global_["avisos"]["causalidad"] == textos.AVISO_CAUSALIDAD

    lote_id = subir(cliente, modelo_id, tabla(40, semilla=5)).get_json()["lote_id"]
    local = cliente.get(f"/api/predicciones/{lote_id}/filas/1/explicacion").get_json()
    assert set(local["avisos"]) == {"escala", "causalidad", "decision"}
    assert local["avisos"]["causalidad"] == textos.AVISO_CAUSALIDAD
    assert len(local["aumentan"]) <= 5 and len(local["reducen"]) <= 5
    # Aditividad: el valor base más las contribuciones da el log-odds del modelo.
    suma = local["valor_base"] + sum(i["contribucion"] for i in local["todas"])
    assert suma == pytest.approx(local["log_odds"], abs=1e-6)
