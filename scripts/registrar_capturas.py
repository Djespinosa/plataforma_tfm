"""Registra en evidencias/manifest.json las capturas de la interfaz (docs/diseno-web.md §12, decisión W-10).

Las capturas se toman a mano (Chrome a 1440 × 900) con web/ y api/ confirmados en un commit, y se guardan en
evidencias/capturas/ con los nombres de CAPTURAS. Este script, desde la raíz y con ese mismo commit, añade o sustituye
en `capturas` una entrada {archivo, descripcion, commit, datos} por cada PNG nuevo o cambiado según `git status` (las
capturas ya confirmadas y sin cambios conservan su entrada y su commit); `datos` lleva el experimento y el
CSV (ruta y SHA-256) que muestra la vista. Reescribe también capturas/indice.md (pantalla, requisito y cambios de código
de cada captura). El árbol debe estar limpio salvo esos PNG (nuevos o cambiados, no borrados) y no se confirma nada
entre la toma y el registro: el commit registrado es el HEAD, el del código que se ve. El
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
CSV_EXTREMA = "data/procesado/demo/semana_12_2014B.csv"  # fila 3261 (632215): clics_glossary −7,61 log-odds
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
    "web-explicacion-extrema.png": ("Explicación local con una contribución extrema, |SHAP| > 5 log-odds, marcada y con "
                                    "su aviso (semana 12, cohorte 2014B)", IMPORTADO, CSV_EXTREMA),
    "web-carga.png": ("Carga de un CSV de entrenamiento (flujo genérico)", GENERICO, CSV_ENTRENAMIENTO),
    "web-configuracion.png": ("Configuración comprobada del entrenamiento (flujo genérico)", GENERICO,
                              CSV_ENTRENAMIENTO),
    "web-seguimiento.png": ("Seguimiento del entrenamiento (flujo genérico)", GENERICO, CSV_ENTRENAMIENTO),
}


# archivo → (pantalla, requisitos de docs/diseno-api.md §1), para el índice capturas/indice.md
PANTALLAS: dict[str, tuple[str, str]] = {
    "web-carga.png": ("Datos para entrenar (paso 1)", "RF-01"),
    "web-configuracion.png": ("Configurar el entrenamiento (paso 2)", "RF-02"),
    "web-seguimiento.png": ("Seguimiento del entrenamiento (paso 3)", "RF-03"),
    "web-evaluacion-resumen.png": ("Evaluación del modelo, vista resumida (paso 4)", "RF-04, RF-07"),
    "web-evaluacion-detalle.png": ("Evaluación del modelo, detalle técnico (paso 4)", "RF-04, RF-07"),
    "web-modelos.png": ("Modelos desplegados (paso 5)", "RF-05"),
    "web-prediccion-lista.png": ("Probabilidades estimadas del lote (paso 5)", "RF-05"),
    "web-explicacion-global.png": ("Variables que más contribuyen (paso 6)", "RF-06"),
    "web-explicacion-local.png": ("Explicación de una estimación (paso 6)", "RF-06, RF-07"),
    "web-explicacion-extrema.png": ("Explicación de una estimación con contribución extrema (paso 6)", "RF-06, RF-07"),
}
INDICE = "capturas/indice.md"
COMPROBACIONES = (
    "Ninguna captura muestra métricas de 2014J: las de evaluación son out-of-fold de la validación cruzada, con su aviso "
    "visible. Las estimaciones de la cohorte 2014B (datos de demostración) llevan el aviso de que están dentro de la "
    "muestra y no miden el rendimiento. El flujo genérico (carga, configuración y seguimiento) usa el presupuesto de "
    "demostración, con su aviso visible.")


def cambios_de_codigo(desde: str, hasta: str) -> list[str]:
    """Archivos de web/src y api/ que cambian entre dos commits, sin las pruebas ni api/exportar_pruebas.py."""
    salida = _git("diff", "--name-only", desde, hasta, "--", "web/src", "api",
                  ":(exclude)api/tests", ":(exclude)*.spec.ts", ":(exclude)web/src/app/pruebas",
                  ":(exclude)api/exportar_pruebas.py")
    return salida.splitlines()


def indice(capturas: list[dict], commit: str, cambios=cambios_de_codigo) -> str:
    """Tabla de las capturas registradas: archivo, pantalla, requisito, experimento, CSV, commit del código con que se
    tomó y archivos de web/ y api/ que cambian desde ese commit hasta `commit` (el del registro)."""
    filas = []
    por_nombre = {c["archivo"].removeprefix("capturas/"): c for c in capturas}
    for nombre in [n for n in PANTALLAS if n in por_nombre]:  # en el orden de los pasos, no del manifest
        c = por_nombre[nombre]
        pantalla, requisito = PANTALLAS[nombre]
        csv = c["datos"].get("csv", {}).get("ruta", "—")
        distintos = ", ".join(f"`{a}`" for a in cambios(c["commit"], commit)) or "ninguno"
        filas.append(f"| `{nombre}` | {pantalla} | {requisito} | {c['datos']['experimento']} | `{csv}` | {c['commit']} "
                     f"| {distintos} |")
    return "\n".join(["# Capturas de la interfaz", "", COMPROBACIONES, "",
                      f"Código de referencia: {commit}. La última columna lista los archivos de `web/src` y `api/` (sin "
                      "pruebas) que cambian entre el commit de cada captura y el de referencia.", "",
                      "| Archivo | Pantalla | Requisito | Experimento | CSV | Commit del código | Cambios hasta el de "
                      "referencia |", "|---|---|---|---|---|---|---|", *filas, ""])


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


def registrar(evidencias: Path, nuevas: list[dict], commit: str, fecha: datetime, cambios=cambios_de_codigo) -> None:
    ruta = evidencias / "manifest.json"
    manifest = json.loads(ruta.read_text(encoding="utf-8"))
    archivos = {c["archivo"] for c in nuevas}
    manifest["capturas"] = [c for c in manifest["capturas"] if c["archivo"] not in archivos | {INDICE}] + nuevas
    (evidencias / INDICE).write_text(indice(manifest["capturas"], commit, cambios), encoding="utf-8", newline="\n")
    manifest["capturas"].append({"archivo": INDICE, "descripcion": "Índice de las capturas: pantalla, requisito, "
                                 "experimento, CSV y comprobaciones", "commit": commit})
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
        if ruta == f"evidencias/{INDICE}" and linea[:2] in ("??", " M", "M "):
            continue  # lo reescribe este script
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
