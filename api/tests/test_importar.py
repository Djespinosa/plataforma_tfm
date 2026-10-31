"""Importador de paquetes desplegados (docs/diseno-api.md §8), GET /api/modelos y la evaluación de un importado (§4.3),
con paquetes y experimentos sintéticos en el formato de ml/ (modelo_final.paquete)."""

import json
import re

import joblib
import numpy as np
import pandas as pd
import pytest
from sklearn.calibration import CalibratedClassifierCV

import modelo_final
from api.importar import ErrorImportacion, importar
from api.tablas import Experimento, Modelo
from automl import busqueda
from evidencias import sha256

COLUMNAS = {"numericas": ["x1", "x2"], "categoricas": ["c"], "imputar_mediana": []}
FINAL, EVALUADO = "exp-2099-01-01-02", "exp-2099-01-01-01"


def datos(n: int = 300, semilla: int = 0):
    rng = np.random.default_rng(semilla)
    X = pd.DataFrame({"x1": rng.normal(size=n), "x2": rng.normal(size=n), "c": rng.choice(["a", "b"], size=n)})
    y = pd.Series((X["x1"] + rng.normal(size=n) > 0.8).astype(int))
    return X, y


def paquete_sintetico(semana: int, desplegado=True) -> dict:
    X, y = datos(semilla=semana)
    calibrado = CalibratedClassifierCV(busqueda.construir("rl", {"C": 1.0}, **COLUMNAS), method="sigmoid", cv=3,
                                       ensemble=False).fit(X, y)
    origen = {"experimento": EVALUADO, "semana": semana, "variante": "principal", "id": FINAL, "commit": "abc1234"}
    if desplegado != "ausente":
        origen["desplegado"] = desplegado
    return modelo_final.paquete(calibrado, 0.3, COLUMNAS, X, semana, origen)


def momento_sintetico(semana: int) -> dict:
    metricas = {"roc_auc_oof": 0.7, "roc_auc_media": 0.69, "roc_auc_desv": 0.02, "pr_auc_oof": 0.4, "brier_oof": 0.15,
                "por_pliegue": [{"pliegue": k} for k in range(1, 6)]}
    calibracion = {"metodo": "platt", "brier_sin_calibrar": 0.2, "brier_calibrado": 0.15, "anidada": True}
    return {
        "semana": semana, "n": 300, "retiros": 60,
        "familias": [{"modelo": "rl", **metricas, "calibracion": calibracion},
                     {"modelo": "gb", **metricas, "roc_auc_oof": 0.71, "calibracion": calibracion}],
        "referencias": [{"modelo": "mayoritaria", **metricas, "calibracion": None, "nota": "texto con D40"}],
        "apilamiento": {**metricas, "calibracion": "salida del metamodelo (D48)"},
        "mejor_automl": "gb",
        "contraste_central": {"modelo_a": "gb", "modelo_b": "rl_optimizada", "diferencia": 0.01,
                              "ic95_bootstrap": [-0.005, 0.015], "delong_p": 0.2, "delong_p_holm": 0.4,
                              "lectura": "equivalencia_practica"},
        "parsimonia": {"regla": "no inferioridad (D49-rev)", "mejor": "gb", "margen": 0.02,
                       "candidatos": [{"modelo": "rl", "roc_auc_oof": 0.7, "perdida": 0.01,
                                       "ic95_bootstrap": [0.002, 0.0123], "cumple": True},
                                      {"modelo": "gb", "roc_auc_oof": 0.71, "perdida": 0.0, "ic95_bootstrap": [0, 0],
                                       "cumple": True}]},
        "modelo_desplegado": {"modelo": "rl", "motivo": "D33/D49-rev: ..."},
        "calibracion": calibracion,
        "punto_operacion_oof": {"umbral": 0.3, "sensibilidad": 0.7, "precision": 0.28, "tasa_alerta": 0.53,
                                "tasa_falsos_positivos": 0.49, "matriz_confusion": [[100, 140], [18, 42]]},
        "equidad_oof": {"gender": {"subgrupos": {g: {"n": 150, "retiros": 30, "retiros_prueba": 99, "sensibilidad": 0.7,
                                                     "sensibilidad_ic95": [0.6, 0.8], "tasa_falsos_positivos": 0.5,
                                                     "tasa_falsos_positivos_ic95": [0.4, 0.6],
                                                     "solo_descriptiva": False} for g in ("F", "M")},
                                   "diferencia_sensibilidad": 0.0, "diferencia_sensibilidad_ic95": [0.0, 0.1],
                                   "diferencia_tasa_falsos_positivos": 0.0,
                                   "diferencia_tasa_falsos_positivos_ic95": [0.0, 0.1],
                                   "metodo_ic_diferencia": "texto"}},
    }


@pytest.fixture
def entorno(tmp_path):
    """Carpetas modelos/, experimentos/, referencia/ y oof/ con dos paquetes desplegados (semanas 4 y 12, que en orden
    alfabético van al revés) y uno no desplegado."""
    modelos, experimentos, referencia, oof = (tmp_path / d for d in ("modelos", "experimentos", "referencia", "oof"))
    for carpeta in (modelos, experimentos, referencia, oof):
        carpeta.mkdir()
    huellas = {}
    for nombre, semana, desplegado in (("x_semana_12.joblib", 12, True), ("x_semana_4.joblib", 4, True),
                                       ("x_otro_semana_4.joblib", 4, False)):
        joblib.dump(paquete_sintetico(semana, desplegado), modelos / nombre)
        huellas[nombre] = sha256(modelos / nombre)
    X, _ = datos(semilla=4)
    X.to_parquet(referencia / "x_semana_4.parquet")
    rng = np.random.default_rng(1)
    pd.DataFrame({"etiqueta": rng.integers(0, 2, 300), "p_rl": rng.random(300), "p_rl_sin_calibrar": rng.random(300)}
                 ).to_parquet(oof / f"{EVALUADO}_semana_4.parquet")
    escribir = lambda id_, contenido: (experimentos / f"{id_}.json").write_text(json.dumps(contenido), encoding="utf-8")
    escribir(FINAL, {"id": FINAL, "commit": "abc1234", "configuracion": {"nombre": "modelo_final",
                                                                          "descripcion": "texto con D41"},
                     "dataset": {"sha256": {"a.csv": "0" * 64}}, "entorno": {"python": "3.13"}, "hardware": {"cpu": "x"},
                     "modelos_sha256": {"carpeta": "modelos", **huellas}})
    escribir(EVALUADO, {"id": EVALUADO, "configuracion": {"familias": ["rl", "gb"], "n_trials_por_familia": 50,
                                                          "apilamiento": True, "n_bootstrap": 2000,
                                                          "sensibilidad_minima": 0.7,
                                                          "semillas": {"optuna": 42, "modelos": 42, "bootstrap": 42}},
                        "momentos": [momento_sintetico(s) for s in (0, 4, 8, 12)],
                        "predicciones_oof_sha256": {"carpeta": oof.as_posix(),
                                                    f"{EVALUADO}_semana_4.parquet": sha256(
                                                        oof / f"{EVALUADO}_semana_4.parquet")}})
    return {"modelos": modelos, "experimentos": experimentos, "referencia": referencia, "oof": oof}


def importar_en(app, entorno) -> list[str]:
    with app.extensions["bd_sesiones"]() as sesion:
        return importar(sesion, entorno["modelos"], entorno["experimentos"], entorno["referencia"])


def contar(app, tabla) -> int:
    with app.extensions["bd_sesiones"]() as sesion:
        return sesion.query(tabla).count()


def test_importador_solo_carga_paquetes_desplegados(app, entorno):
    # El nombre no interviene: «con_sensibles» desplegado se importa; «semana_0» con desplegado distinto de True, no.
    for nombre in ("x_semana_12.joblib", "x_semana_4.joblib", "x_otro_semana_4.joblib"):
        (entorno["modelos"] / nombre).unlink()
    huellas = {}
    for nombre, desplegado in (("x_semana_0.joblib", False), ("y_semana_0.joblib", "True"), ("z_semana_0.joblib", 1),
                               ("w_semana_0.joblib", "ausente"), ("x_con_sensibles_semana_0.joblib", True)):
        joblib.dump(paquete_sintetico(0, desplegado), entorno["modelos"] / nombre)
        huellas[nombre] = sha256(entorno["modelos"] / nombre)
    ruta = entorno["experimentos"] / f"{FINAL}.json"
    contenido = json.loads(ruta.read_text(encoding="utf-8"))
    ruta.write_text(json.dumps(contenido | {"modelos_sha256": huellas}), encoding="utf-8")

    mensajes = importar_en(app, entorno)
    assert sorted(mensajes) == ["w_semana_0.joblib: omitido (no desplegado)",
                        "x_con_sensibles_semana_0.joblib: importado (exp-2099-01-01-02, semana 0)",
                        "x_semana_0.joblib: omitido (no desplegado)",
                        "y_semana_0.joblib: omitido (no desplegado)",
                        "z_semana_0.joblib: omitido (no desplegado)"]
    assert contar(app, Modelo) == 1


def test_importa_por_semana_con_experimento_y_procedencia(app, entorno):
    importar_en(app, entorno)
    with app.extensions["bd_sesiones"]() as sesion:
        experimento = sesion.get(Experimento, FINAL)
        modelos = sesion.query(Modelo).order_by(Modelo.id).all()
        assert experimento.origen == "importado" and experimento.estado == "completado"
        assert experimento.conjunto_id is None and experimento.evaluacion_prueba is None
        assert experimento.procedencia["evaluacion_de"] == EVALUADO
        assert experimento.procedencia["archivo_json_sha256"] == sha256(entorno["experimentos"] / f"{FINAL}.json")
        assert "descripcion" not in experimento.configuracion["origen"]
        assert [m.momento for m in modelos] == ["semana 4", "semana 12"]
        m4 = modelos[0]
        assert m4.familia == "rl" and m4.explicador == "lineal" and m4.umbral == 0.3
        assert m4.sha256_paquete == sha256(entorno["modelos"] / "x_semana_4.joblib")
        assert m4.explicacion_global["n_filas"] == 300 and m4.explicacion_global["explicador"] == "lineal"
        assert modelos[1].explicacion_global is None  # sin filas de referencia


def test_importador_rechaza_sha256_distinto_sin_escribir(app, entorno):
    # Otro contenido con la huella registrada del original.
    joblib.dump(paquete_sintetico(12) | {"umbral": 0.5}, entorno["modelos"] / "x_semana_12.joblib")
    with pytest.raises(ErrorImportacion, match="x_semana_12.joblib: su SHA-256 no coincide con el registrado"):
        importar_en(app, entorno)
    assert contar(app, Experimento) == 0 and contar(app, Modelo) == 0


def test_importador_rechaza_oof_alterado_sin_escribir(app, entorno):
    (entorno["oof"] / f"{EVALUADO}_semana_4.parquet").write_bytes(b"otro")
    with pytest.raises(ErrorImportacion, match="no coincide con el SHA-256 registrado en exp-2099-01-01-01"):
        importar_en(app, entorno)
    assert contar(app, Experimento) == 0


def test_importador_es_idempotente(app, entorno):
    importar_en(app, entorno)
    assert importar_en(app, entorno) == ["x_otro_semana_4.joblib: omitido (no desplegado)",
                                         "x_semana_12.joblib: omitido (ya importado)",
                                         "x_semana_4.joblib: omitido (ya importado)"]
    assert contar(app, Experimento) == 1 and contar(app, Modelo) == 2
    # Otro paquete para el mismo experimento y semana es un error.
    ruta = entorno["experimentos"] / f"{FINAL}.json"
    contenido = json.loads(ruta.read_text(encoding="utf-8"))
    joblib.dump(paquete_sintetico(4) | {"umbral": 0.31}, entorno["modelos"] / "x_bis_semana_4.joblib")
    contenido["modelos_sha256"]["x_bis_semana_4.joblib"] = sha256(entorno["modelos"] / "x_bis_semana_4.joblib")
    ruta.write_text(json.dumps(contenido), encoding="utf-8")
    with pytest.raises(ErrorImportacion, match="ya hay otro modelo importado para exp-2099-01-01-02 y la semana 4"):
        importar_en(app, entorno)


def test_importador_rechaza_dos_paquetes_para_la_misma_semana_sin_escribir(app, entorno):
    joblib.dump(paquete_sintetico(4) | {"umbral": 0.31}, entorno["modelos"] / "x_bis_semana_4.joblib")
    ruta = entorno["experimentos"] / f"{FINAL}.json"
    contenido = json.loads(ruta.read_text(encoding="utf-8"))
    contenido["modelos_sha256"]["x_bis_semana_4.joblib"] = sha256(entorno["modelos"] / "x_bis_semana_4.joblib")
    ruta.write_text(json.dumps(contenido), encoding="utf-8")
    with pytest.raises(ErrorImportacion, match="x_semana_4.joblib y x_bis_semana_4.joblib son dos paquetes para "
                                               "exp-2099-01-01-02 y la semana 4"):
        importar_en(app, entorno)
    assert contar(app, Experimento) == 0 and contar(app, Modelo) == 0


def test_arbol_limpio_solo_si_el_json_viene_de_evidencias(app, entorno):
    importar_en(app, entorno)  # carpeta temporal, no evidencias/experimentos
    with app.extensions["bd_sesiones"]() as sesion:
        assert sesion.get(Experimento, FINAL).reproducibilidad["arbol_limpio"] is None


def test_evaluacion_importada_sale_del_experimento_origen(app, cliente, entorno):
    importar_en(app, entorno)
    r = cliente.get(f"/api/experimentos/{FINAL}/evaluacion")
    assert r.status_code == 200
    cuerpo = r.get_json()
    assert cuerpo["origen"] == "importado" and cuerpo["fuente"] == "validacion_cruzada"
    assert cuerpo["presupuesto"] == {"modo": "completo", "familias": ["rl", "gb"], "n_trials_por_familia": 50,
                                     "apilamiento": True, "n_bootstrap": 2000}
    assert cuerpo["validacion"]["tipo"] == "agrupada" and cuerpo["validacion"]["k"] == 5
    assert cuerpo["aviso_decision"].startswith("Herramienta de apoyo a la decisión.")
    semana4, semana12 = cuerpo["modelos"]
    assert semana4["momento"] == "semana 4" and semana12["momento"] == "semana 12"
    assert semana4["n"] == 300 and semana4["positivos"] == 60
    assert [(c["modelo"], c["papel"]) for c in semana4["candidatos"]] == [("rl", "desplegado"), ("gb", "candidato"),
                                                                          ("apilamiento", "candidato")]
    assert semana4["candidatos"][0]["calibracion"] == "platt" and semana4["candidatos"][2]["calibracion"] is None
    assert semana4["contraste"]["holm_sobre"] == 4 and semana4["contraste"]["delong_p_holm"] == 0.4
    assert semana4["contraste"]["lectura_texto"] == ("El intervalo de la diferencia queda dentro de ±0,02: rendimiento "
                                                     "equivalente en la práctica.")
    assert semana4["desplegado"]["motivo_texto"] == (
        "Se despliega regresión logística: es el modelo más simple cuya pérdida de ROC-AUC frente al mejor "
        "(potenciación de gradiente (scikit-learn)) tiene un límite superior del intervalo del 95 % (0,0123) por "
        "debajo de 0,02.")
    assert semana4["punto_operacion"]["textos"] == {"sensibilidad": "De cada 10 casos positivos, el modelo marca a 7.",
                                                    "precision": "De cada 10 marcados, 3 son positivos.",
                                                    "tasa_alerta": "Se marcaría al 53 % de los casos."}
    assert len(semana4["calibracion"]["curva"]["calibrada"]) == 10 and "motivo" not in semana4["calibracion"]
    assert semana12["calibracion"]["curva"] is None and semana12["calibracion"]["motivo"]
    assert semana4["equidad"]["texto"].startswith("Las variables sensibles (gender) no se usan para predecir")
    texto = json.dumps(cuerpo, ensure_ascii=False)
    assert "retiros_prueba" not in texto  # nada de la cohorte de prueba
    assert not re.search(r"\bD\d+|P-\d+", texto)  # ni códigos de decisión de ml/


def test_evaluacion_de_experimento_inexistente_o_sin_terminar(app, cliente):
    assert cliente.get("/api/experimentos/web-2099-01-01-01/evaluacion").get_json() == {
        "error": "No existe el experimento web-2099-01-01-01."}
    with app.extensions["bd_sesiones"]() as sesion:
        sesion.add(Experimento(id="web-2099-01-01-01", origen="web", configuracion={}, estado="en_curso"))
        sesion.commit()
    r = cliente.get("/api/experimentos/web-2099-01-01-01/evaluacion")
    assert r.status_code == 409
    assert r.get_json() == {"error": "El experimento aún no ha terminado (estado: en curso)."}


def test_modelos_lista_y_detalle(app, cliente, entorno):
    importar_en(app, entorno)
    lista = cliente.get("/api/modelos").get_json()
    assert [(m["momento"], m["origen"], m["familia"], m["explicador"]) for m in lista] == [
        ("semana 4", "importado", "rl", "lineal"), ("semana 12", "importado", "rl", "lineal")]
    detalle = cliente.get(f"/api/modelos/{lista[0]['id']}").get_json()
    assert detalle["columnas"] == {"numericas": ["x1", "x2"], "categoricas": ["c"]}
    assert cliente.get("/api/modelos/99").get_json() == {"error": "No existe el modelo 99."}


def test_comando_importar_paquetes(app, entorno):
    resultado = app.test_cli_runner().invoke(args=[
        "importar-paquetes", "--modelos", str(entorno["modelos"]), "--experimentos", str(entorno["experimentos"]),
        "--referencia", str(entorno["referencia"])])
    assert resultado.exit_code == 0, resultado.output
    assert "x_semana_4.joblib: importado (exp-2099-01-01-02, semana 4)" in resultado.output
    (entorno["oof"] / f"{EVALUADO}_semana_4.parquet").write_bytes(b"otro")
    joblib.dump(paquete_sintetico(8), entorno["modelos"] / "x_semana_8.joblib")  # sin huella registrada
    resultado = app.test_cli_runner().invoke(args=[
        "importar-paquetes", "--modelos", str(entorno["modelos"]), "--experimentos", str(entorno["experimentos"])])
    assert resultado.exit_code == 1
    assert "No se ha importado nada." in resultado.output
