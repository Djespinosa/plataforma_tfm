"""Variante con variables sensibles (D8) sobre un experimento principal, sin nueva búsqueda (D38).

Reentrena cada familia del experimento principal con sus hiperparámetros ya fijados (mismo momento y familia) y la
entrada con `gender`, `disability`, `age_band` e `imd_band`; misma calibración anidada (D37/D54), mismos pliegues y
mismas filas, y apilamiento (D48) con esos modelos. Compara, modelo a modelo, la ROC-AUC out-of-fold calibrada con y
sin sensibles (las predicciones "sin" son las del principal, comprobadas por SHA-256): diferencia = con − sin = coste de
excluirlas, con IC bootstrap pareado y p de DeLong.

Salvaguarda de D38: si en algún momento excluirlas cuesta ≥ 0,02 (estimación puntual) en algún candidato, o entre el
mejor candidato de cada variante, la configuración principal debería pasar a ser "con" y repetirse la búsqueda; el
script lo registra y lo avisa, no cambia nada por su cuenta. La ventaja medida es una cota inferior (la búsqueda se
hizo sin sensibles). Solo validación cruzada: 2014J no se lee.

Uso:
    python ml/variante.py ml/configs/con_sensibles.json
    python ml/variante.py ml/configs/con_sensibles.json --ensayo --semanas 0 --salida <carpeta fuera de evidencias/>
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
from sklearn.metrics import roc_auc_score  # noqa: E402

from automl import busqueda  # noqa: E402
from automl.apilamiento import oof_apilamiento  # noqa: E402
from automl.calibracion import elegir_metodo, oof_anidado  # noqa: E402
from automl.comparacion import auc_bootstrap, delong, intervalo  # noqa: E402
from cortes_oulad import SENSIBLES, ejecutar_pruebas  # noqa: E402
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
    BRIER_SIN_CALIBRAR_DEFINICION,
    CALIBRACION_DEFINICION,
    DPI,
    OOF,
    REJILLA,
    SERIES,
    TINTA,
    TINTA_SECUNDARIA,
    _estilo,
    cargar_cortes,
    cargar_entrenamiento,
    columnas_modelo,
    metricas,
)

MARGEN = 0.02


def reentrenar(familias: list[dict], X: pd.DataFrame, y: pd.Series, pliegue: pd.Series, columnas: dict,
               semilla: int, n_jobs: int, apilar: bool) -> tuple[list[dict], dict, dict]:
    """Cada familia con los hiperparámetros del principal (sin búsqueda) y la calibración anidada de los candidatos.
    Devuelve las filas, las predicciones calibradas con el método elegido y, aparte, las sin calibrar y las de cada
    método (para reproducir el JSON desde el parquet)."""
    filas, predicciones, modelos, otras = [], {}, {}, {}
    for familia in familias:
        nombre = familia["modelo"]
        print(f"    {nombre}", flush=True)
        inicio = time.perf_counter()
        modelo = busqueda.construir(nombre, familia["hiperparametros"], **columnas, semilla=semilla, n_jobs=n_jobs)
        oof = oof_anidado(modelo, X, y, pliegue)
        calibracion = elegir_metodo(y, oof)
        predicciones[nombre], modelos[nombre] = oof[calibracion["metodo"]], modelo
        otras |= {f"{nombre}_{metodo}": p for metodo, p in oof.items()}
        filas.append({"modelo": nombre, "hiperparametros": familia["hiperparametros"], "calibracion": calibracion,
                      "roc_auc_oof_sin_calibrar": round(roc_auc_score(y, oof["sin_calibrar"]), 4),
                      **metricas(y, predicciones[nombre], pliegue), "tiempo_s": round(time.perf_counter() - inicio, 1)})
    if apilar:
        print("    apilamiento", flush=True)
        inicio = time.perf_counter()
        predicciones["apilamiento"] = oof_apilamiento(modelos, X, y, pliegue, semilla=semilla)
        filas.append({"modelo": "apilamiento", "base": list(modelos),
                      "calibracion": "salida del metamodelo logístico, sin calibración adicional (D52)",
                      **metricas(y, predicciones["apilamiento"], pliegue),
                      "tiempo_s": round(time.perf_counter() - inicio, 1)})
    return filas, predicciones, otras


def predicciones_principal(oof: pd.DataFrame, datos: pd.DataFrame) -> pd.DataFrame:
    """OOF del principal alineadas fila a fila con el corte; falla si las filas no son las mismas y en el mismo orden."""
    claves = ["code_module", "code_presentation", "id_student", "pliegue", "etiqueta"]
    if len(oof) != len(datos) or not oof[claves].reset_index(drop=True).equals(datos[claves].reset_index(drop=True)):
        raise ValueError("Las predicciones del experimento principal no corresponden a las filas del corte")
    return oof


def contraste(y: pd.Series, p_con: np.ndarray, p_sin: np.ndarray, n_bootstrap: int, semilla: int) -> dict:
    """Diferencia de ROC-AUC out-of-fold con − sin sensibles (coste de excluirlas), pareada sobre las mismas filas."""
    central = delong(y, p_con, p_sin)
    muestras = auc_bootstrap(y, {"con": p_con, "sin": p_sin}, n_bootstrap, semilla)
    return {"roc_auc_con": round(central["roc_auc_a"], 4), "roc_auc_sin": round(central["roc_auc_b"], 4),
            "diferencia": round(central["diferencia"], 4),
            "ic95_bootstrap": [round(v, 4) for v in intervalo(muestras["con"] - muestras["sin"])],
            "delong_p": central["delong_p"], "alcanza_margen": bool(central["diferencia"] >= MARGEN)}


def salvaguarda(momentos: list[dict]) -> dict:
    """D38: se activa si en algún momento la diferencia con − sin alcanza el margen en algún candidato o entre los
    mejores candidatos de cada variante."""
    activadores = [
        {"semana": m["semana"], "comparacion": c["modelo"], "diferencia": c["diferencia"]}
        for m in momentos for c in [*m["por_modelo"], m["mejores"] | {"modelo": "mejor con − mejor sin"}]
        if c["alcanza_margen"]
    ]
    return {"regla": "D38: si excluir las sensibles cuesta ≥ 0,02 de ROC-AUC out-of-fold calibrada (estimación "
                     "puntual) en algún momento, en algún candidato o entre los mejores de cada variante, la "
                     "configuración principal pasa a ser 'con' y se repite la búsqueda",
            "margen": MARGEN, "activada": bool(activadores), "activadores": activadores}


def momento(semana: int, config: dict, principal: dict, cortes: dict, columnas: dict) -> tuple[dict, pd.DataFrame]:
    datos = cargar_entrenamiento(semana, cortes)
    X = datos[columnas["numericas"] + columnas["categoricas"]]
    y, pliegue = datos["etiqueta"], datos["pliegue"]
    resumen_principal = next(m for m in principal["momentos"] if m["semana"] == semana)
    sin = predicciones_principal(pd.read_parquet(OOF / f"{principal['id']}_semana_{semana}.parquet"), datos)
    semillas = principal["particion"]["semillas"]

    filas, predicciones, otras = reentrenar(resumen_principal["familias"], X, y, pliegue, columnas, semillas["modelos"],
                                     config["n_jobs"], principal["configuracion"]["apilamiento"])
    por_modelo = []
    for fila in filas:
        nombre = fila["modelo"]
        por_modelo.append(fila | contraste(y, predicciones[nombre], sin[f"p_{nombre}"].to_numpy(),
                                           config["n_bootstrap"], semillas["bootstrap"]))
    auc_con = {f["modelo"]: f["roc_auc_con"] for f in por_modelo}
    auc_sin = {f["modelo"]: f["roc_auc_sin"] for f in por_modelo}
    mejor_con, mejor_sin = max(auc_con, key=auc_con.get), max(auc_sin, key=auc_sin.get)
    mejores = {"mejor_con": mejor_con, "mejor_sin": mejor_sin,
               **contraste(y, predicciones[mejor_con], sin[f"p_{mejor_sin}"].to_numpy(), config["n_bootstrap"],
                           semillas["bootstrap"])}
    resumen = {"semana": semana, "n": int(len(y)), "retiros": int(y.sum()),
               "mejor_automl_principal": resumen_principal["mejor_automl"],
               "desplegado_principal": resumen_principal["modelo_desplegado"]["modelo"],
               "por_modelo": por_modelo, "mejores": mejores}
    oof = datos[["code_module", "code_presentation", "id_student", "pliegue", "etiqueta"]].copy()
    for nombre, p in (predicciones | otras).items():
        oof[f"p_{nombre}"] = p
    return resumen, oof


def lista_figuras(id_exp: str, sufijo: str = "") -> list[tuple[str, str]]:
    return [(f"figuras/{id_exp}_coste_excluir_sensibles{sufijo}.png",
             "Diferencia de ROC-AUC out-of-fold con − sin variables sensibles por modelo y momento, y entre el mejor "
             "candidato de cada variante (D8, D38)")]


def figura_diferencias(momentos: list[dict], ruta: Path) -> None:
    """Un panel por momento con eje x común: cada candidato y, en la última fila, mejor con − mejor sin."""
    fig, ejes = plt.subplots(1, len(momentos), figsize=(3.6 * len(momentos), 4.2), sharex=True, sharey=True,
                             squeeze=False)
    for ax, m in zip(ejes[0], momentos):
        filas = m["por_modelo"]
        for posiciones, grupo, marcador, color in ((np.arange(len(filas)), filas, "o", SERIES[0][0]),
                                                   ([len(filas) + 0.5], [m["mejores"]], "D", TINTA)):
            valores = np.array([f["diferencia"] for f in grupo])
            ic = np.array([f["ic95_bootstrap"] for f in grupo])
            ax.errorbar(valores, posiciones, xerr=[valores - ic[:, 0], ic[:, 1] - valores], fmt=marcador,
                        markersize=6, color=color, ecolor=TINTA_SECUNDARIA, elinewidth=1, capsize=0)
        ax.axhline(len(filas) - 0.25, color=REJILLA, linewidth=1.2)
        ax.axvline(0, color=TINTA_SECUNDARIA, linewidth=0.8)
        ax.axvline(MARGEN, color=SERIES[1][0], linewidth=1.2, linestyle="--")
        ax.set_yticks([*range(len(filas)), len(filas) + 0.5],
                      [*(f["modelo"] for f in filas), "mejor con − mejor sin"])
        ax.set(title=f"Semana {m['semana']}", xlabel="ROC-AUC con − sin sensibles")
        ax.xaxis.set_major_locator(ticker.MultipleLocator(0.01))
        _estilo(ax)
    ejes[0][0].invert_yaxis()
    fig.suptitle("Coste de excluir las variables sensibles: diferencia de ROC-AUC out-of-fold con IC 95 %\n"
                 "rombo: mejor candidato con − mejor sin; línea discontinua: margen de 0,02",
                 color=TINTA, fontsize=10)
    fig.tight_layout()
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
    columnas = columnas_modelo(catalogo, sin_sensibles=False)
    momentos, oof_sha256 = [], {}
    for semana in semanas:
        print(f"semana {semana}", flush=True)
        inicio_momento = time.perf_counter()
        resumen, oof = momento(semana, config, principal, cortes, columnas)
        resumen["tiempo_s"] = round(time.perf_counter() - inicio_momento, 1)
        ruta_oof = carpeta_oof / f"{id_exp}_semana_{semana}.parquet"
        oof.to_parquet(ruta_oof, index=False)
        oof_sha256[ruta_oof.name] = sha256(ruta_oof)
        momentos.append(resumen)
        print(f"semana {semana}: {resumen['tiempo_s']} s", flush=True)

    regla = salvaguarda(momentos)
    figuras = lista_figuras(id_exp)
    figura_diferencias(momentos, salida / figuras[0][0])

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
        "variables": columnas | {"sensibles_incluidas": SENSIBLES},
        "particion": principal["particion"],
        "reentrenamiento": "sin nueva búsqueda (D38): hiperparámetros de cada familia y momento tomados de "
                           f"{principal['id']}; mismos pliegues, filas y semillas; apilamiento (D48) con los modelos "
                           "de la variante. La ventaja de 'con' es una cota inferior (búsqueda hecha sin sensibles)",
        "comparacion": "por modelo, ROC-AUC out-of-fold calibrada con − sin sensibles sobre las mismas filas; las "
                       f"predicciones 'sin' son las de {principal['id']} (SHA-256 comprobado); IC bootstrap pareado "
                       "del 95 % sin ajustar y p de DeLong, que solo se informa",
        "calibracion_definicion": CALIBRACION_DEFINICION,
        "brier_sin_calibrar_definicion": BRIER_SIN_CALIBRAR_DEFINICION,
        "evaluado_en_prueba": False,
        "momentos": momentos,
        "salvaguarda_d38": regla,
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
    if regla["activada"]:
        print("AVISO: la salvaguarda de D38 se activa; no sigas con la F3 sin decidir la configuración principal:")
        for a in regla["activadores"]:
            print(f"  semana {a['semana']}, {a['comparacion']}: {a['diferencia']}")


if __name__ == "__main__":
    main()
