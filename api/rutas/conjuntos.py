"""Conjuntos de datos (RF-01): POST /api/conjuntos, GET /api/conjuntos y GET /api/conjuntos/{id} (docs/diseno-api.md
§4.1)."""

from __future__ import annotations

import hashlib
import os
import uuid
from pathlib import Path

from flask import Blueprint, current_app, jsonify, request
from sqlalchemy import select

from api import textos
from api.bd import fecha_iso, sesion
from api.errores import ErrorPlataforma
from api.servicios.tablas_csv import leer_csv, resumir_columnas
from api.tablas import ConjuntoDatos

bp = Blueprint("conjuntos", __name__, url_prefix="/api")


def _resumen(c: ConjuntoDatos) -> dict:
    return {"id": c.id, "nombre_archivo": c.nombre_archivo, "momento": c.momento, "sha256": c.sha256,
            "n_filas": c.n_filas, "n_columnas": c.n_columnas, "columnas": c.columnas, "avisos": c.avisos,
            "aviso_privacidad": textos.AVISO_PRIVACIDAD_CARGA, "creado_en": fecha_iso(c.creado_en)}


@bp.post("/conjuntos")
def subir():
    archivo = request.files.get("archivo")
    if archivo is None or not archivo.filename:
        raise ErrorPlataforma(400, textos.ERROR_SIN_ARCHIVO)
    contenido = archivo.read()
    datos = leer_csv(contenido)
    columnas, avisos = resumir_columnas(datos)
    huella = hashlib.sha256(contenido).hexdigest()
    # Nombre por SHA-256 y no por id: la ruta no puede cambiar después del INSERT (disparador conjunto_datos_inmutable)
    # y el mismo contenido comparte archivo. Relativa a PLATAFORMA_DATOS.
    ruta = Path("conjuntos") / f"{huella}.csv"
    destino = Path(current_app.config["PLATAFORMA_DATOS"]) / ruta
    if not destino.exists() or hashlib.sha256(destino.read_bytes()).hexdigest() != huella:
        # Temporal propio y os.replace: un corte a media escritura o una subida simultánea nunca dejan un archivo
        # truncado con el nombre del hash (y uno así se reescribe en la siguiente subida).
        destino.parent.mkdir(parents=True, exist_ok=True)
        temporal = destino.with_name(f"{huella}.{uuid.uuid4().hex}.tmp")
        temporal.write_bytes(contenido)
        os.replace(temporal, destino)
    momento = (request.form.get("momento") or "").strip() or None
    conjunto = ConjuntoDatos(nombre_archivo=archivo.filename, momento=momento, ruta=ruta.as_posix(), sha256=huella,
                             n_filas=len(datos), n_columnas=datos.shape[1], columnas=columnas, avisos=avisos)
    s = sesion()
    s.add(conjunto)
    s.commit()
    return jsonify(_resumen(conjunto)), 201


@bp.get("/conjuntos")
def listar():
    conjuntos = sesion().scalars(select(ConjuntoDatos).order_by(ConjuntoDatos.id.desc()))
    return jsonify([{"id": c.id, "nombre_archivo": c.nombre_archivo, "momento": c.momento, "n_filas": c.n_filas,
                     "n_columnas": c.n_columnas, "creado_en": fecha_iso(c.creado_en)} for c in conjuntos])


@bp.get("/conjuntos/<int:id_>")
def detalle(id_: int):
    conjunto = sesion().get(ConjuntoDatos, id_)
    if conjunto is None:
        raise ErrorPlataforma(404, textos.error_no_existe("conjunto de datos", id_))
    return jsonify(_resumen(conjunto))
