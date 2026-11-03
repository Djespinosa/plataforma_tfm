"""RF-09: exportación en formato abierto del lote de predicción (CSV) y de la evaluación (JSON), §4.6."""

import io
import json

import pandas as pd
import pytest

from test_configuracion import tabla
from test_predicciones import subir

REQUISITO = "RF-09"
pytestmark = pytest.mark.postgres


def test_exportar_lote_y_evaluacion(cliente, entrenado):
    modelo_id = entrenado["modelos"][0]["id"]
    lote_id = subir(cliente, modelo_id, tabla(40, semilla=5), columna_id="matricula").get_json()["lote_id"]
    r = cliente.get(f"/api/predicciones/{lote_id}/exportar")
    assert r.status_code == 200 and r.headers["Content-Disposition"].startswith("attachment;")
    lineas = r.data.decode("utf-8-sig").split("\n")
    assert lineas[0].startswith("# Herramienta de apoyo a la decisión.") and lineas[1].startswith("# ")
    exportado = pd.read_csv(io.StringIO("\n".join(lineas[2:])), keep_default_na=False)
    assert len(exportado) == 40 and set(exportado["alerta"]) <= {"sí", "no"}

    r = cliente.get(f"/api/experimentos/{entrenado['id']}/evaluacion/exportar")
    assert r.status_code == 200 and r.mimetype == "application/json"
    exportada = json.loads(r.data)
    assert exportada["configuracion"] == entrenado["configuracion"]
    assert exportada["reproducibilidad"] == entrenado["reproducibilidad"] and exportada["evaluacion_prueba"] is None
