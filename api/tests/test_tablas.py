"""Modelo de datos (docs/diseno-api.md §3), evaluación única en la cohorte de prueba (matiz D-2) y migración 0001.

Las pruebas de D-2 se ejecutan con SQLite (tablas.py y sus disparadores) y con PostgreSQL (migración 0001)."""

import re

import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import CheckConstraint, delete, func, insert, inspect, select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from api.tablas import (
    MENSAJE_CONJUNTO_INMUTABLE,
    MENSAJE_DATOS_DISTINTOS,
    MENSAJE_EVALUACION_UNICA,
    MENSAJE_EVALUADO_CONGELADO,
    MENSAJE_ID_INMUTABLE,
    Base,
    ConjuntoDatos,
    Experimento,
    Modelo,
    clave_cohorte,
)

TABLAS = {"conjunto_datos", "experimento", "modelo", "lote_prediccion", "prediccion", "explicacion"}
SHA_DATOS = "a" * 64
COHORTE = {"modo": "valores", "columna": "code_presentation", "valores": ["2014J"]}
EVALUACION = {"roc_auc": 0.7, "fecha": "2026-11-03"}
# Violación del índice único parcial: mensaje de PostgreSQL (nombre del índice) o de SQLite (columnas del índice).
INDICE_UNICO = (r"uq_experimento_evaluacion_prueba|"
                r"UNIQUE constraint failed: experimento\.sha256_datos, experimento\.cohorte_prueba_clave")


@pytest.fixture(params=["sqlite", pytest.param("postgresql", marks=pytest.mark.postgres)])
def motor(request):
    """Motor de SQLite en memoria (create_all) o del PostgreSQL de pruebas (migración 0001)."""
    app = request.getfixturevalue("app" if request.param == "sqlite" else "app_postgres")
    return app.extensions["bd_motor"]


def _conjunto(s: Session, sha256: str = SHA_DATOS) -> int:
    c = ConjuntoDatos(nombre_archivo="datos.csv", ruta="conjuntos/x.csv", sha256=sha256, n_filas=10, n_columnas=3,
                      columnas=[], avisos=[])
    s.add(c)
    s.flush()
    return c.id


def _experimento(s: Session, id_: str, conjunto_id: int, cohorte: dict = COHORTE, sha256_datos: str | None = None) -> None:
    """Experimento web completado; sha256_datos se copia del conjunto, como hará POST /api/experimentos."""
    s.add(Experimento(id=id_, origen="web", conjunto_id=conjunto_id,
                      sha256_datos=sha256_datos or s.get(ConjuntoDatos, conjunto_id).sha256,
                      cohorte_prueba_clave=clave_cohorte(cohorte), configuracion={"cohorte_prueba": cohorte},
                      estado="completado"))
    s.flush()


def _evaluar(s: Session, id_: str) -> None:
    s.execute(update(Experimento).where(Experimento.id == id_).values(evaluacion_prueba=EVALUACION))
    s.commit()


MODELO = {"familia": "rl", "ruta_paquete": "p.joblib", "sha256_paquete": "b" * 64, "umbral": 0.3, "columnas": {},
          "explicador": "lineal", "evaluacion": {}}


def _modelo(s: Session, experimento_id: str) -> None:
    s.add(Modelo(experimento_id=experimento_id, **MODELO))
    s.flush()


def _rechaza(s: Session, sentencia, mensaje: str) -> None:
    with pytest.raises(IntegrityError, match=re.escape(mensaje)):
        s.execute(sentencia)
    s.rollback()


def test_crea_las_6_tablas(app):
    assert set(inspect(app.extensions["bd_motor"]).get_table_names()) == TABLAS


def test_json_none_se_guarda_como_null_de_sql(app):
    motor = app.extensions["bd_motor"]
    with Session(motor) as s:
        s.add(Experimento(id="web-2026-11-03-01", origen="web", configuracion={}, evaluacion_prueba=None))
        s.commit()
        assert s.scalar(text("SELECT evaluacion_prueba IS NULL FROM experimento")) == 1
        assert s.scalar(select(Experimento.estado)) == "en_cola"


def test_estado_y_origen_restringidos(app):
    with Session(app.extensions["bd_motor"]) as s:
        s.add(Experimento(id="a", origen="web", configuracion={}, estado="pausado"))
        with pytest.raises(IntegrityError):
            s.commit()
        s.rollback()
        s.add(Experimento(id="b", origen="otro", configuracion={}))
        with pytest.raises(IntegrityError):
            s.commit()


def test_clave_cohorte_canonica():
    base = clave_cohorte({"modo": "valores", "columna": "c", "valores": ["2014J", "2014B"]})
    # El orden de claves y de valores y los campos descriptivos no cambian la definición.
    assert clave_cohorte({"valores": ["2014B", "2014J"], "columna": "c", "modo": "valores", "filas": 7,
                          "metodo": "filas cuyo valor está en la lista"}) == base
    assert clave_cohorte({"modo": "valores", "columna": "c", "valores": ["2014J"]}) != base
    assert re.fullmatch(r"[0-9a-f]{64}", base)
    # Valores normalizados: sin repetidos y como texto.
    assert (clave_cohorte({"modo": "valores", "columna": "c", "valores": ["2014J"]})
            == clave_cohorte({"modo": "valores", "columna": "c", "valores": ["2014J", "2014J"]}))
    assert (clave_cohorte({"modo": "valores", "columna": "c", "valores": [2014]})
            == clave_cohorte({"modo": "valores", "columna": "c", "valores": ["2014"]}))
    # La semilla no forma parte de la clave en ningún modo.
    assert (clave_cohorte({"modo": "valores", "columna": "c", "valores": ["2014J"], "semilla": None})
            == clave_cohorte({"modo": "valores", "columna": "c", "valores": ["2014J"], "semilla": 42}))
    assert clave_cohorte({"modo": "aleatoria", "semilla": 42}) == clave_cohorte({"modo": "aleatoria", "semilla": 43})
    assert clave_cohorte({"modo": "aleatoria", "semilla": 42}) != base


def test_evaluacion_prueba_no_se_repite_ni_se_borra(motor):
    with Session(motor) as s:
        _experimento(s, "web-2026-11-03-01", _conjunto(s))
        _evaluar(s, "web-2026-11-03-01")
        for sentencia in (
            update(Experimento).values(evaluacion_prueba={"roc_auc": 0.9}),
            update(Experimento).values(evaluacion_prueba=None),
            delete(Experimento),
        ):
            _rechaza(s, sentencia, MENSAJE_EVALUACION_UNICA)
        # El resto del experimento sigue pudiendo actualizarse.
        s.execute(update(Experimento).values(descripcion="otra"))
        s.commit()
        assert s.scalar(select(Experimento.evaluacion_prueba)) == EVALUACION


def test_evaluacion_prueba_solo_en_experimento_web_completado_con_datos_y_cohorte(motor):
    with Session(motor) as s:
        conjunto = _conjunto(s)
        s.commit()
        identificados = {"conjunto_id": conjunto, "sha256_datos": SHA_DATOS, "cohorte_prueba_clave": clave_cohorte(COHORTE)}
        for origen, estado, claves in (
            ("importado", "completado", identificados),
            ("web", "en_curso", identificados),
            ("web", "completado", dict(identificados, conjunto_id=None)),
            ("web", "completado", dict(identificados, sha256_datos=None)),
            ("web", "completado", dict(identificados, cohorte_prueba_clave=None)),
        ):
            s.add(Experimento(id=f"x-{origen}-{estado}", origen=origen, configuracion={}, estado=estado,
                              evaluacion_prueba=EVALUACION, **claves))
            with pytest.raises(IntegrityError, match="ck_experimento_evaluacion_prueba"):
                s.commit()
            s.rollback()


def test_id_del_experimento_no_cambia(motor):
    """Renombrar un experimento evaluado permitiría saltarse D-2; el id no cambia nunca, evaluado o no."""
    with Session(motor) as s:
        conjunto = _conjunto(s)
        _experimento(s, "web-2026-11-03-01", conjunto)
        _experimento(s, "web-2026-11-03-02", conjunto, {"modo": "aleatoria", "semilla": 42})
        _evaluar(s, "web-2026-11-03-01")
        for id_ in ("web-2026-11-03-01", "web-2026-11-03-02"):
            _rechaza(s, update(Experimento).where(Experimento.id == id_).values(id="otro"), MENSAJE_ID_INMUTABLE)
        assert set(s.scalars(select(Experimento.id))) == {"web-2026-11-03-01", "web-2026-11-03-02"}


def test_lo_evaluado_queda_congelado(motor):
    with Session(motor) as s:
        conjunto = _conjunto(s)
        _experimento(s, "evaluado", conjunto)
        _experimento(s, "sin_evaluar", conjunto, {"modo": "aleatoria", "semilla": 42})
        _modelo(s, "evaluado")
        _modelo(s, "sin_evaluar")
        # Antes de evaluar, todo se puede cambiar.
        s.execute(update(Experimento).where(Experimento.id == "evaluado").values(configuracion={"cohorte_prueba": COHORTE, "n": 1}))
        s.execute(update(Modelo).where(Modelo.experimento_id == "evaluado").values(umbral=0.4))
        _evaluar(s, "evaluado")

        del_evaluado = Experimento.id == "evaluado"
        otro_conjunto = _conjunto(s)  # mismo SHA-256: solo cambia conjunto_id
        s.commit()
        for valores in ({"configuracion": {}}, {"conjunto_id": otro_conjunto}, {"sha256_datos": "c" * 64},
                        {"cohorte_prueba_clave": "d" * 64}):
            _rechaza(s, update(Experimento).where(del_evaluado).values(**valores), MENSAJE_EVALUADO_CONGELADO)
        modelo_evaluado = Modelo.experimento_id == "evaluado"
        _rechaza(s, update(Modelo).where(modelo_evaluado).values(umbral=0.5), MENSAJE_EVALUADO_CONGELADO)
        _rechaza(s, delete(Modelo).where(modelo_evaluado), MENSAJE_EVALUADO_CONGELADO)
        # Tampoco se le añade un modelo nuevo ni se trae uno de otro experimento.
        _rechaza(s, insert(Modelo).values(experimento_id="evaluado", **MODELO), MENSAJE_EVALUADO_CONGELADO)
        _rechaza(s, update(Modelo).where(Modelo.experimento_id == "sin_evaluar").values(experimento_id="evaluado"),
                 MENSAJE_EVALUADO_CONGELADO)
        assert s.scalar(select(Experimento.conjunto_id).where(del_evaluado)) == conjunto
        assert s.scalar(select(func.count()).select_from(Modelo).where(modelo_evaluado)) == 1

        # Los modelos y la configuración de otro experimento sin evaluar siguen libres.
        s.execute(update(Experimento).where(Experimento.id == "sin_evaluar").values(configuracion={}))
        s.execute(update(Modelo).where(Modelo.experimento_id == "sin_evaluar").values(umbral=0.5))
        s.execute(delete(Modelo).where(Modelo.experimento_id == "sin_evaluar"))
        s.commit()
        assert s.scalar(select(Modelo.umbral).where(modelo_evaluado)) == 0.4
        assert s.scalar(select(Experimento.configuracion).where(del_evaluado)) == {"cohorte_prueba": COHORTE, "n": 1}


def test_una_sola_evaluacion_por_datos_y_cohorte(motor):
    """El mismo CSV subido dos veces (dos conjunto_datos con el mismo SHA-256) no permite una segunda evaluación con la
    misma cohorte; con otra definición de cohorte sí."""
    with Session(motor) as s:
        primero, segundo = _conjunto(s), _conjunto(s)
        _experimento(s, "web-2026-11-03-01", primero)
        _experimento(s, "web-2026-11-03-02", segundo)
        _experimento(s, "web-2026-11-03-03", segundo, {"modo": "valores", "columna": "code_presentation",
                                                      "valores": ["2014J", "2014B"]})
        s.commit()
        _evaluar(s, "web-2026-11-03-01")
        with pytest.raises(IntegrityError, match=INDICE_UNICO):
            _evaluar(s, "web-2026-11-03-02")
        s.rollback()
        _evaluar(s, "web-2026-11-03-03")
        evaluados = s.scalars(select(Experimento.id).where(Experimento.evaluacion_prueba.is_not(None)))
        assert set(evaluados) == {"web-2026-11-03-01", "web-2026-11-03-03"}


def test_una_sola_evaluacion_aleatoria_por_datos(motor):
    """Otra semilla daría una cohorte aleatoria que comparte filas con la evaluada: la clave no la incluye."""
    with Session(motor) as s:
        primero, segundo = _conjunto(s), _conjunto(s)
        _experimento(s, "web-2026-11-03-01", primero, {"modo": "aleatoria", "semilla": 42})
        _experimento(s, "web-2026-11-03-02", segundo, {"modo": "aleatoria", "semilla": 7})
        s.commit()
        _evaluar(s, "web-2026-11-03-01")
        with pytest.raises(IntegrityError, match=INDICE_UNICO):
            _evaluar(s, "web-2026-11-03-02")


def test_sha256_en_formato_canonico(motor):
    """64 caracteres hexadecimales en minúsculas en conjunto_datos.sha256 y experimento.sha256_datos."""
    with Session(motor) as s:
        conjunto = _conjunto(s)
        s.commit()
        for malo in ("A" * 64, "a" * 63, "g" * 64):  # con 65, PostgreSQL ya lo rechaza por varchar(64)
            _rechaza(s, insert(ConjuntoDatos).values(nombre_archivo="d.csv", ruta="r", sha256=malo, n_filas=1,
                                                     n_columnas=1, columnas=[], avisos=[]), "ck_conjunto_datos_sha256")
            _rechaza(s, insert(Experimento).values(id="x", origen="web", conjunto_id=conjunto, sha256_datos=malo,
                                                   configuracion={}, estado="en_cola"), "ck_experimento_sha256_datos")


def test_evaluar_exige_el_sha256_de_su_conjunto(motor):
    with Session(motor) as s:
        conjunto = _conjunto(s)
        _experimento(s, "web-2026-11-03-01", conjunto, sha256_datos="c" * 64)
        s.commit()
        _rechaza(s, update(Experimento).values(evaluacion_prueba=EVALUACION), MENSAJE_DATOS_DISTINTOS)
        # Tampoco creándolo ya evaluado.
        _rechaza(s, insert(Experimento).values(id="web-2026-11-03-02", origen="web", conjunto_id=conjunto,
                                               sha256_datos="c" * 64, cohorte_prueba_clave=clave_cohorte(COHORTE),
                                               configuracion={}, estado="completado", evaluacion_prueba=EVALUACION),
                 MENSAJE_DATOS_DISTINTOS)
        assert s.scalar(select(Experimento.evaluacion_prueba)) is None


def test_ruta_y_sha256_del_conjunto_no_cambian(motor):
    with Session(motor) as s:
        _conjunto(s)
        s.commit()
        for valores in ({"sha256": "c" * 64}, {"ruta": "conjuntos/otro.csv"}):
            _rechaza(s, update(ConjuntoDatos).values(**valores), MENSAJE_CONJUNTO_INMUTABLE)
        s.execute(update(ConjuntoDatos).values(nombre_archivo="otro.csv", momento="semana 4"))
        s.commit()
        assert s.scalar(select(ConjuntoDatos.sha256)) == SHA_DATOS


def test_mismo_conjunto_con_hash_alterado_no_da_otra_evaluacion(motor):
    """Escenario de la revisión: un segundo experimento sobre el mismo conjunto, con sha256_datos alterado para no
    coincidir en el índice, y una segunda evaluación con la misma cohorte."""
    with Session(motor) as s:
        conjunto = _conjunto(s)
        _experimento(s, "web-2026-11-03-01", conjunto)
        s.commit()
        _evaluar(s, "web-2026-11-03-01")
        # En mayúsculas: lo rechaza el CHECK de formato al crearlo.
        with pytest.raises(IntegrityError, match="ck_experimento_sha256_datos"):
            _experimento(s, "web-2026-11-03-02", conjunto, sha256_datos=SHA_DATOS.upper())
        s.rollback()
        # Otro hash en minúsculas: se crea, pero no se puede evaluar.
        _experimento(s, "web-2026-11-03-02", conjunto, sha256_datos="c" * 64)
        s.commit()
        _rechaza(s, update(Experimento).where(Experimento.id == "web-2026-11-03-02").values(evaluacion_prueba=EVALUACION),
                 MENSAJE_DATOS_DISTINTOS)
        # Ni alterando el SHA-256 del conjunto.
        _rechaza(s, update(ConjuntoDatos).values(sha256="c" * 64), MENSAJE_CONJUNTO_INMUTABLE)
        evaluados = s.scalars(select(Experimento.id).where(Experimento.evaluacion_prueba.is_not(None)))
        assert set(evaluados) == {"web-2026-11-03-01"}


@pytest.mark.postgres
def test_migracion_0001_coincide_con_tablas(motor_postgres):
    with motor_postgres.connect() as conexion:
        diferencias = compare_metadata(MigrationContext.configure(conexion), Base.metadata)
    assert diferencias == []


@pytest.mark.postgres
def test_migracion_0001_crea_check_disparadores_e_indice_parcial(motor_postgres):
    """compare_metadata no compara CHECK ni disparadores: se buscan en el catálogo de PostgreSQL."""
    esperadas = {c.name for t in Base.metadata.tables.values() for c in t.constraints if isinstance(c, CheckConstraint)}
    with motor_postgres.connect() as conexion:
        checks = set(conexion.scalars(text(
            "SELECT c.conname FROM pg_constraint c JOIN pg_namespace n ON n.oid = c.connamespace"
            " WHERE c.contype = 'c' AND n.nspname = current_schema()"
        )))
        disparadores = {tuple(f) for f in conexion.execute(text(
            "SELECT tgrelid::regclass::text, tgname FROM pg_trigger WHERE NOT tgisinternal"
        ))}
        indice = conexion.scalar(text(
            "SELECT indexdef FROM pg_indexes"
            " WHERE schemaname = current_schema() AND indexname = 'uq_experimento_evaluacion_prueba'"
        ))
    assert checks == esperadas
    assert disparadores == {("experimento", "evaluacion_prueba_unica"), ("modelo", "modelo_evaluado_congelado"),
                            ("conjunto_datos", "conjunto_datos_inmutable")}
    assert indice is not None
    assert indice.startswith("CREATE UNIQUE INDEX")
    assert "(sha256_datos, cohorte_prueba_clave) WHERE (evaluacion_prueba IS NOT NULL)" in indice
