"""RF-04: evaluación (OOF, referencias, RL optimizada con DeLong e IC, desplegado y motivo, punto de operación,
calibración; §4.3), de un experimento web y de un modelo importado; y la evaluación única en la cohorte de prueba
reservada (§4.7) con el índice y los disparadores de PostgreSQL."""

import json

import pytest

from test_importar import FINAL
from test_trabajador import crear, procesar

REQUISITO = "RF-04"
pytestmark = pytest.mark.postgres


def comprobar(evaluacion: dict) -> None:
    assert evaluacion["fuente"] == "validacion_cruzada"
    assert evaluacion["aviso_fuente"].startswith("Métricas de validación cruzada") and evaluacion["aviso_decision"]
    m = evaluacion["modelos"][0]
    assert "mayoritaria" in {r["modelo"] for r in m["referencias"]}
    assert m["contraste"]["modelo_b"] == "rl_optimizada" and len(m["contraste"]["ic95_bootstrap"]) == 2
    assert m["contraste"]["delong_p"] is not None and m["contraste"]["lectura_texto"]
    assert m["desplegado"]["modelo"] and m["desplegado"]["motivo_texto"]
    assert {"umbral", "sensibilidad", "precision", "tasa_alerta", "matriz_confusion"} <= set(m["punto_operacion"])
    assert m["calibracion"]["curva"]["calibrada"]
    assert "retiros_prueba" not in json.dumps(evaluacion)  # nada de la cohorte de prueba


def test_evaluacion_de_un_experimento_web(cliente, entrenado):
    r = cliente.get(f"/api/experimentos/{entrenado['id']}/evaluacion")
    assert r.status_code == 200
    comprobar(r.get_json())
    assert r.get_json()["modelos"][0]["contraste"]["holm_sobre"] == 1


def test_evaluacion_de_un_modelo_importado(cliente, importado):
    r = cliente.get(f"/api/experimentos/{FINAL}/evaluacion")
    assert r.status_code == 200
    comprobar(r.get_json())


def test_evaluacion_unica_en_la_cohorte_de_prueba(app, cliente, entrenado):
    otro = crear(cliente)  # el mismo CSV y la misma cohorte
    assert procesar(app) == otro
    url = f"/api/experimentos/{entrenado['id']}/evaluacion-prueba"
    r = cliente.post(url, json={"confirmar": True})
    assert r.status_code == 201 and r.get_json()["fuente"] == "cohorte_prueba"
    assert cliente.post(url, json={"confirmar": True}).status_code == 409
    r = cliente.post(f"/api/experimentos/{otro}/evaluacion-prueba", json={"confirmar": True})
    assert r.status_code == 409 and r.get_json()["error"].startswith("Estos datos ya se evaluaron")
