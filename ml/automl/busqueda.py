"""Familias candidatas, espacios de búsqueda y optimización con Optuna (skill rigor-ml §3).

Cada ensayo ajusta el Pipeline en los 5 pliegues de D29-rev; el valor intermedio tras cada pliegue es la media
acumulada de ROC-AUC (D6) y el podador corta los ensayos que van por debajo de la mediana en el mismo paso.
El desbalance se trata con pesos de clase como hiperparámetro (D30), sin sobremuestreo.
"""

from __future__ import annotations

import time

import numpy as np
import optuna
import pandas as pd
from catboost import CatBoostClassifier
from lightgbm import LGBMClassifier
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.neural_network import MLPClassifier
from sklearn.pipeline import Pipeline
from sklearn.utils.class_weight import compute_sample_weight
from xgboost import XGBClassifier

from automl.preprocesado import codificador

# Orden de simplicidad de D33 (menor = más simple); el apilamiento (D48) va después de todas.
FAMILIAS = ["rl", "rf", "gb", "xgb", "lgbm", "catboost", "mlp"]
COMPLEJIDAD = {"rl": 0, "rf": 1, "gb": 1, "xgb": 1, "lgbm": 1, "catboost": 1, "mlp": 2, "apilamiento": 3}
ESCALAR = {"rl", "mlp"}

# (tipo, mínimo, máximo) o ("categorica", [opciones]). Se exportan tal cual al experimento (Anexo C).
ESPACIOS: dict[str, dict[str, tuple]] = {
    "rl": {
        "C": ("float_log", 1e-4, 1e2),
        "l1_ratio": ("categorica", [0.0, 1.0]),
        "class_weight": ("categorica", [None, "balanced"]),
    },
    "rf": {
        "n_estimators": ("int", 100, 500),
        "max_depth": ("int", 3, 30),
        "min_samples_leaf": ("int_log", 1, 100),
        "max_features": ("categorica", ["sqrt", 0.3, 0.5]),
        "class_weight": ("categorica", [None, "balanced", "balanced_subsample"]),
    },
    "gb": {
        "learning_rate": ("float_log", 0.01, 0.3),
        "max_iter": ("int", 100, 600),
        "max_leaf_nodes": ("int_log", 8, 128),
        "min_samples_leaf": ("int_log", 10, 300),
        "l2_regularization": ("float_log", 1e-6, 10.0),
        "class_weight": ("categorica", [None, "balanced"]),
    },
    "xgb": {
        "n_estimators": ("int", 100, 600),
        "learning_rate": ("float_log", 0.01, 0.3),
        "max_depth": ("int", 2, 10),
        "min_child_weight": ("float_log", 1.0, 50.0),
        "subsample": ("float", 0.5, 1.0),
        "colsample_bytree": ("float", 0.4, 1.0),
        "reg_lambda": ("float_log", 1e-3, 10.0),
        "class_weight": ("categorica", [None, "balanced"]),
    },
    "lgbm": {
        "n_estimators": ("int", 100, 600),
        "learning_rate": ("float_log", 0.01, 0.3),
        "num_leaves": ("int_log", 8, 256),
        "min_child_samples": ("int_log", 5, 300),
        "subsample": ("float", 0.5, 1.0),
        "colsample_bytree": ("float", 0.4, 1.0),
        "reg_lambda": ("float_log", 1e-3, 10.0),
        "class_weight": ("categorica", [None, "balanced"]),
    },
    "catboost": {
        "iterations": ("int", 200, 800),
        "learning_rate": ("float_log", 0.01, 0.3),
        "depth": ("int", 4, 8),
        "l2_leaf_reg": ("float_log", 1.0, 30.0),
        "class_weight": ("categorica", [None, "balanced"]),
    },
    "mlp": {
        "hidden_layer_sizes": ("categorica", ["64", "128", "64-32", "128-64"]),
        "alpha": ("float_log", 1e-5, 1e-1),
        "learning_rate_init": ("float_log", 1e-4, 1e-2),
        "batch_size": ("categorica", [128, 256, 512]),
        "class_weight": ("categorica", [None, "balanced"]),
    },
}
# Primer ensayo de cada búsqueda (enqueue_trial): la optimizada nunca queda por debajo de la configuración por defecto
# en la métrica objetivo. Valores por defecto de cada biblioteca; donde caen fuera del espacio, el valor más cercano.
PREDETERMINADOS: dict[str, dict] = {
    "rl": {"C": 1.0, "l1_ratio": 0.0, "class_weight": None},
    "rf": {"n_estimators": 100, "max_depth": 30, "min_samples_leaf": 1, "max_features": "sqrt", "class_weight": None},
    "gb": {"learning_rate": 0.1, "max_iter": 100, "max_leaf_nodes": 31, "min_samples_leaf": 20,
           "l2_regularization": 1e-6, "class_weight": None},
    "xgb": {"n_estimators": 100, "learning_rate": 0.3, "max_depth": 6, "min_child_weight": 1.0, "subsample": 1.0,
            "colsample_bytree": 1.0, "reg_lambda": 1.0, "class_weight": None},
    "lgbm": {"n_estimators": 100, "learning_rate": 0.1, "num_leaves": 31, "min_child_samples": 20, "subsample": 1.0,
             "colsample_bytree": 1.0, "reg_lambda": 1e-3, "class_weight": None},
    "catboost": {"iterations": 800, "learning_rate": 0.03, "depth": 6, "l2_leaf_reg": 3.0, "class_weight": None},
    "mlp": {"hidden_layer_sizes": "128", "alpha": 1e-4, "learning_rate_init": 1e-3, "batch_size": 256,
            "class_weight": None},
}
PREDETERMINADOS_NOTA = ("primer ensayo encolado de cada familia; valores por defecto de la biblioteca salvo donde caen "
                        "fuera del espacio (valor por defecto entre paréntesis): rf max_depth 30 (None), "
                        "gb l2_regularization 1e-6 (0), lgbm reg_lambda 1e-3 (0), catboost iterations 800 (1000), "
                        "mlp hidden_layer_sizes 128 (100) y batch_size 256 (auto = 200). RL: C = 1, L2, sin pesos de "
                        "clase, idéntica a la referencia rl_defecto")
CONFIGURACION_FIJA = {
    "rl": "solver liblinear (l1_ratio 0 = L2, 1 = L1); saga con red elástica no convergía y multiplicaba el coste",
    "rf": "criterion gini; vacíos tratados de forma nativa",
    "gb": "HistGradientBoostingClassifier de scikit-learn, sin parada temprana",
    "xgb": "tree_method hist; class_weight 'balanced' = pesos por muestra inversos a la frecuencia de clase",
    "lgbm": "subsample_freq 1",
    "catboost": "class_weight 'balanced' = auto_class_weights Balanced",
    "mlp": "activación relu, adam, early_stopping con 10 % de validación interna, max_iter 300; "
           "class_weight 'balanced' = pesos por muestra",
}


class MLPPonderado(MLPClassifier):
    """MLPClassifier con pesos de clase (D30), que scikit-learn solo acepta como pesos por muestra."""

    def __init__(self, hidden_layer_sizes=(100,), alpha=1e-4, learning_rate_init=1e-3, batch_size="auto",
                 early_stopping=False, max_iter=200, random_state=None, class_weight=None):
        super().__init__(hidden_layer_sizes=hidden_layer_sizes, alpha=alpha, learning_rate_init=learning_rate_init,
                         batch_size=batch_size, early_stopping=early_stopping, max_iter=max_iter,
                         random_state=random_state)
        self.class_weight = class_weight

    def fit(self, X, y):
        pesos = compute_sample_weight(self.class_weight, y) if self.class_weight else None
        return super().fit(X, y, sample_weight=pesos)


class XGBPonderado(XGBClassifier):
    """XGBClassifier con pesos de clase (D30) como pesos por muestra."""

    def __init__(self, class_weight=None, **kwargs):
        super().__init__(**kwargs)
        self.class_weight = class_weight

    def fit(self, X, y):
        pesos = compute_sample_weight(self.class_weight, y) if self.class_weight else None
        return super().fit(X, y, sample_weight=pesos, verbose=False)

    def get_xgb_params(self):
        params = super().get_xgb_params()
        params.pop("class_weight", None)  # no es un parámetro del booster
        return params


def estimador(familia: str, params: dict, semilla: int, n_jobs: int):
    p = dict(params)
    if familia == "rl":
        return LogisticRegression(solver="liblinear", random_state=semilla, **p)
    if familia == "rf":
        return RandomForestClassifier(random_state=semilla, n_jobs=n_jobs, **p)
    if familia == "gb":
        return HistGradientBoostingClassifier(early_stopping=False, random_state=semilla, **p)
    if familia == "xgb":
        return XGBPonderado(tree_method="hist", random_state=semilla, n_jobs=n_jobs, **p)
    if familia == "lgbm":
        return LGBMClassifier(subsample_freq=1, random_state=semilla, n_jobs=n_jobs, verbose=-1, **p)
    if familia == "catboost":
        pesos = "Balanced" if p.pop("class_weight", None) == "balanced" else None
        return CatBoostClassifier(auto_class_weights=pesos, random_seed=semilla, thread_count=n_jobs, verbose=0,
                                  allow_writing_files=False, **p)
    if familia == "mlp":
        capas = tuple(int(c) for c in p.pop("hidden_layer_sizes", "100").split("-"))
        return MLPPonderado(hidden_layer_sizes=capas, early_stopping=True, max_iter=300, random_state=semilla, **p)
    raise ValueError(f"Familia desconocida: {familia}")


def construir(familia: str, params: dict, numericas: list[str], categoricas: list[str], imputar_mediana: list[str],
              semilla: int = 42, n_jobs: int = 1) -> Pipeline:
    return Pipeline([
        ("preprocesado", codificador(numericas, categoricas, imputar_mediana, escalar=familia in ESCALAR)),
        ("modelo", estimador(familia, params, semilla, n_jobs)),
    ])


def sugerir(ensayo: optuna.Trial, espacio: dict[str, tuple]) -> dict:
    params = {}
    for nombre, (tipo, *rango) in espacio.items():
        if tipo == "categorica":
            params[nombre] = ensayo.suggest_categorical(nombre, rango[0])
        elif tipo.startswith("int"):
            params[nombre] = ensayo.suggest_int(nombre, rango[0], rango[1], log=tipo.endswith("log"))
        else:
            params[nombre] = ensayo.suggest_float(nombre, rango[0], rango[1], log=tipo.endswith("log"))
    return params


def predecir(modelo, X: pd.DataFrame) -> np.ndarray:
    return modelo.predict_proba(X)[:, 1]


def buscar(familia: str, X: pd.DataFrame, y: pd.Series, cv: list, n_trials: int, columnas: dict,
           semilla: int = 42, n_jobs: int = 1, semilla_modelos: int = 42) -> dict:
    """TPE con poda por mediana; objetivo = media de ROC-AUC en los pliegues de cv. `semilla` es la del muestreador
    (semillas.optuna) y `semilla_modelos` la de cada modelo ajustado (semillas.modelos)."""

    def objetivo(ensayo: optuna.Trial) -> float:
        params = sugerir(ensayo, ESPACIOS[familia])
        valores = []
        for paso, (ajuste, validacion) in enumerate(cv):
            modelo = construir(familia, params, **columnas, semilla=semilla_modelos, n_jobs=n_jobs)
            modelo.fit(X.iloc[ajuste], y.iloc[ajuste])
            valores.append(roc_auc_score(y.iloc[validacion], predecir(modelo, X.iloc[validacion])))
            ensayo.report(float(np.mean(valores)), paso)
            if ensayo.should_prune():
                raise optuna.TrialPruned()
        return float(np.mean(valores))

    inicio = time.perf_counter()
    estudio = optuna.create_study(
        direction="maximize",
        sampler=optuna.samplers.TPESampler(seed=semilla),
        pruner=optuna.pruners.MedianPruner(n_startup_trials=5, n_warmup_steps=1),
    )
    optuna.logging.set_verbosity(optuna.logging.WARNING)
    estudio.enqueue_trial(PREDETERMINADOS[familia])
    estudio.optimize(objetivo, n_trials=n_trials)
    estados = [e.state for e in estudio.trials]
    return {
        "hiperparametros": estudio.best_params,
        "roc_auc_media_busqueda": round(estudio.best_value, 4),
        "roc_auc_media_predeterminado": round(estudio.trials[0].value, 4),
        "n_trials": n_trials,
        "n_completados": estados.count(optuna.trial.TrialState.COMPLETE),
        "n_podados": estados.count(optuna.trial.TrialState.PRUNED),
        "tiempo_busqueda_s": round(time.perf_counter() - inicio, 1),
    }


DESCRIPCION_OPTUNA = {
    "optimizador": "Optuna", "version": optuna.__version__,
    "muestreador": "TPESampler (semilla de la configuración, parámetros por defecto); primer ensayo encolado con la "
                   "configuración por defecto de la familia",
    # Valores efectivos de los parámetros por defecto de Optuna 5.0.0 para un objetivo único (los None de la firma se
    # resuelven dentro del muestreador); test_parametros_efectivos_de_optuna los contrasta con los objetos.
    "parametros_muestreador": {
        "n_startup_trials": 10, "n_ei_candidates": 24, "multivariate": True, "group": False, "constant_liar": True,
        "prior_weight": 1.0, "consider_magic_clip": True, "consider_endpoints": False,
        "gamma": "default_gamma: min(ceil(0,1·n), 25)",
        "weights": "default_weights: 1 para los 25 ensayos más recientes y rampa lineal para los anteriores",
    },
    "constant_liar_efecto": "ninguno: solo actúa con ensayos simultáneos y los ensayos se ejecutan en serie",
    "podador": "MedianPruner(n_startup_trials=5, n_warmup_steps=1); valor intermedio = media acumulada de ROC-AUC "
               "tras cada pliegue",
    "parametros_podador": {"percentil": 50.0, "n_startup_trials": 5, "n_warmup_steps": 1, "interval_steps": 1,
                           "n_min_trials": 1},
    "tiempo_maximo_por_busqueda": "ninguno: cada búsqueda termina al completar n_trials (timeout=None)",
    "metrica_objetivo": "roc_auc (media de los 5 pliegues agrupados por presentación)",
}
NIVEL_N_JOBS = ("n_jobs actúa dentro de cada modelo: hilos de rf, xgb, lgbm y catboost. Los ensayos de Optuna, los "
                "pliegues, la calibración y el apilamiento se ejecutan en serie. rl (liblinear) usa un hilo; gb "
                "(OpenMP) y mlp (BLAS de numpy) usan el paralelismo interno de su biblioteca, que n_jobs no controla")
