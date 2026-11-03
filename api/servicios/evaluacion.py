"""Evaluación de un modelo (RF-04, docs/diseno-api.md §4.3): del resumen de un momento de ml/ (mismas claves que
`momentos[]` de los experimentos de ml/experimento.py) a la parte numérica que se guarda en modelo.evaluacion, y de ella a
la respuesta con textos; y la evaluación única en la cohorte de prueba reservada (§4.7).

Solo se copian campos numéricos y etiquetas cerradas: los textos de ml/ (motivo, regla, nota) llevan códigos de
decisión y no se reenvían. De la equidad no se copian los recuentos de la prueba (retiros_prueba): la plataforma no
muestra nada de la cohorte de prueba.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score

from api import textos
from automl.calibracion import punto_operacion

METRICAS = ("roc_auc_oof", "roc_auc_media", "roc_auc_desv", "pr_auc_oof", "brier_oof")
CAMPOS_SUBGRUPO = ("n", "retiros", "sensibilidad", "sensibilidad_ic95", "tasa_falsos_positivos",
                   "tasa_falsos_positivos_ic95", "solo_descriptiva")
CAMPOS_DIFERENCIAS = ("diferencia_sensibilidad", "diferencia_sensibilidad_ic95", "diferencia_tasa_falsos_positivos",
                      "diferencia_tasa_falsos_positivos_ic95")


def _metodo(calibracion) -> str | None:
    return calibracion.get("metodo") if isinstance(calibracion, dict) else None


def _fila(resumen: dict, papel: str) -> dict:
    return {"modelo": resumen["modelo"], "papel": papel, **{m: resumen.get(m) for m in METRICAS},
            "calibracion": _metodo(resumen.get("calibracion"))}


def _equidad(equidad: dict | None) -> dict | None:
    if not equidad:
        return None
    return {atributo: {"subgrupos": {g: {c: s.get(c) for c in CAMPOS_SUBGRUPO} for g, s in a["subgrupos"].items()},
                       **{c: a.get(c) for c in CAMPOS_DIFERENCIAS}}
            for atributo, a in equidad.items()}


def desde_momento(momento: dict, holm_sobre: int, curva: dict | None, equidad: dict | None) -> dict:
    """Parte numérica de la evaluación de un momento. curva = {calibrada, sin_calibrar} o None (sin predicciones OOF)."""
    desplegado = momento["modelo_desplegado"]["modelo"]
    parsimonia = momento["parsimonia"]
    candidatos = [_fila(f, "desplegado" if f["modelo"] == desplegado else "candidato") for f in momento["familias"]]
    if momento.get("apilamiento"):
        candidatos.append(_fila({"modelo": "apilamiento", **momento["apilamiento"], "calibracion": None}, "candidato"))
    perdida = {c["modelo"]: c for c in parsimonia["candidatos"]}
    contraste = momento["contraste_central"]
    calibracion = momento["calibracion"]
    return {
        "n": momento["n"], "positivos": momento["retiros"],
        "candidatos": candidatos,
        "referencias": [_fila(r, "referencia") for r in momento["referencias"]],
        "contraste": {**{c: contraste[c] for c in ("modelo_a", "modelo_b", "diferencia", "ic95_bootstrap", "delong_p",
                                                   "delong_p_holm", "lectura")},
                      "holm_sobre": holm_sobre},
        "parsimonia": {"mejor": parsimonia["mejor"], "margen": parsimonia["margen"],
                       "candidatos": [{c: p[c] for c in ("modelo", "roc_auc_oof", "perdida", "ic95_bootstrap", "cumple")}
                                      for p in parsimonia["candidatos"]]},
        "desplegado": {"modelo": desplegado, "mejor": parsimonia["mejor"],
                       "limite_superior": perdida[desplegado]["ic95_bootstrap"][1]},
        "punto_operacion": dict(momento["punto_operacion_oof"]),
        # El apilamiento desplegado no tiene calibración propia (salida del metamodelo): método y Brier nulos.
        "calibracion": {"metodo": calibracion.get("metodo"), "brier_sin_calibrar": calibracion.get("brier_sin_calibrar"),
                        "brier_calibrado": calibracion.get("brier_calibrado"), "curva": curva},
        "equidad": _equidad(equidad),
    }


def con_textos(evaluacion: dict) -> dict:
    """La evaluación guardada con los textos de api/textos.py (sin códigos de decisión, coma decimal)."""
    e = {k: (dict(v) if isinstance(v, dict) else v) for k, v in evaluacion.items()}
    e["contraste"]["lectura_texto"] = textos.LECTURAS[e["contraste"]["lectura"]]
    d = e["desplegado"]
    e["desplegado"]["motivo_texto"] = textos.texto_motivo(d["modelo"], d["mejor"], d["limite_superior"],
                                                         e["parsimonia"]["margen"])
    po = e["punto_operacion"]
    po["textos"] = textos.textos_punto_operacion(po["sensibilidad"], po["precision"], po["tasa_alerta"])
    e["calibracion"]["texto"] = textos.TEXTO_CALIBRACION
    if e["calibracion"]["curva"] is None:
        e["calibracion"]["motivo"] = textos.SIN_CURVA_CALIBRACION
    if e["equidad"]:
        e["equidad"] = {"texto": textos.texto_sensibles(list(e["equidad"])), "atributos": e["equidad"]}
    e["textos"] = {"roc_auc": textos.TEXTO_ROC_AUC, "pr_auc": textos.texto_pr_auc(e["positivos"] / e["n"])}
    return e


def en_prueba(y: pd.Series, probabilidad: np.ndarray, umbral: float) -> dict:
    """Métricas del modelo desplegado en la cohorte de prueba con el umbral ya fijado (y con las dos clases)."""
    return {"n": len(y), "positivos": int(y.sum()), "roc_auc": round(roc_auc_score(y, probabilidad), 4),
            "pr_auc": round(average_precision_score(y, probabilidad), 4),
            "brier": round(brier_score_loss(y, probabilidad), 4),
            "punto_operacion": punto_operacion(y, probabilidad, umbral)}


def prueba_con_textos(evaluacion: dict) -> dict:
    """La evaluación en la cohorte de prueba guardada, con sus textos."""
    po = evaluacion["punto_operacion"]
    return {**evaluacion, "fuente": "cohorte_prueba", "aviso_fuente": textos.AVISO_FUENTE_PRUEBA,
            "punto_operacion": {**po, "textos": textos.textos_punto_operacion(po["sensibilidad"], po["precision"],
                                                                              po["tasa_alerta"])},
            "textos": {"roc_auc": textos.TEXTO_ROC_AUC,
                       "pr_auc": textos.texto_pr_auc(evaluacion["positivos"] / evaluacion["n"])},
            "aviso_decision": textos.AVISO_DECISION}
