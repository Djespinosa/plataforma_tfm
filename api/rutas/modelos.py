"""Modelos desplegados: GET /api/modelos y GET /api/modelos/{id} (docs/diseno-api.md §4.4)."""

from __future__ import annotations

from flask import Blueprint, jsonify
from sqlalchemy import select

from api import textos
from api.bd import fecha_iso, sesion
from api.errores import ErrorPlataforma
from api.tablas import Experimento, Modelo

bp = Blueprint("modelos", __name__, url_prefix="/api")


def _resumen(m: Modelo, origen: str) -> dict:
    return {"id": m.id, "experimento_id": m.experimento_id, "origen": origen, "momento": m.momento,
            "familia": m.familia, "umbral": m.umbral, "explicador": m.explicador, "creado_en": fecha_iso(m.creado_en)}


@bp.get("/modelos")
def listar():
    filas = sesion().execute(select(Modelo, Experimento.origen).join(Experimento).order_by(Modelo.id))
    return jsonify([_resumen(m, origen) for m, origen in filas])


@bp.get("/modelos/<int:id_>")
def detalle(id_: int):
    modelo = sesion().get(Modelo, id_)
    if modelo is None:
        raise ErrorPlataforma(404, textos.error_no_existe("modelo", id_))
    origen = sesion().get(Experimento, modelo.experimento_id).origen
    columnas = {c: modelo.columnas[c] for c in ("numericas", "categoricas")}
    return jsonify(_resumen(modelo, origen) | {"columnas": columnas})
