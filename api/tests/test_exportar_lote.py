"""Exportación de un lote de predicción en CSV (RF-09, docs/diseno-api.md §4.6):
GET /api/predicciones/{lote_id}/exportar."""

import io

import pandas as pd

from api import textos
from test_importar import entorno  # noqa: F401  (fixture)
from test_predicciones import importados, modelo_semana, subir, tabla_lote  # noqa: F401  (fixture)


def test_exporta_el_lote_con_los_avisos(app, cliente, importados):  # noqa: F811
    modelo = modelo_semana(app, "semana 4")
    lote_id = subir(cliente, modelo.id, tabla_lote(), columna_id="matricula").get_json()["lote_id"]
    r = cliente.get(f"/api/predicciones/{lote_id}/exportar")
    assert r.status_code == 200 and r.content_type == "text/csv; charset=utf-8"
    assert r.headers["Content-Disposition"] == f'attachment; filename="prediccion_lote_{lote_id}.csv"'
    assert r.data.startswith("﻿".encode())  # BOM: las hojas de cálculo leen bien las tildes
    lineas = r.data.decode("utf-8-sig").split("\n")
    assert lineas[:2] == [f"# {textos.AVISO_DECISION}", f"# {textos.AVISO_RENDIMIENTO}"]

    exportado = pd.read_csv(io.StringIO("\n".join(lineas[2:])), keep_default_na=False)
    filas = cliente.get(f"/api/predicciones/{lote_id}").get_json()["filas"]
    assert list(exportado.columns) == ["fila", "identificador", "probabilidad_estimada_pct", "alerta"]
    assert exportado["fila"].tolist() == list(range(1, 41))
    assert exportado["identificador"].tolist() == [f"A-{i}" for i in range(40)]
    assert exportado["probabilidad_estimada_pct"].tolist() == [round(100 * f["probabilidad"], 1) for f in filas]
    assert exportado["alerta"].tolist() == ["sí" if f["alerta"] else "no" for f in filas]


def test_lote_inexistente(cliente):
    r = cliente.get("/api/predicciones/99/exportar")
    assert r.status_code == 404 and r.get_json()["error"] == "No existe el lote de predicción 99."
