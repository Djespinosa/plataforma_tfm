"""RF-01: carga y validación de la tabla (§4.1)."""

import pytest

from test_conjuntos import subir
from test_configuracion import tabla

REQUISITO = "RF-01"
pytestmark = pytest.mark.postgres


def test_carga_resume_la_tabla_y_avisa(cliente):
    r = subir(cliente, tabla().to_csv(index=False, sep=";"), momento="semana 4")
    assert r.status_code == 201, r.get_json()
    conjunto = r.get_json()
    assert (conjunto["n_filas"], conjunto["n_columnas"], conjunto["momento"]) == (300, 8, "semana 4")
    tipos = {c["nombre"]: c["tipo"] for c in conjunto["columnas"]}
    assert tipos["x1"] == "numerica" and tipos["nivel"] == "categorica"
    assert any(a.startswith("La columna «matricula» parece un identificador") for a in conjunto["avisos"])
    assert conjunto["aviso_privacidad"].startswith("No suba datos personales identificables")
    assert cliente.get(f"/api/conjuntos/{conjunto['id']}").get_json()["sha256"] == conjunto["sha256"]
    assert [c["id"] for c in cliente.get("/api/conjuntos").get_json()] == [conjunto["id"]]


def test_rechaza_una_tabla_mal_formada(cliente):
    r = subir(cliente, "a,b\n1,2,3\n")  # una fila con más campos que la cabecera
    assert r.status_code in (415, 422) and "error" in r.get_json()
    assert cliente.get("/api/conjuntos").get_json() == []
