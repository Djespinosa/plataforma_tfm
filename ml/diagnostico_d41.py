"""Diagnóstico de la aproximación del umbral transferido (D41) desde los paquetes de un modelo final ya exportado, sin
reentrenar (P-19; auditoría de exp-2026-10-29-03, O1).

Para cada momento y variante (desplegado y con sensibles), aplica el paquete a sus propias filas de entrenamiento y da la
sensibilidad y la tasa de alerta con el umbral transferido, junto a las out-of-fold de las que salió ese umbral. Es un
diagnóstico dentro de la muestra y sesgado, no una estimación del rendimiento. Cada paquete se comprueba contra el
SHA-256 registrado en el modelo final.

Solo lee filas de entrenamiento: 2014J no interviene.

Uso:
    python ml/diagnostico_d41.py exp-2026-10-29-03
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

import joblib

from cortes_oulad import ejecutar_pruebas
from evidencias import (
    EVIDENCIAS,
    RAIZ,
    actualizar_manifest,
    comprobar_arbol_limpio,
    escribir_json,
    sha256,
    siguiente_id,
)
from experimento import cargar_cortes, cargar_entrenamiento
from modelo_final import LECTURA_DIAGNOSTICO, diagnostico_d41, predecir_y_explicar

VARIANTES = {"desplegado": "", "con_sensibles": "_con_sensibles"}


def cargar_paquete(final: dict, nombre: str) -> dict:
    ruta = RAIZ / final["modelos_sha256"]["carpeta"] / nombre
    if sha256(ruta) != final["modelos_sha256"][nombre]:
        raise ValueError(f"{nombre} no coincide con el SHA-256 registrado en {final['id']}")
    return joblib.load(ruta)


def diagnostico_momento(paquete: dict, datos, registrado: dict) -> dict:
    """Diagnóstico de un paquete; el umbral del paquete debe ser el registrado en el modelo final."""
    if round(paquete["umbral"], 6) != registrado["umbral"]["valor"]:
        raise ValueError(f"semana {paquete['semana']}: el umbral del paquete no es el registrado")
    columnas = paquete["columnas"]
    prediccion, _ = predecir_y_explicar(paquete, datos[columnas["numericas"] + columnas["categoricas"]])
    oof = registrado["umbral"]["punto_operacion_oof"]
    return {"umbral_exacto": float(paquete["umbral"]),
            **diagnostico_d41(datos["etiqueta"], prediccion["alerta"]),
            "sensibilidad_oof": oof["sensibilidad"], "tasa_alerta_oof": oof["tasa_alerta"]}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("modelo_final")
    parser.add_argument("--salida", type=Path, default=EVIDENCIAS, help="Carpeta de evidencias (por defecto evidencias/)")
    args = parser.parse_args()

    final = json.loads((EVIDENCIAS / "experimentos" / f"{args.modelo_final}.json").read_text(encoding="utf-8"))
    if final.get("variante") != "modelo_final":
        raise ValueError(f"{args.modelo_final} no es un modelo final")
    commit = comprobar_arbol_limpio(args.salida)
    fecha = datetime.now()
    for carpeta in ("experimentos", "pruebas"):
        (args.salida / carpeta).mkdir(parents=True, exist_ok=True)
    id_exp = siguiente_id(args.salida / "experimentos", fecha)
    archivo_pruebas = f"pruebas/{id_exp}_pruebas.xml"
    resultado_pruebas = ejecutar_pruebas(args.salida / archivo_pruebas)
    cortes, _ = cargar_cortes(final["experimento_cortes"])

    momentos = []
    for registrado in final["momentos"]:
        semana = registrado["semana"]
        print(f"semana {semana}", flush=True)
        datos = cargar_entrenamiento(semana, cortes)
        fila = {"semana": semana, "n": int(len(datos)), "retiros": int(datos["etiqueta"].sum())}
        for variante, sufijo in VARIANTES.items():
            paquete = cargar_paquete(final, f"{final['id']}{sufijo}_semana_{semana}.joblib")
            if paquete["origen"]["desplegado"] != (variante == "desplegado") or paquete["semana"] != semana:
                raise ValueError(f"semana {semana}: el paquete {variante} no es el esperado")
            fila[variante] = diagnostico_momento(paquete, datos, registrado if variante == "desplegado"
                                                 else registrado["con_sensibles"])
        momentos.append(fila)

    experimento = {
        "id": id_exp,
        "tipo": "comparacion",
        "fecha": fecha.isoformat(timespec="seconds"),
        "commit": commit,
        "descripcion": f"Diagnóstico del umbral transferido (D41) de los paquetes de {final['id']}, sin reentrenar: "
                       "sensibilidad y tasa de alerta sobre sus propias filas de entrenamiento (auditoría de "
                       f"{final['id']}, O1; P-19).",
        "analisis": "diagnostico_d41",
        "experimentos": [final["id"]],
        "metodo": "cada paquete (SHA-256 comprobado contra el modelo final) predice sus filas de entrenamiento del "
                  "momento; alerta = probabilidad calibrada ≥ umbral exacto del paquete. Se comparan la sensibilidad y "
                  "la tasa de alerta resultantes con las out-of-fold de las que salió el umbral (punto_operacion_oof)",
        "lectura": LECTURA_DIAGNOSTICO,
        "evaluado_en_prueba": False,
        "modelos_sha256": final["modelos_sha256"],
        "momentos": momentos,
        "pruebas": {"informe": archivo_pruebas} | resultado_pruebas,
    }
    escribir_json(args.salida / "experimentos" / f"{id_exp}.json", experimento)
    actualizar_manifest(args.salida, fecha, commit, id_exp, [],
                        [{"archivo": archivo_pruebas, "descripcion": "JUnit de todas las pruebas de ml/tests en el "
                          "commit del experimento", "experimento": id_exp}])
    print(f"Exportado {id_exp} en {args.salida} (commit {commit})")


if __name__ == "__main__":
    main()
