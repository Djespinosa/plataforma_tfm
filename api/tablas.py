"""Las 6 tablas de la plataforma (docs/diseno-api.md §3). El esquema de PostgreSQL lo crean las migraciones de Alembic
(api/migraciones); create_all solo se usa con el SQLite de las pruebas unitarias."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime

from sqlalchemy import (
    DDL,
    Boolean,
    CheckConstraint,
    DateTime,
    Double,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    event,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from api.bd import JSONB_, Base
from automl.validacion import normalizar_valor

ESTADOS = ("en_cola", "en_curso", "completado", "fallido", "interrumpido")
ORIGENES = ("web", "importado")
EXPLICADORES = ("lineal", "arbol", "permutacion")

# Evaluación única en la cohorte de prueba (matiz D-2 del estudiante), impuesta en la base de datos:
# - una vez guardada, no se puede cambiar ni anular, ni borrar su experimento;
# - tras evaluar, no cambian configuracion, conjunto_id, sha256_datos ni cohorte_prueba_clave del experimento, y no se
#   puede cambiar ni borrar ningún modelo suyo, ni añadirle uno nuevo o traído de otro experimento;
# - para evaluar, sha256_datos debe ser el SHA-256 de su conjunto_datos; la ruta y el SHA-256 de un conjunto_datos no
#   cambian nunca; los SHA-256 de los datos son 64 caracteres hexadecimales en minúsculas;
# - el id de un experimento no cambia nunca (si no, renombrarlo permitiría saltarse lo anterior);
# - una sola evaluación por (SHA-256 de los datos, clave_cohorte): volver a subir el mismo CSV no permite otra con la
#   misma cohorte (índice único parcial). No se impiden cohortes distintas que se solapan (docs/diseno-api.md §3).
# Los disparadores de PostgreSQL están en la migración 0001_inicial; los de abajo son su equivalente en SQLite.
MENSAJE_EVALUACION_UNICA = "La evaluación en la cohorte de prueba ya se hizo; se usa una sola vez."
MENSAJE_EVALUADO_CONGELADO = (
    "El experimento ya se evaluó en la cohorte de prueba; su configuración y sus modelos no se pueden cambiar."
)
MENSAJE_ID_INMUTABLE = "El identificador de un experimento no cambia nunca."
MENSAJE_DATOS_DISTINTOS = (
    "El SHA-256 de los datos del experimento no coincide con el de su conjunto de datos; no se puede evaluar en la "
    "cohorte de prueba."
)
MENSAJE_CONJUNTO_INMUTABLE = "La ruta y el SHA-256 de un conjunto de datos no cambian nunca."


def _ahora() -> datetime:
    return datetime.now(UTC)


def _lista(valores: tuple[str, ...]) -> str:
    return ", ".join(f"'{v}'" for v in valores)


def _formato_sha256(columna: str) -> str:
    """CHECK de 64 caracteres hexadecimales en minúsculas; la misma expresión vale en PostgreSQL y en SQLite."""
    return f"length({columna}) = 64 AND trim({columna}, '0123456789abcdef') = ''"


def clave_cohorte(cohorte: dict) -> str:
    """SHA-256 de la definición canónica de la cohorte de prueba (experimento.cohorte_prueba_clave).

    Modo «valores»: columna y conjunto de valores como texto normalizado (validacion.normalizar_valor, el mismo con que
    reservar_prueba elige las filas: 2014 y 2014.0 dan la misma clave), sin repetidos y ordenados. Modo «aleatoria»: solo el modo
    (decisión del estudiante): otra semilla daría una cohorte que comparte filas con la ya evaluada, así que hay una sola
    evaluación aleatoria por datos. «semilla», «filas» y «metodo» no forman parte de la clave."""
    if cohorte["modo"] == "aleatoria":
        definicion = {"modo": "aleatoria"}
    else:
        definicion = {
            "modo": cohorte["modo"],
            "columna": cohorte.get("columna"),
            "valores": sorted(set(map(normalizar_valor, cohorte.get("valores") or []))),
        }
    canonica = json.dumps(definicion, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canonica.encode("utf-8")).hexdigest()


class ConjuntoDatos(Base):
    __tablename__ = "conjunto_datos"
    __table_args__ = (CheckConstraint(_formato_sha256("sha256"), name="sha256"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nombre_archivo: Mapped[str] = mapped_column(Text)
    momento: Mapped[str | None] = mapped_column(Text)
    ruta: Mapped[str] = mapped_column(Text)
    sha256: Mapped[str] = mapped_column(String(64))
    n_filas: Mapped[int] = mapped_column(Integer)
    n_columnas: Mapped[int] = mapped_column(Integer)
    columnas: Mapped[list] = mapped_column(JSONB_)
    avisos: Mapped[list] = mapped_column(JSONB_)
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_ahora)


class Experimento(Base):
    __tablename__ = "experimento"
    __table_args__ = (
        CheckConstraint(f"origen IN ({_lista(ORIGENES)})", name="origen"),
        CheckConstraint(f"estado IN ({_lista(ESTADOS)})", name="estado"),
        CheckConstraint(_formato_sha256("sha256_datos"), name="sha256_datos"),
        # Solo un experimento web terminado puede tener evaluación en prueba (los importados nunca), y con el conjunto,
        # los datos y la cohorte identificados (un NULL en el índice único parcial lo dejaría sin efecto).
        CheckConstraint(
            "evaluacion_prueba IS NULL OR (origen = 'web' AND estado = 'completado' AND conjunto_id IS NOT NULL"
            " AND sha256_datos IS NOT NULL AND cohorte_prueba_clave IS NOT NULL)",
            name="evaluacion_prueba",
        ),
        Index(
            "uq_experimento_evaluacion_prueba",
            "sha256_datos",
            "cohorte_prueba_clave",
            unique=True,
            postgresql_where=text("evaluacion_prueba IS NOT NULL"),
            sqlite_where=text("evaluacion_prueba IS NOT NULL"),
        ),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    origen: Mapped[str] = mapped_column(Text)
    conjunto_id: Mapped[int | None] = mapped_column(ForeignKey("conjunto_datos.id"))
    sha256_datos: Mapped[str | None] = mapped_column(String(64))  # copia de conjunto_datos.sha256 al crearlo
    cohorte_prueba_clave: Mapped[str | None] = mapped_column(String(64))  # clave_cohorte(); NULL sin cohorte
    descripcion: Mapped[str | None] = mapped_column(Text)
    configuracion: Mapped[dict] = mapped_column(JSONB_)
    estado: Mapped[str] = mapped_column(Text, default="en_cola")
    etapa: Mapped[str | None] = mapped_column(Text)
    progreso: Mapped[dict | None] = mapped_column(JSONB_)
    error: Mapped[str | None] = mapped_column(Text)
    latido_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_ahora)
    iniciado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    terminado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    duracion_s: Mapped[float | None] = mapped_column(Double)
    reproducibilidad: Mapped[dict | None] = mapped_column(JSONB_)
    procedencia: Mapped[dict | None] = mapped_column(JSONB_)
    evaluacion_prueba: Mapped[dict | None] = mapped_column(JSONB_)
    reintento_de: Mapped[str | None] = mapped_column(ForeignKey("experimento.id"))


class Modelo(Base):
    __tablename__ = "modelo"
    __table_args__ = (CheckConstraint(f"explicador IN ({_lista(EXPLICADORES)})", name="explicador"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    experimento_id: Mapped[str] = mapped_column(ForeignKey("experimento.id"))
    momento: Mapped[str | None] = mapped_column(Text)
    familia: Mapped[str] = mapped_column(Text)
    ruta_paquete: Mapped[str] = mapped_column(Text)
    sha256_paquete: Mapped[str] = mapped_column(String(64))
    umbral: Mapped[float] = mapped_column(Double)
    metodo_calibracion: Mapped[str | None] = mapped_column(Text)
    columnas: Mapped[dict] = mapped_column(JSONB_)
    explicador: Mapped[str] = mapped_column(Text)
    evaluacion: Mapped[dict] = mapped_column(JSONB_)
    explicacion_global: Mapped[dict | None] = mapped_column(JSONB_)
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_ahora)


class LotePrediccion(Base):
    __tablename__ = "lote_prediccion"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    modelo_id: Mapped[int] = mapped_column(ForeignKey("modelo.id"))
    nombre_archivo: Mapped[str] = mapped_column(Text)
    ruta: Mapped[str] = mapped_column(Text)
    sha256: Mapped[str] = mapped_column(String(64))
    n_filas: Mapped[int] = mapped_column(Integer)
    columna_id: Mapped[str | None] = mapped_column(Text)
    columnas_ignoradas: Mapped[list] = mapped_column(JSONB_)
    umbral: Mapped[float] = mapped_column(Double)
    n_alertas: Mapped[int] = mapped_column(Integer)
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_ahora)


class Prediccion(Base):
    __tablename__ = "prediccion"

    lote_id: Mapped[int] = mapped_column(ForeignKey("lote_prediccion.id"), primary_key=True)
    fila: Mapped[int] = mapped_column(Integer, primary_key=True)  # posición 1..n en el CSV
    identificador: Mapped[str | None] = mapped_column(Text)
    probabilidad: Mapped[float] = mapped_column(Double)
    alerta: Mapped[bool] = mapped_column(Boolean)
    log_odds: Mapped[float] = mapped_column(Double)
    base_log_odds: Mapped[float] = mapped_column(Double)
    valores: Mapped[dict] = mapped_column(JSONB_)


class Explicacion(Base):
    __tablename__ = "explicacion"
    __table_args__ = (
        ForeignKeyConstraint(
            ["lote_id", "fila"], ["prediccion.lote_id", "prediccion.fila"], name="fk_explicacion_prediccion"
        ),
        CheckConstraint(f"explicador IN ({_lista(EXPLICADORES)})", name="explicador"),
    )

    lote_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    fila: Mapped[int] = mapped_column(Integer, primary_key=True)
    contribuciones: Mapped[dict] = mapped_column(JSONB_)
    explicador: Mapped[str] = mapped_column(Text)
    error_aditividad: Mapped[float | None] = mapped_column(Double)
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_ahora)


def _evaluado(fila: str) -> str:
    return f"EXISTS (SELECT 1 FROM experimento WHERE id = {fila}.experimento_id AND evaluacion_prueba IS NOT NULL)"


# Con sha256_datos o conjunto_id NULL, «<>» no es cierto y quien rechaza es el CHECK evaluacion_prueba.
_DATOS_DISTINTOS = ("NEW.evaluacion_prueba IS NOT NULL"
                    " AND NEW.sha256_datos <> (SELECT sha256 FROM conjunto_datos WHERE id = NEW.conjunto_id)")
for _tabla, _ddl in (
    (Experimento, f"""CREATE TRIGGER experimento_id_inmutable BEFORE UPDATE OF id ON experimento
        WHEN NEW.id IS NOT OLD.id
        BEGIN SELECT RAISE(ABORT, '{MENSAJE_ID_INMUTABLE}'); END"""),
    (Experimento, f"""CREATE TRIGGER evaluacion_prueba_unica_cambio BEFORE UPDATE OF evaluacion_prueba ON experimento
        WHEN OLD.evaluacion_prueba IS NOT NULL AND NEW.evaluacion_prueba IS NOT OLD.evaluacion_prueba
        BEGIN SELECT RAISE(ABORT, '{MENSAJE_EVALUACION_UNICA}'); END"""),
    (Experimento, f"""CREATE TRIGGER evaluacion_prueba_unica_borrado BEFORE DELETE ON experimento
        WHEN OLD.evaluacion_prueba IS NOT NULL
        BEGIN SELECT RAISE(ABORT, '{MENSAJE_EVALUACION_UNICA}'); END"""),
    (Experimento, f"""CREATE TRIGGER experimento_evaluado_congelado
        BEFORE UPDATE OF configuracion, conjunto_id, sha256_datos, cohorte_prueba_clave ON experimento
        WHEN OLD.evaluacion_prueba IS NOT NULL AND (NEW.configuracion IS NOT OLD.configuracion
            OR NEW.conjunto_id IS NOT OLD.conjunto_id OR NEW.sha256_datos IS NOT OLD.sha256_datos
            OR NEW.cohorte_prueba_clave IS NOT OLD.cohorte_prueba_clave)
        BEGIN SELECT RAISE(ABORT, '{MENSAJE_EVALUADO_CONGELADO}'); END"""),
    (Experimento, f"""CREATE TRIGGER evaluacion_prueba_datos_alta BEFORE INSERT ON experimento
        WHEN {_DATOS_DISTINTOS}
        BEGIN SELECT RAISE(ABORT, '{MENSAJE_DATOS_DISTINTOS}'); END"""),
    (Experimento, f"""CREATE TRIGGER evaluacion_prueba_datos_cambio BEFORE UPDATE ON experimento
        WHEN OLD.evaluacion_prueba IS NULL AND {_DATOS_DISTINTOS}
        BEGIN SELECT RAISE(ABORT, '{MENSAJE_DATOS_DISTINTOS}'); END"""),
    (Modelo, f"""CREATE TRIGGER modelo_evaluado_congelado_cambio BEFORE UPDATE ON modelo WHEN {_evaluado("OLD")}
        BEGIN SELECT RAISE(ABORT, '{MENSAJE_EVALUADO_CONGELADO}'); END"""),
    (Modelo, f"""CREATE TRIGGER modelo_evaluado_congelado_borrado BEFORE DELETE ON modelo WHEN {_evaluado("OLD")}
        BEGIN SELECT RAISE(ABORT, '{MENSAJE_EVALUADO_CONGELADO}'); END"""),
    (Modelo, f"""CREATE TRIGGER modelo_evaluado_congelado_alta BEFORE INSERT ON modelo WHEN {_evaluado("NEW")}
        BEGIN SELECT RAISE(ABORT, '{MENSAJE_EVALUADO_CONGELADO}'); END"""),
    (Modelo, f"""CREATE TRIGGER modelo_evaluado_congelado_traslado BEFORE UPDATE OF experimento_id ON modelo
        WHEN {_evaluado("NEW")}
        BEGIN SELECT RAISE(ABORT, '{MENSAJE_EVALUADO_CONGELADO}'); END"""),
    (ConjuntoDatos, f"""CREATE TRIGGER conjunto_datos_inmutable BEFORE UPDATE OF ruta, sha256 ON conjunto_datos
        WHEN NEW.ruta IS NOT OLD.ruta OR NEW.sha256 IS NOT OLD.sha256
        BEGIN SELECT RAISE(ABORT, '{MENSAJE_CONJUNTO_INMUTABLE}'); END"""),
):
    event.listen(_tabla.__table__, "after_create", DDL(_ddl).execute_if(dialect="sqlite"))
