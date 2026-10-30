"""Factoría, configuración, errores y GET /api/estado (incremento 0)."""

import sys
from pathlib import Path

import pytest
from sqlalchemy import text

import api
from api import configuracion, crear_app
from api.bd import BLOQUEO_TRABAJADOR
from api.configuracion import Pruebas

RAIZ = Path(__file__).resolve().parents[2]


def test_factoria_pone_ml_en_sys_path_para_cargar_paquetes():
    assert str(RAIZ / "ml") in sys.path
    import automl.busqueda  # noqa: F401  (los paquetes joblib serializan sus clases como automl.*)


def test_flask_encuentra_la_factoria():
    assert api.create_app is crear_app


def test_desarrollo_exige_database_url(monkeypatch):
    monkeypatch.setattr(configuracion, "load_dotenv", lambda *_a, **_k: None)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(RuntimeError, match="Falta DATABASE_URL: copie .env.example a .env."):
        configuracion.Desarrollo()


def test_desarrollo_lee_el_entorno(monkeypatch):
    monkeypatch.setattr(configuracion, "load_dotenv", lambda *_a, **_k: None)
    monkeypatch.setenv("DATABASE_URL", "sqlite+pysqlite:///:memory:")
    monkeypatch.setenv("PLATAFORMA_DATOS", "data/otra")
    monkeypatch.setenv("PLATAFORMA_MAX_MB", "10")
    c = configuracion.Desarrollo()
    assert c.DATABASE_URL == "sqlite+pysqlite:///:memory:"
    assert c.PLATAFORMA_DATOS == RAIZ / "data" / "otra"
    assert c.PLATAFORMA_MAX_MB == 10
    assert c.PLATAFORMA_N_JOBS == 8 and c.PLATAFORMA_MAX_FILAS_PREDICCION == 20000


def test_estado_con_sqlite(cliente):
    import evidencias

    r = cliente.get("/api/estado")
    assert r.status_code == 200
    assert r.get_json() == {
        "motor_bd": "sqlite",
        "trabajador_activo": None,
        "commit": evidencias.git("rev-parse", "--short", "HEAD"),
    }


def test_ruta_inexistente_responde_json_en_espanol(cliente):
    r = cliente.get("/api/no-existe")
    assert r.status_code == 404
    assert r.get_json() == {"error": "No existe la ruta solicitada."}


def test_metodo_no_permitido_responde_json(cliente):
    r = cliente.post("/api/estado")
    assert r.status_code == 405
    assert r.get_json() == {"error": "Esta ruta no admite el método solicitado."}


def test_bd_no_disponible_responde_503(tmp_path):
    inexistente = (tmp_path / "no" / "existe.db").as_posix()
    app = crear_app(Pruebas(database_url=f"sqlite+pysqlite:///{inexistente}", datos=tmp_path))
    r = app.test_client().get("/api/estado")
    assert r.status_code == 503
    assert r.get_json() == {"error": "La base de datos no está disponible."}


def test_error_no_controlado_responde_500_sin_detalles(app):
    @app.get("/api/falla")
    def _falla():
        raise RuntimeError("detalle interno")

    r = app.test_client().get("/api/falla")
    assert r.status_code == 500
    assert r.get_json() == {
        "error": "Error interno de la plataforma. Inténtelo de nuevo; si persiste, consulte el registro del servidor."
    }


@pytest.mark.postgres
def test_estado_con_postgresql_16_15_y_trabajador(app_postgres):
    cliente = app_postgres.test_client()
    r = cliente.get("/api/estado")
    assert r.status_code == 200
    assert r.get_json()["motor_bd"] == "postgresql 16.15"
    assert r.get_json()["trabajador_activo"] is False

    # Otro proceso de PostgreSQL (otra conexión del pool) toma el bloqueo del trabajador: la API lo ve.
    with app_postgres.extensions["bd_motor"].connect() as conexion:
        assert conexion.execute(text("SELECT pg_try_advisory_lock(:c)"), {"c": BLOQUEO_TRABAJADOR}).scalar_one()
        assert cliente.get("/api/estado").get_json()["trabajador_activo"] is True
        conexion.execute(text("SELECT pg_advisory_unlock(:c)"), {"c": BLOQUEO_TRABAJADOR})
    assert cliente.get("/api/estado").get_json()["trabajador_activo"] is False
