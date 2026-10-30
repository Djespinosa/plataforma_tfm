"""No regresión numérica de la extracción a ml/automl/motor.py (docs/diseno-api.md §6.2, matiz (a) del §0), exportada
según CONTRATO.md (tipo "comparacion", analisis "no_regresion").

Ejecuta el mismo ensayo de experimento.py en un commit base (en un git worktree temporal fuera del repositorio, con una copia de
data/, que no está versionada) y en el código actual (HEAD, o el árbol de trabajo con --arbol-de-trabajo, solo en
ensayos), y compara:
  - `momentos` del JSON sin las claves de tiempo (tiempo*), con igualdad exacta;
  - las predicciones out-of-fold (parquet) con pandas.testing.assert_frame_equal: columnas no numéricas exactas y
    probabilidades con atol=TOLERANCIA_OOF, rtol=0 (RandomForest con n_jobs > 1 suma los árboles en el orden en que acaban
    los hilos: diferencias de redondeo de ~1e-16 que la isotónica y el apilamiento llevan a ~1e-13).
Ambos ensayos usan el mismo intérprete y el mismo entorno; cada uno ejecuta antes las pruebas de su propio commit (lo hace
experimento.py). Solo validación cruzada: 2014J no se lee.

Uso:
    python ml/no_regresion.py --base 3395ab4
    python ml/no_regresion.py --base 3395ab4 --salida <carpeta fuera de evidencias/> [--arbol-de-trabajo]
"""

from __future__ import annotations

import argparse
import json
import math
import os
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path

import pandas as pd

from cortes_oulad import ejecutar_pruebas
from evidencias import (
    EVIDENCIAS,
    RAIZ,
    actualizar_manifest,
    comprobar_arbol_limpio,
    escribir_json,
    git,
    hardware,
    sha256,
    siguiente_id,
    versiones_entorno,
)

ENSAYO = ["ml/experimento.py", "ml/configs/principal.json", "--ensayo", "--n-trials", "2", "--semanas", "0",
          "--n-bootstrap", "50"]
TOLERANCIA_OOF = 1e-9
METODO = ("El mismo ensayo de experimento.py (mismo intérprete, entorno, datos y semillas) en el commit base, en un git "
          "worktree temporal con una copia de data/, y en el commit nuevo. Se comparan `momentos` del JSON sin las claves "
          "que empiezan por «tiempo» (igualdad exacta de cada valor, NaN igual a NaN) y las predicciones out-of-fold de "
          "cada semana con pandas.testing.assert_frame_equal (columnas no numéricas exactas; probabilidades con "
          f"atol={TOLERANCIA_OOF:g} y rtol=0, y se registra la diferencia absoluta máxima de cada columna). Las claves de "
          "tiempo se excluyen porque dependen de la carga del equipo. La tolerancia de las predicciones se debe a que "
          "RandomForest (scikit-learn) con n_jobs > 1 suma las predicciones de los árboles en el orden en que terminan "
          "los hilos, con diferencias de redondeo de ~1e-16 entre ejecuciones del mismo código, que la calibración "
          "isotónica y el apilamiento propagan a ~1e-13")


# --- Ejecución de los ensayos ------------------------------------------------------------------------------------------

def desenlazar(enlace: Path) -> None:
    """Quita un enlace sin tocar su destino (os.rmdir en una unión, os.unlink en un enlace simbólico). Solo para los
    restos de versiones anteriores de este script, que enlazaban data/ en lugar de copiarla."""
    if os.path.isjunction(enlace):
        os.rmdir(enlace)
    elif enlace.is_symlink():
        enlace.unlink()


def ensayar(raiz: Path, salida: Path) -> dict:
    """Ejecuta ENSAYO en `raiz` con salida en `salida` y devuelve su JSON. Sin PYTHONPATH, para que cada ensayo importe
    el automl de su propio árbol."""
    entorno = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
    subprocess.run([sys.executable, *ENSAYO, "--salida", str(salida)], cwd=raiz, env=entorno, check=True)
    archivos = sorted((salida / "experimentos").glob("exp-*.json"))
    if len(archivos) != 1:
        raise ValueError(f"Se esperaba un único experimento en {salida / 'experimentos'}; hay {len(archivos)}")
    return json.loads(archivos[0].read_text(encoding="utf-8"))


def limpiar_restos() -> None:
    """Quita los worktrees de ejecuciones anteriores que murieron antes de su `finally` (falta de memoria, cierre de la
    terminal): primero la unión data/ (sin seguirla) y luego el worktree. Aborta si la unión no se puede quitar."""
    for linea in git("worktree", "list", "--porcelain").splitlines():
        if not linea.startswith("worktree "):
            continue
        arbol = Path(linea.removeprefix("worktree "))
        if not arbol.parent.name.startswith("no_regresion_"):
            continue
        desenlazar(arbol / "data")
        if (arbol / "data").exists():
            sys.exit(f"No se pudo quitar la unión {arbol / 'data'}; quítala con «rmdir {arbol / 'data'}» (no sigue la "
                     "unión) y vuelve a ejecutar.")
        git("worktree", "remove", "--force", str(arbol))
    git("worktree", "prune")


def ensayar_en_commit(commit: str, carpeta: Path) -> dict:
    """ENSAYO en un worktree temporal del commit, con una copia de data/ del repositorio (no versionada); el worktree se
    elimina siempre. Copia y no enlace: con un enlace, las rutas resueltas de data/ salen del worktree y falla
    test_carpeta_de_los_oof_registrada_es_la_real; además, borrar el worktree nunca puede alcanzar los datos reales."""
    arbol = carpeta / "arbol_base"
    print(f"Si el proceso se interrumpe, limpia con «git worktree remove --force {arbol}» o vuelve a ejecutar este "
          "script, que lo hace al empezar.", flush=True)
    git("worktree", "add", "--detach", str(arbol), commit)
    try:
        shutil.copytree(RAIZ / "data", arbol / "data")
        return ensayar(arbol, carpeta / "salida_base")
    finally:
        git("worktree", "remove", "--force", str(arbol))


# --- Comparación -------------------------------------------------------------------------------------------------------

def sin_tiempos(valor, excluidas: set[str]):
    if isinstance(valor, dict):
        excluidas |= {k for k in valor if k.startswith("tiempo")}
        return {k: sin_tiempos(v, excluidas) for k, v in valor.items() if not k.startswith("tiempo")}
    if isinstance(valor, list):
        return [sin_tiempos(v, excluidas) for v in valor]
    return valor


def diferencias(a, b, ruta: str) -> tuple[list[dict], int]:
    """(diferencias {ruta, base, nuevo}, nº de valores hoja comparados), con igualdad exacta y NaN igual a NaN."""
    if isinstance(a, dict) and isinstance(b, dict):
        salida, n = [], 0
        for k in list(a) + [k for k in b if k not in a]:
            if k not in a or k not in b:
                salida.append({"ruta": f"{ruta}.{k}", "base": a.get(k, "<ausente>"), "nuevo": b.get(k, "<ausente>")})
                continue
            d, m = diferencias(a[k], b[k], f"{ruta}.{k}")
            salida, n = salida + d, n + m
        if list(a) != list(b) and set(a) == set(b):
            salida.append({"ruta": f"{ruta} (orden de claves)", "base": list(a), "nuevo": list(b)})
        return salida, n
    if isinstance(a, list) and isinstance(b, list) and len(a) == len(b):
        salida, n = [], 0
        for i, (x, y) in enumerate(zip(a, b)):
            d, m = diferencias(x, y, f"{ruta}[{i}]")
            salida, n = salida + d, n + m
        return salida, n
    iguales = type(a) is type(b) and (a == b or (isinstance(a, float) and math.isnan(a) and math.isnan(b)))
    return ([] if iguales else [{"ruta": ruta, "base": a, "nuevo": b}]), 1


def comparar_momentos(base: dict, nuevo: dict) -> dict:
    excluidas: set[str] = set()
    a, b = sin_tiempos(base["momentos"], excluidas), sin_tiempos(nuevo["momentos"], excluidas)
    lista, n = diferencias(a, b, "momentos")
    return {"claves_comparadas": sorted({k for m in a for k in m}), "claves_excluidas": sorted(excluidas),
            "valores_comparados": n, "igual": not lista, "diferencias": lista}


def leer_oof(experimento: dict, salida: Path) -> dict[int, tuple[Path, str]]:
    """{semana: (ruta, sha256)} de las predicciones out-of-fold de un ensayo, comprobando el SHA-256 de su JSON."""
    huellas = {k: v for k, v in experimento["predicciones_oof_sha256"].items() if k != "carpeta"}
    archivos = {}
    for nombre, huella in huellas.items():
        ruta = salida / "oof" / nombre
        if sha256(ruta) != huella:
            raise ValueError(f"{ruta} no coincide con el SHA-256 de su ensayo")
        archivos[int(nombre.removeprefix(f"{experimento['id']}_semana_").removesuffix(".parquet"))] = (ruta, huella)
    return archivos


def comparar_oof(base: dict[int, tuple[Path, str]], nuevo: dict[int, tuple[Path, str]]) -> list[dict]:
    if set(base) != set(nuevo):
        raise ValueError(f"Semanas distintas en las predicciones out-of-fold: {sorted(base)} y {sorted(nuevo)}")
    resultado = []
    for semana in sorted(base):
        a, b = pd.read_parquet(base[semana][0]), pd.read_parquet(nuevo[semana][0])
        try:
            pd.testing.assert_frame_equal(a, b, check_exact=False, rtol=0, atol=TOLERANCIA_OOF)
            diferencia = None
        except AssertionError as error:
            diferencia = str(error)
        maximas = {}
        if list(a.columns) == list(b.columns) and len(a) == len(b):
            for columna in a.select_dtypes("float").columns:
                d = (a[columna] - b[columna]).abs().max()
                if d > 0:
                    maximas[columna] = float(d)
        resultado.append({"semana": semana, "filas": int(len(b)), "columnas": list(b.columns),
                          "igual": diferencia is None, "diferencia": diferencia, "tolerancia": TOLERANCIA_OOF,
                          "diferencia_maxima": maximas,
                          "sha256_base": base[semana][1], "sha256_nuevo": nuevo[semana][1],
                          "sha256_igual": base[semana][1] == nuevo[semana][1]})
    return resultado


# --- Principal ---------------------------------------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base", required=True, help="Commit base (antes de la extracción), p. ej. 3395ab4")
    parser.add_argument("--salida", type=Path, default=EVIDENCIAS, help="Carpeta de evidencias (por defecto evidencias/)")
    parser.add_argument("--arbol-de-trabajo", action="store_true",
                        help="Compara con el árbol de trabajo sin confirmar (solo con --salida fuera de evidencias/)")
    args = parser.parse_args()
    salida: Path = args.salida
    if args.arbol_de_trabajo and salida.resolve() == EVIDENCIAS.resolve():
        parser.error("--arbol-de-trabajo solo vale en un ensayo con --salida fuera de evidencias/")

    inicio = time.perf_counter()
    commit = comprobar_arbol_limpio(salida)
    commit_base = git("rev-parse", "--short", f"{args.base}^{{commit}}")
    sin_confirmar = bool(git("status", "--porcelain"))
    if sin_confirmar and not args.arbol_de_trabajo:
        sys.exit("El árbol de trabajo tiene cambios sin confirmar: el ensayo «nuevo» no sería HEAD. Confirma un commit "
                 "o usa --arbol-de-trabajo en un ensayo.")
    if commit_base == commit and not sin_confirmar:
        sys.exit("El commit base es HEAD: la comparación sería trivial.")
    if subprocess.run(["git", "merge-base", "--is-ancestor", commit_base, "HEAD"], cwd=RAIZ).returncode != 0:
        sys.exit(f"{commit_base} no es antecesor de HEAD.")
    limpiar_restos()
    fecha = datetime.now()
    for carpeta in ("experimentos", "pruebas"):
        (salida / carpeta).mkdir(parents=True, exist_ok=True)
    id_exp = siguiente_id(salida / "experimentos", fecha)
    archivo_pruebas = f"pruebas/{id_exp}_pruebas.xml"

    temporal = Path(tempfile.mkdtemp(prefix="no_regresion_"))
    print(f"Ensayo en el commit base {commit_base} (worktree en {temporal})", flush=True)
    base = ensayar_en_commit(commit_base, temporal)
    print(f"Ensayo en el commit nuevo {commit}{' + árbol de trabajo' if sin_confirmar else ''}", flush=True)
    nuevo = ensayar(RAIZ, temporal / "salida_nuevo")
    if base["commit"] != commit_base or nuevo["commit"] != commit:
        raise ValueError(f"Los ensayos registran los commits {base['commit']} y {nuevo['commit']}, no "
                         f"{commit_base} y {commit}")

    momentos = comparar_momentos(base, nuevo)
    oof = comparar_oof(leer_oof(base, temporal / "salida_base"), leer_oof(nuevo, temporal / "salida_nuevo"))
    if momentos["valores_comparados"] == 0 or not oof:
        raise ValueError("Los ensayos no dejaron momentos ni predicciones que comparar")
    identico = momentos["igual"] and all(o["igual"] for o in oof)
    # Después de los ensayos (el commit es el mismo), para no tener la suite en memoria mientras corren (revisión del
    # incremento 2, importante 3).
    resultado_pruebas = ejecutar_pruebas(salida / archivo_pruebas)

    experimento = {
        "id": id_exp,
        "tipo": "comparacion",
        "analisis": "no_regresion",
        "fecha": fecha.isoformat(timespec="seconds"),
        "commit": commit,
        "descripcion": "No regresión numérica de la extracción de la parte genérica de experimento.py, modelo_final.py "
                       "y shap_estabilidad.py a ml/automl/motor.py y ml/automl/explicacion.py (docs/diseno-api.md "
                       "§6.2): el mismo ensayo en el commit base y en el nuevo debe dar los mismos `momentos` (sin "
                       "tiempos) y las mismas predicciones out-of-fold.",
        "commit_base": commit_base,
        "commit_nuevo": commit,
        "arbol_de_trabajo": sin_confirmar,
        "comando": " ".join(["python", *ENSAYO, "--salida", "<carpeta temporal>"]),
        "metodo": METODO,
        "ensayos": {nombre: {"id": e["id"], "commit": e["commit"], "configuracion": e["configuracion"],
                             "pruebas": e["pruebas"]} for nombre, e in (("base", base), ("nuevo", nuevo))},
        "comparaciones": {"momentos": momentos, "predicciones_oof": oof},
        "identico": identico,
        "oof_sha256": {"base": {str(o["semana"]): o["sha256_base"] for o in oof},
                       "nuevo": {str(o["semana"]): o["sha256_nuevo"] for o in oof}},
        "evaluado_en_prueba": False,
        "dataset": nuevo["dataset"],
        "entorno": versiones_entorno("pandas", "numpy", "pyarrow", "sklearn", "optuna", "xgboost", "lightgbm",
                                     "catboost", "scipy", "pytest") | {"nota": "el mismo intérprete y entorno en los dos ensayos"},
        "hardware": hardware(),
        "pruebas": {"informe": archivo_pruebas} | resultado_pruebas,
        "tiempo_ejecucion_s": round(time.perf_counter() - inicio, 1),
        "figuras": [],
    }
    escribir_json(salida / "experimentos" / f"{id_exp}.json", experimento)
    actualizar_manifest(salida, fecha, commit, id_exp, [],
                        [{"archivo": archivo_pruebas, "descripcion": "JUnit de todas las pruebas de ml/tests en el "
                          "commit de la comprobación de no regresión", "experimento": id_exp}])
    if identico:
        shutil.rmtree(temporal, ignore_errors=True)
        print(f"Igual (predicciones dentro de atol={TOLERANCIA_OOF:g}). Exportado {id_exp} en {salida} (commit {commit}, base {commit_base})")
    else:
        print(f"DISTINTO: revisa {salida / 'experimentos' / f'{id_exp}.json'}; ensayos conservados en {temporal}")
        sys.exit(1)


if __name__ == "__main__":
    main()
