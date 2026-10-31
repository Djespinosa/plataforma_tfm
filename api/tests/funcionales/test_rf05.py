"""RF-05: predicción con probabilidad calibrada y alerta (§4.4), con el modelo de un experimento web y con uno
importado. La columna objetivo se ignora: ninguna ruta calcula métricas con filas de predicción."""

import pytest

from test_configuracion import tabla
from test_predicciones import subir, tabla_lote

REQUISITO = "RF-05"
pytestmark = pytest.mark.postgres


def predecir(cliente, modelo_id: int, lote) -> None:
    r = subir(cliente, modelo_id, lote, columna_id="matricula")
    assert r.status_code == 201, r.get_json()
    cuerpo = r.get_json()
    assert cuerpo["n_filas"] == len(lote) and "objetivo" in cuerpo["columnas_ignoradas"]
    filas = cliente.get(f"/api/predicciones/{cuerpo['lote_id']}").get_json()["filas"]
    assert len(filas) == len(lote) and all(0 <= f["probabilidad"] <= 1 for f in filas)
    assert sum(f["alerta"] for f in filas) == cuerpo["n_alertas"]
    assert all((f["sugerencia"] is not None) == f["alerta"] for f in filas)


def test_prediccion_con_un_modelo_web(cliente, entrenado):
    predecir(cliente, entrenado["modelos"][0]["id"], tabla(40, semilla=5))


def test_prediccion_con_un_modelo_importado(cliente, importado):
    semana_4 = next(m for m in cliente.get("/api/modelos").get_json() if m["momento"] == "semana 4")
    predecir(cliente, semana_4["id"], tabla_lote())
