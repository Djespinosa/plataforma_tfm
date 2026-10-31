"""Entrenamiento de un experimento web en el trabajador (RF-03, docs/diseno-api.md §5): datos → motor.modelar → modelo
final → paquete → explicación global, curva y equidad → base de datos, todo con funciones de ml/automl.

Nada a medias: el modelo, su evaluación y el estado «completado» se escriben en una sola transacción al final; si algo
falla, el experimento queda «fallido» con un mensaje, la traza va a experimentos/<id>/error.log y se borran los archivos
parciales. La cohorte de prueba no llega nunca a modelar: preparar la aparta antes de asignar los pliegues.
"""

from __future__ import annotations

import hashlib
import traceback
from datetime import UTC, datetime
from pathlib import Path

import joblib
import pandas as pd
from flask import current_app
from sqlalchemy.orm import Session, sessionmaker

from api import textos
from api.errores import ErrorPlataforma
from api.servicios.configuracion_exp import huella_pliegues, preparar
from api.servicios.evaluacion import desde_momento
from api.servicios.paquetes import ruta_registrada
from api.servicios.tablas_csv import leer_csv
from api.tablas import ConjuntoDatos, Experimento, Modelo
from automl import busqueda, explicacion, motor
from automl.comparacion import holm, lectura
from automl.validacion import ErrorValidacion
from evidencias import hardware, sha256, versiones_entorno

PARCIALES = ("paquete.joblib", "oof.parquet", "prueba.parquet")


class _Avance:
    """Guarda la etapa y el progreso {completadas, total} con una sesión propia en cuanto empieza cada etapa."""

    def __init__(self, sesiones: sessionmaker, id_: str, familias: list[str], total: int) -> None:
        self.sesiones, self.id_, self.familias, self.total, self.completadas = sesiones, id_, familias, total, 0

    def __call__(self, etapa: str) -> None:
        if etapa in self.familias:
            texto = textos.etapa_familia(etapa, self.familias.index(etapa) + 1, len(self.familias))
        else:
            texto = textos.ETAPAS[etapa]
        with self.sesiones() as s:
            experimento = s.get(Experimento, self.id_)
            experimento.etapa = texto
            experimento.progreso = {"completadas": self.completadas, "total": self.total}
            s.commit()
        self.completadas += 1


def _terminar(s: Session, experimento: Experimento, estado: str) -> None:
    experimento.estado = estado
    experimento.terminado_en = datetime.now(UTC)
    iniciado = experimento.iniciado_en
    if iniciado is not None:
        iniciado = iniciado if iniciado.tzinfo else iniciado.replace(tzinfo=UTC)
        experimento.duracion_s = round((experimento.terminado_en - iniciado).total_seconds(), 1)


def _reproducibilidad(id_: str, config: dict, sha256_datos: str, sha256_oof: str) -> dict:
    # El código que se ejecuta es el que el proceso cargó al arrancar: commit y árbol limpio de ese momento
    # (trabajador.estado_codigo), no los de ahora, que pueden haber cambiado durante un entrenamiento de horas.
    codigo = current_app.config.get("CODIGO_TRABAJADOR") or {"commit": current_app.config["COMMIT"],
                                                              "arbol_limpio": None}
    return {"id": id_, **codigo, "semillas": config["semillas"],
            "versiones": versiones_entorno("pandas", "numpy", "sklearn", "xgboost", "lightgbm", "catboost", "optuna",
                                           "shap", "joblib", "flask", "sqlalchemy", "psycopg"),
            "sha256_datos": sha256_datos, "sha256_oof": sha256_oof, "hardware": hardware(),
            "optuna": busqueda.DESCRIPCION_OPTUNA,
            "n_jobs": {"valor": config["n_jobs"], "nivel": busqueda.NIVEL_N_JOBS}}


def _entrenar(sesiones: sessionmaker, id_: str, carpeta: Path) -> None:
    with sesiones() as s:
        experimento = s.get(Experimento, id_)
        conjunto = s.get(ConjuntoDatos, experimento.conjunto_id)
        config, sha256_datos, momento = experimento.configuracion, experimento.sha256_datos, conjunto.momento
        ruta_datos = Path(current_app.config["PLATAFORMA_DATOS"]) / conjunto.ruta
    contenido = ruta_datos.read_bytes()
    if hashlib.sha256(contenido).hexdigest() != sha256_datos:
        raise ErrorPlataforma(409, textos.ERROR_CONJUNTO_CAMBIADO)
    p = preparar(leer_csv(contenido), config)
    if huella_pliegues(p.pliegue) != config["validacion"]["pliegues_sha256"]:
        raise ErrorPlataforma(409, textos.ERROR_PLIEGUES_DISTINTOS)

    columnas = config["variables"]
    presupuesto = config["presupuesto"]
    ajustes = {c: presupuesto[c] for c in ("familias", "n_trials_por_familia", "apilamiento", "n_bootstrap")} | {
        c: config[c] for c in ("semillas", "n_jobs", "sensibilidad_minima")}
    total = len(ajustes["familias"]) + 2 + ajustes["apilamiento"] + 2 + bool(config["sensibles"])
    avance = _Avance(sesiones, id_, ajustes["familias"], total)
    resumen, predicciones, otras, modelos = motor.modelar(p.X, p.y, p.pliegue, columnas, ajustes, avance)
    contraste = resumen["contraste_central"]
    contraste["delong_p_holm"] = holm([contraste["delong_p"]])[0]  # un solo momento: Holm sobre 1 contraste = p
    contraste["lectura"] = lectura(contraste["diferencia"], contraste["ic95_bootstrap"], contraste["delong_p_holm"])

    avance("final")
    desplegado = resumen["modelo_desplegado"]["modelo"]
    corte = resumen["punto_operacion_oof"]["umbral_exacto"]
    semilla = config["semillas"]["modelos"]
    final = motor.entrenar_desplegado(resumen, modelos, p.X, p.y, p.pliegue, columnas, ajustes)
    paquete = explicacion.preparar_paquete(final, desplegado, corte, columnas, p.X,
                                           {"experimento": id_, "desplegado": True}, semilla, momento)
    carpeta.mkdir(parents=True, exist_ok=True)
    joblib.dump(paquete, carpeta / "paquete.joblib")

    avance("global")
    global_ = explicacion.explicacion_global(paquete, p.X, semilla)
    sin_calibrar = otras.get(f"{desplegado}_sin_calibrar")  # el apilamiento no tiene salida sin calibrar
    curva = {"calibrada": motor.curva_calibracion(p.y, predicciones[desplegado]),
             "sin_calibrar": motor.curva_calibracion(p.y, sin_calibrar) if sin_calibrar is not None else None}
    equidad = None
    if config["sensibles"]:
        avance("equidad")
        # Recuentos de referencia = el entrenamiento: la plataforma no muestra nada de la cohorte de prueba.
        auditoria = motor.auditar_equidad(p.y, predicciones[desplegado], corte, p.atributos, p.y, p.atributos,
                                          ajustes["n_bootstrap"], config["semillas"]["bootstrap"],
                                          recuentos_de="entrenamiento")
        equidad = {k: v for k, v in auditoria.items() if k != "recuentos_de"}

    pd.DataFrame({"etiqueta": p.y, **{f"p_{m}": v for m, v in (predicciones | otras).items()}}).to_parquet(
        carpeta / "oof.parquet", index=False)
    if len(p.filas_prueba):
        pd.DataFrame({"fila": p.filas_prueba}).to_parquet(carpeta / "prueba.parquet", index=False)

    with sesiones() as s:
        s.add(Modelo(experimento_id=id_, momento=momento, familia=desplegado,
                     ruta_paquete=ruta_registrada(carpeta / "paquete.joblib"),
                     sha256_paquete=sha256(carpeta / "paquete.joblib"), umbral=float(corte),
                     metodo_calibracion=resumen["calibracion"].get("metodo"), columnas=columnas,
                     explicador=paquete["explicador"], evaluacion=desde_momento(resumen, 1, curva, equidad),
                     explicacion_global=global_))
        experimento = s.get(Experimento, id_)
        experimento.etapa = None
        experimento.progreso = {"completadas": total, "total": total}
        experimento.reproducibilidad = _reproducibilidad(id_, config, sha256_datos, sha256(carpeta / "oof.parquet"))
        _terminar(s, experimento, "completado")
        s.commit()


def ejecutar(id_: str) -> None:
    """Entrena el experimento id_ (en_curso) y lo deja «completado» o «fallido». Dentro del contexto de la app."""
    sesiones = current_app.extensions["bd_sesiones"]
    carpeta = Path(current_app.config["PLATAFORMA_DATOS"]) / "experimentos" / id_
    try:
        _entrenar(sesiones, id_, carpeta)
    except Exception as e:
        # Solo se reenvían los mensajes propios (en español); cualquier otro error, de ml/ o de una biblioteca, va al
        # registro y el usuario ve un texto genérico.
        mensaje = e.mensaje if isinstance(e, ErrorPlataforma) else str(e) if isinstance(e, ErrorValidacion) \
            else textos.ERROR_ENTRENAMIENTO
        carpeta.mkdir(parents=True, exist_ok=True)
        (carpeta / "error.log").write_text(traceback.format_exc(), encoding="utf-8")
        for nombre in PARCIALES:
            (carpeta / nombre).unlink(missing_ok=True)
        with sesiones() as s:
            experimento = s.get(Experimento, id_)
            experimento.error = mensaje
            _terminar(s, experimento, "fallido")
            s.commit()
