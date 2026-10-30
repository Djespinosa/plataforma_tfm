"""Configuración de la aplicación: Desarrollo (desde el entorno y .env) y Pruebas (docs/diseno-api.md §9)."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

RAIZ = Path(__file__).resolve().parents[1]


def _ruta(valor: str) -> Path:
    ruta = Path(valor)
    return ruta if ruta.is_absolute() else RAIZ / ruta


class Desarrollo:
    """Lee las variables de .env.example del entorno (o de .env en la raíz, sin sobrescribir el entorno)."""

    TESTING = False

    def __init__(self) -> None:
        load_dotenv(RAIZ / ".env")
        url = os.environ.get("DATABASE_URL")
        if not url:
            raise RuntimeError("Falta DATABASE_URL: copie .env.example a .env.")
        self.DATABASE_URL = url
        self.PLATAFORMA_DATOS = _ruta(os.environ.get("PLATAFORMA_DATOS", "data/plataforma"))
        self.PLATAFORMA_N_JOBS = int(os.environ.get("PLATAFORMA_N_JOBS", "8"))
        self.PLATAFORMA_MAX_MB = int(os.environ.get("PLATAFORMA_MAX_MB", "50"))
        self.PLATAFORMA_MAX_FILAS_PREDICCION = int(os.environ.get("PLATAFORMA_MAX_FILAS_PREDICCION", "20000"))


class Pruebas:
    """SQLite en memoria (pruebas unitarias, con create_all) o la URL indicada (DATABASE_URL_PRUEBAS, con Alembic)."""

    TESTING = True

    def __init__(self, database_url: str = "sqlite+pysqlite:///:memory:", datos: Path | None = None) -> None:
        self.DATABASE_URL = database_url
        self.PLATAFORMA_DATOS = datos  # las pruebas pasan un directorio temporal
        self.PLATAFORMA_N_JOBS = 1
        self.PLATAFORMA_MAX_MB = 50
        self.PLATAFORMA_MAX_FILAS_PREDICCION = 20000
