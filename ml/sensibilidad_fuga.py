"""Sensibilidad a la fuga (D20, D39) sobre el experimento principal, sin nueva búsqueda (D38).

Para cada momento se reentrenan, en la población que no excluye a los ya retirados (corte
`semana_<k>_sin_exclusion_retirados`, D39), el mejor AutoML (D44) y la RL optimizada desplegada (D49-rev) con sus
hiperparámetros del principal, mismas semillas y el método de calibración que eligió el principal (el apilamiento, la
salida del metamodelo, D52). La población con fuga contiene a la principal: los retirados añadidos entran en el pliegue de
su presentación. Las predicciones del principal son las de su JSON (SHA-256 comprobado).

Lectura primaria (D20): inflación = ROC-AUC del modelo con fuga en su población − ROC-AUC del principal en la suya.
Complementaria: el modelo con fuga en las filas comunes frente al principal (pareada, DeLong informativo). Descomposición:
inflación = [fuga(su población) − fuga(comunes)] (evaluar con los retirados) + [fuga(comunes) − principal] (entrenar con
ellos). Los tres IC salen del mismo bootstrap por estudiante sobre la población con fuga. Como los hiperparámetros se
buscaron sin fuga, la inflación es una cota inferior (D38). Solo validación cruzada: 2014J no se lee.

Uso:
    python ml/sensibilidad_fuga.py ml/configs/sin_exclusion_retirados.json
    python ml/sensibilidad_fuga.py ml/configs/sin_exclusion_retirados.json --ensayo --semanas 4 --salida <carpeta fuera de evidencias/>
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
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from ablacion import predecir_sin_grupo as predecir  # noqa: E402
from automl import busqueda  # noqa: E402
from automl.comparacion import auc_rapida, delong, intervalo  # noqa: E402
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

SUFIJO = "_sin_exclusion_retirados"
CLAVES = ["code_module", "code_presentation", "id_student"]
COMPONENTES = {"inflacion": "inflación (fuga en su población − principal)",
               "efecto_evaluar": "evaluar con los retirados (fuga: su población − comunes)",
               "efecto_entrenar": "entrenar con los retirados (comunes: fuga − principal)"}


def filas_comunes(fuga: pd.DataFrame, principal: pd.DataFrame) -> np.ndarray:
    """Máscara de las filas de la población con fuga que pertenecen a la principal; falla si no la contiene en el mismo
    orden, con los mismos pliegues y etiquetas, o si una presentación tiene más de un pliegue."""
    comun = fuga[CLAVES].merge(principal[CLAVES], how="left", indicator=True)["_merge"].eq("both").to_numpy()
    columnas = CLAVES + ["pliegue", "etiqueta"]
    if comun.sum() != len(principal) or not fuga.loc[comun, columnas].reset_index(drop=True).equals(
            principal[columnas].reset_index(drop=True)):
        raise ValueError("La población con fuga no contiene a la principal en el mismo orden y con los mismos pliegues")
    if fuga.groupby("presentacion")["pliegue"].nunique().max() != 1:
        raise ValueError("Hay presentaciones con más de un pliegue en la población con fuga")
    return comun


def bootstrap_por_estudiante(estudiante: np.ndarray, y: np.ndarray, p_fuga: np.ndarray, comun: np.ndarray,
                             p_principal: np.ndarray, n_bootstrap: int, semilla: int) -> pd.DataFrame:
    """En cada réplica se remuestrean estudiantes con reemplazo (con todas sus matrículas) en la población con fuga; la
    ROC-AUC con fuga se calcula sobre la réplica y sobre sus filas comunes, y la del principal sobre esas mismas filas
    comunes. `p_principal` va alineada con las filas comunes."""
    _, codigo = np.unique(estudiante, return_inverse=True)
    n_estudiantes = codigo.max() + 1
    p_principal_fuga = np.full(len(y), np.nan)
    p_principal_fuga[comun] = p_principal
    rng = np.random.default_rng(semilla)
    filas = []
    while len(filas) < n_bootstrap:
        veces = np.bincount(rng.integers(0, n_estudiantes, n_estudiantes), minlength=n_estudiantes)
        indices = np.repeat(np.arange(len(y)), veces[codigo])
        comunes = indices[comun[indices]]
        if y[indices].min() == y[indices].max() or y[comunes].min() == y[comunes].max():
            continue  # réplica sin las dos clases: se descarta
        filas.append({"fuga_poblacion": auc_rapida(y[indices], p_fuga[indices]),
                      "fuga_comunes": auc_rapida(y[comunes], p_fuga[comunes]),
                      "principal": auc_rapida(y[comunes], p_principal_fuga[comunes])})
    return pd.DataFrame(filas)


def descomposicion(estudiante: np.ndarray, y: np.ndarray, p_fuga: np.ndarray, comun: np.ndarray,
                   p_principal: np.ndarray, n_bootstrap: int, semilla: int) -> dict:
    """Inflación total y sus dos componentes, con IC del mismo bootstrap; comprueba que los componentes suman."""
    fuga_poblacion = auc_rapida(y, p_fuga)
    pareada = delong(y[comun], p_fuga[comun], p_principal)
    fuga_comunes, principal = pareada["roc_auc_a"], pareada["roc_auc_b"]
    valores = {"inflacion": fuga_poblacion - principal, "efecto_evaluar": fuga_poblacion - fuga_comunes,
               "efecto_entrenar": fuga_comunes - principal}
    if abs(valores["inflacion"] - valores["efecto_evaluar"] - valores["efecto_entrenar"]) > 1e-12:
        raise ArithmeticError("Los componentes no suman la inflación")
    m = bootstrap_por_estudiante(estudiante, y, p_fuga, comun, p_principal, n_bootstrap, semilla)
    muestras = {"inflacion": m["fuga_poblacion"] - m["principal"],
                "efecto_evaluar": m["fuga_poblacion"] - m["fuga_comunes"],
                "efecto_entrenar": m["fuga_comunes"] - m["principal"]}
    componentes = {c: {"valor": round(v, 4), "ic95_bootstrap": [round(x, 4) for x in intervalo(muestras[c])]}
                   for c, v in valores.items()}
    componentes["efecto_entrenar"]["delong_p"] = pareada["delong_p"]
    return {"roc_auc_fuga_su_poblacion": round(fuga_poblacion, 4), "roc_auc_fuga_comunes": round(fuga_comunes, 4),
            "roc_auc_principal": round(principal, 4), **componentes, "suma_comprobada": True}


def poblacion(y: pd.Series) -> dict:
    return {"n": int(len(y)), "retiros": int(y.sum()), "prevalencia": round(float(y.mean()), 4)}


def momento(semana: int, config: dict, principal: dict, cortes: dict, columnas: dict) -> tuple[dict, pd.DataFrame]:
    datos = cargar_entrenamiento(semana, cortes)
    fuga = cargar_entrenamiento(semana, cortes, SUFIJO)
    comun = filas_comunes(fuga, datos)
    completo = predicciones_principal(pd.read_parquet(OOF / f"{principal['id']}_semana_{semana}.parquet"), datos)
    resumen_principal = next(m for m in principal["momentos"] if m["semana"] == semana)
    semillas = principal["particion"]["semillas"]
    desplegado = resumen_principal["modelo_desplegado"]["modelo"]
    if desplegado != "rl":
        raise ValueError(f"semana {semana}: el desplegado es {desplegado}, no la RL optimizada")

    y = fuga["etiqueta"]
    X = fuga[columnas["numericas"] + columnas["categoricas"]]
    oof = fuga[CLAVES + ["pliegue", "etiqueta"]].assign(comun=comun)
    modelos = []
    for papel, modelo in (("mejor_automl", resumen_principal["mejor_automl"]), ("rl_desplegada", desplegado)):
        print(f"    {papel} ({modelo})", flush=True)
        inicio = time.perf_counter()
        familia = next((f for f in resumen_principal["familias"] if f["modelo"] == modelo), None)
        p = predecir(modelo, resumen_principal, X, y, fuga["pliegue"], columnas, semillas["modelos"], config["n_jobs"])
        oof[f"p_{papel}"] = p
        modelos.append({"papel": papel, "modelo": modelo,
                        "calibracion": familia["calibracion"]["metodo"] if familia else
                        "salida del metamodelo logístico, sin calibración adicional (D52)",
                        **descomposicion(fuga["id_student"].to_numpy(), y.to_numpy(), p, comun,
                                         completo[f"p_{modelo}"].to_numpy(), config["n_bootstrap"],
                                         semillas["bootstrap"]),
                        "tiempo_s": round(time.perf_counter() - inicio, 1)})
    resumen = {"semana": semana, "poblaciones": {"principal": poblacion(datos["etiqueta"]), "con_fuga": poblacion(y),
                                                 "retirados_anadidos": int((~comun).sum())},
               "modelos": modelos}
    return resumen, oof


def lista_figuras(id_exp: str, sufijo: str = "") -> list[tuple[str, str]]:
    return [(f"figuras/{id_exp}_sensibilidad_fuga{sufijo}.png",
             "Inflación de la ROC-AUC out-of-fold por no excluir a los ya retirados y su descomposición (evaluar y "
             "entrenar con ellos), mejor AutoML y RL desplegada por momento (D20, D39)")]


def figura_inflacion(momentos: list[dict], ruta: Path) -> None:
    """Un panel por modelo con eje y común; en cada momento, la inflación y sus dos componentes con su IC."""
    papeles = {"mejor_automl": "Mejor AutoML", "rl_desplegada": "RL desplegada"}
    fig, ejes = plt.subplots(1, 2, figsize=(9, 4.4), sharey=True)
    semanas = [m["semana"] for m in momentos]
    for ax, (papel, titulo) in zip(ejes, papeles.items()):
        for (componente, etiqueta), (color, _), marcador, desplazamiento in zip(
                COMPONENTES.items(), SERIES, ("o", "s", "^"), (-0.2, 0, 0.2)):
            filas = [next(r for r in m["modelos"] if r["papel"] == papel)[componente] for m in momentos]
            valores = np.array([f["valor"] for f in filas])
            ic = np.array([f["ic95_bootstrap"] for f in filas])
            ax.errorbar(np.arange(len(semanas)) + desplazamiento, valores, yerr=[valores - ic[:, 0], ic[:, 1] - valores],
                        fmt=marcador, markersize=5, color=color, ecolor=TINTA_SECUNDARIA, elinewidth=1, capsize=0,
                        label=etiqueta)
        modelos = [next(r for r in m["modelos"] if r["papel"] == papel)["modelo"] for m in momentos]
        ax.set_xticks(np.arange(len(semanas)), [f"{s}\n({mod})" if papel == "mejor_automl" else str(s)
                                                for s, mod in zip(semanas, modelos)])
        ax.axhline(0, color=TINTA_SECUNDARIA, linewidth=0.8)
        ax.set(title=titulo, xlabel="Semana", ylabel="Diferencia de ROC-AUC out-of-fold")
        ax.title.set_fontsize(9)
        _estilo(ax)
    fig.legend(*ejes[0].get_legend_handles_labels(), loc="lower center", ncol=3, fontsize=7, frameon=False)
    fig.suptitle("Sensibilidad a la fuga (D20): no excluir a los ya retirados, con IC 95 %\n"
                 "hiperparámetros del principal (D38): la inflación es una cota inferior", color=TINTA, fontsize=10)
    fig.tight_layout(rect=(0, 0.07, 1, 1))
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
        resumen, oof = momento(semana, config, principal, cortes, columnas)
        resumen["tiempo_s"] = round(time.perf_counter() - inicio_momento, 1)
        ruta_oof = carpeta_oof / f"{id_exp}_semana_{semana}.parquet"
        oof.to_parquet(ruta_oof, index=False)
        oof_sha256[ruta_oof.name] = sha256(ruta_oof)
        momentos.append(resumen)
        print(f"semana {semana}: {resumen['tiempo_s']} s", flush=True)

    figuras = lista_figuras(id_exp)
    figura_inflacion(momentos, salida / figuras[0][0])

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
        "dataset": principal["dataset"] | {"cortes_sha256": {
            nombre: cortes["salidas_sha256"][nombre]
            for s in semanas for nombre in (f"semana_{s}.parquet", f"semana_{s}{SUFIJO}.parquet")}},
        "variables": columnas,
        "poblacion": "D39: la población con fuga solo deja de excluir a los ya retirados (date_unregistration ≤ 7k con "
                     "fecha ≥ 0); se mantienen la exclusión de las bajas anteriores al día 0 (D24), la matrícula tardía "
                     "(D34) y las eliminaciones de D26 y D27. Contiene a la principal: los retirados añadidos entran en "
                     "el pliegue de su presentación. En las filas comunes cambian solo los percentiles de cohorte, que se "
                     "calculan sobre la población de cada corte",
        "particion": principal["particion"],
        "reentrenamiento": "sin nueva búsqueda (D38): hiperparámetros de cada modelo y momento tomados de "
                           f"{principal['id']}; mismos pliegues por presentación y semillas. Las familias usan el método "
                           "de calibración que eligió el principal; el apilamiento, la salida del metamodelo (D52), y "
                           "solo se reentrena el apilamiento (misma ruta que la ablación; "
                           "test_oulad_ruta_abreviada_reproduce_el_principal_en_la_semana_8 en el JUnit). Los "
                           "hiperparámetros se buscaron sin fuga: la inflación es una cota inferior (D38)",
        "comparacion": "por modelo y momento: inflación = ROC-AUC out-of-fold del modelo con fuga en su población − la "
                       f"del principal ({principal['id']}, SHA-256 comprobado) en la suya (lectura primaria, D20). "
                       "Descomposición: efecto_evaluar = con fuga en su población − con fuga en las filas comunes; "
                       "efecto_entrenar = con fuga − principal en las filas comunes (pareada, p de DeLong que solo se "
                       "informa); inflación = efecto_evaluar + efecto_entrenar, comprobado sin redondear. IC del 95 % sin "
                       "ajustar de un mismo bootstrap por estudiante (todas sus matrículas) sobre la población con fuga: "
                       "en cada réplica, la ROC-AUC con fuga sobre la réplica y sobre sus filas comunes y la del "
                       "principal sobre esas filas comunes. El IC condiciona a las predicciones ajustadas y no recoge la "
                       "variabilidad del reentrenamiento (M1 de la auditoría de exp-2026-10-28-03; único control "
                       "documentado, en la semana 0: +0,0045 en el apilamiento y −0,0023 en la RL), así que las "
                       "diferencias de ese orden no se leen como efecto",
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
