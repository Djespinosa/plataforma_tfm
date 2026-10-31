"""Pruebas funcionales (docs/diseno-api.md §10): un caso por requisito contra el PostgreSQL 16.15 del contenedor, con el
cliente de Flask, la tabla sintética de test_configuracion y el presupuesto «prueba». Cada caso registra en el JUnit su
requisito (propiedad «requisito», la constante REQUISITO del módulo) y la suite, el de las funcionales
(«motor_bd_funcionales»).

Aquí `app` es la de PostgreSQL, así que `cliente` y las funciones auxiliares de las pruebas unitarias la usan."""

import pytest
from sqlalchemy import create_engine, text

from api import trabajador
from test_importar import entorno, importar_en  # noqa: F401  (fixture)
from test_trabajador import crear, procesar


@pytest.fixture(scope="session", autouse=True)
def motor_bd(record_testsuite_property, url_postgres):
    motor = create_engine(url_postgres)
    with motor.connect() as conexion:
        version = conexion.execute(text("SHOW server_version")).scalar_one().split()[0]
    motor.dispose()
    record_testsuite_property("motor_bd_funcionales", f"postgresql {version}")


@pytest.fixture(autouse=True)
def requisito(request, record_property):
    record_property("requisito", request.module.REQUISITO)


@pytest.fixture(autouse=True)
def sin_latido(monkeypatch):
    monkeypatch.setattr(trabajador, "LATIDO_S", 3600)


@pytest.fixture
def app(app_postgres):
    return app_postgres


@pytest.fixture
def entrenado(app, cliente) -> dict:
    """Experimento web entrenado con el presupuesto «prueba» (detalle de GET /api/experimentos/{id})."""
    id_ = crear(cliente)
    assert procesar(app) == id_
    return cliente.get(f"/api/experimentos/{id_}").get_json()


@pytest.fixture
def importado(app, entorno) -> None:  # noqa: F811
    """Paquetes sintéticos importados (semanas 4 y 12) con el mecanismo genérico de §8."""
    importar_en(app, entorno)
