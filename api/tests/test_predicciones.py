"""Predicción (RF-05) y explicaciones (RF-06), docs/diseno-api.md §4.4 y §4.5, con los paquetes sintéticos del importador
(RL en el formato de modelo_final) y un bosque aleatorio preparado con automl.explicacion (permutación)."""

import io
import json
import re
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import pytest

import modelo_final
from api.servicios import explicaciones
from api.tablas import Experimento, Explicacion, LotePrediccion, Modelo
from automl import busqueda, explicacion, motor
from evidencias import sha256
from test_importar import COLUMNAS, FINAL, datos, entorno, importar_en, paquete_sintetico  # noqa: F401 (fixture)


def subir(cliente, modelo_id: int, tabla: pd.DataFrame, **campos):
    contenido = tabla.to_csv(index=False).encode("utf-8")
    return cliente.post(f"/api/modelos/{modelo_id}/predicciones",
                        data={"archivo": (io.BytesIO(contenido), "lote.csv"), **campos},
                        content_type="multipart/form-data")


def tabla_lote(n: int = 40) -> pd.DataFrame:
    X, y = datos(n, semilla=7)
    X.loc[3, "x2"] = np.nan
    return pd.concat([pd.DataFrame({"matricula": [f"A-{i}" for i in range(n)]}), X, y.rename("objetivo")], axis=1)


def modelo_semana(app, momento: str) -> Modelo:
    with app.extensions["bd_sesiones"]() as sesion:
        return sesion.query(Modelo).filter_by(momento=momento).one()


@pytest.fixture
def importados(app, entorno):  # noqa: F811
    importar_en(app, entorno)
    return entorno


def test_prediccion_lineal_igual_que_predecir_y_explicar(app, cliente, importados):
    modelo = modelo_semana(app, "semana 4")
    tabla = tabla_lote()
    r = subir(cliente, modelo.id, tabla, columna_id="matricula")
    assert r.status_code == 201, r.get_json()
    cuerpo = r.get_json()
    assert cuerpo["n_filas"] == 40 and cuerpo["explicaciones"] == "completas"
    assert cuerpo["columnas_ignoradas"] == ["objetivo"]  # la columna objetivo se ignora: nunca se calculan métricas
    assert cuerpo["aviso_decision"].startswith("Herramienta de apoyo a la decisión.") and cuerpo["aviso_rendimiento"]

    # Lo esperado, con las mismas filas tal como las lee la API del CSV.
    X = pd.read_csv(io.StringIO(tabla.to_csv(index=False)))[["x1", "x2", "c"]]
    esperada, phi = modelo_final.predecir_y_explicar(joblib.load(modelo.ruta_paquete), X)
    assert cuerpo["n_alertas"] == int(esperada["alerta"].sum())

    lote = cliente.get(f"/api/predicciones/{cuerpo['lote_id']}").get_json()
    assert [f["probabilidad"] for f in lote["filas"]] == esperada["probabilidad"].tolist()
    assert [f["alerta"] for f in lote["filas"]] == esperada["alerta"].tolist()
    assert [f["identificador"] for f in lote["filas"]] == [f"A-{i}" for i in range(40)]
    assert all((f["sugerencia"] is not None) == f["alerta"] for f in lote["filas"])
    assert lote["textos"] == {"probabilidad": "Probabilidad estimada por el modelo",
                              "sugerencia": "Sugerencia: priorizar contacto de apoyo"}

    for fila in (1, 4):
        local = cliente.get(f"/api/predicciones/{cuerpo['lote_id']}/filas/{fila}/explicacion").get_json()
        assert {i["variable"]: i["contribucion"] for i in local["todas"]} == phi.iloc[fila - 1].to_dict()
        assert local["valor_base"] == esperada["base_log_odds"].iloc[fila - 1]
        assert local["log_odds"] == esperada["log_odds"].iloc[fila - 1]
    assert {i["variable"]: i["valor"] for i in local["todas"]}["x2"] == "sin dato"  # fila 4: x2 vacío
    assert local["escala"] == "log-odds sin calibrar" and set(local["avisos"]) == {"escala", "causalidad", "decision"}
    assert local["aviso_rendimiento"] == cuerpo["aviso_rendimiento"]


def test_prediccion_rechaza_paquete_no_desplegado(app, cliente, importados):
    # Defensa en servicios.paquetes aunque el modelo esté en la base de datos: el paquete cambiado por uno no
    # desplegado (con su SHA-256 actualizado en la tabla) no se usa.
    modelo = modelo_semana(app, "semana 4")
    joblib.dump(paquete_sintetico(4, desplegado=False), modelo.ruta_paquete)
    r = subir(cliente, modelo.id, tabla_lote())
    assert r.status_code == 409
    assert r.get_json() == {"error": "El archivo del modelo no coincide con el registrado."}
    with app.extensions["bd_sesiones"]() as sesion:
        sesion.get(Modelo, modelo.id).sha256_paquete = sha256(Path(modelo.ruta_paquete))
        sesion.commit()
    r = subir(cliente, modelo.id, tabla_lote())
    assert r.status_code == 409
    assert r.get_json() == {"error": "Este modelo no está desplegado y no puede usarse para predecir."}


def test_errores_de_prediccion(app, cliente, importados):
    modelo = modelo_semana(app, "semana 4")
    tabla = tabla_lote()
    assert subir(cliente, 99, tabla).get_json() == {"error": "No existe el modelo 99."}
    assert cliente.post(f"/api/modelos/{modelo.id}/predicciones").status_code == 400
    assert subir(cliente, modelo.id, tabla.drop(columns=["x1", "c"])).get_json() == {
        "error": "Faltan columnas que el modelo necesita: x1, c."}
    malo = tabla.astype({"x2": object})
    malo.loc[5, "x2"] = "abc"
    assert subir(cliente, modelo.id, malo).get_json() == {
        "error": "La columna «x2» debe ser numérica (fila 6: «abc»)."}
    infinito = tabla.copy()
    infinito.loc[2, "x1"] = np.inf  # pandas lo lee como float inf: sklearn lo rechaza y JSONB no lo admite
    assert subir(cliente, modelo.id, infinito).get_json() == {
        "error": "La columna «x1» debe ser numérica (fila 3: «inf»)."}
    assert subir(cliente, modelo.id, tabla, columna_id="dni").get_json() == {
        "error": "La columna identificadora «dni» no existe."}
    app.config["PLATAFORMA_MAX_FILAS_PREDICCION"] = 30
    r = subir(cliente, modelo.id, tabla)
    assert r.status_code == 422
    assert r.get_json() == {"error": "El archivo tiene 40 filas; el máximo por lote es 30."}
    assert cliente.get("/api/predicciones/99").get_json() == {"error": "No existe el lote de predicción 99."}
    with app.extensions["bd_sesiones"]() as sesion:
        assert sesion.query(LotePrediccion).count() == 0  # ningún error deja un lote a medias


def test_fila_inexistente(app, cliente, importados):
    lote_id = subir(cliente, modelo_semana(app, "semana 4").id, tabla_lote()).get_json()["lote_id"]
    for fila in (0, 41):
        r = cliente.get(f"/api/predicciones/{lote_id}/filas/{fila}/explicacion")
        assert r.status_code == 404 and r.get_json() == {"error": f"No existe la fila {fila} del lote {lote_id}."}


def test_explicacion_global(app, cliente, importados):
    modelo = modelo_semana(app, "semana 4")  # con filas de referencia
    cuerpo = cliente.get(f"/api/modelos/{modelo.id}/explicacion-global").get_json()
    referencia = pd.read_parquet(importados["referencia"] / "x_semana_4.parquet")
    esperada = explicacion.explicacion_global(joblib.load(modelo.ruta_paquete), referencia)
    assert cuerpo["variables"] == esperada["variables"]  # identidad exacta con ml/ (matiz D-3)
    assert cuerpo["fuente"] == "filas de entrenamiento (n = 300)" and cuerpo["escala"] == "log-odds sin calibrar"
    assert cuerpo["explicador"] == "lineal" and set(cuerpo["avisos"]) == {"escala", "causalidad", "decision"}

    sin_referencia = cliente.get(f"/api/modelos/{modelo_semana(app, 'semana 12').id}/explicacion-global").get_json()
    assert sin_referencia["variables"] is None and sin_referencia["motivo"]
    assert cliente.get("/api/modelos/99/explicacion-global").status_code == 404


def test_local_top5_por_signo_extremas_y_sin_contribucion():
    contribuciones = {"a": 0.5, "b": -6.0, "c": 0.1, "d": -0.2, "e": 0.3, "f": 0.05, "g": 0.0, "vacia": 0.0}
    valores = {"a": 12.0, "b": 0.8333333, "c": "x", "d": None, "e": 3, "f": 1.5, "g": 2.0, "vacia": None}
    local = explicaciones.local(contribuciones, valores, ["vacia"])
    assert [(i["variable"], i["valor"], i["extrema"]) for i in local["aumentan"]] == [
        ("a", "12", False), ("e", "3", False), ("c", "x", False)]
    assert [(i["variable"], i["valor"], i["extrema"]) for i in local["reducen"]] == [
        ("b", "0,8333", True), ("d", "sin dato", False)]
    assert local["resto"] == {"n_variables": 2, "suma": 0.05}
    # Sin valores en el entrenamiento pero con φ ≠ 0 (permutación o MLP con un valor en la fila): se muestra.
    con_valor = explicaciones.local({"a": 0.5, "vacia": -0.3}, {"a": 1.0, "vacia": 2.0}, ["vacia"])
    assert [i["variable"] for i in con_valor["todas"]] == ["a", "vacia"] and con_valor["sin_contribucion"] == []
    assert [i["variable"] for i in local["todas"]] == ["b", "a", "e", "d", "c", "f", "g"]  # nunca «vacia»
    assert local["sin_contribucion"] == [{"variable": "vacia", "motivo": explicaciones.textos.SIN_CONTRIBUCION}]
    assert local["hay_extremas"] is True
    assert explicaciones.local({"a": 5.0}, {"a": 1.0}, [])["hay_extremas"] is False  # |φ| > 5, no ≥ 5


def modelo_permutacion(app, tmp_path) -> int:
    """Bosque aleatorio desplegado (explicador de permutación) registrado como experimento web."""
    X, y = datos(200, semilla=3)
    calibrado = motor.entrenar_final("rf", busqueda.PREDETERMINADOS["rf"] | {"n_estimators": 20}, "platt", X, y,
                                     pd.Series(np.arange(len(X)) % 5 + 1), COLUMNAS, 42, 1)
    paquete = explicacion.preparar_paquete(calibrado, "rf", 0.3, COLUMNAS, X, {"desplegado": True}, 42)
    ruta = tmp_path / "rf.joblib"
    joblib.dump(paquete, ruta)
    with app.extensions["bd_sesiones"]() as sesion:
        sesion.add(Experimento(id="web-2099-01-01-01", origen="web", configuracion={}, estado="completado"))
        modelo = Modelo(experimento_id="web-2099-01-01-01", familia="rf", ruta_paquete=str(ruta),
                        sha256_paquete=sha256(ruta), umbral=0.3, columnas=COLUMNAS, explicador="permutacion",
                        evaluacion={})
        sesion.add(modelo)
        sesion.commit()
        return modelo.id


def test_permutacion_explica_bajo_demanda_y_guarda(app, cliente, tmp_path):
    modelo_id = modelo_permutacion(app, tmp_path)
    cuerpo = subir(cliente, modelo_id, tabla_lote(10)).get_json()
    assert cuerpo["explicaciones"] == "bajo_demanda"
    with app.extensions["bd_sesiones"]() as sesion:
        assert sesion.query(Explicacion).count() == 0
    ruta = f"/api/predicciones/{cuerpo['lote_id']}/filas/2/explicacion"
    local = cliente.get(ruta).get_json()
    suma = sum(i["contribucion"] for i in local["todas"]) + local["valor_base"]
    assert local["explicador"] == "permutacion" and abs(suma - local["log_odds"]) < 1e-4
    with app.extensions["bd_sesiones"]() as sesion:
        assert sesion.query(Explicacion).count() == 1
    assert cliente.get(ruta).get_json() == local  # la segunda vez se lee la guardada


def test_respuestas_sin_codigos_de_decision(app, cliente, importados):
    modelo = modelo_semana(app, "semana 4")
    lote_id = subir(cliente, modelo.id, tabla_lote()).get_json()["lote_id"]
    texto = json.dumps([cliente.get(r).get_json() for r in (
        f"/api/predicciones/{lote_id}", f"/api/predicciones/{lote_id}/filas/1/explicacion",
        f"/api/modelos/{modelo.id}/explicacion-global")], ensure_ascii=False)
    assert not re.search(r"\bD\d+|P-\d+", texto)
