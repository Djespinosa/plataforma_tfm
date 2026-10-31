"""Predicción (RF-05) y explicación local (RF-06): POST /api/modelos/{id}/predicciones, GET /api/predicciones/{lote_id} y
GET /api/predicciones/{lote_id}/filas/{fila}/explicacion (docs/diseno-api.md §4.4 y §4.5).

Nunca se calculan métricas con las filas de predicción: la columna objetivo, si viene, se ignora como cualquier otra
columna que el modelo no usa. Con explicador lineal o de árbol se explican todas las filas al predecir; con permutación,
cada fila la primera vez que se pide.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from flask import Blueprint, current_app, jsonify, request
from sqlalchemy import insert, select

from api import textos
from api.bd import fecha_iso, sesion
from api.errores import ErrorPlataforma
from api.servicios import explicaciones
from api.servicios.paquetes import cargar_paquete
from api.servicios.tablas_csv import coaccionar, guardar, leer_csv
from api.tablas import Explicacion, LotePrediccion, Modelo, Prediccion
from automl import explicacion
from automl.validacion import normalizar_valor

bp = Blueprint("predicciones", __name__, url_prefix="/api")

COMPLETAS = ("lineal", "arbol")  # explicadores rápidos: todas las filas al predecir


def _modo_explicaciones(modelo: Modelo) -> str:
    return "completas" if modelo.explicador in COMPLETAS else "bajo_demanda"


def _modelo(id_: int) -> Modelo:
    modelo = sesion().get(Modelo, id_)
    if modelo is None:
        raise ErrorPlataforma(404, textos.error_no_existe("modelo", id_))
    return modelo


def _registros(tabla: pd.DataFrame) -> list[dict]:
    """Filas como diccionarios JSON (NaN → None; JSONB no admite NaN)."""
    return tabla.astype(object).where(tabla.notna(), None).to_dict("records")


def _errores_aditividad(phi: pd.DataFrame, prediccion: pd.DataFrame) -> np.ndarray:
    return np.abs(phi.sum(axis=1).to_numpy() + prediccion["base_log_odds"].to_numpy()
                  - prediccion["log_odds"].to_numpy())


@bp.post("/modelos/<int:id_>/predicciones")
def predecir(id_: int):
    modelo = _modelo(id_)
    archivo = request.files.get("archivo")
    if archivo is None or not archivo.filename:
        raise ErrorPlataforma(400, textos.ERROR_SIN_ARCHIVO)
    paquete = cargar_paquete(modelo)
    contenido = archivo.read()
    datos = leer_csv(contenido)
    maximo = current_app.config["PLATAFORMA_MAX_FILAS_PREDICCION"]
    if len(datos) > maximo:
        raise ErrorPlataforma(422, textos.error_max_filas(len(datos), maximo))
    columna_id = (request.form.get("columna_id") or "").strip() or None
    if columna_id is not None and columna_id not in datos.columns:
        raise ErrorPlataforma(422, textos.error_columna_id(columna_id))
    X = coaccionar(datos, modelo.columnas).reset_index(drop=True)
    ignoradas = [c for c in datos.columns if c not in X.columns and c != columna_id]

    prediccion = explicacion.predecir(paquete, X)
    ruta, huella = guardar(contenido, "predicciones")
    s = sesion()
    lote = LotePrediccion(modelo_id=modelo.id, nombre_archivo=archivo.filename, ruta=ruta, sha256=huella,
                          n_filas=len(X), columna_id=columna_id, columnas_ignoradas=ignoradas, umbral=modelo.umbral,
                          n_alertas=int(prediccion["alerta"].sum()))
    s.add(lote)
    s.flush()
    identificadores = ([None if pd.isna(v) else normalizar_valor(v) for v in datos[columna_id]]
                       if columna_id is not None else [None] * len(X))
    s.execute(insert(Prediccion), [
        {"lote_id": lote.id, "fila": i + 1, "identificador": identificadores[i], "probabilidad": float(p.probabilidad),
         "alerta": bool(p.alerta), "log_odds": float(p.log_odds), "base_log_odds": float(p.base_log_odds),
         "valores": valores}
        for i, (p, valores) in enumerate(zip(prediccion.itertuples(), _registros(X)))])
    if modelo.explicador in COMPLETAS:
        phi, _ = explicacion.explicar(paquete, X)
        errores = _errores_aditividad(phi, prediccion)
        s.execute(insert(Explicacion), [
            {"lote_id": lote.id, "fila": i + 1, "contribuciones": contribuciones, "explicador": modelo.explicador,
             "error_aditividad": float(errores[i])}
            for i, contribuciones in enumerate(phi.astype(float).to_dict("records"))])
    s.commit()
    return jsonify({"lote_id": lote.id, "modelo_id": modelo.id, "n_filas": lote.n_filas, "n_alertas": lote.n_alertas,
                    "tasa_alerta": lote.n_alertas / lote.n_filas, "umbral": lote.umbral,
                    "columnas_ignoradas": ignoradas, "explicaciones": _modo_explicaciones(modelo),
                    "aviso_rendimiento": textos.AVISO_RENDIMIENTO, "aviso_decision": textos.AVISO_DECISION}), 201


def _lote(lote_id: int) -> tuple[LotePrediccion, Modelo]:
    lote = sesion().get(LotePrediccion, lote_id)
    if lote is None:
        raise ErrorPlataforma(404, textos.error_no_existe("lote de predicción", lote_id))
    return lote, sesion().get(Modelo, lote.modelo_id)


@bp.get("/predicciones/<int:lote_id>")
def lote(lote_id: int):
    lote, modelo = _lote(lote_id)
    filas = sesion().scalars(select(Prediccion).where(Prediccion.lote_id == lote_id).order_by(Prediccion.fila))
    return jsonify({
        "lote": {"id": lote.id, "modelo_id": lote.modelo_id, "nombre_archivo": lote.nombre_archivo,
                 "n_filas": lote.n_filas, "n_alertas": lote.n_alertas, "tasa_alerta": lote.n_alertas / lote.n_filas,
                 "umbral": lote.umbral, "columna_id": lote.columna_id, "columnas_ignoradas": lote.columnas_ignoradas,
                 "explicaciones": _modo_explicaciones(modelo), "creado_en": fecha_iso(lote.creado_en)},
        "filas": [{"fila": p.fila, "identificador": p.identificador, "probabilidad": p.probabilidad, "alerta": p.alerta,
                   "sugerencia": textos.SUGERENCIA if p.alerta else None} for p in filas],
        "textos": {"probabilidad": textos.TEXTO_PROBABILIDAD, "sugerencia": textos.SUGERENCIA},
        "aviso_rendimiento": textos.AVISO_RENDIMIENTO, "aviso_decision": textos.AVISO_DECISION,
    })


def _explicar_fila(paquete: dict, modelo: Modelo, prediccion: Prediccion) -> Explicacion:
    """Explicación de una fila que aún no la tiene (explicador de permutación), desde los valores guardados."""
    columnas = modelo.columnas
    X = pd.DataFrame([prediccion.valores], columns=columnas["numericas"] + columnas["categoricas"])
    X = X.astype({c: float for c in columnas["numericas"]})
    for c in columnas["categoricas"]:
        X[c] = X[c].where(X[c].notna(), np.nan)  # None → NaN, el vacío que imputa el preprocesado
    phi, error = explicacion.explicar(paquete, X)
    return Explicacion(lote_id=prediccion.lote_id, fila=prediccion.fila, explicador=modelo.explicador,
                       contribuciones=phi.astype(float).iloc[0].to_dict(), error_aditividad=error)


@bp.get("/predicciones/<int:lote_id>/filas/<int:fila>/explicacion")
def explicacion_local(lote_id: int, fila: int):
    _, modelo = _lote(lote_id)
    s = sesion()
    prediccion = s.get(Prediccion, (lote_id, fila))
    if prediccion is None:
        raise ErrorPlataforma(404, textos.error_fila_no_existe(fila, lote_id))
    paquete = cargar_paquete(modelo)
    fila_explicada = s.get(Explicacion, (lote_id, fila))
    if fila_explicada is None:
        fila_explicada = _explicar_fila(paquete, modelo, prediccion)
        s.add(fila_explicada)
        s.commit()
    detalle = explicaciones.local(fila_explicada.contribuciones, prediccion.valores,
                                  explicacion.variables_sin_valores(paquete))
    avisos = {"escala": textos.AVISO_ESCALA, "causalidad": textos.AVISO_CAUSALIDAD, "decision": textos.AVISO_DECISION}
    if detalle["hay_extremas"]:
        avisos["extrema"] = textos.AVISO_EXTREMA
    return jsonify({"fila": prediccion.fila, "identificador": prediccion.identificador,
                    "probabilidad": prediccion.probabilidad, "alerta": prediccion.alerta,
                    "sugerencia": textos.SUGERENCIA if prediccion.alerta else None,
                    "escala": textos.ESCALA, "valor_base": prediccion.base_log_odds, "log_odds": prediccion.log_odds,
                    "explicador": fila_explicada.explicador, **detalle, "avisos": avisos,
                    "aviso_decision": textos.AVISO_DECISION})
