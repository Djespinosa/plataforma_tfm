"""Filas de referencia y CSV de demostración de los paquetes desplegados de OULAD para la plataforma (docs/diseno-api.md
§8, decisiones D-3 y D-4 del bloque E). Script de OULAD: la API no sabe nada de OULAD.

Para cada paquete con origen["desplegado"] is True de --modelos escribe:
  - data/procesado/referencia/<paquete>.parquet: las filas de entrenamiento de su semana (las 15 presentaciones
    anteriores a 2014J, con la verificación de SHA-256 de experimento.cargar_entrenamiento) y solo las columnas del
    paquete; el importador calcula con ellas la explicación global.
  - con --demo <presentación>: data/procesado/demo/semana_<k>_<presentación>.csv con las filas de esa presentación de
    entrenamiento, sin la etiqueta (identificación + columnas del paquete). Es una demostración dentro de la muestra:
    nunca sirve para medir el rendimiento.
2014J no se lee (el filtro de cargar_entrenamiento se aplica al leer el parquet). Las salidas no se versionan.

Uso:
    python ml/referencia_oulad.py [--modelos data/procesado/modelos] [--demo 2014B]
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import joblib

from cortes_oulad import PROCESADO
from evidencias import EVIDENCIAS, RAIZ
from experimento import cargar_cortes, cargar_entrenamiento

IDENTIFICACION = ["code_module", "code_presentation", "id_student"]


def columnas_paquete(paquete: dict) -> list[str]:
    return paquete["columnas"]["numericas"] + paquete["columnas"]["categoricas"]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--modelos", type=Path, default=RAIZ / "data" / "procesado" / "modelos")
    parser.add_argument("--demo", help="Presentación de entrenamiento para el CSV de demostración, p. ej. 2014B")
    args = parser.parse_args()

    salida_ref, salida_demo = PROCESADO.parent / "referencia", PROCESADO.parent / "demo"
    cortes_cache: dict[str, dict] = {}
    for archivo in sorted(args.modelos.glob("*.joblib")):
        paquete = joblib.load(archivo)
        if paquete.get("origen", {}).get("desplegado") is not True:
            print(f"{archivo.name}: omitido (no desplegado)")
            continue
        origen = json.loads((EVIDENCIAS / "experimentos" / f"{paquete['origen']['id']}.json").read_text(encoding="utf-8"))
        id_cortes = origen["experimento_cortes"]
        if id_cortes not in cortes_cache:
            cortes_cache[id_cortes] = cargar_cortes(id_cortes)[0]
        datos = cargar_entrenamiento(paquete["semana"], cortes_cache[id_cortes])
        salida_ref.mkdir(parents=True, exist_ok=True)
        datos[columnas_paquete(paquete)].to_parquet(salida_ref / f"{archivo.stem}.parquet", index=False)
        print(f"{archivo.name}: {len(datos)} filas de referencia")
        if args.demo:
            demo = datos[datos["code_presentation"] == args.demo]
            if demo.empty:
                raise ValueError(f"{args.demo} no es una presentación de entrenamiento de la semana {paquete['semana']}")
            salida_demo.mkdir(parents=True, exist_ok=True)
            ruta = salida_demo / f"semana_{paquete['semana']}_{args.demo}.csv"
            demo[IDENTIFICACION + columnas_paquete(paquete)].to_csv(ruta, index=False)
            print(f"  demostración: {len(demo)} filas en {ruta.relative_to(RAIZ).as_posix()}")


if __name__ == "__main__":
    main()
