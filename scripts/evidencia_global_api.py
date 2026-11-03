"""Evidencia de la explicación global del modelo OULAD en la plataforma (docs/diseno-api.md §0, matiz D-3).

Importa los paquetes desplegados de exp-2026-10-29-03 con el importador genérico en una base SQLite en memoria (no toca
la base de datos de la plataforma) y, por semana, pide GET /api/modelos/{id}/explicacion-global:
  - identidad: la respuesta debe ser exactamente (==, mismo orden) la media de |φ| de modelo_final.predecir_y_explicar
    sobre las mismas filas de referencia; si no lo es, no se exporta nada;
  - comparación descriptiva, sin umbral, con la importancia out-of-fold de la RL desplegada de exp-2026-10-29-02 (media
    de 5 modelos de pliegue) y las variables nulas de exp-2026-10-29-05: Spearman del orden completo (todas las
    variables y sin las nulas), solapamiento del top-10 y variables que cambian en el top-10.
No entrena nada ni lee 2014J: las filas de referencia (data/procesado/referencia, ml/referencia_oulad.py) deben ser
exactamente las de entrenamiento que reconstruye experimento.cargar_entrenamiento (SHA-256 de los cortes, sin 2014J), y
su SHA-256 queda registrado.

Está fuera de api/ y de ml/ porque cruza las dos capas con datos de OULAD: la API no sabe nada de OULAD (D10) y ml/ no
importa Flask. Se ejecuta desde la raíz del repositorio:

    python -m scripts.evidencia_global_api                    # a evidencias/ (árbol limpio)
    python -m scripts.evidencia_global_api --salida carpeta   # ensayo
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from datetime import datetime
from pathlib import Path

import joblib
import pandas as pd
from scipy.stats import spearmanr

from api import RAIZ, crear_app  # también pone ml/ en sys.path
from api.configuracion import Pruebas
from api.importar import importar
from api.tablas import Base
from cortes_oulad import ejecutar_pruebas
from evidencias import (EVIDENCIAS, actualizar_manifest, comprobar_arbol_limpio, escribir_json, sha256,
                        siguiente_id)
from experimento import cargar_cortes, cargar_entrenamiento
from modelo_final import predecir_y_explicar

FINAL, OOF, NULAS = "exp-2026-10-29-03", "exp-2026-10-29-02", "exp-2026-10-29-05"
TOP = 10  # el de shap_estabilidad.TOP


def leer(id_: str) -> dict:
    return json.loads((EVIDENCIAS / "experimentos" / f"{id_}.json").read_text(encoding="utf-8"))


def respuestas_api(modelos: Path, referencia: Path) -> dict[int, dict]:
    """Explicación global de cada semana tal como la devuelve la API tras importar los paquetes."""
    with tempfile.TemporaryDirectory() as temporal:
        app = crear_app(Pruebas(datos=Path(temporal)))
        Base.metadata.create_all(app.extensions["bd_motor"])
        with app.extensions["bd_sesiones"]() as sesion:
            importar(sesion, modelos, EVIDENCIAS / "experimentos", referencia)
        cliente = app.test_client()
        respuestas = {}
        for m in cliente.get("/api/modelos").get_json():
            if m["experimento_id"] == FINAL:
                semana = int(m["momento"].removeprefix("semana "))
                respuestas[semana] = cliente.get(f"/api/modelos/{m['id']}/explicacion-global").get_json()
        app.extensions["bd_motor"].dispose()
    return respuestas


def identidad(api: dict, paquete: dict, filas: pd.DataFrame, semana: int) -> dict:
    """Comprueba que la explicación global de la API es la media de |φ| de ml/ (aborta si no) y la resume."""
    _, phi = predecir_y_explicar(paquete, filas)
    sin = [s["variable"] for s in api["sin_contribucion"]]
    if not all((phi[v] == 0).all() for v in sin):
        sys.exit(f"Semana {semana}: una variable sin contribución en la API tiene φ distinto de 0 en ml/.")
    medias = phi.drop(columns=sin).abs().mean().sort_values(ascending=False, kind="stable")
    esperada = [(v, float(m)) for v, m in medias.items()]
    obtenida = [(i["variable"], i["importancia_media_abs"]) for i in api["variables"]]
    if obtenida != esperada:
        sys.exit(f"Semana {semana}: la explicación global de la API no es idéntica a la de ml/; no se exporta.")
    return {"identica": True, "variables": len(obtenida), "sin_contribucion": sin, "n_filas": len(filas)}


def posiciones(importancias: pd.Series) -> dict[str, int]:
    """Posición 1..n por importancia descendente (empates en el orden dado)."""
    orden = importancias.sort_values(ascending=False, kind="stable").index
    return {v: i + 1 for i, v in enumerate(orden)}


def comparar(api: pd.Series, oof: pd.Series, nulas: list[str]) -> dict:
    """api y oof: importancia por variable (las mismas variables). Spearman con todas y sin las nulas; top-10."""
    rho = lambda a, b: round(float(spearmanr(a, b[a.index]).statistic), 4)  # noqa: E731
    pos_api, pos_oof = posiciones(api), posiciones(oof)
    top_api = [v for v, p in pos_api.items() if p <= TOP]
    top_oof = {v for v, p in pos_oof.items() if p <= TOP}
    return {
        "todas": {"variables": len(api), "spearman": rho(api, oof)},
        "sin_nulas": {"variables": len(api) - len(nulas), "spearman": rho(api.drop(nulas), oof)},
        "variables_nulas": nulas,
        "top10": {"solape": round(len(set(top_api) & top_oof) / TOP, 4),
                  "entran": [v for v in top_api if v not in top_oof],
                  "salen": sorted(top_oof - set(top_api), key=pos_oof.get),
                  "cambian_posicion": [{"variable": v, "posicion_api": pos_api[v], "posicion_oof": pos_oof[v]}
                                       for v in top_api if v in top_oof and pos_api[v] != pos_oof[v]]},
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--salida", type=Path, default=EVIDENCIAS)
    parser.add_argument("--modelos", type=Path, default=RAIZ / "data" / "procesado" / "modelos")
    parser.add_argument("--referencia", type=Path, default=RAIZ / "data" / "procesado" / "referencia")
    args = parser.parse_args()
    commit = comprobar_arbol_limpio(args.salida)
    final, oof, nulas = leer(FINAL), leer(OOF), leer(NULAS)
    fecha = datetime.now()
    for carpeta in ("experimentos", "pruebas"):
        (args.salida / carpeta).mkdir(parents=True, exist_ok=True)
    id_exp = siguiente_id(args.salida / "experimentos", fecha)

    respuestas = respuestas_api(args.modelos, args.referencia)
    if sorted(respuestas) != [m["semana"] for m in final["momentos"]]:
        sys.exit(f"La API no tiene un modelo importado de {FINAL} por semana: {sorted(respuestas)}.")
    cortes, _ = cargar_cortes(final["experimento_cortes"])
    momentos = []
    for m in final["momentos"]:
        semana, api = m["semana"], respuestas[m["semana"]]
        archivo = args.modelos / f"{FINAL}_semana_{semana}.joblib"
        if sha256(archivo) != final["modelos_sha256"][archivo.name]:
            sys.exit(f"{archivo.name} no coincide con el SHA-256 registrado en {FINAL}.")
        paquete = joblib.load(archivo)
        ruta_referencia = args.referencia / f"{archivo.stem}.parquet"
        filas = pd.read_parquet(ruta_referencia)
        columnas = paquete["columnas"]["numericas"] + paquete["columnas"]["categoricas"]
        entrenamiento = cargar_entrenamiento(semana, cortes)[columnas].reset_index(drop=True)
        if len(filas) != m["n"] or not entrenamiento.equals(filas):
            sys.exit(f"Semana {semana}: las filas de referencia no son las de entrenamiento de {FINAL}.")
        resumen = identidad(api, paquete, filas, semana) | {"referencia_sha256": sha256(ruta_referencia)}
        rl = lambda e: next(x for x in next(n for n in e["momentos"] if n["semana"] == semana)["modelos"]  # noqa: E731
                            if x["papel"] == "rl_desplegada")
        importancia_oof = pd.Series({i["variable"]: i["media_abs"] for i in rl(oof)["importancia_global"]})
        importancia_api = pd.Series({i["variable"]: i["importancia_media_abs"] for i in api["variables"]}
                                    | dict.fromkeys(resumen["sin_contribucion"], 0.0))
        if set(importancia_api.index) != set(importancia_oof.index):
            sys.exit(f"Semana {semana}: las variables de la API y de {OOF} no son las mismas.")
        momentos.append({"semana": semana, "modelo": m["modelo"], "paquete": archivo.name,
                         "fuente_api": api["fuente"], "identidad": resumen,
                         "comparacion_oof": comparar(importancia_api, importancia_oof,
                                                     rl(nulas)["estabilidad"]["variables_nulas"])})

    archivo_pruebas = f"pruebas/{id_exp}_pruebas.xml"
    resultado_pruebas = ejecutar_pruebas(args.salida / archivo_pruebas)
    escribir_json(args.salida / "experimentos" / f"{id_exp}.json", {
        "id": id_exp, "tipo": "comparacion", "fecha": fecha.isoformat(timespec="seconds"), "commit": commit,
        "descripcion": f"Explicación global que da la API para el modelo final {FINAL} (D-3 del bloque E): identidad "
                       f"con ml/ y comparación descriptiva con la importancia out-of-fold de {OOF}, sin reentrenar.",
        "analisis": "explicacion_global_api",
        "experimentos": [FINAL, OOF, NULAS],
        "metodo": {
            "identidad": "paquetes desplegados de la carpeta de modelos importados con api/importar.py en SQLite en "
                         "memoria; GET /api/modelos/{id}/explicacion-global frente a la media de |SHAP| (log-odds sin "
                         "calibrar) de modelo_final.predecir_y_explicar sobre las mismas filas de referencia "
                         "(iguales a las de entrenamiento que reconstruye experimento.cargar_entrenamiento: 15 "
                         "presentaciones, sin 2014J; su SHA-256 en referencia_sha256), con igualdad exacta de "
                         "variables, orden y valores; las variables sin contribución de la API deben tener SHAP 0 en "
                         "todas las filas",
            "comparacion": f"descriptiva, sin umbral: compara el modelo final (una RL reentrenada con las 15 "
                           f"presentaciones, sobre sus filas de entrenamiento) con la media out-of-fold de 5 modelos de "
                           f"pliegue de {OOF} (importancia redondeada a 4 decimales); no son el mismo estimador. "
                           f"Spearman del orden completo con todas las variables (las sin contribución de la API, con "
                           f"importancia 0) y sin las variables nulas de {NULAS}; el top-10 no cambia al quitarlas "
                           f"(importancia 0). Posiciones por importancia descendente",
        },
        "lectura": "descriptiva: SHAP es contribución a la predicción del modelo, no causa",
        "evaluado_en_prueba": False,
        "modelos_sha256": {m["paquete"]: final["modelos_sha256"][m["paquete"]] for m in momentos},
        "momentos": momentos,
        "pruebas": {"informe": archivo_pruebas} | resultado_pruebas,
    })
    actualizar_manifest(args.salida, fecha, commit, id_exp, [],
                        [{"archivo": archivo_pruebas, "descripcion": "JUnit de todas las pruebas de ml/tests en el "
                          "commit del experimento", "experimento": id_exp}])
    for m in momentos:
        c = m["comparacion_oof"]
        print(f"semana {m['semana']}: idéntica; Spearman {c['todas']['spearman']} (sin nulas "
              f"{c['sin_nulas']['spearman']}), top-10 {c['top10']['solape']}")
    print(f"{id_exp} en {args.salida}")


if __name__ == "__main__":
    main()
