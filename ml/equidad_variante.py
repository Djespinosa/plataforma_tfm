"""Equidad descriptiva de la variante con variables sensibles (D8, D50) frente a la configuración principal.

Para cada momento, el modelo desplegado del principal (la RL) en la variante "con": sus probabilidades out-of-fold
calibradas, su propio umbral out-of-fold (D45) y la misma auditoría por subgrupo que el principal (D50), junto a la del
principal recalculada desde sus predicciones (debe coincidir con su JSON). Es solo descriptivo: no se contrasta ni
decide nada, y la variante "con" no se despliega. No entrena modelos ni lee filas de 2014J (solo los recuentos de
retiros del experimento de cortes, como el principal).

Uso:
    python ml/equidad_variante.py exp-2026-10-28-01
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

from automl.calibracion import punto_operacion, umbral
from automl.equidad import auditar
from cortes_oulad import SENSIBLES
from evidencias import EVIDENCIAS, actualizar_manifest, comprobar_arbol_limpio, escribir_json, sha256, siguiente_id
from experimento import OOF, cargar_cortes, cargar_entrenamiento, retiros_prueba
from variante import predicciones_principal


def leer_oof(experimento: dict, semana: int) -> pd.DataFrame:
    ruta = OOF / f"{experimento['id']}_semana_{semana}.parquet"
    if sha256(ruta) != experimento["predicciones_oof_sha256"][ruta.name]:
        raise ValueError(f"{ruta.name} no coincide con el SHA-256 registrado en {experimento['id']}")
    return pd.read_parquet(ruta)


def equidad(y: pd.Series, p: np.ndarray, atributos: pd.DataFrame, retiros: dict, sensibilidad_minima: float,
            n_bootstrap: int, semilla: int) -> dict:
    corte = umbral(y, p, sensibilidad_minima)
    return {"punto_operacion_oof": punto_operacion(y, p, corte),
            "equidad_oof": auditar(y, p, corte, atributos, retiros, n_bootstrap, semilla)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("variante")
    parser.add_argument("--salida", type=Path, default=EVIDENCIAS, help="Carpeta de evidencias (por defecto evidencias/)")
    args = parser.parse_args()

    leer = lambda id_exp: json.loads((EVIDENCIAS / "experimentos" / f"{id_exp}.json").read_text(encoding="utf-8"))  # noqa: E731
    variante = leer(args.variante)
    principal = leer(variante["hiperparametros_de"])
    configuracion = principal["configuracion"]
    semilla = principal["particion"]["semillas"]["bootstrap"]
    commit = comprobar_arbol_limpio(args.salida)
    fecha = datetime.now()
    cortes, _ = cargar_cortes(principal["experimento_cortes"])

    momentos = []
    for resumen in principal["momentos"]:
        semana, modelo = resumen["semana"], resumen["modelo_desplegado"]["modelo"]
        print(f"semana {semana}", flush=True)
        datos = cargar_entrenamiento(semana, cortes)
        y, atributos, retiros = datos["etiqueta"], datos[SENSIBLES], retiros_prueba(cortes, semana)
        p_sin = predicciones_principal(leer_oof(principal, semana), datos)[f"p_{modelo}"].to_numpy()
        p_con = predicciones_principal(leer_oof(variante, semana), datos)[f"p_{modelo}"].to_numpy()
        argumentos = (configuracion["sensibilidad_minima"], configuracion["n_bootstrap"], semilla)
        sin = equidad(y, p_sin, atributos, retiros, *argumentos)
        if sin["equidad_oof"] != resumen["equidad_oof"] or sin["punto_operacion_oof"] != resumen["punto_operacion_oof"]:
            raise ValueError(f"semana {semana}: la equidad recalculada no coincide con la de {principal['id']}")
        fila_con = next(f for f in next(m for m in variante["momentos"] if m["semana"] == semana)["por_modelo"]
                        if f["modelo"] == modelo)
        momentos.append({"semana": semana, "n": int(len(y)), "retiros": int(y.sum()), "modelo": modelo,
                         "con": {"calibracion": fila_con["calibracion"]["metodo"], **equidad(y, p_con, atributos,
                                                                                             retiros, *argumentos)},
                         "sin": {"calibracion": resumen["calibracion"]["metodo"], **sin}})

    id_exp = siguiente_id(args.salida / "experimentos", fecha)
    experimento = {
        "id": id_exp,
        "tipo": "comparacion",
        "fecha": fecha.isoformat(timespec="seconds"),
        "commit": commit,
        "descripcion": f"Equidad descriptiva (D8, D50) del modelo desplegado del principal en la variante con variables "
                       f"sensibles ({variante['id']}) frente a la configuración principal ({principal['id']}). Solo "
                       "descriptivo: la variante con sensibles no se despliega.",
        "analisis": "equidad_con_sensibles",
        "experimentos": [principal["id"], variante["id"]],
        "origen_predicciones": "oof",
        "metodo": "por momento, el modelo desplegado del principal con sus probabilidades out-of-fold calibradas en "
                  "cada variante; umbral out-of-fold propio de cada variante (D45, sensibilidad mínima "
                  f"{configuracion['sensibilidad_minima']}) y auditoría por subgrupo de D50 con "
                  f"{configuracion['n_bootstrap']} réplicas bootstrap y semilla {semilla}. La parte 'sin' se recalcula "
                  f"desde las predicciones de {principal['id']} y coincide con su JSON",
        "lectura": "descriptiva: no se contrasta con − sin ni se toma ninguna decisión",
        "evaluado_en_prueba": False,
        "momentos": momentos,
    }
    escribir_json(args.salida / "experimentos" / f"{id_exp}.json", experimento)
    actualizar_manifest(args.salida, fecha, commit, id_exp, [])
    print(f"Exportado {id_exp} en {args.salida} (commit {commit})")


if __name__ == "__main__":
    main()
