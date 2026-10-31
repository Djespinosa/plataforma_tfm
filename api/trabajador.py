"""Proceso de entrenamiento en segundo plano (RNF-03, docs/diseno-api.md §5): `flask --app api trabajador`.

La cola es la tabla experimento. Un solo trabajador (bloqueo consultivo de PostgreSQL BLOQUEO_TRABAJADOR, que GET
/api/estado consulta); al arrancar, los experimentos «en_curso» son huérfanos de un trabajador anterior y pasan a
«interrumpido» (no se reanudan a medias). Después toma los experimentos «en_cola» de uno en uno, del más antiguo al más
reciente, y mantiene un latido cada LATIDO_S segundos mientras entrena.
"""

from __future__ import annotations

import subprocess
import threading
import time
from contextlib import contextmanager
from datetime import UTC, datetime

import click
from flask import Flask, current_app
from sqlalchemy import func, select, update

from api import textos
from api.bd import BLOQUEO_TRABAJADOR
from api.servicios import entrenamiento
from api.tablas import Experimento
from evidencias import git

ESPERA_S = 5
LATIDO_S = 30


def estado_codigo() -> dict:
    """Commit y árbol limpio del código que carga este proceso (RNF-06); None si git no está disponible."""
    try:
        return {"commit": git("rev-parse", "--short", "HEAD"), "arbol_limpio": not git("status", "--porcelain")}
    except (OSError, subprocess.CalledProcessError):
        return {"commit": None, "arbol_limpio": None}


def recuperar_huerfanos() -> int:
    """«en_curso» → «interrumpido» con su mensaje. Solo con el bloqueo tomado (ningún otro trabajador vivo)."""
    with current_app.extensions["bd_sesiones"]() as s:
        n = s.execute(update(Experimento).where(Experimento.estado == "en_curso").values(
            estado="interrumpido", error=textos.ERROR_INTERRUMPIDO, terminado_en=datetime.now(UTC))).rowcount
        s.commit()
    return n


def tomar() -> str | None:
    """Pasa a «en_curso» el experimento «en_cola» más antiguo y devuelve su id (None si no hay ninguno)."""
    with current_app.extensions["bd_sesiones"]() as s:
        experimento = s.scalars(select(Experimento).where(Experimento.estado == "en_cola")
                                .order_by(Experimento.creado_en, Experimento.id).limit(1)
                                .with_for_update(skip_locked=True)).first()
        if experimento is None:
            return None
        ahora = datetime.now(UTC)
        experimento.estado, experimento.iniciado_en, experimento.latido_en = "en_curso", ahora, ahora
        s.commit()
        return experimento.id


@contextmanager
def latido(id_: str):
    """Actualiza latido_en cada LATIDO_S segundos, con una sesión propia, mientras dura el bloque."""
    app = current_app._get_current_object()
    parar = threading.Event()

    def latir() -> None:
        with app.app_context():
            while not parar.wait(LATIDO_S):
                with app.extensions["bd_sesiones"]() as s:
                    s.execute(update(Experimento).where(Experimento.id == id_).values(latido_en=datetime.now(UTC)))
                    s.commit()

    hilo = threading.Thread(target=latir, name=f"latido-{id_}", daemon=True)
    hilo.start()
    try:
        yield
    finally:
        parar.set()
        hilo.join()


def procesar_siguiente() -> str | None:
    """Toma y entrena el siguiente experimento en cola; devuelve su id (None si la cola está vacía)."""
    id_ = tomar()
    if id_ is not None:
        with latido(id_):
            entrenamiento.ejecutar(id_)
    return id_


def registrar(app: Flask) -> None:
    @app.cli.command("trabajador")
    def _trabajador() -> None:
        """Entrena en segundo plano los experimentos en cola (uno a la vez). Ctrl+C para detenerlo."""
        motor = current_app.extensions["bd_motor"]
        conexion = None
        if motor.dialect.name == "postgresql":
            # Bloqueo de sesión: dura mientras esta conexión siga abierta, es decir, mientras viva el proceso.
            conexion = motor.connect()
            if not conexion.execute(select(func.pg_try_advisory_lock(BLOQUEO_TRABAJADOR))).scalar_one():
                conexion.close()
                raise click.ClickException(textos.ERROR_TRABAJADOR_ACTIVO)
            conexion.commit()
        current_app.config["CODIGO_TRABAJADOR"] = estado_codigo()  # el código cargado al arrancar es el que se ejecuta
        try:
            huerfanos = recuperar_huerfanos()
            if huerfanos:
                click.echo(f"{huerfanos} experimentos interrumpidos por un cierre anterior.")
            click.echo("Esperando experimentos en cola (Ctrl+C para detener).")
            while True:
                id_ = procesar_siguiente()
                if id_ is None:
                    time.sleep(ESPERA_S)
                else:
                    with current_app.extensions["bd_sesiones"]() as s:
                        click.echo(f"{id_}: {s.get(Experimento, id_).estado}.")
        except KeyboardInterrupt:
            click.echo("Detenido. Un experimento a medias quedará «interrumpido» al volver a arrancar.")
        finally:
            if conexion is not None:
                # close() devuelve la conexión al pool sin cerrarla: el bloqueo se suelta explícitamente.
                conexion.execute(select(func.pg_advisory_unlock(BLOQUEO_TRABAJADOR)))
                conexion.commit()
                conexion.close()
