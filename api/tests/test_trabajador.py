"""Trabajador y entrenamiento web (RF-03, RF-04 web, RNF-06; docs/diseno-api.md §5): entrenamiento síncrono con el
presupuesto «prueba», huérfanos, fallo sin modelo y la cohorte de prueba fuera de modelar."""

import io
import json
import re
from pathlib import Path

import joblib
import pandas as pd
import pytest

from api import trabajador
from api.servicios import entrenamiento
from api.tablas import Experimento, Modelo
from automl import motor
from test_configuracion import cuerpo, subir_conjunto, tabla


@pytest.fixture(autouse=True)
def sin_latido(monkeypatch):
    monkeypatch.setattr(trabajador, "LATIDO_S", 3600)  # las pruebas terminan antes del primer latido


def crear(cliente, **cambios) -> str:
    conjunto = subir_conjunto(cliente, tabla())
    r = cliente.post("/api/experimentos", json=cuerpo(conjunto, **cambios))
    assert r.status_code == 202, r.get_json()
    return r.get_json()["id"]


def procesar(app) -> str | None:
    with app.app_context():
        return trabajador.procesar_siguiente()


def test_entrenamiento_de_punta_a_punta(app, cliente, monkeypatch):
    vistos = {}
    modelar = motor.modelar

    def espia(X, y, *args, **kwargs):
        vistos["X"], vistos["y"] = X.copy(), y.copy()
        return modelar(X, y, *args, **kwargs)
    monkeypatch.setattr(motor, "modelar", espia)

    id_ = crear(cliente)
    # Lo que el trabajador registró al arrancar, no lo que diga git al terminar (RNF-06).
    app.config["CODIGO_TRABAJADOR"] = {"commit": "abc1234", "arbol_limpio": False}
    assert procesar(app) == id_ and procesar(app) is None
    e = cliente.get(f"/api/experimentos/{id_}").get_json()
    assert e["estado"] == "completado", e["error"]
    # rl, lgbm, referencias, apilamiento, comparación, modelo final, explicación global y equidad
    assert e["progreso"] == {"completadas": 8, "total": 8} and e["etapa"] is None and e["duracion_s"] >= 0
    assert e["reproducibilidad"]["commit"] == "abc1234" and e["reproducibilidad"]["arbol_limpio"] is False
    assert set(e["reproducibilidad"]["versiones"]) >= {"python", "scikit-learn", "shap", "flask", "sqlalchemy"}
    assert len(e["modelos"]) == 1

    # Anti-fuga: modelar solo recibe las filas de entrenamiento (sin la cohorte 2014J ni las filas sin objetivo).
    datos = tabla()
    entrenamiento_ = datos[datos["objetivo"].notna() & (datos["cohorte"] != "2014J")]
    assert vistos["X"]["x1"].tolist() == entrenamiento_["x1"].tolist()
    assert list(vistos["X"].columns) == ["x1", "x2", "nivel"]

    ev = cliente.get(f"/api/experimentos/{id_}/evaluacion").get_json()
    modelo = ev["modelos"][0]
    assert modelo["n"] == len(entrenamiento_) and modelo["contraste"]["holm_sobre"] == 1
    assert modelo["contraste"]["delong_p_holm"] == modelo["contraste"]["delong_p"]
    assert modelo["equidad"]["texto"].startswith("Las variables sensibles (sexo) no se usan para predecir")
    assert len(modelo["calibracion"]["curva"]["calibrada"]) > 0
    assert not re.search(r"\bD\d+|P-\d+", json.dumps(ev, ensure_ascii=False))

    carpeta = Path(app.config["PLATAFORMA_DATOS"]) / "experimentos" / id_
    assert {p.name for p in carpeta.iterdir()} == {"paquete.joblib", "oof.parquet", "prueba.parquet"}
    filas_prueba = pd.read_parquet(carpeta / "prueba.parquet")["fila"]
    assert (datos.iloc[filas_prueba - 1]["cohorte"] == "2014J").all()
    global_ = cliente.get(f"/api/modelos/{e['modelos'][0]['id']}/explicacion-global").get_json()
    assert global_["fuente"] == f"filas de entrenamiento (n = {len(entrenamiento_)})"


def test_categorica_escrita_como_numero_predice_igual(app, cliente):
    # «nivel» se entrenó como categórica ("1", "2", "A"); un lote donde solo trae 1, 2 y vacíos se lee como número y
    # debe predecir lo mismo que con los valores como texto (misma coerción al entrenar y al predecir).
    id_ = crear(cliente)
    procesar(app)
    with app.extensions["bd_sesiones"]() as sesion:
        modelo = sesion.query(Modelo).filter_by(experimento_id=id_).one()
    lote = tabla(40, semilla=5).drop(columns=["objetivo"])
    lote["nivel"] = ["1", "2", None, "2"] * 10
    contenido = lote.to_csv(index=False).encode()
    assert pd.read_csv(io.BytesIO(contenido))["nivel"].dtype == float  # el lote se lee como número (1.0, 2.0, NaN)
    r = cliente.post(f"/api/modelos/{modelo.id}/predicciones",
                     data={"archivo": (io.BytesIO(contenido), "lote.csv")}, content_type="multipart/form-data")
    assert r.status_code == 201, r.get_json()
    filas = cliente.get(f"/api/predicciones/{r.get_json()['lote_id']}").get_json()["filas"]
    paquete = joblib.load(Path(app.config["PLATAFORMA_DATOS"]) / "experimentos" / id_ / "paquete.joblib")
    X = lote[["x1", "x2", "nivel"]]
    X = X.assign(nivel=X["nivel"].where(X["nivel"].notna(), float("nan")))  # como al entrenar: texto y NaN
    assert [f["probabilidad"] for f in filas] == paquete["modelo"].predict_proba(X)[:, 1].tolist()


def test_fallo_deja_fallido_sin_modelo_ni_archivos(app, cliente):
    id_ = crear(cliente)
    conjuntos = Path(app.config["PLATAFORMA_DATOS"]) / "conjuntos"
    for archivo in conjuntos.glob("*.csv"):
        archivo.write_text("a,b\n1,2\n", encoding="utf-8")
    procesar(app)
    e = cliente.get(f"/api/experimentos/{id_}").get_json()
    assert e["estado"] == "fallido" and e["error"] == "El archivo del conjunto ha cambiado desde que se cargó."
    assert e["modelos"] == [] and e["terminado_en"] is not None
    carpeta = Path(app.config["PLATAFORMA_DATOS"]) / "experimentos" / id_
    assert [p.name for p in carpeta.iterdir()] == ["error.log"]
    assert cliente.get(f"/api/experimentos/{id_}/evaluacion").status_code == 409


def test_error_interno_no_muestra_detalles(app, cliente, monkeypatch):
    id_ = crear(cliente)

    def falla(*args, **kwargs):
        raise ValueError("Output feature names are not unique")  # ValueError de una biblioteca: no se reenvía
    monkeypatch.setattr(entrenamiento.motor, "modelar", falla)
    procesar(app)
    e = cliente.get(f"/api/experimentos/{id_}").get_json()
    assert e["estado"] == "fallido" and e["error"] == "El entrenamiento ha fallado por un error interno."


def test_huerfanos_pasan_a_interrumpido_y_cola_por_antiguedad(app, cliente):
    primero, segundo = crear(cliente), crear(cliente)
    with app.extensions["bd_sesiones"]() as sesion:
        sesion.add(Experimento(id="web-2099-01-01-01", origen="web", configuracion={}, estado="en_curso"))
        sesion.commit()
    with app.app_context():
        assert trabajador.recuperar_huerfanos() == 1
        assert trabajador.tomar() == primero and trabajador.tomar() == segundo and trabajador.tomar() is None
    huerfano = cliente.get("/api/experimentos/web-2099-01-01-01").get_json()
    assert huerfano["estado"] == "interrumpido" and huerfano["error"].startswith("El proceso de entrenamiento se detuvo")
    en_curso = cliente.get(f"/api/experimentos/{primero}").get_json()
    assert en_curso["estado"] == "en_curso" and en_curso["iniciado_en"] and en_curso["sin_respuesta"] is False


@pytest.mark.postgres
def test_un_solo_trabajador(app_postgres, motor_postgres):
    from sqlalchemy import func, select

    from api.bd import BLOQUEO_TRABAJADOR
    with motor_postgres.connect() as otro:  # otro trabajador ya en marcha
        assert otro.execute(select(func.pg_try_advisory_lock(BLOQUEO_TRABAJADOR))).scalar_one()
        resultado = app_postgres.test_cli_runner().invoke(args=["trabajador"])
        assert resultado.exit_code == 1 and "Ya hay un proceso de entrenamiento en marcha." in resultado.output
        otro.execute(select(func.pg_advisory_unlock(BLOQUEO_TRABAJADOR)))
