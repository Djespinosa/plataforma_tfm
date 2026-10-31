"""Explicaciones global y local para la respuesta (RF-06, docs/diseno-api.md §4.5; skill guardarrailes-interfaz).

Los valores SHAP los calcula ml/ (automl.explicacion); aquí solo se ordenan y se presentan: los 5 de mayor |φ| entre
las variables con contribución, repartidos en «aumentan» y «reducen»; las contribuciones mayores que
explicacion.LIMITE_EXTREMO se marcan como extremas (no se recorta ninguna) y las variables sin valores en el
entrenamiento (φ = 0 por construcción, auditoría O4) van aparte, nunca entre las contribuciones.
"""

from __future__ import annotations

import math

from api import textos
from automl.explicacion import LIMITE_EXTREMO

TOP = 5


def valor_llano(valor) -> str:
    """Valor de una variable en texto: vacío → «sin dato»; número entero sin decimales; resto con coma decimal."""
    if valor is None or (isinstance(valor, float) and math.isnan(valor)):
        return textos.SIN_DATO
    if isinstance(valor, float):
        return str(int(valor)) if valor.is_integer() else f"{valor:.4g}".replace(".", ",")
    return str(valor)


def sin_contribucion(variables: list[str]) -> list[dict]:
    return [{"variable": v, "motivo": textos.SIN_CONTRIBUCION} for v in variables]


def global_(explicacion_global: dict | None) -> dict:
    """Parte de GET /api/modelos/{id}/explicacion-global que sale de modelo.explicacion_global."""
    if explicacion_global is None:
        return {"fuente": None, "variables": None, "sin_contribucion": [], "motivo": textos.SIN_REFERENCIA}
    return {"fuente": textos.fuente_global(explicacion_global["n_filas"]),
            "variables": explicacion_global["variables"],
            "sin_contribucion": sin_contribucion(explicacion_global["sin_contribucion"])}


def local(contribuciones: dict, valores: dict, sin_valores: list[str]) -> dict:
    """aumentan, reducen, resto, todas, sin_contribucion y hay_extremas de una fila. Una variable sin valores en el
    entrenamiento solo va a sin_contribucion si su φ es 0: con permutación o MLP puede no serlo si la fila trae un valor,
    y entonces se muestra como cualquier otra contribución."""
    sin = [v for v in sin_valores if contribuciones.get(v) == 0]
    con = {v: phi for v, phi in contribuciones.items() if v not in sin}
    orden = sorted(con, key=lambda v: abs(con[v]), reverse=True)

    def item(v: str) -> dict:
        return {"variable": v, "valor": valor_llano(valores.get(v)), "contribucion": con[v],
                "extrema": abs(con[v]) > LIMITE_EXTREMO}

    aumentan = [item(v) for v in orden[:TOP] if con[v] > 0]
    reducen = [item(v) for v in orden[:TOP] if con[v] < 0]
    mostradas = {i["variable"] for i in aumentan + reducen}
    resto = [v for v in orden if v not in mostradas]
    return {"aumentan": aumentan, "reducen": reducen,
            "resto": {"n_variables": len(resto), "suma": sum(con[v] for v in resto)},
            "todas": [item(v) for v in orden],
            "sin_contribucion": sin_contribucion(sin),
            "hay_extremas": any(abs(phi) > LIMITE_EXTREMO for phi in con.values())}
