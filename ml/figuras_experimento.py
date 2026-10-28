"""Regenera las figuras de un experimento de modelado desde su JSON y sus predicciones out-of-fold, sin reentrenar.

Las figuras nuevas llevan un sufijo propio y no sustituyen a las existentes; el manifiesto registra el commit con el
que se dibujaron. Las predicciones se comprueban contra los SHA-256 que registró el experimento.

Uso:
    python ml/figuras_experimento.py exp-2026-10-27-01 --sufijo _v2
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

import pandas as pd

from evidencias import EVIDENCIAS, RAIZ, actualizar_manifest, comprobar_arbol_limpio, sha256
from experimento import dibujar_figuras, lista_figuras


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("experimento")
    parser.add_argument("--sufijo", required=True, help="Sufijo de los archivos nuevos (p. ej. _v2)")
    parser.add_argument("--salida", type=Path, default=EVIDENCIAS, help="Carpeta de evidencias (por defecto evidencias/)")
    args = parser.parse_args()

    commit = comprobar_arbol_limpio(args.salida)
    experimento = json.loads((EVIDENCIAS / "experimentos" / f"{args.experimento}.json").read_text(encoding="utf-8"))
    huellas = dict(experimento["predicciones_oof_sha256"])
    carpeta = RAIZ / huellas.pop("carpeta")
    salidas = {}
    for resumen in experimento["momentos"]:
        ruta = carpeta / f"{args.experimento}_semana_{resumen['semana']}.parquet"
        if sha256(ruta) != huellas[ruta.name]:
            raise ValueError(f"{ruta.name} no coincide con el SHA-256 registrado en {args.experimento}")
        salidas[resumen["semana"]] = pd.read_parquet(ruta)

    figuras = lista_figuras(args.experimento, args.sufijo)
    for archivo, _ in figuras:
        if (args.salida / archivo).exists():
            raise FileExistsError(f"{archivo} ya existe: usa otro sufijo")
    (args.salida / "figuras").mkdir(parents=True, exist_ok=True)
    dibujar_figuras(experimento["momentos"], salidas, args.salida, figuras)
    nota = f" (redibujada con el commit {commit} desde las predicciones out-of-fold, sin reentrenar)"
    actualizar_manifest(args.salida, datetime.now(), commit, args.experimento,
                        [{"archivo": a, "descripcion": d + nota, "experimento": args.experimento} for a, d in figuras])
    print(f"Figuras de {args.experimento} con sufijo {args.sufijo} en {args.salida} (commit {commit})")


if __name__ == "__main__":
    main()
