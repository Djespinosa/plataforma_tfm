"""Configuración de un experimento web (RF-02, docs/diseno-api.md §4.2 y §6.4): de la petición a la configuración
efectiva que se guarda, y de la configuración guardada a los datos de entrenamiento (preparar), la misma función en
POST /api/experimentos/validacion, POST /api/experimentos y el trabajador: mismas semillas, mismos pliegues.

La columna de grupo y la que define la cohorte de prueba nunca son predictores; las sensibles tampoco (solo se usan en la
auditoría de equidad). La cohorte de prueba se aparta antes de asignar pliegues y no llega nunca al entrenamiento.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

import numpy as np
import pandas as pd

from api import textos
from api.errores import ErrorPlataforma
from api.servicios.tablas_csv import coaccionar
from api.tablas import ConjuntoDatos
from automl import busqueda
from automl.validacion import K, ErrorValidacion, asignar_pliegues, normalizar_valor, reservar_prueba

SEMILLA = 42
# LightGBM no admite " , : { } en los nombres de columna y XGBoost no admite [ ] <; las columnas one-hot se llaman
# <variable>_<categoría> y preprocesado.nombre_columna solo sustituye [ ] <. Se rechazan al configurar, no tras horas de
# entrenamiento.
NO_ADMITIDOS_NOMBRE = set('[]<",:{}')
NO_ADMITIDOS_CATEGORIA = set('",:{}')
SENSIBILIDAD_MINIMA = 0.70
PRESUPUESTOS = {
    "completo": {"familias": list(busqueda.FAMILIAS), "n_trials_por_familia": 50, "apilamiento": True,
                 "n_bootstrap": 2000},
    "demostracion": {"familias": list(busqueda.FAMILIAS), "n_trials_por_familia": 5, "apilamiento": True,
                     "n_bootstrap": 200},
    # Solo con la configuración Pruebas: dos familias (la RL es obligatoria en el contraste central) para que una
    # prueba entrene en segundos.
    "prueba": {"familias": ["rl", "lgbm"], "n_trials_por_familia": 1, "apilamiento": True, "n_bootstrap": 20},
}


@dataclass
class Preparados:
    X: pd.DataFrame  # filas de entrenamiento, columnas del modelo coaccionadas (índice 0..n-1)
    y: pd.Series  # 1 = clase positiva
    pliegue: pd.Series
    atributos: pd.DataFrame  # columnas sensibles de las filas de entrenamiento
    n_grupos: int | None
    filas_prueba: np.ndarray  # posición 1..n en el CSV de las filas de la cohorte de prueba
    filas_sin_objetivo: int


def huella_pliegues(pliegue: pd.Series) -> str:
    return hashlib.sha256(np.asarray(pliegue, dtype=np.int64).tobytes()).hexdigest()


def _reservar(datos: pd.DataFrame, config: dict) -> tuple[pd.DataFrame, pd.Series, np.ndarray, np.ndarray]:
    """(filas con objetivo, y de esas filas, máscara de la cohorte de prueba entre ellas, máscara con objetivo)."""
    con_objetivo = datos[config["objetivo"]].notna().to_numpy()
    filas = datos[con_objetivo]
    y = (filas[config["objetivo"]].map(normalizar_valor) == config["clase_positiva"]).astype(int)
    columna_grupo = config["validacion"]["columna_grupo"]
    grupos = filas[columna_grupo] if columna_grupo else None
    prueba = reservar_prueba(filas, y, config["cohorte_prueba"], grupos, config["semillas"]["modelos"]).to_numpy()
    return filas, y, prueba, con_objetivo


def preparar_prueba(datos: pd.DataFrame, config: dict) -> tuple[pd.DataFrame, pd.Series, np.ndarray]:
    """(X, y, posición 1..n en el CSV) de la cohorte de prueba reservada. Solo para la evaluación única (§4.7)."""
    filas, y, prueba, con_objetivo = _reservar(datos, config)
    return (coaccionar(filas[prueba].reset_index(drop=True), config["variables"]), y[prueba].reset_index(drop=True),
            np.flatnonzero(con_objetivo)[prueba] + 1)


def preparar(datos: pd.DataFrame, config: dict) -> Preparados:
    """Datos de entrenamiento según la configuración (efectiva o en construcción). ErrorValidacion de automl.validacion
    si la validación o la cohorte de prueba no son posibles."""
    filas, y, prueba, con_objetivo = _reservar(datos, config)
    columna_grupo = config["validacion"]["columna_grupo"]
    entrenamiento = filas[~prueba].reset_index(drop=True)
    y = y[~prueba].reset_index(drop=True)
    grupos = entrenamiento[columna_grupo].rename(columna_grupo) if columna_grupo else None
    pliegue = asignar_pliegues(y, grupos, config["semillas"]["modelos"])
    return Preparados(X=coaccionar(entrenamiento, config["variables"]), y=y, pliegue=pliegue,
                      atributos=entrenamiento[config["sensibles"]],
                      n_grupos=int(grupos.nunique()) if grupos is not None else None,
                      filas_prueba=np.flatnonzero(con_objetivo)[prueba] + 1,
                      filas_sin_objetivo=int((~con_objetivo).sum()))


def _texto(cuerpo: dict, campo: str) -> str | None:
    valor = cuerpo.get(campo)
    if valor is not None and not isinstance(valor, str):
        raise ErrorPlataforma(422, textos.error_lista_columnas(campo))
    return valor or None


def _lista(cuerpo: dict, campo: str) -> list[str]:
    valor = cuerpo.get(campo) or []
    if not isinstance(valor, list) or not all(isinstance(v, str) for v in valor):
        raise ErrorPlataforma(422, textos.error_lista_columnas(campo))
    return list(dict.fromkeys(valor))


def _cohorte(cuerpo: dict) -> dict | None:
    cohorte = cuerpo.get("cohorte_prueba")
    if cohorte is None:
        return None
    if not isinstance(cohorte, dict):
        raise ErrorPlataforma(422, textos.ERROR_COHORTE)
    if cohorte.get("modo") == "aleatoria":
        return {"modo": "aleatoria"}
    valores = cohorte.get("valores")
    if (cohorte.get("modo") != "valores" or not isinstance(cohorte.get("columna"), str) or not isinstance(valores, list)
            or not valores or not all(isinstance(v, (str, int, float)) for v in valores)):
        raise ErrorPlataforma(422, textos.ERROR_COHORTE)
    return {"modo": "valores", "columna": cohorte["columna"], "valores": valores}


def configurar(cuerpo: dict, conjunto: ConjuntoDatos, datos: pd.DataFrame, *, permitir_prueba: bool,
               n_jobs: int) -> tuple[dict, Preparados]:
    """(configuración efectiva, datos preparados) de la petición; ErrorPlataforma 422 con el primer problema."""
    for campo in ("objetivo", "clase_positiva"):
        if cuerpo.get(campo) is None:
            raise ErrorPlataforma(400, textos.error_falta_campo(campo))
    objetivo = _texto(cuerpo, "objetivo")
    excluidas, sensibles = _lista(cuerpo, "excluidas"), _lista(cuerpo, "sensibles")
    columna_grupo = _texto(cuerpo, "columna_grupo")
    cohorte = _cohorte(cuerpo)
    columna_cohorte = cohorte.get("columna") if cohorte else None
    if objetivo not in datos.columns:
        raise ErrorPlataforma(422, textos.error_objetivo_no_existe(objetivo))
    nombradas = [c for c in [*excluidas, *sensibles, columna_grupo, columna_cohorte] if c]
    desconocidas = list(dict.fromkeys(c for c in nombradas if c not in datos.columns))
    if desconocidas:
        raise ErrorPlataforma(422, textos.error_columnas_desconocidas(desconocidas))
    if objetivo in nombradas:
        raise ErrorPlataforma(422, textos.ERROR_OBJETIVO_EXCLUIDO)
    nombre_presupuesto = cuerpo.get("presupuesto") or "completo"
    if nombre_presupuesto not in PRESUPUESTOS or (nombre_presupuesto == "prueba" and not permitir_prueba):
        raise ErrorPlataforma(422, textos.ERROR_PRESUPUESTO)
    clase = normalizar_valor(cuerpo["clase_positiva"])
    if clase not in set(datos[objetivo].dropna().map(normalizar_valor)):
        raise ErrorPlataforma(422, textos.error_clase_positiva(clase))

    automaticas = []
    if columna_grupo:
        automaticas.append({"columna": columna_grupo, "motivo": textos.EXCLUIDA_GRUPO})
    if columna_cohorte and columna_cohorte != columna_grupo:
        automaticas.append({"columna": columna_cohorte, "motivo": textos.EXCLUIDA_COHORTE})
    fuera = {objetivo, *nombradas}
    tipos = {c["nombre"]: c["tipo"] for c in conjunto.columnas}
    variables = {"numericas": [c for c in datos.columns if c not in fuera and tipos[c] == "numerica"],
                 "categoricas": [c for c in datos.columns if c not in fuera and tipos[c] != "numerica"],
                 "imputar_mediana": []}
    if not variables["numericas"] + variables["categoricas"]:
        raise ErrorPlataforma(422, textos.ERROR_SIN_VARIABLES)
    for c in variables["numericas"] + variables["categoricas"]:
        if NO_ADMITIDOS_NOMBRE & set(c):
            raise ErrorPlataforma(422, textos.error_nombre_columna(c))
    for c in variables["categoricas"]:
        if any(NO_ADMITIDOS_CATEGORIA & set(v) for v in datos[c].dropna().map(normalizar_valor).unique()):
            raise ErrorPlataforma(422, textos.error_valores_columna(c))

    metodo = "StratifiedGroupKFold" if columna_grupo else "StratifiedKFold"
    config = {
        "objetivo": objetivo, "clase_positiva": clase, "excluidas": excluidas, "sensibles": sensibles,
        "excluidas_automaticamente": automaticas, "variables": variables,
        "validacion": {"tipo": "agrupada_estratificada" if columna_grupo else "estratificada", "k": K,
                       "semilla": SEMILLA, "columna_grupo": columna_grupo,
                       "metodo": f"{metodo}(n_splits={K}, shuffle=True, random_state={SEMILLA})",
                       "aviso": None if columna_grupo else textos.AVISO_SIN_GRUPO},
        "cohorte_prueba": cohorte,
        "presupuesto": {"modo": nombre_presupuesto, **PRESUPUESTOS[nombre_presupuesto]},
        "sensibilidad_minima": SENSIBILIDAD_MINIMA,
        "semillas": {"optuna": SEMILLA, "modelos": SEMILLA, "bootstrap": SEMILLA}, "n_jobs": n_jobs,
    }
    try:
        preparados = preparar(datos, config)
    except ErrorValidacion as e:
        raise ErrorPlataforma(422, str(e)) from None
    except ValueError:  # de scikit-learn u otra biblioteca: sin texto técnico en inglés
        raise ErrorPlataforma(422, textos.ERROR_CONFIGURACION) from None

    config["validacion"] |= {"n_grupos": preparados.n_grupos, "pliegues_sha256": huella_pliegues(preparados.pliegue)}
    if cohorte:
        aleatoria = cohorte["modo"] == "aleatoria"
        config["cohorte_prueba"] = cohorte | {
            "filas": len(preparados.filas_prueba),
            "metodo": textos.COHORTE_ALEATORIA if aleatoria else textos.COHORTE_VALORES,
            "semilla": SEMILLA if aleatoria else None}
    config["filas_sin_objetivo"] = preparados.filas_sin_objetivo
    avisos = [textos.aviso_excluida(a["columna"], a["motivo"]) for a in automaticas]
    if preparados.filas_sin_objetivo:
        avisos.append(textos.aviso_sin_objetivo(preparados.filas_sin_objetivo))
    if not columna_grupo:
        avisos.append(textos.AVISO_SIN_GRUPO)
    if nombre_presupuesto == "demostracion":
        avisos.append(textos.AVISO_DEMOSTRACION)
    config["avisos"] = avisos
    return config, preparados
