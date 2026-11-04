"""Aplicación de pruebas: SQLite en memoria (unitarias) o el PostgreSQL de DATABASE_URL_PRUEBAS (marcador
«postgres»)."""

import os
import sys
from pathlib import Path
from urllib.parse import quote, quote_plus

import pytest

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))

from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from dotenv import load_dotenv  # noqa: E402
from sqlalchemy import create_engine, make_url, text  # noqa: E402
from sqlalchemy.exc import OperationalError  # noqa: E402

from api import crear_app  # noqa: E402
from api.tablas import Base  # noqa: E402  (con las 6 tablas registradas)
from api.configuracion import Pruebas  # noqa: E402

load_dotenv(RAIZ / ".env")


def pytest_configure(config):
    config.addinivalue_line(
        "markers", "postgres: necesita el PostgreSQL del contenedor (DATABASE_URL_PRUEBAS, base plataforma_pruebas)"
    )


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """Oculta la contraseña de DATABASE_URL_PRUEBAS en el informe de cualquier fallo (preparación, prueba o limpieza):
    si la conexión se pierde, los marcos de psycopg y SQLAlchemy la llevan en conninfo/kwargs y pytest los mostraría en
    la traza (con -l, también las variables locales), en consola y en el JUnit."""
    informe = (yield).get_result()
    texto = os.environ.get("DATABASE_URL_PRUEBAS")
    contrasena = make_url(texto).password if texto else None
    if not informe.failed or not contrasena:
        return
    formas = {contrasena, quote_plus(contrasena), quote(contrasena, safe="")}

    def ocultar(s: str) -> str:
        for forma in formas:
            s = s.replace(forma, "***")
        return s
    largo = str(informe.longrepr)
    if any(forma in largo for forma in formas):
        informe.longrepr = ocultar(largo)  # texto plano: pierde colores y la línea del resumen corto, no información
    informe.sections = [(titulo, ocultar(contenido)) for titulo, contenido in informe.sections]


@pytest.fixture(autouse=True)
def motor_bd_prueba(request, record_property):  # (las funcionales tienen su fixture «motor_bd», de sesión)
    """Motor de cada prueba en el JUnit (propiedad «motor_bd»): PostgreSQL si lleva el marcador «postgres» (las que usan
    la base del contenedor, también las parametrizadas de test_tablas que la piden con getfixturevalue), si no SQLite
    en memoria (o ninguna base)."""
    record_property("motor_bd", "postgresql" if request.node.get_closest_marker("postgres") else "sqlite")


def pytest_collection_modifyitems(items):
    """Toda prueba que pide la base del contenedor debe llevar el marcador «postgres» (de él sale su motor_bd)."""
    sin_marcar = [i.nodeid for i in items if "url_postgres" in getattr(i, "fixturenames", ())
                  and not i.get_closest_marker("postgres")]
    if sin_marcar:
        raise pytest.UsageError("Usan PostgreSQL sin el marcador «postgres»: " + ", ".join(sin_marcar))


@pytest.fixture
def app(tmp_path):
    app = crear_app(Pruebas(datos=tmp_path))
    Base.metadata.create_all(app.extensions["bd_motor"])
    yield app
    app.extensions["bd_motor"].dispose()


@pytest.fixture
def cliente(app):
    return app.test_client()


def configuracion_alembic(url: str) -> Config:
    cfg = Config(RAIZ / "api" / "alembic.ini")
    cfg.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    cfg.attributes["configurar_registro"] = False
    return cfg


@pytest.fixture(scope="session")
def url_postgres():
    """Fixture interna (solo para app_postgres y motor_postgres): ninguna prueba recibe la URL como argumento. Es un
    URL de SQLAlchemy, cuyo repr oculta la contraseña si pytest lo muestra en un fallo."""
    texto = os.environ.get("DATABASE_URL_PRUEBAS")
    if not texto:
        pytest.skip("Sin DATABASE_URL_PRUEBAS (copie .env.example a .env y arranque docker compose).")
    url = make_url(texto)
    if url.database != "plataforma_pruebas":
        pytest.fail("DATABASE_URL_PRUEBAS debe apuntar a plataforma_pruebas.")
    try:
        command.upgrade(configuracion_alembic(url.render_as_string(hide_password=False)), "head")
    except OperationalError as e:
        # Sin traza: el marco más profundo (psycopg.connect) mostraría la contraseña entre sus argumentos.
        pytest.fail(f"No se puede conectar con plataforma_pruebas ({type(e.orig).__name__}); ¿está levantado el "
                    "contenedor (docker compose up -d)?", pytrace=False)
    return url


def _vaciar(motor) -> None:
    tablas = ", ".join(t.name for t in Base.metadata.sorted_tables)
    with motor.begin() as conexion:
        conexion.execute(text(f"TRUNCATE {tablas} RESTART IDENTITY CASCADE"))


@pytest.fixture
def app_postgres(url_postgres, tmp_path):
    app = crear_app(Pruebas(database_url=url_postgres.render_as_string(hide_password=False), datos=tmp_path))
    motor = app.extensions["bd_motor"]
    _vaciar(motor)  # restos de una ejecución interrumpida
    yield app
    _vaciar(motor)
    motor.dispose()


@pytest.fixture
def motor_postgres(url_postgres):
    """Engine de plataforma_pruebas (su repr oculta la contraseña)."""
    motor = create_engine(url_postgres)
    yield motor
    motor.dispose()
