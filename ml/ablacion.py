"""Ablación por grupos de variables (D46) sobre el experimento principal, sin nueva búsqueda (D38).

Para cada momento se quita, uno a uno, cada grupo de `GRUPOS` (columna `grupo_ablacion` del catálogo, reparto D51-rev)
y se reentrenan dos modelos con sus hiperparámetros del principal: el mejor AutoML (D44) y la RL optimizada desplegada
(D49-rev). Mismos pliegues, filas y semillas. Las familias usan el método de calibración que eligió el principal y el
apilamiento, la salida del metamodelo (D52); para el apilamiento solo se reentrena el apilamiento, sin la calibración
por familia, que no interviene en él (la prueba con OULAD de la semana 8 comprueba que reproduce el principal).

Pérdida = ROC-AUC out-of-fold completo − sin el grupo, sobre las mismas filas; las predicciones "completo" son las del
principal (SHA-256 comprobado). IC bootstrap pareado y p de DeLong, que solo se informa. Como los hiperparámetros se
buscaron con todas las variables, la pérdida es una cota superior de la contribución de cada grupo. Solo validación
cruzada: 2014J no se lee.

Uso:
    python ml/ablacion.py ml/configs/ablacion.json
    python ml/ablacion.py ml/configs/ablacion.json --ensayo --semanas 4 --salida <carpeta fuera de evidencias/>
"""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib import ticker  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from automl import busqueda  # noqa: E402
from automl.apilamiento import oof_apilamiento  # noqa: E402
from automl.calibracion import oof_anidado  # noqa: E402
from automl.comparacion import auc_bootstrap, delong, intervalo  # noqa: E402
from cortes_oulad import GRUPOS, ejecutar_pruebas  # noqa: E402
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
    CALIBRACION_DEFINICION,
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

NOMBRE_GRUPO = {"demograficas_matricula": "demográficas y matrícula", "aula_virtual_clics": "aula virtual: clics",
                "aula_virtual_derivadas": "aula virtual: derivadas", "evaluaciones": "evaluaciones",
                "contexto_modulo": "contexto del módulo"}


def columnas_sin_grupo(columnas: dict, catalogo: pd.DataFrame, grupo: str) -> dict:
    quitar = set(catalogo.loc[catalogo["grupo_ablacion"] == grupo, "nombre"])
    return {clave: [c for c in lista if c not in quitar] for clave, lista in columnas.items()}


def predecir_sin_grupo(modelo: str, resumen_principal: dict, X: pd.DataFrame, y: pd.Series, pliegue: pd.Series,
                       columnas: dict, semilla: int, n_jobs: int) -> np.ndarray:
    """OOF del modelo con los hiperparámetros del principal y las columnas dadas, sin búsqueda (D38)."""
    familias = {f["modelo"]: f for f in resumen_principal["familias"]}
    construir = lambda f: busqueda.construir(f, familias[f]["hiperparametros"], **columnas,  # noqa: E731
                                            semilla=semilla, n_jobs=n_jobs)
    if modelo == "apilamiento":
        return oof_apilamiento({f: construir(f) for f in familias}, X, y, pliegue, semilla=semilla)
    return oof_anidado(construir(modelo), X, y, pliegue)[familias[modelo]["calibracion"]["metodo"]]


def perdida(y: pd.Series, p_completo: np.ndarray, p_sin_grupo: np.ndarray, n_bootstrap: int, semilla: int) -> dict:
    """Completo − sin el grupo (pérdida al quitarlo), pareada sobre las mismas filas."""
    central = delong(y, p_completo, p_sin_grupo)
    muestras = auc_bootstrap(y, {"completo": p_completo, "sin_grupo": p_sin_grupo}, n_bootstrap, semilla)
    return {"roc_auc_completo": round(central["roc_auc_a"], 4), "roc_auc_sin_grupo": round(central["roc_auc_b"], 4),
            "perdida": round(central["diferencia"], 4),
            "ic95_bootstrap": [round(v, 4) for v in intervalo(muestras["completo"] - muestras["sin_grupo"])],
            "delong_p": central["delong_p"]}


def momento(semana: int, config: dict, principal: dict, cortes: dict, catalogo: pd.DataFrame,
            columnas: dict) -> tuple[dict, pd.DataFrame]:
    datos = cargar_entrenamiento(semana, cortes)
    y, pliegue = datos["etiqueta"], datos["pliegue"]
    resumen_principal = next(m for m in principal["momentos"] if m["semana"] == semana)
    completo = predicciones_principal(pd.read_parquet(OOF / f"{principal['id']}_semana_{semana}.parquet"), datos)
    semillas = principal["particion"]["semillas"]
    desplegado = resumen_principal["modelo_desplegado"]["modelo"]
    if desplegado != "rl":
        raise ValueError(f"semana {semana}: el desplegado es {desplegado}, no la RL optimizada")

    oof = datos[["code_module", "code_presentation", "id_student", "pliegue", "etiqueta"]].copy()
    modelos = []
    for papel, modelo in (("mejor_automl", resumen_principal["mejor_automl"]), ("rl_desplegada", desplegado)):
        familia = next((f for f in resumen_principal["familias"] if f["modelo"] == modelo), None)
        filas = []
        for grupo in GRUPOS:
            print(f"    {papel} ({modelo}) sin {grupo}", flush=True)
            inicio = time.perf_counter()
            sin_grupo = columnas_sin_grupo(columnas, catalogo, grupo)
            X = datos[sin_grupo["numericas"] + sin_grupo["categoricas"]]
            p = predecir_sin_grupo(modelo, resumen_principal, X, y, pliegue, sin_grupo, semillas["modelos"],
                                   config["n_jobs"])
            oof[f"p_{papel}_sin_{grupo}"] = p
            filas.append({"grupo": grupo,
                          "variables_quitadas": len(columnas["numericas"]) + len(columnas["categoricas"])
                          - len(X.columns),
                          **perdida(y, completo[f"p_{modelo}"].to_numpy(), p, config["n_bootstrap"],
                                    semillas["bootstrap"]),
                          "tiempo_s": round(time.perf_counter() - inicio, 1)})
        modelos.append({"papel": papel, "modelo": modelo,
                        "calibracion": familia["calibracion"]["metodo"] if familia else
                        "salida del metamodelo logístico, sin calibración adicional (D52)",
                        "grupos": filas})
    resumen = {"semana": semana, "n": int(len(y)), "retiros": int(y.sum()), "modelos": modelos}
    return resumen, oof


def lista_figuras(id_exp: str, sufijo: str = "") -> list[tuple[str, str]]:
    return [(f"figuras/{id_exp}_ablacion{sufijo}.png",
             "Pérdida de ROC-AUC out-of-fold al quitar cada grupo de variables (completo − sin el grupo), mejor "
             "AutoML y RL desplegada por momento (D46)")]


def figura_perdidas(momentos: list[dict], ruta: Path) -> None:
    """Un panel por momento con eje x común; en cada grupo, el mejor AutoML y la RL desplegada."""
    fig, ejes = plt.subplots(1, len(momentos), figsize=(max(3.6 * len(momentos) + 1.6, 8), 4.6), sharex=True,
                             sharey=True, squeeze=False)
    estilos = {"mejor_automl": ("o", SERIES[0][0], -0.15), "rl_desplegada": ("s", SERIES[1][0], 0.15)}
    for ax, m in zip(ejes[0], momentos):
        for resumen in m["modelos"]:
            marcador, color, desplazamiento = estilos[resumen["papel"]]
            valores = np.array([g["perdida"] for g in resumen["grupos"]])
            ic = np.array([g["ic95_bootstrap"] for g in resumen["grupos"]])
            etiqueta = "RL desplegada" if resumen["papel"] == "rl_desplegada" else "mejor AutoML (modelo en el título)"
            ax.errorbar(valores, np.arange(len(valores)) + desplazamiento,
                        xerr=[valores - ic[:, 0], ic[:, 1] - valores], fmt=marcador, markersize=5, color=color,
                        ecolor=TINTA_SECUNDARIA, elinewidth=1, capsize=0, label=etiqueta)
        ax.axvline(0, color=TINTA_SECUNDARIA, linewidth=0.8)
        ax.set_yticks(np.arange(len(GRUPOS)), [NOMBRE_GRUPO[g] for g in GRUPOS])
        mejor = next(r["modelo"] for r in m["modelos"] if r["papel"] == "mejor_automl")
        ax.set(title=f"Semana {m['semana']} (mejor AutoML: {mejor})", xlabel="ROC-AUC completo − sin el grupo")
        ax.title.set_fontsize(9)
        ax.xaxis.set_major_locator(ticker.MaxNLocator(4))
        _estilo(ax)
    ejes[0][0].invert_yaxis()
    fig.legend(*ejes[0][0].get_legend_handles_labels(), loc="lower center", ncol=2, fontsize=8, frameon=False)
    fig.suptitle("Ablación por grupos de variables: pérdida de ROC-AUC out-of-fold con IC 95 %\n"
                 "hiperparámetros buscados con todas las variables: la pérdida es una estimación sesgada al alza "
                 "de la contribución",
                 color=TINTA, fontsize=10)
    fig.tight_layout(rect=(0, 0.06, 1, 1))
    fig.savefig(ruta, dpi=DPI)
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("configuracion", type=Path)
    parser.add_argument("--salida", type=Path, default=EVIDENCIAS, help="Carpeta de evidencias (por defecto evidencias/)")
    parser.add_argument("--ensayo", action="store_true", help="Ensayo cronometrado: exige --salida fuera de evidencias/")
    parser.add_argument("--semanas", type=int, nargs="+", help="Sustituye las semanas (solo con --ensayo)")
    parser.add_argument("--n-bootstrap", type=int, help="Sustituye n_bootstrap (solo con --ensayo)")
    args = parser.parse_args()

    config = json.loads(args.configuracion.read_text(encoding="utf-8"))
    principal = json.loads((EVIDENCIAS / "experimentos" / f"{config['hiperparametros_de']}.json")
                           .read_text(encoding="utf-8"))
    semanas = [m["semana"] for m in principal["momentos"]]
    if args.semanas or args.n_bootstrap or args.ensayo:
        if not args.ensayo or args.salida.resolve() == EVIDENCIAS.resolve():
            parser.error("Las sustituciones solo valen en un --ensayo con --salida fuera de evidencias/")
        semanas = args.semanas or semanas
        config["n_bootstrap"] = args.n_bootstrap or config["n_bootstrap"]
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
        resumen, oof = momento(semana, config, principal, cortes, catalogo, columnas)
        resumen["tiempo_s"] = round(time.perf_counter() - inicio_momento, 1)
        ruta_oof = carpeta_oof / f"{id_exp}_semana_{semana}.parquet"
        oof.to_parquet(ruta_oof, index=False)
        oof_sha256[ruta_oof.name] = sha256(ruta_oof)
        momentos.append(resumen)
        print(f"semana {semana}: {resumen['tiempo_s']} s", flush=True)

    figuras = lista_figuras(id_exp)
    figura_perdidas(momentos, salida / figuras[0][0])

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
        "grupos": {g: {"nombre": NOMBRE_GRUPO[g],
                       "variables": [c for c in columnas["numericas"] + columnas["categoricas"]
                                     if c in set(catalogo.loc[catalogo["grupo_ablacion"] == g, "nombre"])]}
                   for g in GRUPOS},
        "particion": principal["particion"],
        "reentrenamiento": "sin nueva búsqueda (D38): hiperparámetros de cada modelo y momento tomados de "
                           f"{principal['id']}; mismos pliegues, filas y semillas. Las familias usan el método de "
                           "calibración que eligió el principal; el apilamiento, la salida del metamodelo (D52), y "
                           "solo se reentrena el apilamiento (la calibración por familia no interviene en él; con "
                           "todas las variables reproduce el apilamiento del principal en la semana 8 con ROC-AUC "
                           "idéntica y diferencias ≤ 1e-9 por coma flotante en paralelo: "
                           "test_oulad_ruta_abreviada_reproduce_el_principal_en_la_semana_8 en el JUnit). Los "
                           "hiperparámetros se buscaron con todas las variables: la pérdida es una estimación sesgada al "
                           "alza de la contribución de cada grupo (D46)",
        "comparacion": "por modelo y grupo, ROC-AUC out-of-fold completo − sin el grupo sobre las mismas filas; las "
                       f"predicciones 'completo' son las de {principal['id']} (SHA-256 comprobado); IC bootstrap "
                       "pareado del 95 % sin ajustar y p de DeLong, que solo se informa",
        "calibracion_definicion": CALIBRACION_DEFINICION,
        "evaluado_en_prueba": False,
        "momentos": momentos,
        "metricas_test": None,
        "motivos_null": {"metricas_test": "Entrega 2: solo validación cruzada; 2014J se evalúa una vez en la Entrega 3"},
        "predicciones_oof_sha256": {"carpeta": (carpeta_oof.resolve().relative_to(RAIZ)
                                                if carpeta_oof.resolve().is_relative_to(RAIZ)
                                                else carpeta_oof.resolve()).as_posix()} | oof_sha256,
        "entorno": versiones_entorno("pandas", "numpy", "pyarrow", "sklearn", "optuna", "xgboost", "lightgbm",
                                     "catboost", "scipy", "matplotlib", "pytest"),
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
