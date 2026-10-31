"""RF-02: configuración (objetivo, clase positiva, grupo, cohorte de prueba, excluidas, sensibles; §4.2)."""

import pytest

from test_configuracion import cuerpo, subir_conjunto, tabla

REQUISITO = "RF-02"
pytestmark = pytest.mark.postgres


def test_esquema_efectivo_sin_crear_nada(cliente):
    conjunto = subir_conjunto(cliente, tabla())
    r = cliente.post("/api/experimentos/validacion", json=cuerpo(conjunto))
    assert r.status_code == 200, r.get_json()
    v = r.get_json()
    # Ni el identificador, ni la sensible, ni el grupo, ni la columna de la cohorte de prueba son predictores.
    assert v["variables"] == {"numericas": ["x1", "x2"], "categoricas": ["nivel"]}
    assert v["validacion"]["tipo"] == "agrupada_estratificada" and v["validacion"]["n_grupos"] == 8
    assert v["filas_prueba"] > 0 and v["filas_sin_objetivo"] == 3
    assert cliente.get("/api/experimentos").get_json() == []


def test_configuracion_invalida(cliente):
    conjunto = subir_conjunto(cliente, tabla())
    r = cliente.post("/api/experimentos", json=cuerpo(conjunto, clase_positiva="Suspenso"))
    assert r.status_code == 422
    assert r.get_json() == {"error": "La clase positiva «Suspenso» no aparece en la columna objetivo."}
    assert cliente.get("/api/experimentos").get_json() == []
