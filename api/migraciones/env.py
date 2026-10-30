"""Entorno de Alembic. URL: la opción sqlalchemy.url si quien llama la fija (pruebas contra PostgreSQL) o, si no,
DATABASE_URL de configuracion.Desarrollo."""

from __future__ import annotations

import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import create_engine

RAIZ = Path(__file__).resolve().parents[2]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from api import tablas  # noqa: E402  (registra las tablas en Base.metadata)
from api.configuracion import Desarrollo  # noqa: E402

config = context.config
if config.config_file_name is not None and config.attributes.get("configurar_registro", True):
    fileConfig(config.config_file_name)

url = config.get_main_option("sqlalchemy.url") or Desarrollo().DATABASE_URL
metadatos = tablas.Base.metadata


if context.is_offline_mode():
    context.configure(url=url, target_metadata=metadatos, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()
else:
    motor = create_engine(url)
    with motor.connect() as conexion:
        context.configure(connection=conexion, target_metadata=metadatos)
        with context.begin_transaction():
            context.run_migrations()
    motor.dispose()
