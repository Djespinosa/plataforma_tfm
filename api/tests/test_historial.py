"""Historial y reintento (RF-08, docs/diseno-api.md §4.2): GET /api/experimentos y
POST /api/experimentos/{id}/reintentar."""

from pathlib import Path

import pytest

from api import trabajador
from api.tablas import Experimento
from test_trabajador import crear, procesar


@pytest.fixture(autouse=True)
def sin_latido(monkeypatch):
    monkeypatch.setattr(trabajador, "LATIDO_S", 3600)


def interrumpir(app) -> None:
    """Toma el siguiente experimento en cola y simula un cierre del trabajador a medias."""
    with app.app_context():
        trabajador.tomar()
        trabajador.recuperar_huerfanos()


def test_historial_del_mas_reciente_al_mas_antiguo(app, cliente):
    assert cliente.get("/api/experimentos").get_json() == []
    with app.extensions["bd_sesiones"]() as sesion:
        sesion.add(Experimento(id="exp-2026-10-27-01", origen="importado", estado="completado",
                               configuracion={"presupuesto": {"modo": "completo"}}))
        sesion.commit()
    primero = crear(cliente, descripcion="primero")
    segundo = crear(cliente)
    procesar(app)
    historial = cliente.get("/api/experimentos").get_json()
    assert [e["id"] for e in historial] == [segundo, primero, "exp-2026-10-27-01"]
    web = historial[1]
    assert web["estado"] == "completado" and web["descripcion"] == "primero" and web["duracion_s"] >= 0
    assert web["conjunto"]["nombre_archivo"] == "t.csv" and web["objetivo"] == "objetivo"
    assert web["presupuesto"] == "prueba" and web["reintento_de"] is None
    assert [m["familia"] for m in web["modelos"]] == [cliente.get(f"/api/experimentos/{primero}").get_json()
                                                      ["modelos"][0]["familia"]]
    assert historial[0]["estado"] == "en_cola" and historial[0]["modelos"] == []
    importado = historial[2]
    assert importado["conjunto"] is None and importado["objetivo"] is None and importado["presupuesto"] == "completo"


def test_reintentar_un_interrumpido_crea_otro_con_la_misma_configuracion(app, cliente):
    id_ = crear(cliente, descripcion="con cierre")
    interrumpir(app)
    r = cliente.post(f"/api/experimentos/{id_}/reintentar")
    assert r.status_code == 202, r.get_json()
    nuevo = r.get_json()
    assert nuevo["id"] != id_ and nuevo["estado"] == "en_cola" and nuevo["reintento_de"] == id_
    assert r.headers["Location"].endswith(f"/api/experimentos/{nuevo['id']}")
    anterior = cliente.get(f"/api/experimentos/{id_}").get_json()
    assert nuevo["configuracion"] == anterior["configuracion"] and nuevo["descripcion"] == "con cierre"
    assert anterior["estado"] == "interrumpido"  # el anterior no cambia
    with app.extensions["bd_sesiones"]() as sesion:
        a, b = sesion.get(Experimento, id_), sesion.get(Experimento, nuevo["id"])
        assert (b.conjunto_id, b.sha256_datos, b.cohorte_prueba_clave) == (a.conjunto_id, a.sha256_datos,
                                                                          a.cohorte_prueba_clave)
    assert procesar(app) == nuevo["id"]  # mismos pliegues: el trabajador lo entrena
    assert cliente.get(f"/api/experimentos/{nuevo['id']}").get_json()["estado"] == "completado"
    assert cliente.get("/api/experimentos").get_json()[0]["reintento_de"] == id_


def test_un_solo_reintento_por_experimento(app, cliente):
    id_ = crear(cliente)
    interrumpir(app)
    primero = cliente.post(f"/api/experimentos/{id_}/reintentar").get_json()["id"]
    r = cliente.post(f"/api/experimentos/{id_}/reintentar")  # doble clic
    assert r.status_code == 409 and r.get_json() == {
        "error": f"Este experimento ya se ha reintentado ({primero}); si el reintento falla, reintente ese."}
    assert len(cliente.get("/api/experimentos").get_json()) == 2
    interrumpir(app)  # el reintento también se interrumpe: se reintenta el reintento
    assert cliente.post(f"/api/experimentos/{primero}/reintentar").status_code == 202


@pytest.mark.parametrize("estado", ["en_cola", "en_curso", "completado"])
def test_solo_se_reintenta_fallido_o_interrumpido(app, cliente, estado):
    id_ = crear(cliente)
    with app.extensions["bd_sesiones"]() as sesion:
        sesion.get(Experimento, id_).estado = estado
        sesion.commit()
    r = cliente.post(f"/api/experimentos/{id_}/reintentar")
    assert r.status_code == 409
    assert r.get_json() == {"error": "Solo se puede reintentar un experimento fallido o interrumpido."}
    assert len(cliente.get("/api/experimentos").get_json()) == 1


def test_reintentar_con_el_archivo_cambiado_no_crea_nada(app, cliente):
    id_ = crear(cliente)
    for archivo in (Path(app.config["PLATAFORMA_DATOS"]) / "conjuntos").glob("*.csv"):
        archivo.write_text("a,b\n1,2\n", encoding="utf-8")
    procesar(app)  # fallido: el archivo ha cambiado
    r = cliente.post(f"/api/experimentos/{id_}/reintentar")
    assert r.status_code == 409 and r.get_json() == {"error": "El archivo del conjunto ha cambiado desde que se cargó."}
    assert len(cliente.get("/api/experimentos").get_json()) == 1
    assert cliente.post("/api/experimentos/web-2099-01-01-01/reintentar").status_code == 404
