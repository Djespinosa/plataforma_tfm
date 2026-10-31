"""Experimentos (docs/diseno-api.md §4.2 y §4.3): POST /api/experimentos/validacion, POST /api/experimentos,
GET /api/experimentos (historial, RF-08), GET /api/experimentos/{id}, POST /api/experimentos/{id}/reintentar (RF-08) y
GET /api/experimentos/{id}/evaluacion.

El servidor web solo crea experimentos «en_cola» y lee su estado; los entrena el trabajador (api/trabajador.py).
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta
from pathlib import Path

from flask import Blueprint, current_app, jsonify, request, url_for
from sqlalchemy import select

from api import textos
from api.bd import fecha_iso, sesion
from api.errores import ErrorPlataforma
from api.servicios.configuracion_exp import Preparados, configurar
from api.servicios.evaluacion import con_textos
from api.servicios.tablas_csv import leer_csv
from api.tablas import ConjuntoDatos, Experimento, Modelo, clave_cohorte

bp = Blueprint("experimentos", __name__, url_prefix="/api")

SIN_RESPUESTA_S = 120
REINTENTABLES = ("fallido", "interrumpido")


def _contenido(conjunto: ConjuntoDatos) -> bytes:
    """Bytes del CSV del conjunto; 409 si el archivo ya no es el que se cargó."""
    contenido = (Path(current_app.config["PLATAFORMA_DATOS"]) / conjunto.ruta).read_bytes()
    if hashlib.sha256(contenido).hexdigest() != conjunto.sha256:
        raise ErrorPlataforma(409, textos.ERROR_CONJUNTO_CAMBIADO)
    return contenido


def _configurar() -> tuple[dict, ConjuntoDatos, dict, Preparados]:
    cuerpo = request.get_json(silent=True)
    if not isinstance(cuerpo, dict):
        raise ErrorPlataforma(400, textos.ERROR_JSON)
    if cuerpo.get("conjunto_id") is None:
        raise ErrorPlataforma(400, textos.error_falta_campo("conjunto_id"))
    conjunto = sesion().get(ConjuntoDatos, cuerpo["conjunto_id"]) if isinstance(cuerpo["conjunto_id"], int) else None
    if conjunto is None:
        raise ErrorPlataforma(404, textos.error_no_existe("conjunto de datos", cuerpo["conjunto_id"]))
    config, preparados = configurar(cuerpo, conjunto, leer_csv(_contenido(conjunto)),
                                    permitir_prueba=current_app.testing, n_jobs=current_app.config["PLATAFORMA_N_JOBS"])
    return cuerpo, conjunto, config, preparados


@bp.post("/experimentos/validacion")
def validacion():
    _, _, config, p = _configurar()
    return jsonify({
        "filas_entrenamiento": len(p.y), "filas_prueba": len(p.filas_prueba),
        "filas_sin_objetivo": p.filas_sin_objetivo, "positivos_entrenamiento": int(p.y.sum()),
        "prevalencia_entrenamiento": float(p.y.mean()),
        "variables": {c: config["variables"][c] for c in ("numericas", "categoricas")},
        "excluidas_automaticamente": config["excluidas_automaticamente"],
        "validacion": {c: config["validacion"][c] for c in ("tipo", "k", "semilla", "columna_grupo", "n_grupos")},
        "cohorte_prueba": config["cohorte_prueba"],
        "presupuesto": {c: config["presupuesto"][c] for c in ("modo", "familias", "n_trials_por_familia",
                                                              "n_bootstrap")},
        "avisos": config["avisos"],
    })


def _nuevo_id() -> str:
    prefijo = f"web-{datetime.now():%Y-%m-%d}-"
    ids = sesion().scalars(select(Experimento.id).where(Experimento.id.like(f"{prefijo}%")))
    return f"{prefijo}{max((int(i.removeprefix(prefijo)) for i in ids), default=0) + 1:02d}"


@bp.post("/experimentos")
def crear():
    cuerpo, conjunto, config, _ = _configurar()
    descripcion = cuerpo.get("descripcion")
    experimento = Experimento(
        id=_nuevo_id(), origen="web", conjunto_id=conjunto.id, sha256_datos=conjunto.sha256,
        cohorte_prueba_clave=clave_cohorte(config["cohorte_prueba"]) if config["cohorte_prueba"] else None,
        descripcion=descripcion if isinstance(descripcion, str) else None, configuracion=config, estado="en_cola")
    return _encolar(experimento)


def _encolar(experimento: Experimento):
    s = sesion()
    s.add(experimento)
    s.commit()
    respuesta = jsonify(_detalle(experimento))
    respuesta.headers["Location"] = url_for("experimentos.detalle", id_=experimento.id)
    return respuesta, 202


@bp.get("/experimentos")
def historial():
    s = sesion()
    experimentos = s.scalars(select(Experimento).order_by(Experimento.creado_en.desc(), Experimento.id.desc())).all()
    conjuntos = {c.id: c for c in s.scalars(select(ConjuntoDatos))}
    modelos: dict[str, list[dict]] = {}
    for m in s.scalars(select(Modelo).order_by(Modelo.id)):
        modelos.setdefault(m.experimento_id, []).append({"id": m.id, "momento": m.momento, "familia": m.familia})
    return jsonify([{
        "id": e.id, "origen": e.origen, "estado": e.estado, "creado_en": fecha_iso(e.creado_en),
        "duracion_s": e.duracion_s, "descripcion": e.descripcion,
        "conjunto": ({"id": c.id, "nombre_archivo": c.nombre_archivo, "momento": c.momento}
                     if (c := conjuntos.get(e.conjunto_id)) else None),
        "objetivo": e.configuracion.get("objetivo"),  # los importados no lo registran
        "presupuesto": e.configuracion["presupuesto"]["modo"], "reintento_de": e.reintento_de,
        "modelos": modelos.get(e.id, []),
    } for e in experimentos])


@bp.post("/experimentos/<id_>/reintentar")
def reintentar(id_: str):
    """Experimento nuevo con la misma configuración efectiva (mismos pliegues): no se reanuda el anterior."""
    s = sesion()
    anterior = s.get(Experimento, id_)
    if anterior is None:
        raise ErrorPlataforma(404, textos.error_no_existe("experimento", id_))
    if anterior.estado not in REINTENTABLES:  # los importados están siempre completados
        raise ErrorPlataforma(409, textos.ERROR_REINTENTO)
    # Un solo reintento por experimento: un doble clic no encola dos entrenamientos iguales (un solo trabajador). Si el
    # reintento también falla, se reintenta el reintento.
    previo = s.scalars(select(Experimento.id).where(Experimento.reintento_de == id_).limit(1)).first()
    if previo is not None:
        raise ErrorPlataforma(409, textos.error_ya_reintentado(previo))
    _contenido(s.get(ConjuntoDatos, anterior.conjunto_id))
    return _encolar(Experimento(
        id=_nuevo_id(), origen="web", conjunto_id=anterior.conjunto_id, sha256_datos=anterior.sha256_datos,
        cohorte_prueba_clave=anterior.cohorte_prueba_clave, descripcion=anterior.descripcion,
        configuracion=anterior.configuracion, estado="en_cola", reintento_de=anterior.id))


def _detalle(e: Experimento) -> dict:
    latido = e.latido_en.replace(tzinfo=e.latido_en.tzinfo or UTC) if e.latido_en else None
    sin_respuesta = (e.estado == "en_curso" and latido is not None
                     and datetime.now(UTC) - latido > timedelta(seconds=SIN_RESPUESTA_S))
    modelos = sesion().scalars(select(Modelo).where(Modelo.experimento_id == e.id).order_by(Modelo.id))
    fecha = lambda v: fecha_iso(v) if v else None  # noqa: E731
    return {"id": e.id, "origen": e.origen, "estado": e.estado, "etapa": e.etapa, "progreso": e.progreso,
            "latido_en": fecha(e.latido_en), "sin_respuesta": sin_respuesta,
            "aviso_sin_respuesta": textos.SIN_RESPUESTA if sin_respuesta else None, "error": e.error,
            "creado_en": fecha(e.creado_en), "iniciado_en": fecha(e.iniciado_en), "terminado_en": fecha(e.terminado_en),
            "duracion_s": e.duracion_s, "descripcion": e.descripcion, "configuracion": e.configuracion,
            "reproducibilidad": e.reproducibilidad, "procedencia": e.procedencia,
            "reintento_de": e.reintento_de,
            "modelos": [{"id": m.id, "momento": m.momento, "familia": m.familia} for m in modelos]}


@bp.get("/experimentos/<id_>")
def detalle(id_: str):
    experimento = sesion().get(Experimento, id_)
    if experimento is None:
        raise ErrorPlataforma(404, textos.error_no_existe("experimento", id_))
    return jsonify(_detalle(experimento))


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
