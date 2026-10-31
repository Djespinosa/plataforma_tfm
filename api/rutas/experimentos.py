"""Experimentos: GET /api/experimentos/{id}/evaluacion (RF-04, docs/diseno-api.md §4.3). El resto de rutas del §4.2
llega en el incremento 6."""

from __future__ import annotations

from flask import Blueprint, jsonify
from sqlalchemy import select

from api import textos
from api.bd import sesion
from api.errores import ErrorPlataforma
from api.servicios.evaluacion import con_textos
from api.tablas import Experimento, Modelo

bp = Blueprint("experimentos", __name__, url_prefix="/api")


@bp.get("/experimentos/<id_>/evaluacion")
def evaluacion(id_: str):
    s = sesion()
    experimento = s.get(Experimento, id_)
    if experimento is None:
        raise ErrorPlataforma(404, textos.error_no_existe("experimento", id_))
    if experimento.estado != "completado":
        raise ErrorPlataforma(409, textos.error_no_terminado(experimento.estado))
    modelos = s.scalars(select(Modelo).where(Modelo.experimento_id == id_).order_by(Modelo.id))
    config = experimento.configuracion
    return jsonify({
        "experimento": experimento.id, "origen": experimento.origen, "fuente": "validacion_cruzada",
        "aviso_fuente": textos.AVISO_FUENTE_VALIDACION,
        "presupuesto": config["presupuesto"], "validacion": config["validacion"],
        "modelos": [{"modelo_id": m.id, "momento": m.momento, **con_textos(m.evaluacion)} for m in modelos],
        "aviso_decision": textos.AVISO_DECISION,
    })
