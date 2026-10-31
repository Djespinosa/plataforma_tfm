"""Textos visibles de la API (docs/diseno-api.md §7; skill guardarrailes-interfaz). Ninguna ruta escribe texto fuera de
aquí, salvo los ValueError de ml/."""

from __future__ import annotations

ERROR_INTERNO = "Error interno de la plataforma. Inténtelo de nuevo; si persiste, consulte el registro del servidor."
ERROR_BD_NO_DISPONIBLE = "La base de datos no está disponible."
ERROR_RUTA_NO_EXISTE = "No existe la ruta solicitada."
ERROR_METODO_NO_PERMITIDO = "Esta ruta no admite el método solicitado."
ERROR_PETICION = "La petición no se ha podido atender."

# Conjuntos de datos (RF-01, §4.1)
AVISO_PRIVACIDAD_CARGA = ("No suba datos personales identificables sin autorización. La plataforma no envía datos a "
                          "servicios externos.")
ERROR_SIN_ARCHIVO = "No se ha recibido ningún archivo."
ERROR_NO_CSV = "El archivo debe ser un CSV en UTF-8 separado por comas o por punto y coma."
ERROR_SIN_FILAS = "El archivo no tiene filas de datos."
ERROR_POCAS_COLUMNAS = "Se necesitan al menos 2 columnas."


def error_columnas_repetidas(nombres: list[str]) -> str:
    return f"Hay columnas con el mismo nombre: {', '.join(nombres)}."


def error_tamano_maximo(mb: int) -> str:
    return f"El archivo supera el tamaño máximo de {mb} MB."


def error_no_existe(recurso: str, id_: object) -> str:
    return f"No existe el {recurso} {id_}."


def aviso_identificador(columna: str) -> str:
    return (f"La columna «{columna}» parece un identificador; excluirla de las variables protege la privacidad y evita "
            "que el modelo memorice filas.")


def aviso_columna_vacia(columna: str) -> str:
    return f"La columna «{columna}» no tiene ningún valor."


def aviso_columna_constante(columna: str) -> str:
    return f"La columna «{columna}» tiene el mismo valor en todas las filas; no aporta información al modelo."
