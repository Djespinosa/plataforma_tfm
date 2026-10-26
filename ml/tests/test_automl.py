"""Pruebas del núcleo de ml/automl: comparación estadística, umbral, equidad y anti-fuga de las predicciones
out-of-fold (calibración anidada D37 y apilamiento D48).

Prueba anti-fuga central: permutar las etiquetas del pliegue f no puede cambiar ninguna predicción de f, porque
ni el modelo, ni el calibrador, ni el metamodelo que predicen f deben haber visto sus etiquetas.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from sklearn.base import clone
from sklearn.metrics import roc_auc_score
from scipy.stats import norm

from automl.apilamiento import oof_apilamiento
from automl.busqueda import ESPACIOS, FAMILIAS, PREDETERMINADOS, buscar, construir, sugerir
from automl.calibracion import elegir_metodo, oof_anidado, punto_operacion, umbral
from automl.comparacion import auc_bootstrap, delong, holm, intervalo, lectura, parsimonia
from automl.equidad import auditar
from automl.particion import divisiones

COLUMNAS = {"numericas": ["a", "b", "date_registration"], "categoricas": ["c"], "imputar_mediana": ["date_registration"]}


def datos(n: int = 750, semilla: int = 0) -> tuple[pd.DataFrame, pd.Series, pd.Series]:
    rng = np.random.default_rng(semilla)
    X = pd.DataFrame({
        "a": rng.normal(size=n),
        "b": np.where(rng.random(n) < 0.2, np.nan, rng.normal(size=n)),
        "date_registration": np.where(rng.random(n) < 0.05, np.nan, rng.normal(-50, 20, size=n)),
        "c": rng.choice(["x", "y", None], n),
    })
    y = pd.Series((X["a"] + 0.5 * X["b"].fillna(0) + rng.normal(size=n) > 0.8).astype(int))
    pliegue = pd.Series(np.repeat(np.arange(1, 6), n // 5)).astype("Int64")
    return X, y, pliegue


def permutar_pliegue(y: pd.Series, pliegue: pd.Series, f: int, semilla: int = 1) -> pd.Series:
    nuevo = y.copy()
    en = (pliegue == f).to_numpy()
    nuevo[en] = np.random.default_rng(semilla).permutation(y[en].to_numpy())
    return nuevo


# --- DeLong, bootstrap, Holm ---------------------------------------------------------------------------------------

def delong_fuerza_bruta(y, p_a, p_b):
    """Implementación directa de DeLong et al. (1988) con la matriz psi completa (O(m·n))."""
    v10, v01 = [], []
    for p in (p_a, p_b):
        pos, neg = p[y == 1], p[y == 0]
        psi = (pos[:, None] > neg[None, :]) + 0.5 * (pos[:, None] == neg[None, :])
        v10.append(psi.mean(axis=1))
        v01.append(psi.mean(axis=0))
    auc = [v.mean() for v in v10]
    s10, s01 = np.cov(np.vstack(v10)), np.cov(np.vstack(v01))
    var = (s10[0, 0] + s10[1, 1] - 2 * s10[0, 1]) / len(v10[0]) + (s01[0, 0] + s01[1, 1] - 2 * s01[0, 1]) / len(v01[0])
    return auc[0], auc[1], 2 * norm.sf(abs(auc[0] - auc[1]) / np.sqrt(var))


def test_delong_coincide_con_la_implementacion_directa_y_con_sklearn():
    rng = np.random.default_rng(3)
    y = rng.integers(0, 2, 300)
    p_a = y + rng.normal(0, 1.0, 300)
    p_b = np.round(y + rng.normal(0, 1.5, 300), 1)  # con empates
    resultado = delong(y, p_a, p_b)
    auc_a, auc_b, p = delong_fuerza_bruta(y, p_a, p_b)
    assert resultado["roc_auc_a"] == pytest.approx(roc_auc_score(y, p_a))
    assert resultado["roc_auc_b"] == pytest.approx(auc_b)
    assert resultado["delong_p"] == pytest.approx(p)
    assert resultado["delong_p"] < 0.05


def test_delong_modelos_identicos():
    rng = np.random.default_rng(4)
    y, p = rng.integers(0, 2, 100), rng.random(100)
    assert delong(y, p, p)["delong_p"] == 1.0


def test_holm_caso_calculado_a_mano():
    # Orden: 0.005·4 = 0.02; 0.01·3 = 0.03; 0.03·2 = 0.06; 0.04·1 = 0.04 → monótono: 0.06.
    assert holm([0.01, 0.04, 0.03, 0.005]) == pytest.approx([0.03, 0.06, 0.06, 0.02])


def test_bootstrap_pareado_y_reproducible():
    rng = np.random.default_rng(5)
    y, p = rng.integers(0, 2, 200), rng.random(200)
    a = auc_bootstrap(y, {"m": p, "n": p}, 50, 42)
    assert (a["m"] == a["n"]).all()  # mismas matrículas para los dos modelos
    pd.testing.assert_frame_equal(a, auc_bootstrap(y, {"m": p, "n": p}, 50, 42))


def test_lectura_en_cuatro_casos():
    assert lectura(0.05, [0.03, 0.07], 0.001) == "ventaja_relevante"
    assert lectura(0.01, [0.005, 0.015], 0.001) == "detectable_sin_relevancia"
    assert lectura(0.005, [-0.01, 0.015], 0.2) == "equivalencia_practica"
    assert lectura(0.01, [-0.01, 0.04], 0.2) == "no_concluyente"


def test_parsimonia_por_no_inferioridad():
    rng = np.random.default_rng(6)
    y = rng.integers(0, 2, 4000)
    senal = y + rng.normal(0, 1, 4000)
    predicciones = {
        "rl": senal + rng.normal(0, 0.05, 4000),     # casi igual que el mejor: no inferior
        "lgbm": senal,
        "mlp": senal + rng.normal(0, 0.02, 4000),
    }
    complejidad = {"rl": 0, "lgbm": 1, "mlp": 2}
    resultado = parsimonia(y, predicciones, complejidad, 200, 42)
    assert resultado["desplegado"] == "rl"
    predicciones["rl"] = y + rng.normal(0, 3, 4000)  # claramente peor: no cumple
    resultado = parsimonia(y, predicciones, complejidad, 200, 42)
    rl = next(c for c in resultado["candidatos"] if c["modelo"] == "rl")
    assert not rl["cumple"] and resultado["desplegado"] == "lgbm"
    assert rl["perdida"] > 0 and rl["ic95_bootstrap"][1] >= 0.02


# --- Umbral y punto de operación --------------------------------------------------------------------------------------

def test_umbral_maxima_precision_con_sensibilidad_minima():
    y = np.array([1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 0, 0, 0, 0, 0])
    p = np.array([.95, .9, .85, .8, .75, .7, .65, .3, .2, .1, .92, .6, .5, .4, .05])
    t = umbral(y, p, 0.70)
    punto = punto_operacion(y, p, t)
    assert t == pytest.approx(0.65)  # 7 de 10 positivos con un solo falso positivo
    assert punto["sensibilidad"] == 0.7 and punto["precision"] == pytest.approx(7 / 8)
    assert punto["matriz_confusion"] == [[4, 1], [3, 7]] and punto["tasa_alerta"] == pytest.approx(8 / 15, abs=1e-4)


# --- Anti-fuga de las predicciones out-of-fold ------------------------------------------------------------------------

def test_calibracion_anidada_no_ve_las_etiquetas_del_pliegue_evaluado():
    X, y, pliegue = datos()
    modelo = construir("rl", {"C": 1.0}, **COLUMNAS)
    original = oof_anidado(modelo, X, y, pliegue)
    for f in (1, 4):
        alterado = oof_anidado(modelo, X, permutar_pliegue(y, pliegue, f), pliegue)
        en = (pliegue == f).to_numpy()
        for nombre in original:
            np.testing.assert_allclose(original[nombre][en], alterado[nombre][en])
            assert not np.allclose(original[nombre][~en], alterado[nombre][~en])  # la prueba detecta cambios
    assert not any(np.isnan(v).any() for v in original.values())
    assert elegir_metodo(y, original)["metodo"] in ("platt", "isotonica")


def test_calibracion_anidada_usa_divisiones_internas_agrupadas():
    """El calibrador de cada pliegue externo usa como divisiones internas los otros 4 pliegues (no cv=5 sin grupos)."""
    _, _, pliegue = datos()
    for ajuste, _ in divisiones(pliegue):
        internas = divisiones(pliegue.iloc[ajuste])
        assert len(internas) == 4
        for _, validacion_interna in internas:
            assert pliegue.iloc[ajuste].iloc[validacion_interna].nunique() == 1


def test_apilamiento_no_ve_las_etiquetas_del_pliegue_evaluado():
    X, y, pliegue = datos()
    base = {"rl": construir("rl", {"C": 1.0}, **COLUMNAS),
            "lgbm": construir("lgbm", {"n_estimators": 30}, **COLUMNAS)}
    original = oof_apilamiento(base, X, y, pliegue)
    alterado = oof_apilamiento(base, X, permutar_pliegue(y, pliegue, 2), pliegue)
    en = (pliegue == 2).to_numpy()
    np.testing.assert_allclose(original[en], alterado[en])
    assert not np.allclose(original[~en], alterado[~en])


# --- Búsqueda y familias ----------------------------------------------------------------------------------------------

@pytest.mark.parametrize("familia", FAMILIAS)
def test_cada_familia_se_construye_clona_y_ajusta(familia):
    import optuna

    X, y, _ = datos(300)
    fijo = {k: (v[1][-1] if v[0] == "categorica" else v[1]) for k, v in ESPACIOS[familia].items()}
    params = sugerir(optuna.trial.FixedTrial(fijo), ESPACIOS[familia])
    modelo = clone(construir(familia, params, **COLUMNAS)).fit(X, y)
    p = modelo.predict_proba(X)[:, 1]
    assert p.shape == (300,) and np.isfinite(p).all()


@pytest.mark.parametrize("familia", FAMILIAS)
def test_columna_sin_valores_no_rompe_ninguna_familia(familia):
    """Semana 0: antelacion_media y proporcion_entregadas están vacías porque aún no vence ninguna evaluación."""
    X, y, _ = datos(300)
    X["vacia"] = np.nan
    columnas = COLUMNAS | {"numericas": [*COLUMNAS["numericas"], "vacia"]}
    p = construir(familia, {}, **columnas).fit(X, y).predict_proba(X)[:, 1]
    assert np.isfinite(p).all()


def test_busqueda_reproducible_con_la_misma_semilla():
    X, y, pliegue = datos(400)
    cv = divisiones(pliegue)
    a = buscar("rl", X, y, cv, 6, COLUMNAS, semilla=42)
    b = buscar("rl", X, y, cv, 6, COLUMNAS, semilla=42)
    assert a["hiperparametros"] == b["hiperparametros"] and a["roc_auc_media_busqueda"] == b["roc_auc_media_busqueda"]
    assert a["n_completados"] + a["n_podados"] == 6


@pytest.mark.parametrize("familia", FAMILIAS)
def test_predeterminados_dentro_del_espacio(familia):
    espacio, valores = ESPACIOS[familia], PREDETERMINADOS[familia]
    assert set(valores) == set(espacio)
    for nombre, (tipo, *rango) in espacio.items():
        if tipo == "categorica":
            assert valores[nombre] in rango[0]
        else:
            assert rango[0] <= valores[nombre] <= rango[1]


def test_espacio_de_la_rl_incluye_c_1_con_l2():
    tipo, minimo, maximo = ESPACIOS["rl"]["C"]
    assert tipo == "float_log" and minimo <= 0.1 and maximo >= 10  # C alrededor de 1 en escala logarítmica
    assert 0.0 in ESPACIOS["rl"]["l1_ratio"][1]  # l1_ratio 0 = L2
    assert PREDETERMINADOS["rl"] == {"C": 1.0, "l1_ratio": 0.0, "class_weight": None}


def test_rl_optimizada_nunca_por_debajo_de_la_rl_por_defecto():
    """El primer ensayo es la RL por defecto (la misma Pipeline que la referencia rl_defecto), así que la mejor
    configuración no puede quedar por debajo en la métrica objetivo; con un solo ensayo, es la configuración por defecto."""
    from experimento import rl_defecto

    X, y, pliegue = datos(400)
    cv = divisiones(pliegue)
    referencia = rl_defecto(COLUMNAS)
    auc = [roc_auc_score(y.iloc[v], clone(referencia).fit(X.iloc[a], y.iloc[a]).predict_proba(X.iloc[v])[:, 1])
           for a, v in cv]
    for n_trials in (1, 6):
        resultado = buscar("rl", X, y, cv, n_trials, COLUMNAS, semilla=42)
        assert resultado["roc_auc_media_predeterminado"] == pytest.approx(np.mean(auc), abs=5e-5)
        assert resultado["roc_auc_media_busqueda"] >= resultado["roc_auc_media_predeterminado"]
    assert buscar("rl", X, y, cv, 1, COLUMNAS, semilla=42)["hiperparametros"] == PREDETERMINADOS["rl"]


# --- Equidad ----------------------------------------------------------------------------------------------------------

def test_equidad_tasas_por_subgrupo_y_diferencia_maxima():
    y = np.array([1, 1, 0, 0, 1, 1, 0, 0, 1, 0])
    p = np.array([.9, .1, .8, .2, .9, .9, .1, .1, .1, .1])
    atributos = pd.DataFrame({"gender": ["F", "F", "F", "F", "M", "M", "M", "M", None, None]})
    resultado = auditar(y, p, 0.5, atributos, {"gender": {"F": 40, "M": 12}}, 50, 42)["gender"]
    f, m, faltante = (resultado["subgrupos"][k] for k in ("F", "M", "faltante"))
    assert (f["n"], f["retiros"], f["sensibilidad"], f["tasa_falsos_positivos"]) == (4, 2, 0.5, 0.5)
    assert (m["sensibilidad"], m["tasa_falsos_positivos"]) == (1.0, 0.0)
    assert faltante["sensibilidad"] == 0.0
    assert resultado["diferencia_sensibilidad"] == 1.0 and resultado["diferencia_tasa_falsos_positivos"] == 0.5
    assert not f["solo_descriptiva"] and m["solo_descriptiva"] and faltante["solo_descriptiva"]
