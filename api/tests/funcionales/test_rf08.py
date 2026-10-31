"""RF-08: historial, reapertura y reintento de un experimento interrumpido (§4.2)."""

import pytest

from test_historial import interrumpir
from test_trabajador import crear, procesar

REQUISITO = "RF-08"
pytestmark = pytest.mark.postgres


def test_historial_reapertura_y_reintento(app, cliente, importado):
    id_ = crear(cliente)
    interrumpir(app)
    nuevo = cliente.post(f"/api/experimentos/{id_}/reintentar").get_json()
    assert procesar(app) == nuevo["id"]
    historial = cliente.get("/api/experimentos").get_json()
    assert [e["id"] for e in historial][:2] == [nuevo["id"], id_]
    assert {e["origen"] for e in historial} == {"web", "importado"}
    assert historial[0]["reintento_de"] == id_ and historial[0]["estado"] == "completado"
    # Reabrir desde el historial: la evaluación sigue disponible.
    assert cliente.get(f"/api/experimentos/{nuevo['id']}/evaluacion").status_code == 200
