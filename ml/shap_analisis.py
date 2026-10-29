"""Estabilidad de SHAP en dos versiones y SHAP locales extremos de la RL (D9, D32), desde un experimento SHAP ya exportado,
sin reentrenar.

1. Estabilidad (D9): Spearman y solapamiento del top-10 entre los 10 pares de pliegues, media y rango, con todas las
   variables y sin las que tienen SHAP nulo en todos los pliegues (la principal es la segunda: los ceros empatados
   inflan la concordancia; auditoría de exp-2026-10-29-02, m1). La versión con todas debe reproducir la del JSON.
2. Extremos de la RL desplegada (auditoría de exp-2026-10-29-02, O1): filas out-of-fold con alguna |SHAP| > 5 log-odds,
   variables que las producen, sus valores y su percentil en el entrenamiento del momento, y cuántas cambiarían de
   alerta si cada contribución se acotara a ±5. Como el calibrador de cada pliegue es monótono y el valor base es
   constante en el pliegue, la alerta equivale a Σ SHAP ≥ s_f, con s_f la menor Σ SHAP alertada del pliegue; el
   contrafactual compara la Σ SHAP acotada con ese mismo s_f. No cambia el modelo: es para declararlo como limitación.

Solo lee filas de entrenamiento: 2014J no interviene.

Uso:
    python ml/shap_analisis.py exp-2026-10-29-02
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

from evidencias import EVIDENCIAS, actualizar_manifest, comprobar_arbol_limpio, escribir_json, sha256, siguiente_id
from experimento import OOF, cargar_cortes, cargar_entrenamiento
from shap_estabilidad import estabilidad
from variante import predicciones_principal

LIMITE = 5.0
CLAVES = ["code_module", "code_presentation", "id_student", "pliegue", "etiqueta"]


def leer_parquet(experimento: dict, nombre: str) -> pd.DataFrame:
    ruta = OOF / nombre
    if sha256(ruta) != experimento["predicciones_oof_sha256"][nombre]:
        raise ValueError(f"{nombre} no coincide con el SHA-256 registrado en {experimento['id']}")
    return pd.read_parquet(ruta)


def estabilidad_dos_versiones(phi: pd.DataFrame, pliegue: pd.Series) -> dict:
    por_pliegue = phi.abs().groupby(pliegue.to_numpy()).mean()
    nulas = [v for v in phi.columns if (phi[v] == 0).all()]
    return {"todas": {"variables": int(phi.shape[1]), **estabilidad(por_pliegue)},
            "sin_nulas": {"variables": int(phi.shape[1] - len(nulas)), **estabilidad(por_pliegue.drop(columns=nulas))},
            "variables_nulas": nulas}


def percentil(valores_entrenamiento: pd.Series, x: float) -> float | None:
    """Porcentaje de filas de entrenamiento con valor ≤ x (sin contar vacíos)."""
    validos = valores_entrenamiento.dropna()
    return None if pd.isna(x) or validos.empty else round(float((validos <= x).mean() * 100), 2)


def umbral_en_suma(suma: np.ndarray, alerta: np.ndarray, pliegue: np.ndarray) -> np.ndarray:
    """s_f por fila: la menor Σ SHAP alertada de su pliegue (∞ si el pliegue no tiene alertas)."""
    s = pd.Series(np.where(alerta, suma, np.inf)).groupby(pliegue).transform("min")
    return s.to_numpy()


def extremos(phi: pd.DataFrame, datos: pd.DataFrame, alerta: np.ndarray, limite: float = LIMITE) -> dict:
    pliegue = datos["pliegue"].to_numpy()
    suma = phi.sum(axis=1).to_numpy()
    s_f = umbral_en_suma(suma, alerta, pliegue)
    incoherentes = int(((suma >= s_f) != alerta).sum())
    if incoherentes:
        raise ValueError(f"{incoherentes} filas no cumplen alerta ⇔ Σ SHAP ≥ s_f: el SHAP no es del modelo calibrado")
    exceso = phi.abs() > limite
    filas = exceso.any(axis=1).to_numpy()
    acotada = suma - (phi - phi.clip(-limite, limite)).sum(axis=1).to_numpy()
    alerta_acotada = acotada >= s_f
    variables = []
    for v in exceso.columns[exceso.any()]:
        m = exceso[v].to_numpy()
        valores = datos.loc[m, v]
        numerica = pd.api.types.is_numeric_dtype(datos[v])
        fila = {"variable": v, "filas": int(m.sum()),
                "shap_min": round(float(phi.loc[m, v].min()), 2), "shap_max": round(float(phi.loc[m, v].max()), 2)}
        if numerica:
            percentiles = [percentil(datos[v], x) for x in valores]
            fila |= {"valor_min": float(valores.min()), "valor_max": float(valores.max()),
                     "percentil_min": min(p for p in percentiles if p is not None),
                     "percentil_max": max(p for p in percentiles if p is not None)}
        else:
            fila |= {"valores": sorted(valores.astype(str).unique().tolist())}
        variables.append(fila)
    variables.sort(key=lambda f: -f["filas"])
    return {"n": int(len(phi)), "filas_con_extremo": int(filas.sum()),
            "proporcion": round(float(filas.mean()), 4),
            "shap_abs_max": round(float(phi.abs().to_numpy().max()), 2),
            "variables": variables,
            "alerta": {"alertadas": int(alerta.sum()),
                       "cambian_al_acotar": int((alerta != alerta_acotada).sum()),
                       "dejan_de_alertar": int((alerta & ~alerta_acotada).sum()),
                       "pasan_a_alertar": int((~alerta & alerta_acotada).sum()),
                       "cambian_entre_filas_con_extremo": int((alerta != alerta_acotada)[filas].sum())}}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("experimento_shap")
    parser.add_argument("--salida", type=Path, default=EVIDENCIAS, help="Carpeta de evidencias (por defecto evidencias/)")
    args = parser.parse_args()

    leer = lambda id_exp: json.loads((EVIDENCIAS / "experimentos" / f"{id_exp}.json").read_text(encoding="utf-8"))  # noqa: E731
    shap_exp = leer(args.experimento_shap)
    principal = leer(shap_exp["hiperparametros_de"])
    commit = comprobar_arbol_limpio(args.salida)
    fecha = datetime.now()
    cortes, _ = cargar_cortes(principal["experimento_cortes"])
    variables = shap_exp["variables"]["numericas"] + shap_exp["variables"]["categoricas"]

    momentos = []
    for resumen in shap_exp["momentos"]:
        semana = resumen["semana"]
        print(f"semana {semana}", flush=True)
        datos = cargar_entrenamiento(semana, cortes)
        tabla = leer_parquet(shap_exp, f"{shap_exp['id']}_shap_semana_{semana}.parquet")
        if not tabla[CLAVES].equals(datos[CLAVES]):
            raise ValueError(f"semana {semana}: las filas SHAP no son las del corte")
        modelos = []
        for r in resumen["modelos"]:
            if not r["explicador"]:
                continue
            phi = tabla[[f"shap_{r['papel']}__{v}" for v in variables]].set_axis(variables, axis=1)
            fila = {"papel": r["papel"], "modelo": r["modelo"], "estabilidad": estabilidad_dos_versiones(phi, datos["pliegue"])}
            if fila["estabilidad"]["todas"] | {"variables": None} != r["estabilidad"] | {"variables": None}:
                raise ValueError(f"semana {semana}: la estabilidad con todas las variables no reproduce {shap_exp['id']}")
            if r["papel"] == "rl_desplegada":
                oof = predicciones_principal(leer_parquet(principal, f"{principal['id']}_semana_{semana}.parquet"), datos)
                corte = next(m for m in principal["momentos"] if m["semana"] == semana)["punto_operacion_oof"]["umbral"]
                fila["extremos"] = extremos(phi, datos, oof["p_rl"].to_numpy() >= corte)
            modelos.append(fila)
        momentos.append({"semana": semana, "modelos": modelos})

    id_exp = siguiente_id(args.salida / "experimentos", fecha)
    experimento = {
        "id": id_exp,
        "tipo": "comparacion",
        "fecha": fecha.isoformat(timespec="seconds"),
        "commit": commit,
        "descripcion": f"Estabilidad de SHAP en dos versiones (D9) y SHAP locales extremos de la RL desplegada, desde "
                       f"{shap_exp['id']} sin reentrenar (auditoría de {shap_exp['id']}: m1 y O1).",
        "analisis": "shap_estabilidad_y_extremos",
        "experimentos": [shap_exp["id"], principal["id"]],
        "origen_predicciones": "oof",
        "metodo": {
            "estabilidad": "importancia por pliegue = media de |SHAP| de sus filas out-of-fold; Spearman y solapamiento "
                           "del top-10 entre los 10 pares de pliegues, media y rango, sin umbral. 'todas' usa las 51 "
                           "variables (reproduce el JSON de origen); 'sin_nulas' quita las variables con SHAP nulo en "
                           "todos los pliegues y es la lectura principal",
            "extremos": f"filas out-of-fold de la RL desplegada con alguna |SHAP| > {LIMITE:g} log-odds sin calibrar "
                        "(D32). Percentil = porcentaje de filas de entrenamiento del momento con valor ≤ el de la fila. "
                        "Alerta = probabilidad calibrada out-of-fold del principal ≥ su umbral (D45); como el calibrador "
                        "de cada pliegue es monótono y el valor base es constante en el pliegue, equivale a "
                        "Σ SHAP ≥ s_f (comprobado en todas las filas). Contrafactual: cada SHAP acotado a "
                        f"±{LIMITE:g} y la misma s_f. Es una limitación declarada: el modelo no cambia",
        },
        "lectura": "descriptiva: SHAP es contribución a la predicción del modelo, no causa",
        "evaluado_en_prueba": False,
        "momentos": momentos,
    }
    escribir_json(args.salida / "experimentos" / f"{id_exp}.json", experimento)
    actualizar_manifest(args.salida, fecha, commit, id_exp, [])
    print(f"Exportado {id_exp} en {args.salida} (commit {commit})")


if __name__ == "__main__":
    main()
