"""Carga de los paquetes de los modelos desplegados (docs/diseno-api.md §1, invariantes 2 y 4; §4.4).

joblib.load solo sobre la ruta registrada en `modelo` y después de comprobar su SHA-256; el paquete debe traer
origen["desplegado"] is True aunque el modelo ya esté en la base de datos (identidad, no veracidad). Los últimos
TAMANO_CACHE paquetes cargados se guardan en memoria (los errores no).
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import joblib

from api import textos
from api.errores import ErrorPlataforma
from api.tablas import Modelo
from evidencias import RAIZ, sha256

TAMANO_CACHE = 8


@lru_cache(maxsize=TAMANO_CACHE)
def _cargar(ruta: str, huella: str) -> dict:
    archivo = Path(ruta) if Path(ruta).is_absolute() else RAIZ / ruta
    if not archivo.is_file() or sha256(archivo) != huella:
        raise ErrorPlataforma(409, textos.ERROR_PAQUETE_DISTINTO)
    paquete = joblib.load(archivo)
    if paquete.get("origen", {}).get("desplegado") is not True:
        raise ErrorPlataforma(409, textos.ERROR_NO_DESPLEGADO)
    return paquete


def ruta_registrada(ruta: Path) -> str:
    """Ruta que se guarda en modelo.ruta_paquete: relativa a la raíz del repositorio si está dentro; si no, absoluta."""
    ruta = ruta.resolve()
    return (ruta.relative_to(RAIZ) if ruta.is_relative_to(RAIZ) else ruta).as_posix()


def cargar_paquete(modelo: Modelo) -> dict:
    """Paquete del modelo (no se debe modificar: es el de la caché). 409 si el archivo no coincide con el registrado o
    el paquete no es de un modelo desplegado."""
    return _cargar(modelo.ruta_paquete, modelo.sha256_paquete)
