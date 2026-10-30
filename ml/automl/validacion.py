"""Cohorte de prueba reservada y pliegues de validación cruzada para conjuntos genéricos (flujo web, docs/diseno-api.md §6.1).

k = 5 fijo (particion.PLIEGUES). Sin columna de grupo, StratifiedKFold con semilla; con columna de grupo,
StratifiedGroupKFold con semilla (D-7: equilibra la prevalencia entre pliegues; es distinto del reparto de D29-rev, que
sigue siendo el de OULAD en cortes_oulad.py). Si el esquema pedido no es posible, falla con un mensaje claro: nunca
cambia de esquema en silencio. Los mensajes de ValueError son los que la API devuelve tal cual (§4.2, marcados con †).

Las filas reservadas no entran en búsqueda, calibración ni umbral; eso lo garantiza quien llama (aquí solo la máscara).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.model_selection import StratifiedGroupKFold, StratifiedKFold, train_test_split

from automl.particion import PLIEGUES

K = len(PLIEGUES)  # 5
MINIMO_POR_CLASE = K
FRACCION_PRUEBA = 0.2


def normalizar_valor(valor) -> str:
    """Texto con que se comparan los valores de una cohorte: un número entero escrito como decimal cuenta como entero
    (2014.0 → "2014"), porque una columna entera con vacíos se lee como float."""
    if isinstance(valor, (float, np.floating)) and float(valor).is_integer():
        return str(int(valor))
    return str(valor)


def reservar_prueba(datos: pd.DataFrame, y: pd.Series, cohorte: dict | None, grupos: pd.Series | None,
                    semilla: int) -> pd.Series:
    """Máscara booleana (índice de datos) de las filas reservadas como cohorte de prueba; False en todas si cohorte es None.

    {"modo": "valores", "columna", "valores"}: filas con datos[columna] ∈ valores (comparación con normalizar_valor);
    falla si alguno de los valores pedidos no aparece y, con grupos, si algún grupo tiene filas a ambos lados. {"modo": "aleatoria"}: train_test_split estratificado por y,
    test_size=FRACCION_PRUEBA, random_state=semilla; falla si grupos no es None.
    """
    if cohorte is None:
        return pd.Series(False, index=datos.index, name="prueba")
    if cohorte["modo"] == "aleatoria":
        if grupos is not None:
            raise ValueError("Con columna de grupo, la cohorte de prueba se elige por valores (cohortes completas), no al "
                             "azar, para que filas relacionadas no queden a ambos lados.")
        posiciones = np.arange(len(datos))
        _, prueba = train_test_split(posiciones, test_size=FRACCION_PRUEBA, stratify=y.to_numpy(), random_state=semilla)
        mascara = np.zeros(len(datos), dtype=bool)
        mascara[prueba] = True
        return pd.Series(mascara, index=datos.index, name="prueba")
    if cohorte["modo"] != "valores":
        raise ValueError(f"Modo de cohorte de prueba desconocido: {cohorte['modo']}")
    columna = cohorte["columna"]
    valores = datos[columna].map(normalizar_valor, na_action="ignore")
    pedidos = {normalizar_valor(v) for v in cohorte["valores"]}
    mascara = valores.isin(pedidos).rename("prueba")
    if not mascara.any():
        raise ValueError(f"Ningún valor de la cohorte de prueba aparece en «{columna}».")
    ausentes = sorted(pedidos - set(valores.dropna()))
    if ausentes:
        raise ValueError(f"Los valores «{', '.join(ausentes)}» de la cohorte de prueba no aparecen en «{columna}».")
    if grupos is not None:
        compartidos = int((mascara.groupby(grupos).nunique() > 1).sum())
        if compartidos:
            raise ValueError(f"La cohorte de prueba comparte grupos con el entrenamiento ({compartidos} grupos); elija "
                             "cohortes completas.")
    return mascara


def asignar_pliegues(y: pd.Series, grupos: pd.Series | None, semilla: int) -> pd.Series:
    """Pliegue 1..K (Int64, mismo índice que y) de las filas de entrenamiento.

    Sin grupos: StratifiedKFold(K, shuffle=True, random_state=semilla).
    Con grupos: StratifiedGroupKFold(K, shuffle=True, random_state=semilla); falla si hay vacíos en grupos, si hay menos
    de K grupos o si algún pliegue queda sin una de las clases. Nunca cambia de esquema en silencio.
    En ambos casos falla si una clase tiene menos de MINIMO_POR_CLASE filas.
    """
    if y.nunique() < 2:
        raise ValueError("La columna objetivo solo tiene una clase en las filas de entrenamiento; se necesitan ambas.")
    for clase, n in y.value_counts().items():
        if n < MINIMO_POR_CLASE:
            raise ValueError(f"La clase «{clase}» tiene {n} filas de entrenamiento; la validación cruzada de {K} "
                             f"pliegues necesita al menos {MINIMO_POR_CLASE} por clase.")
    if grupos is None:
        divisor = StratifiedKFold(K, shuffle=True, random_state=semilla)
        particiones = divisor.split(np.zeros(len(y)), y.to_numpy())
    else:
        if not grupos.index.equals(y.index):
            raise ValueError("La columna de grupo y el objetivo deben tener el mismo índice")
        vacios = int(grupos.isna().sum())
        if vacios:
            raise ValueError(f"La columna de grupo «{grupos.name}» tiene valores vacíos en {vacios} filas.")
        n_grupos = grupos.nunique()
        if n_grupos < K:
            raise ValueError(f"La columna de grupo «{grupos.name}» tiene {n_grupos} valores distintos; la validación "
                             f"agrupada necesita al menos {K}. Indique otra columna de grupo o ninguna.")
        divisor = StratifiedGroupKFold(K, shuffle=True, random_state=semilla)
        particiones = divisor.split(np.zeros(len(y)), y.to_numpy(), grupos.to_numpy())
    pliegue = np.zeros(len(y), dtype=int)
    for numero, (_, validacion) in enumerate(particiones, start=1):
        pliegue[validacion] = numero
    pliegue = pd.Series(pliegue, index=y.index, name="pliegue").astype("Int64")
    if grupos is not None:
        clases = y.nunique()
        for numero in sorted(PLIEGUES):
            if y[pliegue == numero].nunique() < clases:
                raise ValueError(f"Con esta columna de grupo, el pliegue {numero} queda sin filas de una de las clases; "
                                 "indique otra columna.")
    return pliegue
