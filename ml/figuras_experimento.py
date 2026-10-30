"""Regenera las figuras de un experimento de modelado desde su JSON y sus predicciones out-of-fold, sin reentrenar.

Las figuras nuevas llevan un sufijo propio y no sustituyen a las existentes; el manifiesto registra el commit con el
que se dibujaron. Las predicciones se comprueban contra los SHA-256 que registró el experimento. Las variantes (D8,
ablación, D20, SHAP) solo usan su JSON; en SHAP, `--estabilidad` toma la estabilidad sin variables nulas de un análisis
`shap_estabilidad_y_extremos` del mismo experimento (lectura principal).

Uso:
    python ml/figuras_experimento.py exp-2026-10-27-01 --sufijo _v2
    python ml/figuras_experimento.py exp-2026-10-28-01 --sufijo _v2   (variante D8: solo usa el JSON)
    python ml/figuras_experimento.py exp-2026-10-29-02 --sufijo _v2 --estabilidad exp-2026-10-29-04
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

import pandas as pd

import ablacion
import sensibilidad_fuga
import shap_estabilidad
import variante
from evidencias import EVIDENCIAS, RAIZ, actualizar_manifest, comprobar_arbol_limpio, sha256
from experimento import dibujar_figuras, lista_figuras

NOTA_SIN_NULAS = ", sin las variables con SHAP nulo en todos los pliegues"


def momentos_sin_nulas(momentos: list[dict], analisis: dict) -> list[dict]:
    """Copia de los momentos SHAP con la estabilidad `sin_nulas` del análisis en lugar de la de todas las variables."""
    if analisis.get("analisis") != "shap_estabilidad_y_extremos":
        raise ValueError(f"{analisis['id']} no es un análisis shap_estabilidad_y_extremos")
    sin_nulas = {(m["semana"], r["papel"]): r["estabilidad"] for m in analisis["momentos"] for r in m["modelos"]}
    copia = []
    for m in momentos:
        modelos = []
        for r in m["modelos"]:
            if r["explicador"]:
                e = sin_nulas[(m["semana"], r["papel"])]
                if e["todas"] | {"variables": None} != r["estabilidad"] | {"variables": None}:
                    raise ValueError(f"semana {m['semana']}: {analisis['id']} no procede de este experimento SHAP")
                r = r | {"estabilidad": e["sin_nulas"]}
            modelos.append(r)
        copia.append(m | {"modelos": modelos})
    return copia


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("experimento")
    parser.add_argument("--sufijo", required=True, help="Sufijo de los archivos nuevos (p. ej. _v2)")
    parser.add_argument("--salida", type=Path, default=EVIDENCIAS, help="Carpeta de evidencias (por defecto evidencias/)")
    parser.add_argument("--estabilidad", help="SHAP: análisis shap_estabilidad_y_extremos con la estabilidad sin nulas")
    args = parser.parse_args()

    commit = comprobar_arbol_limpio(args.salida)
    leer = lambda id_exp: json.loads((EVIDENCIAS / "experimentos" / f"{id_exp}.json").read_text(encoding="utf-8"))  # noqa: E731
    experimento = leer(args.experimento)
    momentos = experimento["momentos"]
    tipo = experimento.get("variante")
    tipo = None if tipo == "principal" else tipo
    if (args.estabilidad is not None) != (tipo == "shap"):
        parser.error("--estabilidad es obligatorio en los experimentos SHAP y solo vale en ellos")
    if tipo is None:
        huellas = dict(experimento["predicciones_oof_sha256"])
        carpeta = RAIZ / huellas.pop("carpeta")
        salidas = {}
        for resumen in momentos:
            ruta = carpeta / f"{args.experimento}_semana_{resumen['semana']}.parquet"
            if sha256(ruta) != huellas[ruta.name]:
                raise ValueError(f"{ruta.name} no coincide con el SHA-256 registrado en {args.experimento}")
            salidas[resumen["semana"]] = pd.read_parquet(ruta)
        figuras = lista_figuras(args.experimento, args.sufijo)
        dibujar = lambda: dibujar_figuras(momentos, salidas, args.salida, figuras)  # noqa: E731
    elif tipo == "shap":
        papeles = [p for p in ("rl_desplegada", "mejor_automl")
                   if any(r["papel"] == p and r["explicador"] for m in momentos for r in m["modelos"])]
        figuras = shap_estabilidad.lista_figuras(args.experimento, papeles, args.sufijo)
        sin_nulas = momentos_sin_nulas(momentos, leer(args.estabilidad))
        dibujar = lambda: [shap_estabilidad.figura_importancia(sin_nulas, p, args.salida / a,  # noqa: E731
                                                               nota_estabilidad=NOTA_SIN_NULAS)
                           for p, (a, _) in zip(papeles, figuras)]
    else:
        modulo, funcion = {"con_sensibles": (variante, variante.figura_diferencias),
                           "ablacion": (ablacion, ablacion.figura_perdidas),
                           "sin_exclusion_retirados": (sensibilidad_fuga, sensibilidad_fuga.figura_inflacion)}[tipo]
        figuras = modulo.lista_figuras(args.experimento, args.sufijo)
        dibujar = lambda: funcion(momentos, args.salida / figuras[0][0])  # noqa: E731

    for archivo, _ in figuras:
        if (args.salida / archivo).exists():
            raise FileExistsError(f"{archivo} ya existe: usa otro sufijo")
    (args.salida / "figuras").mkdir(parents=True, exist_ok=True)
    dibujar()
    origen = "las predicciones out-of-fold" if tipo is None else "el JSON del experimento"
    if tipo == "shap":
        origen += f" y la estabilidad sin variables nulas de {args.estabilidad}"
    nota = f" (redibujada con el commit {commit} desde {origen}, sin reentrenar)"
    actualizar_manifest(args.salida, datetime.now(), commit, args.experimento,
                        [{"archivo": a, "descripcion": d + nota, "experimento": args.experimento} for a, d in figuras])
    print(f"Figuras de {args.experimento} con sufijo {args.sufijo} en {args.salida} (commit {commit})")


if __name__ == "__main__":
    main()
