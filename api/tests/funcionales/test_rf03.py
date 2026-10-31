"""RF-03, RNF-03 y RNF-06: entrenamiento en segundo plano con seguimiento; las consultas responden mientras entrena;
id, semillas, versiones, commit y SHA-256 registrados (§4.2, §5)."""

import threading
import time

import pytest

from api import trabajador
from test_trabajador import crear

REQUISITO = "RF-03, RNF-03, RNF-06"
pytestmark = pytest.mark.postgres


def test_entrena_en_segundo_plano_y_responde_mientras(app, cliente):
    id_ = crear(cliente)
    assert cliente.get(f"/api/experimentos/{id_}").get_json()["estado"] == "en_cola"

    def entrenar():
        with app.app_context():
            trabajador.procesar_siguiente()
    hilo = threading.Thread(target=entrenar)
    hilo.start()
    vistos, esperas = [], []
    while hilo.is_alive():
        inicio = time.perf_counter()
        r = cliente.get(f"/api/experimentos/{id_}")
        esperas.append(time.perf_counter() - inicio)
        assert r.status_code == 200
        vistos.append((r.get_json()["estado"], r.get_json()["etapa"]))
        time.sleep(0.2)
    hilo.join()
    etapas = [etapa for estado, etapa in vistos if estado == "en_curso"]
    assert any(etapas)  # seguimiento: la etapa en curso es visible mientras entrena
    assert max(esperas) < 2  # RNF-03: la consulta no espera a que termine el entrenamiento

    e = cliente.get(f"/api/experimentos/{id_}").get_json()
    assert e["estado"] == "completado", e["error"]
    assert e["progreso"]["completadas"] == e["progreso"]["total"] and e["duracion_s"] > 0
    rep = e["reproducibilidad"]
    assert rep["id"] == id_ and rep["semillas"] == {"optuna": 42, "modelos": 42, "bootstrap": 42}
    assert rep["commit"] and len(rep["sha256_datos"]) == 64 and len(rep["sha256_oof"]) == 64
    assert {"python", "scikit-learn", "optuna", "shap"} <= set(rep["versiones"])
