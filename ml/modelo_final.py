"""Modelo final por momento (D41, D31-rev), preparado sin evaluar en 2014J.

Para cada momento, el modelo desplegado del principal (la RL optimizada, D49-rev) con sus hiperparámetros y su método de
calibración (D38) se reentrena con las 15 presentaciones de entrenamiento y se calibra con CalibratedClassifierCV sobre
los 5 pliegues agrupados por presentación y ensemble=False (D54): el calibrador se ajusta con las predicciones
out-of-fold de los 5 pliegues y el modelo base se reentrena con todo el entrenamiento. Se le aplica el umbral fijado
sobre las predicciones out-of-fold calibradas de forma anidada del principal (D41), que se recalcula y debe coincidir con
su JSON. Se declara como aproximación: umbral y modelo final proceden de ajustes distintos.

Con el mismo procedimiento se prepara, sin desplegarlo, el modelo final de la variante con sensibles (P-13,
D8-concreción-rev): la misma RL con los hiperparámetros del principal, el método de calibración que eligió esa variante y
su propio umbral out-of-fold (registrado en su análisis de equidad), para informar ambas variantes en prueba. El JSON
registra también los parámetros efectivos de Optuna, que valen para el experimento principal (P-4).

Cada paquete guarda el modelo calibrado, el umbral, las columnas y el fondo del explicador, y `predecir_y_explicar` da,
para cualquier matrícula, la probabilidad calibrada, la alerta y su SHAP en log-odds sin calibrar (D32) por variable
original (OE4). 2014J no se lee: la evaluación única en prueba es de la Entrega 3.

Uso:
    python ml/modelo_final.py ml/configs/modelo_final.json
    python ml/modelo_final.py ml/configs/modelo_final.json --ensayo --semanas 4 --salida <carpeta fuera de evidencias/>
"""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV

from automl import busqueda
from automl.calibracion import METODOS, umbral
from automl.particion import divisiones
from cortes_oulad import ejecutar_pruebas
from evidencias import (
    EVIDENCIAS,
    actualizar_manifest,
    comprobar_arbol_limpio,
    escribir_json,
    hardware,
    ruta_registrada,
    sha256,
    siguiente_id,
    versiones_entorno,
)
from experimento import CALIBRACION_DEFINICION, OOF, cargar_cortes, cargar_entrenamiento, columnas_modelo, coma
from shap_estabilidad import agregar
from variante import predicciones_principal

MODELOS = OOF.parent / "modelos"  # data/procesado/modelos, no versionada


def entrenar_final(familia: str, hiperparametros: dict, metodo: str, X: pd.DataFrame, y: pd.Series,
                   pliegue: pd.Series, columnas: dict, semilla: int, n_jobs: int) -> CalibratedClassifierCV:
    """Modelo base con todo el entrenamiento y calibrador con las predicciones out-of-fold de los 5 pliegues agrupados
    (ensemble=False). `divisiones` falla si hay filas sin pliegue (las de 2014J)."""
    base = busqueda.construir(familia, hiperparametros, **columnas, semilla=semilla, n_jobs=n_jobs)
    return CalibratedClassifierCV(base, method=METODOS[metodo], cv=divisiones(pliegue), ensemble=False).fit(X, y)


def paquete(calibrado: CalibratedClassifierCV, corte: float, columnas: dict, X: pd.DataFrame, semana: int,
            origen: dict) -> dict:
    """Lo que necesita la plataforma para predecir y explicar: el modelo, el umbral transferido, las columnas y la media
    de las filas de entrenamiento transformadas (fondo del SHAP lineal)."""
    base = calibrado.calibrated_classifiers_[0].estimator
    return {"semana": semana, "modelo": calibrado, "umbral": corte, "columnas": columnas,
            "fondo": base.named_steps["preprocesado"].transform(X).mean(), "origen": origen}


def predecir_y_explicar(paquete_: dict, X: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Probabilidad calibrada, alerta (probabilidad ≥ umbral) y log-odds sin calibrar por matrícula, y su SHAP por
    variable original en log-odds sin calibrar (D32), con valor base en `base_log_odds`."""
    base = paquete_["modelo"].calibrated_classifiers_[0].estimator
    estimador = base.named_steps["modelo"]
    Xt = base.named_steps["preprocesado"].transform(X)
    coef = estimador.coef_[0]
    phi = (Xt - paquete_["fondo"]) * coef
    probabilidad = paquete_["modelo"].predict_proba(X)[:, 1]
    prediccion = pd.DataFrame({"probabilidad": probabilidad, "alerta": probabilidad >= paquete_["umbral"],
                               "log_odds": estimador.decision_function(Xt),
                               "base_log_odds": estimador.intercept_[0] + paquete_["fondo"].to_numpy() @ coef},
                              index=X.index)
    return prediccion, agregar(phi, paquete_["columnas"])


LECTURA_DIAGNOSTICO = ("diagnóstico de la aproximación del umbral transferido, dentro de la muestra y sesgado: no es "
                       "rendimiento")


def diagnostico_d41(y: pd.Series, alerta: pd.Series) -> dict:
    """Sensibilidad y tasa de alerta del modelo final con el umbral transferido sobre sus propias filas de entrenamiento
    (auditoría de exp-2026-10-29-03, O1). Es un diagnóstico de la aproximación D41, no una estimación del rendimiento."""
    y, alerta = y.to_numpy(), alerta.to_numpy()
    return {"sensibilidad_en_entrenamiento": round(float(alerta[y == 1].mean()), 4),
            "tasa_alerta_en_entrenamiento": round(float(alerta.mean()), 4),
            "lectura": LECTURA_DIAGNOSTICO}


def leer_oof(experimento: dict, semana: int, datos: pd.DataFrame) -> pd.DataFrame:
    ruta = OOF / f"{experimento['id']}_semana_{semana}.parquet"
    if sha256(ruta) != experimento["predicciones_oof_sha256"][ruta.name]:
        raise ValueError(f"{ruta.name} no coincide con el SHA-256 registrado en {experimento['id']}")
    return predicciones_principal(pd.read_parquet(ruta), datos)


def ajustar(datos: pd.DataFrame, columnas: dict, hiperparametros: dict, metodo: str, p_oof: np.ndarray,
            umbral_registrado: float, sensibilidad_minima: float, semilla: int, n_jobs: int,
            origen: dict) -> tuple[dict, dict]:
    """Modelo final de una variante: umbral recalculado desde sus OOF calibradas (debe coincidir con el registrado,
    D41), reentrenamiento con todo el entrenamiento y calibración sobre los 5 pliegues (D54)."""
    y, pliegue = datos["etiqueta"], datos["pliegue"]
    X = datos[columnas["numericas"] + columnas["categoricas"]]
    corte = umbral(y, p_oof, sensibilidad_minima)
    if round(corte, 6) != umbral_registrado:
        raise ValueError(f"semana {origen['semana']}: el umbral recalculado ({corte:.6f}) no coincide con el "
                         f"registrado ({umbral_registrado})")
    inicio = time.perf_counter()
    calibrado = entrenar_final("rl", hiperparametros, metodo, X, y, pliegue, columnas, semilla, n_jobs)
    resultado = paquete(calibrado, corte, columnas, X, origen["semana"], origen)
    prediccion, valores = predecir_y_explicar(resultado, X)
    base = calibrado.calibrated_classifiers_[0].estimator
    return {
        "modelo": "rl", "hiperparametros": hiperparametros,
        "calibracion": {"metodo": metodo, "cv": "5 pliegues agrupados por presentación (D29-rev)", "ensemble": False},
        "umbral": {"valor": round(corte, 6), "valor_exacto": float(corte), "origen": origen["umbral_de"]},
        "diagnostico_d41": diagnostico_d41(y, prediccion["alerta"]),
        "explicador": "lineal exacto en log-odds sin calibrar (D32) con fondo = media de las filas de entrenamiento "
                      "transformadas",
        "coeficientes_no_nulos": int((base.named_steps["modelo"].coef_[0] != 0).sum()),
        "columnas_transformadas": int(len(resultado["fondo"])),
        "aditividad_error_max": float(np.abs(valores.sum(axis=1).to_numpy() + prediccion["base_log_odds"].to_numpy()
                                             - prediccion["log_odds"].to_numpy()).max()),
        "tiempo_s": round(time.perf_counter() - inicio, 1),
    }, resultado


def momento(semana: int, principal: dict, con_sensibles: dict, equidad: dict, cortes: dict, columnas: dict,
            columnas_con: dict, n_jobs: int) -> tuple[dict, dict]:
    """Modelo final desplegado (la RL del principal) y, sin desplegar, el de la variante con sensibles (P-13,
    D8-concreción-rev: en prueba se informan ambas variantes)."""
    datos = cargar_entrenamiento(semana, cortes)
    sensibilidad_minima = principal["configuracion"]["sensibilidad_minima"]
    semilla = principal["particion"]["semillas"]["modelos"]
    resumen = next(m for m in principal["momentos"] if m["semana"] == semana)
    if resumen["modelo_desplegado"]["modelo"] != "rl":
        raise ValueError(f"semana {semana}: el desplegado es {resumen['modelo_desplegado']['modelo']}, no la RL")
    familia = next(f for f in resumen["familias"] if f["modelo"] == "rl")
    metodo = resumen["calibracion"]["metodo"]
    if familia["calibracion"]["metodo"] != metodo:
        raise ValueError(f"semana {semana}: el método de calibración del desplegado no es el de su familia")
    desplegado, paquete_desplegado = ajustar(
        datos, columnas, familia["hiperparametros"], metodo, leer_oof(principal, semana, datos)["p_rl"].to_numpy(),
        resumen["punto_operacion_oof"]["umbral"], sensibilidad_minima, semilla, n_jobs,
        {"experimento": principal["id"], "semana": semana, "variante": "principal", "desplegado": True,
         "umbral_de": f"punto_operacion_oof de {principal['id']} (D41), recalculado desde sus predicciones "
                      "out-of-fold calibradas de forma anidada"})

    rl_con = next(f for f in next(m for m in con_sensibles["momentos"] if m["semana"] == semana)["por_modelo"]
                  if f["modelo"] == "rl")
    if rl_con["hiperparametros"] != familia["hiperparametros"]:
        raise ValueError(f"semana {semana}: la variante con sensibles no usa los hiperparámetros del principal (D38)")
    equidad_con = next(m for m in equidad["momentos"] if m["semana"] == semana)["con"]
    if equidad_con["calibracion"] != rl_con["calibracion"]["metodo"]:
        raise ValueError(f"semana {semana}: el método de calibración de {equidad['id']} no es el de {con_sensibles['id']}")
    variante, paquete_variante = ajustar(
        datos, columnas_con, rl_con["hiperparametros"], rl_con["calibracion"]["metodo"],
        leer_oof(con_sensibles, semana, datos)["p_rl"].to_numpy(), equidad_con["punto_operacion_oof"]["umbral"],
        sensibilidad_minima, semilla, n_jobs,
        {"experimento": con_sensibles["id"], "semana": semana, "variante": "con_sensibles", "desplegado": False,
         "umbral_de": f"umbral out-of-fold propio de la variante (D45), recalculado desde las predicciones de "
                      f"{con_sensibles['id']} y registrado en {equidad['id']} ({con_sensibles['id']} no lo registra)"})
    resumen_final = {"semana": semana, "n": int(len(datos)), "retiros": int(datos["etiqueta"].sum()),
                     "presentaciones": int(datos["presentacion"].nunique()),
                     **desplegado,
                     "umbral": desplegado["umbral"] | {"punto_operacion_oof": resumen["punto_operacion_oof"]},
                     "con_sensibles": {"desplegado": False, **variante,
                                       "umbral": variante["umbral"] | {"punto_operacion_oof":
                                                                       equidad_con["punto_operacion_oof"]}}}
    return resumen_final, {"principal": paquete_desplegado, "con_sensibles": paquete_variante}


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
    leer = lambda id_exp: json.loads((EVIDENCIAS / "experimentos" / f"{id_exp}.json").read_text(encoding="utf-8"))  # noqa: E731
    con_sensibles, equidad = leer(config["con_sensibles_de"]), leer(config["umbral_con_sensibles_de"])
    if con_sensibles["hiperparametros_de"] != principal["id"] or equidad["experimentos"] != [principal["id"],
                                                                                             con_sensibles["id"]]:
        raise ValueError("La variante con sensibles o su equidad no proceden del experimento principal")

    inicio = time.perf_counter()
    salida: Path = args.salida
    commit = comprobar_arbol_limpio(salida)
    fecha = datetime.now()
    for carpeta in ("experimentos", "pruebas"):
        (salida / carpeta).mkdir(parents=True, exist_ok=True)
    id_exp = siguiente_id(salida / "experimentos", fecha)
    archivo_pruebas = f"pruebas/{id_exp}_pruebas.xml"
    resultado_pruebas = ejecutar_pruebas(salida / archivo_pruebas)
    carpeta_modelos = MODELOS if salida.resolve() == EVIDENCIAS.resolve() else salida / "modelos"
    carpeta_modelos.mkdir(parents=True, exist_ok=True)

    cortes, catalogo = cargar_cortes(principal["experimento_cortes"])
    columnas = columnas_modelo(catalogo, sin_sensibles=principal["configuracion"]["sin_sensibles"])
    columnas_con = columnas_modelo(catalogo, sin_sensibles=False)
    if any(columnas_con[c] != con_sensibles["variables"][c] for c in ("numericas", "categoricas")):
        raise ValueError(f"Las columnas con sensibles no son las de {con_sensibles['id']}")
    momentos, modelos_sha256 = [], {}
    for semana in semanas:
        print(f"semana {semana}", flush=True)
        resumen, paquetes = momento(semana, principal, con_sensibles, equidad, cortes, columnas, columnas_con,
                                    config["n_jobs"])
        for variante, resultado in paquetes.items():
            sufijo = "" if variante == "principal" else f"_{variante}"
            ruta = carpeta_modelos / f"{id_exp}{sufijo}_semana_{semana}.joblib"
            joblib.dump(resultado | {"origen": resultado["origen"] | {"id": id_exp, "commit": commit}}, ruta)
            modelos_sha256[ruta.name] = sha256(ruta)
        momentos.append(resumen)
        print(f"semana {semana}: umbral {resumen['umbral']['valor']} (con sensibles "
              f"{resumen['con_sensibles']['umbral']['valor']})", flush=True)

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
        "variables_con_sensibles": columnas_con,
        "con_sensibles": f"P-13 (D8-concreción-rev): modelo final de la variante con sensibles de {con_sensibles['id']}, "
                         "con los mismos hiperparámetros (D38), su propio método de calibración y su umbral out-of-fold; "
                         "no se despliega y solo se prepara para informar ambas variantes en prueba (Entrega 3)",
        "optuna": busqueda.DESCRIPCION_OPTUNA | {
            "vale_para": f"{principal['id']}: la construcción de TPESampler(seed) y MedianPruner es idéntica desde "
                         "e49f339 (código de ese experimento) y la versión de Optuna es la misma (P-4)"},
        "particion": principal["particion"],
        "reentrenamiento": "D41/D31-rev: modelo desplegado del principal (RL optimizada, D49-rev) con sus "
                           f"hiperparámetros y método de calibración de {principal['id']}, sin nueva búsqueda (D38), "
                           "reentrenado con las 15 presentaciones de entrenamiento; CalibratedClassifierCV sobre los 5 "
                           "pliegues agrupados con ensemble=False (D54): calibrador ajustado con sus predicciones "
                           "out-of-fold y modelo base reentrenado con todo el entrenamiento",
        "umbral_transferido": "D41: el umbral se fija sobre las predicciones out-of-fold calibradas de forma anidada "
                              f"del principal (sensibilidad mínima {coma(principal['configuracion']['sensibilidad_minima'], 2)}, "
                              "sin margen, D45) y se aplica al modelo final. Es una aproximación: el calibrador final se "
                              "ajusta de forma distinta a los anidados, así que la sensibilidad en prueba puede no ser "
                              "la out-of-fold",
        "calibracion_definicion": CALIBRACION_DEFINICION,
        "evaluado_en_prueba": False,
        "momentos": momentos,
        "metricas_test": None,
        "motivos_null": {"metricas_test": "D31-rev: la evaluación única en 2014J es de la Entrega 3; este experimento "
                                          "no lee filas de prueba"},
        "modelos_sha256": {"carpeta": ruta_registrada(carpeta_modelos)} | modelos_sha256,
        "entorno": versiones_entorno("pandas", "numpy", "pyarrow", "sklearn", "optuna", "joblib", "scipy", "pytest"),
        "hardware": hardware(),
        "n_jobs": {"valor": config["n_jobs"], "nivel": busqueda.NIVEL_N_JOBS},
        "pruebas": {"informe": archivo_pruebas} | resultado_pruebas,
        "tiempo_ejecucion_s": round(time.perf_counter() - inicio, 1),
        "figuras": [],
    }
    escribir_json(salida / "experimentos" / f"{id_exp}.json", experimento)
    actualizar_manifest(salida, fecha, commit, id_exp, [],
                        [{"archivo": archivo_pruebas, "descripcion": "JUnit de todas las pruebas de ml/tests en el "
                          "commit del experimento", "experimento": id_exp}])
    print(f"Exportado {id_exp} en {salida} (commit {commit})")


if __name__ == "__main__":
    main()
