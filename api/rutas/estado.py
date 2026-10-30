"""GET /api/estado: motor de base de datos, trabajador activo y commit (docs/diseno-api.md §4)."""

from __future__ import annotations

from flask import Blueprint, current_app, jsonify
from sqlalchemy import text

from api.bd import BLOQUEO_TRABAJADOR, sesion

bp = Blueprint("estado", __name__, url_prefix="/api")

# El bloqueo consultivo con una clave bigint aparece en pg_locks con classid = 32 bits altos, objid = 32 bits bajos y
# objsubid = 1, en la base de datos donde se tomó.
_TRABAJADOR_ACTIVO = text("""
    SELECT EXISTS (
        SELECT 1 FROM pg_locks
        WHERE locktype = 'advisory' AND granted AND objsubid = 1
          AND database = (SELECT oid FROM pg_database WHERE datname = current_database())
          AND classid::bigint = (CAST(:clave AS bigint) >> 32)
          AND objid::bigint = (CAST(:clave AS bigint) & 4294967295)
    )
""")


@bp.get("/estado")
def estado():
    s = sesion()
    if s.get_bind().dialect.name == "postgresql":
        version = s.execute(text("SHOW server_version")).scalar_one().split()[0]
        motor_bd = f"postgresql {version}"
        trabajador_activo = s.execute(_TRABAJADOR_ACTIVO, {"clave": BLOQUEO_TRABAJADOR}).scalar_one()
    else:
        s.execute(text("SELECT 1"))
        motor_bd = s.get_bind().dialect.name
        trabajador_activo = None
    return jsonify(motor_bd=motor_bd, trabajador_activo=trabajador_activo, commit=current_app.config["COMMIT"])
