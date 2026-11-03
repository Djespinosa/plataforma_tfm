"""Evaluación única en la cohorte de prueba reservada (docs/diseno-api.md §4.7, matiz D-2) y exportación de la
evaluación (RF-09, §4.6): POST /api/experimentos/{id}/evaluacion-prueba y GET /api/experimentos/{id}/evaluacion/exportar.
"""

import io
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import pytest
from sklearn.metrics import roc_auc_score

from api import trabajador
from api.servicios.tablas_csv import coaccionar
from api.tablas import Experimento
from automl import explicacion
from test_configuracion import cuerpo, subir_conjunto, tabla
from test_importar import FINAL, entorno, importar_en  # noqa: F401  (fixture)
from test_trabajador import crear, procesar

CONFIRMAR = {"confirmar": True}


@pytest.fixture(autouse=True)
def sin_latido(monkeypatch):
    monkeypatch.setattr(trabajador, "LATIDO_S", 3600)


def entrenar(app, cliente, datos: pd.DataFrame | None = None, **cambios) -> str:
    conjunto = subir_conjunto(cliente, tabla() if datos is None else datos)
    r = cliente.post("/api/experimentos", json=cuerpo(conjunto, **cambios))
    assert r.status_code == 202, r.get_json()
    assert procesar(app) == r.get_json()["id"]
    return r.get_json()["id"]


def evaluar(cliente, id_: str, cuerpo_=CONFIRMAR):
    return cliente.post(f"/api/experimentos/{id_}/evaluacion-prueba", json=cuerpo_)


def test_evaluacion_unica_con_el_modelo_y_el_umbral_fijados(app, cliente):
    id_ = entrenar(app, cliente)
    antes = cliente.get(f"/api/experimentos/{id_}/evaluacion").get_json()
    exportada = cliente.get(f"/api/experimentos/{id_}/evaluacion/exportar")
    assert exportada.headers["Content-Disposition"] == f'attachment; filename="evaluacion_{id_}.json"'
    assert json.loads(exportada.data)["evaluacion_prueba"] is None

    for sin_confirmar in (None, {}, {"confirmar": "sí"}):
        r = evaluar(cliente, id_, sin_confirmar)
        assert r.status_code == 400 and "una sola vez" in r.get_json()["error"]
    r = evaluar(cliente, id_)
    assert r.status_code == 201, r.get_json()
    ev = r.get_json()

    # Lo esperado: el paquete guardado sobre las filas 2014J con objetivo, con su umbral, sin reentrenar nada.
    detalle = cliente.get(f"/api/experimentos/{id_}").get_json()
    modelo = cliente.get(f"/api/modelos/{detalle['modelos'][0]['id']}").get_json()
    paquete = joblib.load(Path(app.config["PLATAFORMA_DATOS"]) / "experimentos" / id_ / "paquete.joblib")
    datos = pd.read_csv(io.StringIO(tabla().to_csv(index=False)))
    prueba = datos[datos["objetivo"].notna() & (datos["cohorte"] == "2014J")]
    y = (prueba["objetivo"] == "Retirado").astype(int)
    p = paquete["modelo"].predict_proba(coaccionar(prueba, detalle["configuracion"]["variables"]))[:, 1]
    assert ev["n"] == len(prueba) and ev["positivos"] == int(y.sum())
    assert ev["roc_auc"] == round(roc_auc_score(y, p), 4)
    assert ev["punto_operacion"]["umbral_exacto"] == paquete["umbral"] == modelo["umbral"]
    assert ev["punto_operacion"]["tasa_alerta"] == round(float((p >= paquete["umbral"]).mean()), 4)
    assert ev["modelo_id"] == modelo["id"] and len(ev["sha256_paquete"]) == 64
    assert ev["fuente"] == "cohorte_prueba" and ev["aviso_fuente"].startswith("Métricas en la cohorte de prueba")
    assert set(ev["punto_operacion"]["textos"]) == {"sensibilidad", "precision", "tasa_alerta"}
    assert ev["aviso_decision"] and set(ev["textos"]) == {"roc_auc", "pr_auc"}

    # Se guarda, no se repite y no cambia la evaluación de validación cruzada.
    assert detalle["evaluacion_prueba"] == ev
    r = evaluar(cliente, id_)
    assert r.status_code == 409
    assert r.get_json()["error"].startswith("La evaluación en la cohorte de prueba ya se hizo (")
    assert cliente.get(f"/api/experimentos/{id_}").get_json()["evaluacion_prueba"] == ev
    assert cliente.get(f"/api/experimentos/{id_}/evaluacion").get_json() == antes

    exportada = json.loads(cliente.get(f"/api/experimentos/{id_}/evaluacion/exportar").data)
    assert exportada == {**antes, "configuracion": detalle["configuracion"],
                         "reproducibilidad": detalle["reproducibilidad"], "evaluacion_prueba": ev}


def test_mismos_datos_y_cohorte_en_otro_experimento(app, cliente):
    """El mismo CSV subido otra vez y entrenado con la misma cohorte no da una segunda evaluación (índice del §3)."""
    primero, segundo = entrenar(app, cliente), entrenar(app, cliente)
    assert evaluar(cliente, primero).status_code == 201
    r = evaluar(cliente, segundo)
    assert r.status_code == 409 and r.get_json()["error"].startswith("Estos datos ya se evaluaron")
    assert cliente.get(f"/api/experimentos/{segundo}").get_json()["evaluacion_prueba"] is None


def test_sin_cohorte_importado_no_terminado_e_inexistente(app, cliente, entorno):  # noqa: F811
    importar_en(app, entorno)
    sin_cohorte = entrenar(app, cliente, cohorte_prueba=None)
    for id_ in (FINAL, sin_cohorte):
        r = evaluar(cliente, id_)
        assert r.status_code == 409
        assert r.get_json()["error"] == "Este experimento no tiene cohorte de prueba reservada."
    en_cola = crear(cliente)
    r = evaluar(cliente, en_cola)
    assert r.status_code == 409 and r.get_json()["error"] == "El experimento aún no ha terminado (estado: en cola)."
    assert cliente.get(f"/api/experimentos/{en_cola}/evaluacion/exportar").status_code == 409
    assert evaluar(cliente, "web-2099-01-01-01").status_code == 404
    # El importado se exporta con la evaluación de su origen y sin evaluación en la cohorte de prueba.
    exportada = json.loads(cliente.get(f"/api/experimentos/{FINAL}/evaluacion/exportar").data)
    assert exportada["reproducibilidad"]["id"] == FINAL and exportada["evaluacion_prueba"] is None


def test_cohorte_distinta_de_la_reservada_o_de_una_clase(app, cliente):
    id_ = entrenar(app, cliente)
    reservadas = Path(app.config["PLATAFORMA_DATOS"]) / "experimentos" / id_ / "prueba.parquet"
    pd.DataFrame({"fila": pd.read_parquet(reservadas)["fila"][1:]}).to_parquet(reservadas, index=False)
    r = evaluar(cliente, id_)
    assert r.status_code == 409 and r.get_json()["error"].startswith("Las filas de la cohorte de prueba no coinciden")

    datos = tabla()
    datos.loc[datos["objetivo"].notna() & (datos["cohorte"] == "2014J"), "objetivo"] = "Aprobado"
    una_clase = entrenar(app, cliente, datos)
    r = evaluar(cliente, una_clase)
    assert r.status_code == 409
    assert r.get_json()["error"].startswith("La cohorte de prueba solo tiene casos de una clase")
    with app.extensions["bd_sesiones"]() as sesion:
        assert sesion.get(Experimento, id_).evaluacion_prueba is None
        assert sesion.get(Experimento, una_clase).evaluacion_prueba is None


def test_ningun_caso_marcado_se_guarda_y_se_muestra(app, cliente, monkeypatch):
    """Con el umbral por encima de todas las probabilidades, la precisión es None: la evaluación se guarda (congelada)
    y el detalle y la exportación se siguen mostrando."""
    id_ = entrenar(app, cliente)
    monkeypatch.setattr(explicacion, "predecir", lambda paquete, X: pd.DataFrame({"probabilidad": np.zeros(len(X))}))
    r = evaluar(cliente, id_)
    assert r.status_code == 201, r.get_json()
    po = r.get_json()["punto_operacion"]
    assert po["precision"] is None and po["tasa_alerta"] == 0 and po["textos"]["precision"].startswith("Con este umbral")
    assert cliente.get(f"/api/experimentos/{id_}").get_json()["evaluacion_prueba"] == r.get_json()
    assert cliente.get(f"/api/experimentos/{id_}/evaluacion/exportar").status_code == 200
