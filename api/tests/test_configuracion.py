"""Configuración de experimentos web (RF-02, docs/diseno-api.md §4.2 y §6.4): POST /api/experimentos/validacion y
POST /api/experimentos con una tabla sintética (300 filas, 10 grupos, 3 cohortes)."""

import io

import numpy as np
import pandas as pd
import pytest

from api.tablas import Experimento, clave_cohorte

COHORTES = {**{f"g{i}": "2013B" for i in range(4)}, **{f"g{i}": "2013J" for i in range(4, 8)},
            "g8": "2014J", "g9": "2014J"}


def tabla(n: int = 300, semilla: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(semilla)
    grupo = [f"g{i % 10}" for i in range(n)]
    x1 = rng.normal(size=n)
    objetivo = np.where(x1 + rng.normal(size=n) > 0.5, "Retirado", "Aprobado").astype(object)
    objetivo[[0, 7, 13]] = None
    return pd.DataFrame({
        "matricula": [f"M-{i}" for i in range(n)], "grupo": grupo, "cohorte": [COHORTES[g] for g in grupo],
        "x1": x1, "x2": np.where(rng.random(n) < 0.1, np.nan, rng.normal(size=n)),
        "nivel": rng.choice(["1", "2", "A"], size=n), "sexo": rng.choice(["F", "M"], size=n), "objetivo": objetivo,
    })


def subir_conjunto(cliente, datos: pd.DataFrame) -> int:
    r = cliente.post("/api/conjuntos", data={"archivo": (io.BytesIO(datos.to_csv(index=False).encode()), "t.csv")},
                     content_type="multipart/form-data")
    assert r.status_code == 201, r.get_json()
    return r.get_json()["id"]


def cuerpo(conjunto_id: int, **cambios) -> dict:
    return {"conjunto_id": conjunto_id, "objetivo": "objetivo", "clase_positiva": "Retirado",
            "excluidas": ["matricula"], "sensibles": ["sexo"], "columna_grupo": "grupo",
            "cohorte_prueba": {"modo": "valores", "columna": "cohorte", "valores": ["2014J"]},
            "presupuesto": "prueba"} | cambios


@pytest.fixture
def conjunto(cliente):
    return subir_conjunto(cliente, tabla())


def test_validacion_con_grupo_y_cohorte_por_valores(cliente, conjunto):
    r = cliente.post("/api/experimentos/validacion", json=cuerpo(conjunto))
    assert r.status_code == 200, r.get_json()
    v = r.get_json()
    datos = tabla()
    con_objetivo = datos["objetivo"].notna()
    en_prueba = con_objetivo & (datos["cohorte"] == "2014J")
    assert v["filas_sin_objetivo"] == 3 and v["filas_prueba"] == int(en_prueba.sum())
    assert v["filas_entrenamiento"] == int((con_objetivo & ~en_prueba).sum())
    # Ni el identificador excluido, ni la sensible, ni el grupo, ni la columna de la cohorte son predictores.
    assert v["variables"] == {"numericas": ["x1", "x2"], "categoricas": ["nivel"]}
    assert v["excluidas_automaticamente"] == [{"columna": "grupo", "motivo": "columna de grupo"},
                                              {"columna": "cohorte", "motivo": "define la cohorte de prueba"}]
    assert v["validacion"] == {"tipo": "agrupada_estratificada", "k": 5, "semilla": 42, "columna_grupo": "grupo",
                               "n_grupos": 8}
    assert v["cohorte_prueba"]["filas"] == v["filas_prueba"] and v["cohorte_prueba"]["semilla"] is None
    assert "3 filas no tienen valor en la columna objetivo y no se usan." in v["avisos"]
    assert not any("Sin columna de grupo" in a for a in v["avisos"])


def test_validacion_sin_grupo_avisa_y_cohorte_aleatoria(cliente, conjunto):
    v = cliente.post("/api/experimentos/validacion", json=cuerpo(
        conjunto, columna_grupo=None, cohorte_prueba={"modo": "aleatoria"}, presupuesto="demostracion")).get_json()
    assert v["validacion"]["tipo"] == "estratificada" and v["validacion"]["n_grupos"] is None
    assert v["filas_prueba"] == 60  # train_test_split redondea hacia arriba: ceil(0,2 · 297)
    assert v["variables"]["categoricas"] == ["grupo", "cohorte", "nivel"]  # sin grupo ni cohorte por valores
    assert any(a.startswith("Sin columna de grupo, los pliegues se forman al azar") for a in v["avisos"])
    assert any(a.startswith("Presupuesto reducido de demostración") for a in v["avisos"])
    assert v["presupuesto"] == {"modo": "demostracion", "familias": ["rl", "rf", "gb", "xgb", "lgbm", "catboost", "mlp"],
                                "n_trials_por_familia": 5, "n_bootstrap": 200}


@pytest.mark.parametrize("cambios, mensaje", [
    ({"objetivo": "resultado"}, "La columna objetivo «resultado» no existe en el conjunto."),
    ({"clase_positiva": "Suspenso"}, "La clase positiva «Suspenso» no aparece en la columna objetivo."),
    ({"excluidas": ["dni"], "sensibles": ["edad"]}, "Columnas desconocidas: dni, edad."),
    ({"sensibles": ["objetivo"]}, "La columna objetivo no puede ser también de grupo, excluida ni sensible."),
    ({"excluidas": ["matricula", "x1", "x2", "nivel"]}, "No queda ninguna variable para entrenar tras las exclusiones."),
    ({"columna_grupo": "cohorte", "cohorte_prueba": None},
     "La columna de grupo «cohorte» tiene 3 valores distintos; la validación agrupada necesita al menos 5. Indique otra "
     "columna de grupo o ninguna."),
    ({"cohorte_prueba": {"modo": "aleatoria"}},
     "Con columna de grupo, la cohorte de prueba se elige por valores (cohortes completas), no al azar, para que filas "
     "relacionadas no queden a ambos lados."),
    ({"cohorte_prueba": {"modo": "valores", "columna": "cohorte", "valores": ["2015B"]}},
     "Ningún valor de la cohorte de prueba aparece en «cohorte»."),
    ({"cohorte_prueba": {"modo": "valores", "columna": "cohorte", "valores": []}}, None),
    ({"presupuesto": "rapido"}, "El presupuesto debe ser «completo» o «demostracion»."),
    ({"excluidas": "matricula"}, "El campo «excluidas» debe ser una lista de nombres de columna."),
])
def test_errores_de_configuracion(cliente, conjunto, cambios, mensaje):
    r = cliente.post("/api/experimentos/validacion", json=cuerpo(conjunto, **cambios))
    assert r.status_code == 422
    if mensaje is not None:
        assert r.get_json() == {"error": mensaje}


def test_errores_de_peticion(app, cliente, conjunto):
    assert cliente.post("/api/experimentos/validacion", data="x", content_type="application/json").get_json() == {
        "error": "La petición no es JSON válido."}
    sin_objetivo = cuerpo(conjunto)
    del sin_objetivo["objetivo"]
    r = cliente.post("/api/experimentos", json=sin_objetivo)
    assert r.status_code == 400 and r.get_json() == {"error": "Falta el campo «objetivo»."}
    assert cliente.post("/api/experimentos", json=cuerpo(99)).get_json() == {"error": "No existe el conjunto de datos 99."}
    app.testing = False  # el presupuesto «prueba» solo existe con la configuración de pruebas
    assert cliente.post("/api/experimentos/validacion", json=cuerpo(conjunto)).status_code == 422
    with app.extensions["bd_sesiones"]() as sesion:
        assert sesion.query(Experimento).count() == 0


def test_nombres_y_categorias_que_los_modelos_no_admiten(cliente):
    # LightGBM rechaza " , : { } y XGBoost [ ] < en los nombres de columna (también en los one-hot <variable>_<valor>):
    # se rechazan al configurar y no después de horas de entrenamiento.
    con_coma = tabla().assign(nivel=lambda d: d["nivel"].replace("A", "Madrid, España"))
    r = cliente.post("/api/experimentos/validacion", json=cuerpo(subir_conjunto(cliente, con_coma)))
    assert r.status_code == 422 and r.get_json()["error"].startswith("La columna «nivel» tiene valores con caracteres")
    con_nombre = tabla().rename(columns={"x1": "nota<5"})
    r = cliente.post("/api/experimentos/validacion", json=cuerpo(subir_conjunto(cliente, con_nombre)))
    assert r.status_code == 422 and r.get_json()["error"].startswith("El nombre de la columna «nota<5» contiene")


def test_error_de_biblioteca_no_llega_en_ingles(cliente):
    datos = tabla()
    datos["objetivo"] = "Aprobado"
    datos.loc[5, "objetivo"] = "Retirado"  # una sola fila positiva: train_test_split no puede estratificar
    r = cliente.post("/api/experimentos/validacion", json=cuerpo(
        subir_conjunto(cliente, datos), columna_grupo=None, cohorte_prueba={"modo": "aleatoria"}))
    assert r.status_code == 422
    assert r.get_json() == {"error": "No se puede preparar la validación con estos datos y esta configuración."}


def test_una_sola_clase_en_entrenamiento(cliente):
    datos = tabla()
    datos["objetivo"] = np.where(datos["cohorte"] == "2014J", "Retirado", "Aprobado")
    r = cliente.post("/api/experimentos/validacion", json=cuerpo(subir_conjunto(cliente, datos)))
    assert r.get_json() == {"error": "La columna objetivo solo tiene una clase en las filas de entrenamiento; se "
                                     "necesitan ambas."}


def test_crear_guarda_configuracion_efectiva_y_clave_de_cohorte(app, cliente, conjunto):
    r = cliente.post("/api/experimentos", json=cuerpo(conjunto, descripcion="primera prueba"))
    assert r.status_code == 202, r.get_json()
    e = r.get_json()
    assert e["estado"] == "en_cola" and e["id"].startswith("web-") and e["id"].endswith("-01")
    assert r.headers["Location"].endswith(f"/api/experimentos/{e['id']}")
    config = e["configuracion"]
    assert config["validacion"]["pliegues_sha256"] and config["semillas"] == {"optuna": 42, "modelos": 42,
                                                                              "bootstrap": 42}
    assert config["presupuesto"]["modo"] == "prueba" and config["sensibilidad_minima"] == 0.7
    with app.extensions["bd_sesiones"]() as sesion:
        guardado = sesion.get(Experimento, e["id"])
        assert guardado.cohorte_prueba_clave == clave_cohorte(guardado.configuracion["cohorte_prueba"])
        assert guardado.sha256_datos is not None and guardado.descripcion == "primera prueba"
    assert cliente.post("/api/experimentos", json=cuerpo(conjunto)).get_json()["id"].endswith("-02")
    # Misma petición → mismos pliegues (los recalcula el trabajador y los compara).
    otra = cliente.post("/api/experimentos/validacion", json=cuerpo(conjunto))
    assert otra.status_code == 200
    assert cliente.get(f"/api/experimentos/{e['id']}").get_json()["configuracion"] == config


def test_clave_de_cohorte_normaliza_los_valores():
    base = {"modo": "valores", "columna": "anio"}
    assert clave_cohorte(base | {"valores": [2014.0]}) == clave_cohorte(base | {"valores": ["2014"]})
    assert clave_cohorte(base | {"valores": [2014, "2013", 2014]}) == clave_cohorte(base | {"valores": ["2013", "2014"]})
    assert clave_cohorte(base | {"valores": [2014.5]}) != clave_cohorte(base | {"valores": ["2014"]})
