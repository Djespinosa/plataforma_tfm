"""SHAP out-of-fold y su estabilidad entre pliegues (D9, D32, D33) sobre el experimento principal, sin nueva búsqueda (D38).

Para cada momento y pliegue externo se ajusta el modelo base sin calibrar con los hiperparámetros y la semilla del
principal en los otros 4 pliegues (el mismo modelo base que, con ensemble=False, recibe la calibración del principal) y
se explican las filas del pliegue en la escala sin calibrar, log-odds (D32). Modelos (planificación de evidencias de la
Entrega 2): la RL desplegada (D49-rev), con SHAP lineal exacto con fondo = filas de ajuste del pliegue, y el mejor AutoML
(D44) cuando es de árboles, con TreeSHAP. El apilamiento y el MLP necesitan el explicador de permutación (D33), que queda
para la Entrega 3.

Los valores SHAP de las columnas transformadas se suman por variable original (one-hot e indicador de faltante).
Importancia = media de |SHAP| por variable. Estabilidad (D9): Spearman de las importancias y solapamiento del top-10 entre
los 10 pares de pliegues, con media y rango, sin umbral. Solo validación cruzada: 2014J no se lee.

Uso:
    python ml/shap_estabilidad.py ml/configs/shap.json
    python ml/shap_estabilidad.py ml/configs/shap.json --ensayo --semanas 4 --salida <carpeta fuera de evidencias/>
"""

from __future__ import annotations

import argparse
import itertools
import json
import time
from datetime import datetime
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import shap  # noqa: E402
from scipy.stats import spearmanr  # noqa: E402

from automl import busqueda  # noqa: E402
from cortes_oulad import ejecutar_pruebas  # noqa: E402
from evidencias import (  # noqa: E402
    EVIDENCIAS,
    RAIZ,
    actualizar_manifest,
    comprobar_arbol_limpio,
    escribir_json,
    hardware,
    sha256,
    siguiente_id,
    versiones_entorno,
)
from experimento import (  # noqa: E402
    DPI,
    OOF,
    SERIES,
    TINTA,
    TINTA_SECUNDARIA,
    _estilo,
    cargar_cortes,
    cargar_entrenamiento,
    columnas_modelo,
)
from variante import predicciones_principal  # noqa: E402

TREESHAP = {"catboost"}  # mejor AutoML de árboles en exp-2026-10-27-01; otra familia necesitaría su salida bruta
PERMUTACION = {"apilamiento", "mlp"}
TOP = 10
PENDIENTE = ("explicador de permutación con muestra de fondo (D33): Entrega 3, según la planificación de evidencias de "
             "2026-10-23 (en la Entrega 2, SHAP out-of-fold solo con TreeSHAP y para el modelo desplegado)")


def variable_original(columna: str, columnas: dict) -> str:
    """Variable de la que procede una columna transformada (numérica, indicador de faltante o one-hot)."""
    if columna in columnas["numericas"]:
        return columna
    if columna.startswith("missingindicator_"):
        return columna.removeprefix("missingindicator_")
    candidatas = [c for c in columnas["categoricas"] if columna.startswith(f"{c}_")]
    if not candidatas:
        raise ValueError(f"No se reconoce la variable de la columna {columna}")
    return max(candidatas, key=len)


def agregar(phi: pd.DataFrame, columnas: dict) -> pd.DataFrame:
    """Suma los SHAP de las columnas transformadas por variable original; las variables que el pliegue descartó (sin
    valores) reciben 0."""
    variables = columnas["numericas"] + columnas["categoricas"]
    return phi.T.groupby([variable_original(c, columnas) for c in phi.columns]).sum().T.reindex(columns=variables,
                                                                                                 fill_value=0.0)


def explicar(modelo, X_ajuste: pd.DataFrame, X_validacion: pd.DataFrame) -> tuple[pd.DataFrame, np.ndarray, str]:
    """SHAP en log-odds sin calibrar del modelo base ya ajustado, con su salida bruta para comprobar la aditividad."""
    preprocesado, estimador = modelo.named_steps["preprocesado"], modelo.named_steps["modelo"]
    Xa, Xv = preprocesado.transform(X_ajuste), preprocesado.transform(X_validacion)
    if hasattr(estimador, "coef_"):  # lineal: phi_j = coef_j (x_j − media de ajuste), fondo = filas de ajuste
        coef = estimador.coef_[0]
        phi = (Xv - Xa.mean()) * coef
        base = estimador.intercept_[0] + Xa.mean().to_numpy() @ coef
        bruta = estimador.decision_function(Xv)
        explicador = "lineal exacto (equivale a shap.LinearExplainer con fondo independiente = filas de ajuste)"
    else:
        arbol = shap.TreeExplainer(estimador)
        phi = pd.DataFrame(arbol.shap_values(Xv), index=Xv.index, columns=Xv.columns)
        base = float(np.ravel(arbol.expected_value)[0])
        bruta = estimador.predict(Xv, prediction_type="RawFormulaVal")
        explicador = "TreeSHAP (shap.TreeExplainer, tree_path_dependent)"
    error = np.abs(phi.sum(axis=1).to_numpy() + base - bruta)
    return phi, error, explicador


def estabilidad(importancias: pd.DataFrame) -> dict:
    """Spearman y solapamiento del top-10 entre cada par de pliegues (filas de `importancias`), con media y rango."""
    rhos, solapes = [], []
    for a, b in itertools.combinations(importancias.index, 2):
        rhos.append(spearmanr(importancias.loc[a], importancias.loc[b]).statistic)
        top = lambda f: set(importancias.loc[f].nlargest(TOP).index)  # noqa: E731
        solapes.append(len(top(a) & top(b)) / TOP)
    redondear = lambda v: round(float(v), 4)  # noqa: E731
    return {"pares": len(rhos), "spearman_media": redondear(np.mean(rhos)),
            "spearman_rango": [redondear(min(rhos)), redondear(max(rhos))],
            "top10_solape_media": redondear(np.mean(solapes)),
            "top10_solape_rango": [redondear(min(solapes)), redondear(max(solapes))]}


def shap_oof(modelo: str, familia: dict, X: pd.DataFrame, y: pd.Series, pliegue: pd.Series, p_principal: np.ndarray,
             columnas: dict, semilla: int, n_jobs: int) -> tuple[dict, pd.DataFrame]:
    inicio = time.perf_counter()
    agregados, errores, concordancias = [], [], []
    for f in sorted(pliegue.unique()):
        ajuste, validacion = (pliegue != f).to_numpy(), (pliegue == f).to_numpy()
        base = busqueda.construir(modelo, familia["hiperparametros"], **columnas, semilla=semilla, n_jobs=n_jobs)
        base.fit(X[ajuste], y[ajuste])
        phi, error, explicador = explicar(base, X[ajuste], X[validacion])
        bruta = phi.sum(axis=1).to_numpy()
        # El calibrador es monótono (D32): el orden de la salida bruta debe coincidir con el de la OOF del principal.
        concordancias.append(spearmanr(bruta, p_principal[validacion]).statistic)
        agregados.append(agregar(phi, columnas).assign(pliegue=f))
        errores.append(error.max())
    valores = pd.concat(agregados).loc[X.index]
    por_pliegue = valores.abs().groupby("pliegue").mean()
    global_ = valores.drop(columns="pliegue").abs().mean()
    importancia = [{"variable": v, "media_abs": round(float(global_[v]), 4),
                    "rango_pliegues": [round(float(por_pliegue[v].min()), 4), round(float(por_pliegue[v].max()), 4)]}
                   for v in global_.sort_values(ascending=False).index]
    return ({"explicador": explicador, "salida": "log-odds sin calibrar (D32)",
             "coste_s": round(time.perf_counter() - inicio, 1),
             "aditividad_error_max": float(max(errores)),
             "concordancia_con_oof_principal_spearman_min": round(float(min(concordancias)), 4),
             "importancia_global": importancia, "estabilidad": estabilidad(por_pliegue)},
            valores.drop(columns="pliegue"))


def momento(semana: int, config: dict, principal: dict, cortes: dict, columnas: dict) -> tuple[dict, pd.DataFrame]:
    datos = cargar_entrenamiento(semana, cortes)
    y, pliegue = datos["etiqueta"], datos["pliegue"]
    X = datos[columnas["numericas"] + columnas["categoricas"]]
    completo = predicciones_principal(pd.read_parquet(OOF / f"{principal['id']}_semana_{semana}.parquet"), datos)
    resumen_principal = next(m for m in principal["momentos"] if m["semana"] == semana)
    desplegado = resumen_principal["modelo_desplegado"]["modelo"]
    if desplegado != "rl":
        raise ValueError(f"semana {semana}: el desplegado es {desplegado}, no la RL optimizada")
    familias = {f["modelo"]: f for f in resumen_principal["familias"]}

    oof = datos[["code_module", "code_presentation", "id_student", "pliegue", "etiqueta"]].copy()
    modelos = []
    for papel, modelo in (("rl_desplegada", desplegado), ("mejor_automl", resumen_principal["mejor_automl"])):
        if modelo in PERMUTACION:
            modelos.append({"papel": papel, "modelo": modelo, "explicador": None, "motivo": PENDIENTE})
            continue
        if modelo != "rl" and modelo not in TREESHAP:
            raise ValueError(f"semana {semana}: sin explicador implementado para {modelo}")
        print(f"    {papel} ({modelo})", flush=True)
        resumen, valores = shap_oof(modelo, familias[modelo], X, y, pliegue, completo[f"p_{modelo}"].to_numpy(),
                                    columnas, principal["particion"]["semillas"]["modelos"], config["n_jobs"])
        oof = oof.join(valores.add_prefix(f"shap_{papel}__"))
        modelos.append({"papel": papel, "modelo": modelo, **resumen})
    return {"semana": semana, "n": int(len(y)), "retiros": int(y.sum()), "modelos": modelos}, oof


def lista_figuras(id_exp: str, papeles: list[str], sufijo: str = "") -> list[tuple[str, str]]:
    nombres = {"rl_desplegada": "la RL desplegada", "mejor_automl": "el mejor AutoML de árboles"}
    return [(f"figuras/{id_exp}_shap_{papel}{sufijo}.png",
             f"Importancia SHAP global out-of-fold (media de |SHAP| en log-odds sin calibrar) de {nombres[papel]} por "
             "momento, con el rango entre pliegues y la estabilidad entre pliegues (D9, D32)") for papel in papeles]


def figura_importancia(momentos: list[dict], papel: str, ruta: Path, n_variables: int = 15) -> None:
    """Un panel por momento con el modelo de ese papel: top de variables por media de |SHAP| y su rango entre pliegues."""
    filas = [(m["semana"], next(r for r in m["modelos"] if r["papel"] == papel)) for m in momentos]
    filas = [(s, r) for s, r in filas if r["explicador"]]
    fig, ejes = plt.subplots(1, len(filas), figsize=(max(3.4 * len(filas) + 1.4, 5.5), 5.2), squeeze=False)
    maximo = max(v["rango_pliegues"][1] for _, r in filas for v in r["importancia_global"][:n_variables])
    for ax, (semana, r) in zip(ejes[0], filas):
        top = r["importancia_global"][:n_variables]
        valores = np.array([v["media_abs"] for v in top])
        rango = np.array([v["rango_pliegues"] for v in top])
        posiciones = np.arange(len(top))
        ax.barh(posiciones, valores, color=SERIES[0][0] if papel == "rl_desplegada" else SERIES[1][0], height=0.65)
        ax.errorbar(valores, posiciones, xerr=[valores - rango[:, 0], rango[:, 1] - valores], fmt="none",
                    ecolor=TINTA_SECUNDARIA, elinewidth=1, capsize=0)
        ax.set_yticks(posiciones, [v["variable"] for v in top], fontsize=7)
        ax.invert_yaxis()
        ax.set_xlim(0, maximo * 1.05)
        e = r["estabilidad"]
        ax.set_title(f"Semana {semana} ({r['modelo']})\nSpearman {e['spearman_media']:.2f}; top-10 "
                     f"{e['top10_solape_media']:.2f}".replace(".", ","), fontsize=8)
        ax.set_xlabel("media de |SHAP| (log-odds)", fontsize=8)
        _estilo(ax)
    fig.suptitle("Importancia SHAP global out-of-fold con el rango entre pliegues\n"
                 "contribución a la predicción del modelo, no causa; estabilidad = media entre los 10 pares de pliegues",
                 color=TINTA, fontsize=9)
    fig.tight_layout()
    fig.savefig(ruta, dpi=DPI)
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("configuracion", type=Path)
    parser.add_argument("--salida", type=Path, default=EVIDENCIAS, help="Carpeta de evidencias (por defecto evidencias/)")
    parser.add_argument("--ensayo", action="store_true", help="Ensayo cronometrado: exige --salida fuera de evidencias/")
    parser.add_argument("--semanas", type=int, nargs="+", help="Sustituye las semanas (solo con --ensayo)")
    args = parser.parse_args()

    config = json.loads(args.configuracion.read_text(encoding="utf-8"))
    principal = json.loads((EVIDENCIAS / "experimentos" / f"{config['hiperparametros_de']}.json")
                           .read_text(encoding="utf-8"))
    semanas = [m["semana"] for m in principal["momentos"]]
    if args.semanas or args.ensayo:
        if not args.ensayo or args.salida.resolve() == EVIDENCIAS.resolve():
            parser.error("Las sustituciones solo valen en un --ensayo con --salida fuera de evidencias/")
        semanas = args.semanas or semanas
    huellas = dict(principal["predicciones_oof_sha256"])
    huellas.pop("carpeta")
    for semana in semanas:
        nombre = f"{principal['id']}_semana_{semana}.parquet"
        if sha256(OOF / nombre) != huellas[nombre]:
            raise ValueError(f"{nombre} no coincide con el SHA-256 registrado en {principal['id']}")

    inicio = time.perf_counter()
    salida: Path = args.salida
    commit = comprobar_arbol_limpio(salida)
    fecha = datetime.now()
    for carpeta in ("experimentos", "figuras", "pruebas"):
        (salida / carpeta).mkdir(parents=True, exist_ok=True)
    id_exp = siguiente_id(salida / "experimentos", fecha)
    archivo_pruebas = f"pruebas/{id_exp}_pruebas.xml"
    resultado_pruebas = ejecutar_pruebas(salida / archivo_pruebas)
    carpeta_oof = OOF if salida.resolve() == EVIDENCIAS.resolve() else salida / "oof"
    carpeta_oof.mkdir(parents=True, exist_ok=True)

    cortes, catalogo = cargar_cortes(principal["experimento_cortes"])
    columnas = columnas_modelo(catalogo, sin_sensibles=principal["configuracion"]["sin_sensibles"])
    momentos, oof_sha256 = [], {}
    for semana in semanas:
        print(f"semana {semana}", flush=True)
        inicio_momento = time.perf_counter()
        resumen, oof = momento(semana, config, principal, cortes, columnas)
        resumen["tiempo_s"] = round(time.perf_counter() - inicio_momento, 1)
        ruta_oof = carpeta_oof / f"{id_exp}_shap_semana_{semana}.parquet"
        oof.to_parquet(ruta_oof, index=False)
        oof_sha256[ruta_oof.name] = sha256(ruta_oof)
        momentos.append(resumen)
        print(f"semana {semana}: {resumen['tiempo_s']} s", flush=True)

    papeles = [p for p in ("rl_desplegada", "mejor_automl")
               if any(r["papel"] == p and r["explicador"] for m in momentos for r in m["modelos"])]
    figuras = lista_figuras(id_exp, papeles)
    for papel, (archivo, _) in zip(papeles, figuras):
        figura_importancia(momentos, papel, salida / archivo)

    experimento = {
        "id": id_exp,
        "tipo": "modelado",
        "fecha": fecha.isoformat(timespec="seconds"),
        "commit": commit,
        "descripcion": f"{config['descripcion']} Configuración: {args.configuracion.as_posix()}.",
        "variante": config["variante"],
        "hiperparametros_de": principal["id"],
        "configuracion": config,
        "experimento_cortes": principal["experimento_cortes"],
        "dataset": principal["dataset"] | {"cortes_sha256": {f"semana_{s}.parquet":
                                                             cortes["salidas_sha256"][f"semana_{s}.parquet"]
                                                             for s in semanas}},
        "variables": columnas,
        "particion": principal["particion"],
        "reentrenamiento": "sin nueva búsqueda (D38): en cada pliegue externo, el modelo base sin calibrar con los "
                           f"hiperparámetros y la semilla de {principal['id']}, ajustado con los otros 4 pliegues: es el "
                           "modelo base que, con ensemble=False, recibe la calibración del principal (D54). "
                           "concordancia_con_oof_principal_spearman_min comprueba que su orden coincide con el de las "
                           "predicciones calibradas del principal (el calibrador es monótono; la isotónica crea empates)",
        "metodo": "SHAP de las filas de cada pliegue externo en log-odds sin calibrar (D32); los valores de las columnas "
                  "transformadas se suman por variable original (one-hot e indicador de faltante); las variables que "
                  "un pliegue descarta por no tener valores reciben 0. Importancia = media de |SHAP| por variable, "
                  "global (todas las filas out-of-fold) y por pliegue (rango). Estabilidad (D9, D9-concreción): "
                  f"Spearman de las importancias y solapamiento del top-{TOP} entre los 10 pares de pliegues, media y "
                  "rango, sin umbral. aditividad_error_max = máx. |Σ SHAP + valor base − salida bruta|. SHAP es "
                  "contribución a la predicción del modelo, no causa",
        "explicadores": {"rl": "lineal exacto con fondo = filas de ajuste del pliegue",
                         "arboles": "TreeSHAP (D33)", "apilamiento_y_mlp": PENDIENTE},
        "evaluado_en_prueba": False,
        "momentos": momentos,
        "metricas_test": None,
        "motivos_null": {"metricas_test": "Entrega 2: solo validación cruzada; 2014J se evalúa una vez en la Entrega 3",
                         "momentos.modelos.explicador": PENDIENTE},
        "predicciones_oof_sha256": {"carpeta": (carpeta_oof.resolve().relative_to(RAIZ)
                                                if carpeta_oof.resolve().is_relative_to(RAIZ)
                                                else carpeta_oof.resolve()).as_posix()} | oof_sha256,
        "entorno": versiones_entorno("pandas", "numpy", "pyarrow", "sklearn", "xgboost", "lightgbm", "catboost",
                                     "shap", "scipy", "matplotlib", "pytest"),
        "hardware": hardware(),
        "n_jobs": {"valor": config["n_jobs"], "nivel": busqueda.NIVEL_N_JOBS},
        "pruebas": {"informe": archivo_pruebas} | resultado_pruebas,
        "tiempo_ejecucion_s": round(time.perf_counter() - inicio, 1),
        "figuras": [archivo for archivo, _ in figuras],
    }
    escribir_json(salida / "experimentos" / f"{id_exp}.json", experimento)
    actualizar_manifest(salida, fecha, commit, id_exp,
                        [{"archivo": a, "descripcion": d, "experimento": id_exp} for a, d in figuras],
                        [{"archivo": archivo_pruebas, "descripcion": "JUnit de todas las pruebas de ml/tests en el "
                          "commit del experimento", "experimento": id_exp}])
    print(f"Exportado {id_exp} en {salida} (commit {commit})")


if __name__ == "__main__":
    main()
