"""Registra en evidencias/manifest.json las capturas de la interfaz (docs/diseno-web.md §12, decisión W-10).

Las capturas se toman a mano (Chrome a 1440 × 900) con web/ y api/ confirmados en un commit, y se guardan en
evidencias/capturas/ con los nombres de CAPTURAS. Este script, desde la raíz y con ese mismo commit, añade o sustituye
en `capturas` una entrada {archivo, descripcion, commit, datos} por cada PNG nuevo o cambiado según `git status` (las
capturas ya confirmadas y sin cambios conservan su entrada y su commit); `datos` lleva el experimento y el
CSV (ruta y SHA-256) que muestra la vista. El árbol debe estar limpio salvo esos PNG (nuevos o cambiados, no
borrados) y no se confirma nada entre la toma y el registro: el commit registrado es el HEAD, el del código que se ve. El
estudiante confirma después los PNG y el manifest en un commit propio.

    python -m scripts.registrar_capturas --experimento-web web-2026-11-04-01

`--experimento-web` es el experimento del flujo genérico (carga, configuración y seguimiento); solo hace falta si están
esas capturas.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
EVIDENCIAS = RAIZ / "evidencias"

IMPORTADO = "exp-2026-10-29-03"
CSV_LOTE = "data/procesado/demo/semana_4_2014B.csv"
CSV_ENTRENAMIENTO = "data/procesado/demo/entrenamiento_semana_4.csv"
GENERICO = "--experimento-web"  # marcador: se sustituye por el argumento

# archivo → (descripción, experimento, CSV o None)
CAPTURAS: dict[str, tuple[str, str, str | None]] = {
    "web-modelos.png": ("Modelos desplegados del modelo importado (4 momentos)", IMPORTADO, None),
    "web-evaluacion-resumen.png": ("Evaluación, vista resumida (semana 4; métricas out-of-fold de exp-2026-10-27-01)",
                                   IMPORTADO, None),
    "web-evaluacion-detalle.png": ("Evaluación, detalle técnico (semana 4; métricas out-of-fold de exp-2026-10-27-01)",
                                   IMPORTADO, None),
    "web-prediccion-lista.png": ("Lista de probabilidades estimadas de una cohorte 2014B (semana 4)", IMPORTADO,
                                 CSV_LOTE),
    "web-explicacion-local.png": ("Explicación local de un caso marcado (semana 4)", IMPORTADO, CSV_LOTE),
    "web-explicacion-global.png": ("Explicación global del modelo (semana 4)", IMPORTADO, None),
    "web-carga.png": ("Carga de un CSV de entrenamiento (flujo genérico)", GENERICO, CSV_ENTRENAMIENTO),
    "web-configuracion.png": ("Configuración comprobada del entrenamiento (flujo genérico)", GENERICO,
                              CSV_ENTRENAMIENTO),
    "web-seguimiento.png": ("Seguimiento del entrenamiento (flujo genérico)", GENERICO, CSV_ENTRENAMIENTO),
}


def entradas(nombres: set[str], raiz: Path, commit: str, experimento_web: str | None) -> list[dict]:
    """Una entrada por cada captura de `nombres` (en el orden de CAPTURAS); error si falta el experimento web."""
    nuevas = []
    for archivo, (descripcion, experimento, csv) in CAPTURAS.items():
        if archivo not in nombres:
            continue
        if experimento == GENERICO:
            if not experimento_web:
                raise ValueError(f"{archivo} necesita --experimento-web")
            experimento = experimento_web
        datos: dict = {"experimento": experimento}
        if csv:
            datos["csv"] = {"ruta": csv, "sha256": hashlib.sha256((raiz / csv).read_bytes()).hexdigest()}
        nuevas.append({"archivo": f"capturas/{archivo}", "descripcion": descripcion, "commit": commit, "datos": datos})
    return nuevas


def registrar(evidencias: Path, nuevas: list[dict], commit: str, fecha: datetime) -> None:
    ruta = evidencias / "manifest.json"
    manifest = json.loads(ruta.read_text(encoding="utf-8"))
    archivos = {c["archivo"] for c in nuevas}
    manifest["capturas"] = [c for c in manifest["capturas"] if c["archivo"] not in archivos] + nuevas
    manifest["generado"] = fecha.isoformat(timespec="seconds")
    manifest["commit"] = commit
    ruta.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def clasificar(status: str) -> tuple[set[str], list[str]]:
    """(capturas nuevas o cambiadas, líneas ajenas) de `git status --porcelain`. Solo se admite un archivo de CAPTURAS
    directamente en evidencias/capturas/ con estado nuevo o modificado; cualquier otra línea es ajena (un borrado
    también: su entrada quedaría en el manifest apuntando a un archivo que no existe)."""
    cambiadas, ajenas = set(), []
    for linea in status.splitlines():
        ruta = linea[3:]
        nombre = ruta.removeprefix("evidencias/capturas/")
        if linea[:2] in ("??", " M", "M ", "A ") and ruta != nombre and nombre in CAPTURAS:
            cambiadas.add(nombre)
        else:
            ajenas.append(linea)
    return cambiadas, ajenas


def _git(*args: str) -> str:
    # Sin strip: en el formato porcelain el primer carácter de la línea es parte del estado (« M ruta»).
    return subprocess.run(["git", *args], cwd=RAIZ, capture_output=True, text=True, check=True).stdout.rstrip("\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--experimento-web", help="experimento del flujo genérico (web-AAAA-MM-DD-NN)")
    args = parser.parse_args()
    # Limpio salvo los PNG nuevos o cambiados de las capturas: el commit registrado es el del código que se ve.
    cambiadas, otros = clasificar(_git("status", "--porcelain", "--untracked-files=all"))
    if otros:
        sys.exit("El árbol tiene cambios aparte de las capturas; confirma un commit antes de registrarlas:\n"
                 + "\n".join(otros))
    commit = _git("rev-parse", "--short", "HEAD")
    try:
        nuevas = entradas(cambiadas, RAIZ, commit, args.experimento_web)
    except ValueError as e:
        sys.exit(str(e))
    if not nuevas:
        sys.exit("No hay capturas nuevas ni cambiadas en evidencias/capturas/.")
    registrar(EVIDENCIAS, nuevas, commit, datetime.now())
    print(f"{len(nuevas)} capturas registradas con el commit {commit}.")


if __name__ == "__main__":
    main()
