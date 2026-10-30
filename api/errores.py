"""Errores de la plataforma y manejadores: toda respuesta de error es {"error": "<mensaje en español>"}."""

from __future__ import annotations

from flask import Flask, jsonify
from sqlalchemy.exc import OperationalError
from werkzeug.exceptions import HTTPException

from api import textos


class ErrorPlataforma(Exception):
    def __init__(self, codigo: int, mensaje: str, detalles: list[str] | None = None) -> None:
        super().__init__(mensaje)
        self.codigo = codigo
        self.mensaje = mensaje
        self.detalles = detalles


def _respuesta(codigo: int, mensaje: str, detalles: list[str] | None = None):
    cuerpo = {"error": mensaje} | ({"detalles": detalles} if detalles else {})
    return jsonify(cuerpo), codigo


def registrar(app: Flask) -> None:
    @app.errorhandler(ErrorPlataforma)
    def _plataforma(e: ErrorPlataforma):
        return _respuesta(e.codigo, e.mensaje, e.detalles)

    # Cualquier OperationalError responde 503 aunque la causa no sea de disponibilidad (p. ej. un bloqueo o una
    # consulta cancelada); el detalle queda en el registro.
    @app.errorhandler(OperationalError)
    def _bd(e: OperationalError):
        app.logger.error("Base de datos no disponible: %s", e)
        return _respuesta(503, textos.ERROR_BD_NO_DISPONIBLE)

    @app.errorhandler(HTTPException)
    def _http(e: HTTPException):
        mensajes = {404: textos.ERROR_RUTA_NO_EXISTE, 405: textos.ERROR_METODO_NO_PERMITIDO}
        return _respuesta(e.code or 500, mensajes.get(e.code, textos.ERROR_PETICION))

    @app.errorhandler(Exception)
    def _interno(e: Exception):
        app.logger.exception("Error no controlado")
        return _respuesta(500, textos.ERROR_INTERNO)
