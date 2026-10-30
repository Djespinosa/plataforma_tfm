"""Esquema inicial: las 6 tablas de docs/diseno-api.md §3 y la evaluación única en la cohorte de prueba (matiz D-2).

Revisión: 0001
Anterior:
Fecha: 2026-10-30
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

FECHA = sa.DateTime(timezone=True)

# Evaluación única en la cohorte de prueba (matiz D-2; mismos mensajes que api/tablas.py):
# - el id de un experimento no cambia nunca (renombrarlo permitiría saltarse lo demás);
# - una vez guardada la evaluación, no se puede cambiar, anular ni borrar su experimento, ni cambiar su configuración,
#   conjunto_id, sha256_datos o cohorte_prueba_clave, ni cambiar, borrar, añadir o traer de otro experimento sus modelos;
# - para evaluar, sha256_datos debe ser el SHA-256 de su conjunto_datos (cuya ruta y SHA-256 no cambian nunca);
# - una sola evaluación por (sha256_datos, cohorte_prueba_clave): índice único parcial.
# (TRUNCATE no dispara disparadores de fila: solo lo usan las pruebas para vaciar su propia base de datos.)
FORMATO_SHA256 = "length({c}) = 64 AND trim({c}, '0123456789abcdef') = ''"  # 64 hexadecimales en minúsculas
FUNCION_EVALUACION_UNICA = """
CREATE FUNCTION evaluacion_prueba_unica() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'UPDATE' THEN
        IF NEW.id IS DISTINCT FROM OLD.id THEN
            RAISE EXCEPTION 'El identificador de un experimento no cambia nunca.'
                USING ERRCODE = 'check_violation';
        END IF;
    END IF;
    IF TG_OP <> 'INSERT' THEN
        IF OLD.evaluacion_prueba IS NOT NULL THEN
            IF TG_OP = 'DELETE' THEN
                RAISE EXCEPTION 'La evaluación en la cohorte de prueba ya se hizo; se usa una sola vez.'
                    USING ERRCODE = 'check_violation';
            END IF;
            IF NEW.evaluacion_prueba IS DISTINCT FROM OLD.evaluacion_prueba THEN
                RAISE EXCEPTION 'La evaluación en la cohorte de prueba ya se hizo; se usa una sola vez.'
                    USING ERRCODE = 'check_violation';
            END IF;
            IF NEW.configuracion IS DISTINCT FROM OLD.configuracion
               OR NEW.conjunto_id IS DISTINCT FROM OLD.conjunto_id
               OR NEW.sha256_datos IS DISTINCT FROM OLD.sha256_datos
               OR NEW.cohorte_prueba_clave IS DISTINCT FROM OLD.cohorte_prueba_clave THEN
                RAISE EXCEPTION 'El experimento ya se evaluó en la cohorte de prueba; su configuración y sus modelos no se pueden cambiar.'
                    USING ERRCODE = 'check_violation';
            END IF;
        END IF;
    END IF;
    IF TG_OP = 'DELETE' THEN
        RETURN OLD;
    END IF;
    -- Al evaluar (o crear ya evaluado). Si ya estaba evaluado, conjunto_id y sha256_datos no han cambiado (arriba) y el
    -- SHA-256 del conjunto tampoco (conjunto_datos_inmutable), así que solo puede fallar en la transición NULL -> no NULL.
    -- Con sha256_datos o conjunto_id NULL, «<>» no es cierto y quien rechaza es el CHECK evaluacion_prueba.
    IF NEW.evaluacion_prueba IS NOT NULL
       AND NEW.sha256_datos <> (SELECT sha256 FROM conjunto_datos WHERE id = NEW.conjunto_id) THEN
        RAISE EXCEPTION 'El SHA-256 de los datos del experimento no coincide con el de su conjunto de datos; no se puede evaluar en la cohorte de prueba.'
            USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END
$$
"""
DISPARADOR_EVALUACION_UNICA = """
CREATE TRIGGER evaluacion_prueba_unica BEFORE INSERT OR UPDATE OR DELETE ON experimento
FOR EACH ROW EXECUTE FUNCTION evaluacion_prueba_unica()
"""
FUNCION_MODELO_CONGELADO = """
CREATE FUNCTION modelo_evaluado_congelado() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP <> 'INSERT' THEN
        IF EXISTS (SELECT 1 FROM experimento WHERE id = OLD.experimento_id AND evaluacion_prueba IS NOT NULL) THEN
            RAISE EXCEPTION 'El experimento ya se evaluó en la cohorte de prueba; su configuración y sus modelos no se pueden cambiar.'
                USING ERRCODE = 'check_violation';
        END IF;
    END IF;
    IF TG_OP = 'DELETE' THEN
        RETURN OLD;
    END IF;
    IF EXISTS (SELECT 1 FROM experimento WHERE id = NEW.experimento_id AND evaluacion_prueba IS NOT NULL) THEN
        RAISE EXCEPTION 'El experimento ya se evaluó en la cohorte de prueba; su configuración y sus modelos no se pueden cambiar.'
            USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END
$$
"""
DISPARADOR_MODELO_CONGELADO = """
CREATE TRIGGER modelo_evaluado_congelado BEFORE INSERT OR UPDATE OR DELETE ON modelo
FOR EACH ROW EXECUTE FUNCTION modelo_evaluado_congelado()
"""
FUNCION_CONJUNTO_INMUTABLE = """
CREATE FUNCTION conjunto_datos_inmutable() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.ruta IS DISTINCT FROM OLD.ruta OR NEW.sha256 IS DISTINCT FROM OLD.sha256 THEN
        RAISE EXCEPTION 'La ruta y el SHA-256 de un conjunto de datos no cambian nunca.'
            USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END
$$
"""
DISPARADOR_CONJUNTO_INMUTABLE = """
CREATE TRIGGER conjunto_datos_inmutable BEFORE UPDATE ON conjunto_datos
FOR EACH ROW EXECUTE FUNCTION conjunto_datos_inmutable()
"""


def upgrade() -> None:
    op.create_table(
        "conjunto_datos",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("nombre_archivo", sa.Text(), nullable=False),
        sa.Column("momento", sa.Text(), nullable=True),
        sa.Column("ruta", sa.Text(), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("n_filas", sa.Integer(), nullable=False),
        sa.Column("n_columnas", sa.Integer(), nullable=False),
        sa.Column("columnas", JSONB(), nullable=False),
        sa.Column("avisos", JSONB(), nullable=False),
        sa.Column("creado_en", FECHA, nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_conjunto_datos"),
        sa.CheckConstraint(FORMATO_SHA256.format(c="sha256"), name=op.f("ck_conjunto_datos_sha256")),
    )
    op.create_table(
        "experimento",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("origen", sa.Text(), nullable=False),
        sa.Column("conjunto_id", sa.Integer(), nullable=True),
        sa.Column("sha256_datos", sa.String(64), nullable=True),
        sa.Column("cohorte_prueba_clave", sa.String(64), nullable=True),
        sa.Column("descripcion", sa.Text(), nullable=True),
        sa.Column("configuracion", JSONB(), nullable=False),
        sa.Column("estado", sa.Text(), nullable=False),
        sa.Column("etapa", sa.Text(), nullable=True),
        sa.Column("progreso", JSONB(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("latido_en", FECHA, nullable=True),
        sa.Column("creado_en", FECHA, nullable=False),
        sa.Column("iniciado_en", FECHA, nullable=True),
        sa.Column("terminado_en", FECHA, nullable=True),
        sa.Column("duracion_s", sa.Double(), nullable=True),
        sa.Column("reproducibilidad", JSONB(), nullable=True),
        sa.Column("procedencia", JSONB(), nullable=True),
        sa.Column("evaluacion_prueba", JSONB(), nullable=True),
        sa.Column("reintento_de", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_experimento"),
        sa.ForeignKeyConstraint(["conjunto_id"], ["conjunto_datos.id"], name="fk_experimento_conjunto_id"),
        sa.ForeignKeyConstraint(["reintento_de"], ["experimento.id"], name="fk_experimento_reintento_de"),
        sa.CheckConstraint("origen IN ('web', 'importado')", name=op.f("ck_experimento_origen")),
        sa.CheckConstraint(
            "estado IN ('en_cola', 'en_curso', 'completado', 'fallido', 'interrumpido')",
            name=op.f("ck_experimento_estado"),
        ),
        sa.CheckConstraint(FORMATO_SHA256.format(c="sha256_datos"), name=op.f("ck_experimento_sha256_datos")),
        sa.CheckConstraint(
            "evaluacion_prueba IS NULL OR (origen = 'web' AND estado = 'completado' AND conjunto_id IS NOT NULL"
            " AND sha256_datos IS NOT NULL AND cohorte_prueba_clave IS NOT NULL)",
            name=op.f("ck_experimento_evaluacion_prueba"),
        ),
    )
    op.create_index(
        "uq_experimento_evaluacion_prueba",
        "experimento",
        ["sha256_datos", "cohorte_prueba_clave"],
        unique=True,
        postgresql_where=sa.text("evaluacion_prueba IS NOT NULL"),
    )
    op.create_table(
        "modelo",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("experimento_id", sa.Text(), nullable=False),
        sa.Column("momento", sa.Text(), nullable=True),
        sa.Column("familia", sa.Text(), nullable=False),
        sa.Column("ruta_paquete", sa.Text(), nullable=False),
        sa.Column("sha256_paquete", sa.String(64), nullable=False),
        sa.Column("umbral", sa.Double(), nullable=False),
        sa.Column("metodo_calibracion", sa.Text(), nullable=True),
        sa.Column("columnas", JSONB(), nullable=False),
        sa.Column("explicador", sa.Text(), nullable=False),
        sa.Column("evaluacion", JSONB(), nullable=False),
        sa.Column("explicacion_global", JSONB(), nullable=True),
        sa.Column("creado_en", FECHA, nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_modelo"),
        sa.ForeignKeyConstraint(["experimento_id"], ["experimento.id"], name="fk_modelo_experimento_id"),
        sa.CheckConstraint("explicador IN ('lineal', 'arbol', 'permutacion')", name=op.f("ck_modelo_explicador")),
    )
    op.create_table(
        "lote_prediccion",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("modelo_id", sa.Integer(), nullable=False),
        sa.Column("nombre_archivo", sa.Text(), nullable=False),
        sa.Column("ruta", sa.Text(), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("n_filas", sa.Integer(), nullable=False),
        sa.Column("columna_id", sa.Text(), nullable=True),
        sa.Column("columnas_ignoradas", JSONB(), nullable=False),
        sa.Column("umbral", sa.Double(), nullable=False),
        sa.Column("n_alertas", sa.Integer(), nullable=False),
        sa.Column("creado_en", FECHA, nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_lote_prediccion"),
        sa.ForeignKeyConstraint(["modelo_id"], ["modelo.id"], name="fk_lote_prediccion_modelo_id"),
    )
    op.create_table(
        "prediccion",
        sa.Column("lote_id", sa.Integer(), nullable=False),
        sa.Column("fila", sa.Integer(), nullable=False),
        sa.Column("identificador", sa.Text(), nullable=True),
        sa.Column("probabilidad", sa.Double(), nullable=False),
        sa.Column("alerta", sa.Boolean(), nullable=False),
        sa.Column("log_odds", sa.Double(), nullable=False),
        sa.Column("base_log_odds", sa.Double(), nullable=False),
        sa.Column("valores", JSONB(), nullable=False),
        sa.PrimaryKeyConstraint("lote_id", "fila", name="pk_prediccion"),
        sa.ForeignKeyConstraint(["lote_id"], ["lote_prediccion.id"], name="fk_prediccion_lote_id"),
    )
    op.create_table(
        "explicacion",
        sa.Column("lote_id", sa.Integer(), nullable=False),
        sa.Column("fila", sa.Integer(), nullable=False),
        sa.Column("contribuciones", JSONB(), nullable=False),
        sa.Column("explicador", sa.Text(), nullable=False),
        sa.Column("error_aditividad", sa.Double(), nullable=True),
        sa.Column("creado_en", FECHA, nullable=False),
        sa.PrimaryKeyConstraint("lote_id", "fila", name="pk_explicacion"),
        sa.ForeignKeyConstraint(
            ["lote_id", "fila"], ["prediccion.lote_id", "prediccion.fila"], name="fk_explicacion_prediccion"
        ),
        sa.CheckConstraint("explicador IN ('lineal', 'arbol', 'permutacion')", name=op.f("ck_explicacion_explicador")),
    )
    op.execute(FUNCION_EVALUACION_UNICA)
    op.execute(DISPARADOR_EVALUACION_UNICA)
    op.execute(FUNCION_MODELO_CONGELADO)
    op.execute(DISPARADOR_MODELO_CONGELADO)
    op.execute(FUNCION_CONJUNTO_INMUTABLE)
    op.execute(DISPARADOR_CONJUNTO_INMUTABLE)


def downgrade() -> None:
    op.execute("DROP TRIGGER conjunto_datos_inmutable ON conjunto_datos")
    op.execute("DROP FUNCTION conjunto_datos_inmutable()")
    op.execute("DROP TRIGGER modelo_evaluado_congelado ON modelo")
    op.execute("DROP FUNCTION modelo_evaluado_congelado()")
    op.execute("DROP TRIGGER evaluacion_prueba_unica ON experimento")
    op.execute("DROP FUNCTION evaluacion_prueba_unica()")
    for tabla in ("explicacion", "prediccion", "lote_prediccion", "modelo", "experimento", "conjunto_datos"):
        op.drop_table(tabla)
