"""Motor, sesiones y Base declarativa (SQLAlchemy 2, sin Flask-SQLAlchemy; docs/diseno-api.md §2)."""

from __future__ import annotations

from flask import Flask, current_app, g
from sqlalchemy import JSON, MetaData, create_engine, event
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import StaticPool

# Clave del bloqueo consultivo del trabajador (§5); GET /api/estado la busca en pg_locks.
BLOQUEO_TRABAJADOR = 727301

# JSONB en PostgreSQL, JSON en SQLite; None se guarda como NULL de SQL (no como el JSON «null»), para que las
# comprobaciones «IS NULL» de la base de datos (evaluación única en prueba) sean fiables.
JSONB_ = JSON(none_as_null=True).with_variant(JSONB(none_as_null=True), "postgresql")


class Base(DeclarativeBase):
    # Nombres de restricciones estables (los mismos en create_all y en las migraciones de Alembic).
    metadata = MetaData(naming_convention={
        "pk": "pk_%(table_name)s",
        "fk": "fk_%(table_name)s_%(column_0_name)s",
        "uq": "uq_%(table_name)s_%(column_0_name)s",
        "ck": "ck_%(table_name)s_%(constraint_name)s",
        "ix": "ix_%(table_name)s_%(column_0_name)s",
    })


def crear_motor(url: str) -> Engine:
    if url.startswith("sqlite"):
        motor = create_engine(url, poolclass=StaticPool, connect_args={"check_same_thread": False})

        @event.listens_for(motor, "connect")
        def _claves_foraneas(conexion, _registro) -> None:
            conexion.execute("PRAGMA foreign_keys = ON")

        return motor
    return create_engine(url, pool_pre_ping=True)


def iniciar(app: Flask) -> None:
    motor = crear_motor(app.config["DATABASE_URL"])
    app.extensions["bd_motor"] = motor
    app.extensions["bd_sesiones"] = sessionmaker(motor, expire_on_commit=False)
    app.teardown_appcontext(_cerrar_sesion)


def motor() -> Engine:
    return current_app.extensions["bd_motor"]


def sesion() -> Session:
    """Sesión de la petición en curso; se cierra al terminar (teardown)."""
    if "bd_sesion" not in g:
        g.bd_sesion = current_app.extensions["bd_sesiones"]()
    return g.bd_sesion


def _cerrar_sesion(_excepcion: BaseException | None) -> None:
    s = g.pop("bd_sesion", None)
    if s is not None:
        s.close()
