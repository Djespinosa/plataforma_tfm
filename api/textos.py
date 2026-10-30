"""Textos visibles de la API (docs/diseno-api.md §7; skill guardarrailes-interfaz). Ninguna ruta escribe texto fuera de
aquí, salvo los ValueError de ml/."""

from __future__ import annotations

ERROR_INTERNO = "Error interno de la plataforma. Inténtelo de nuevo; si persiste, consulte el registro del servidor."
ERROR_BD_NO_DISPONIBLE = "La base de datos no está disponible."
ERROR_RUTA_NO_EXISTE = "No existe la ruta solicitada."
ERROR_METODO_NO_PERMITIDO = "Esta ruta no admite el método solicitado."
ERROR_PETICION = "La petición no se ha podido atender."
