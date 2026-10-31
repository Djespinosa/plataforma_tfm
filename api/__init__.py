"""API Flask de la plataforma (docs/diseno-api.md). Se ejecuta desde la raíz del repositorio:
`flask --app api run --port 5000`."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from flask import Flask

RAIZ = Path(__file__).resolve().parents[1]
# ml/ va en sys.path antes de cualquier joblib.load: los paquetes serializan sus clases como automl.* (módulo de primer
# nivel), y la API reutiliza el núcleo sin reimplementarlo.
if str(RAIZ / "ml") not in sys.path:
    sys.path.insert(0, str(RAIZ / "ml"))


def _commit() -> str | None:
    import evidencias

    try:
        return evidencias.git("rev-parse", "--short", "HEAD")
    except (OSError, subprocess.CalledProcessError):
        return None


def crear_app(configuracion: object | None = None) -> Flask:
    from api import bd, errores
    from api.configuracion import Desarrollo
    from api.rutas import conjuntos, estado

    app = Flask(__name__)
    app.config.from_object(configuracion if configuracion is not None else Desarrollo())
    app.config["COMMIT"] = _commit()
    app.config["MAX_CONTENT_LENGTH"] = app.config["PLATAFORMA_MAX_MB"] * 1024 * 1024  # 413 al leer request.files
    app.json.ensure_ascii = False
    bd.iniciar(app)
    errores.registrar(app)
    app.register_blueprint(estado.bp)
    app.register_blueprint(conjuntos.bp)
    return app


# Nombre de factoría que busca `flask --app api`.
create_app = crear_app
