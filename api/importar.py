"""Importación de paquetes desplegados de ml/ (docs/diseno-api.md §8): `flask --app api importar-paquetes`.

Solo se importa un paquete con origen["desplegado"] is True; el nombre del archivo no interviene. Antes de escribir nada
se comprueban todos: SHA-256 del paquete frente al de su experimento (<origen.id>.json, modelos_sha256), momento presente
en el experimento evaluado (<origen.experimento>.json) y SHA-256 de sus predicciones out-of-fold si están en el equipo.
Si algo falla, no se escribe nada. Es idempotente: un paquete ya importado con el mismo SHA-256 se omite; otro paquete
para el mismo experimento y momento es un error.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import click
import joblib
import pandas as pd
from flask import Flask, current_app
from sqlalchemy import select
from sqlalchemy.orm import Session

from api import textos
from api.servicios.evaluacion import desde_momento
from api.servicios.paquetes import ruta_registrada
from api.tablas import Experimento, Modelo
from automl.explicacion import explicacion_global, tipo_explicador
from automl.motor import curva_calibracion
from evidencias import EVIDENCIAS, RAIZ, sha256


class ErrorImportacion(Exception):
    pass


@dataclass
class Pendiente:
    archivo: Path
    huella: str
    paquete: dict
    origen: dict  # JSON del experimento del paquete (modelo final)
    evaluado: dict  # JSON del experimento cuyas métricas de validación se muestran
    momento: dict
    curva: dict | None
    ruta_origen: Path
    ruta_evaluado: Path


def _leer_json(carpeta: Path, id_: str) -> tuple[dict, Path]:
    ruta = carpeta / f"{id_}.json"
    if not ruta.exists():
        raise ErrorImportacion(f"No está {ruta}.")
    return json.loads(ruta.read_text(encoding="utf-8")), ruta


def _curva(evaluado: dict, semana: int, modelo: str) -> dict | None:
    """Curva de calibración del modelo desplegado desde las predicciones out-of-fold registradas; None si no están en
    este equipo. Un archivo presente con otro SHA-256 es un error."""
    huellas = evaluado.get("predicciones_oof_sha256") or {}
    nombre = f"{evaluado['id']}_semana_{semana}.parquet"
    if nombre not in huellas:
        return None
    ruta = RAIZ / huellas["carpeta"] / nombre
    if not ruta.exists():
        return None
    if sha256(ruta) != huellas[nombre]:
        raise ErrorImportacion(f"{ruta_registrada(ruta)} no coincide con el SHA-256 registrado en {evaluado['id']}.")
    oof = pd.read_parquet(ruta, columns=["etiqueta", f"p_{modelo}", f"p_{modelo}_sin_calibrar"])
    return {"calibrada": curva_calibracion(oof["etiqueta"], oof[f"p_{modelo}"]),
            "sin_calibrar": curva_calibracion(oof["etiqueta"], oof[f"p_{modelo}_sin_calibrar"])}


def _preparar(archivo: Path, paquete: dict, experimentos: Path) -> Pendiente:
    origen = paquete["origen"]
    datos_origen, ruta_origen = _leer_json(experimentos, origen["id"])
    huella = sha256(archivo)
    if (datos_origen.get("modelos_sha256") or {}).get(archivo.name) != huella:
        raise ErrorImportacion(f"{archivo.name}: su SHA-256 no coincide con el registrado en {origen['id']}.")
    evaluado, ruta_evaluado = _leer_json(experimentos, origen["experimento"])
    momentos = [m for m in evaluado["momentos"] if m["semana"] == paquete["semana"]]
    if len(momentos) != 1:
        raise ErrorImportacion(f"{archivo.name}: la semana {paquete['semana']} no está en {origen['experimento']}.")
    momento = momentos[0]
    curva = _curva(evaluado, paquete["semana"], momento["modelo_desplegado"]["modelo"])
    return Pendiente(archivo, huella, paquete, datos_origen, evaluado, momento, curva, ruta_origen, ruta_evaluado)


def _experimento(p: Pendiente) -> Experimento:
    o, ev = p.origen, p.evaluado
    config = ev["configuracion"]
    return Experimento(
        id=o["id"], origen="importado", estado="completado",
        descripcion=textos.descripcion_importado(o["id"], ev["id"]),
        configuracion={
            "presupuesto": {"modo": "completo", **{c: config[c] for c in ("familias", "n_trials_por_familia",
                                                                         "apilamiento", "n_bootstrap")}},
            # Los experimentos de ml/ validan siempre con pliegues agrupados por presentación (fijos en los cortes).
            "validacion": {"tipo": "agrupada", "k": len(p.momento["familias"][0]["por_pliegue"]),
                           "semilla": config["semillas"]["modelos"], "columna_grupo": None, "aviso": None},
            "sensibilidad_minima": config["sensibilidad_minima"], "semillas": config["semillas"],
            "origen": {k: v for k, v in o["configuracion"].items() if k != "descripcion"},
        },
        # Solo una exportación a evidencias/ exige árbol limpio (evidencias.comprobar_arbol_limpio); el JSON no lo
        # registra, así que fuera de evidencias/ no se sabe.
        reproducibilidad={"id": o["id"], "commit": o["commit"],
                          "arbol_limpio": True if p.ruta_origen.parent.resolve() == (EVIDENCIAS / "experimentos").resolve()
                          else None,
                          "versiones": o.get("entorno"), "hardware": o.get("hardware"),
                          "sha256_datos": o["dataset"]["sha256"]},
        procedencia={"experimento": o["id"], "evaluacion_de": ev["id"],
                     "archivo_json_sha256": sha256(p.ruta_origen), "evaluacion_json_sha256": sha256(p.ruta_evaluado)},
    )


def importar(sesion: Session, modelos: Path, experimentos: Path, referencia: Path | None) -> list[str]:
    """Importa los paquetes desplegados de `modelos`; devuelve un mensaje por archivo. ErrorImportacion sin escribir
    nada si alguno no se puede importar."""
    mensajes, pendientes, vistos = [], [], {}
    for archivo in sorted(modelos.glob("*.joblib")):
        paquete = joblib.load(archivo)
        if paquete.get("origen", {}).get("desplegado") is not True:
            mensajes.append(f"{archivo.name}: omitido (no desplegado)")
            continue
        pendiente = _preparar(archivo, paquete, experimentos)
        clave = (paquete["origen"]["id"], paquete["semana"])
        if clave in vistos:
            raise ErrorImportacion(f"{archivo.name} y {vistos[clave]} son dos paquetes para {clave[0]} y la semana "
                                   f"{clave[1]}; solo puede haber uno.")
        vistos[clave] = archivo.name
        existente = sesion.scalars(select(Modelo).where(Modelo.experimento_id == paquete["origen"]["id"],
                                                        Modelo.momento == f"semana {paquete['semana']}")).first()
        if existente is not None:
            if existente.sha256_paquete != pendiente.huella:
                raise ErrorImportacion(f"{archivo.name}: ya hay otro modelo importado para {paquete['origen']['id']} y "
                                       f"la semana {paquete['semana']}.")
            mensajes.append(f"{archivo.name}: omitido (ya importado)")
            continue
        pendientes.append(pendiente)

    for p in sorted(pendientes, key=lambda p: (p.origen["id"], p.paquete["semana"])):
        if sesion.get(Experimento, p.origen["id"]) is None:
            sesion.add(_experimento(p))
            sesion.flush()
        global_ = None
        if referencia is not None and (referencia / f"{p.archivo.stem}.parquet").exists():
            global_ = explicacion_global(p.paquete, pd.read_parquet(referencia / f"{p.archivo.stem}.parquet"))
        momento = p.momento
        sesion.add(Modelo(
            experimento_id=p.origen["id"], momento=f"semana {p.paquete['semana']}",
            familia=p.paquete.get("familia", momento["modelo_desplegado"]["modelo"]),
            ruta_paquete=ruta_registrada(p.archivo), sha256_paquete=p.huella, umbral=float(p.paquete["umbral"]),
            metodo_calibracion=momento["calibracion"]["metodo"], columnas=p.paquete["columnas"],
            explicador=tipo_explicador(p.paquete),
            evaluacion=desde_momento(momento, len(p.evaluado["momentos"]), p.curva, momento.get("equidad_oof")),
            explicacion_global=global_,
        ))
        mensajes.append(f"{p.archivo.name}: importado ({p.origen['id']}, semana {p.paquete['semana']})")
    sesion.commit()
    return mensajes


def registrar(app: Flask) -> None:
    @app.cli.command("importar-paquetes")
    @click.option("--modelos", type=click.Path(exists=True, file_okay=False, path_type=Path),
                  default=RAIZ / "data" / "procesado" / "modelos")
    @click.option("--experimentos", type=click.Path(exists=True, file_okay=False, path_type=Path),
                  default=RAIZ / "evidencias" / "experimentos")
    @click.option("--referencia", type=click.Path(file_okay=False, path_type=Path),
                  default=RAIZ / "data" / "procesado" / "referencia")
    def _importar_paquetes(modelos: Path, experimentos: Path, referencia: Path) -> None:
        """Importa los paquetes desplegados de ml/ (modelo, evaluación y explicación global)."""
        with current_app.extensions["bd_sesiones"]() as sesion:
            try:
                mensajes = importar(sesion, modelos, experimentos, referencia if referencia.exists() else None)
            except ErrorImportacion as e:
                sesion.rollback()
                raise click.ClickException(f"{e} No se ha importado nada.") from None
        for mensaje in mensajes:
            click.echo(mensaje)
