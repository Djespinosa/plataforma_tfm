"""Análisis exploratorio de OULAD exportado a evidencias/ según evidencias/CONTRATO.md.

Genera:
  - Presentaciones por módulo (courses.csv + nº de estudiantes de studentInfo.csv).
  - Distribución de final_result por presentación (studentInfo.csv).
  - Bajas por semana a partir de date_unregistration (studentRegistration.csv),
    incluidas las anteriores al día 0 del módulo-presentación.
  - Calidad de datos, versiones del entorno y SHA-256 de los CSV de entrada.

Uso:
    python ml/exploracion_oulad.py
    python ml/exploracion_oulad.py --salida /tmp/prueba   # ensayo fuera de evidencias/
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.patches  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import matplotlib.ticker  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

RAIZ = Path(__file__).resolve().parents[1]
DATOS = RAIZ / "data" / "raw" / "oulad"
EVIDENCIAS = RAIZ / "evidencias"
ARCHIVOS_ENTRADA = ["courses.csv", "studentInfo.csv", "studentRegistration.csv"]
PRESENTACION_REFERENCIA = "2014J"

ORDEN_RESULTADOS = ["Distinction", "Pass", "Fail", "Withdrawn"]
COLORES_RESULTADOS = {
    "Distinction": "#1a9850",
    "Pass": "#91cf60",
    "Fail": "#fc8d59",
    "Withdrawn": "#d73027",
}
DPI = 300


def git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=RAIZ, capture_output=True, text=True, check=True
    ).stdout.strip()


def comprobar_arbol_limpio(salida: Path) -> str:
    """Devuelve el commit actual; aborta si se exporta a evidencias/ con cambios sin confirmar."""
    commit = git("rev-parse", "--short", "HEAD")
    if salida.resolve() == EVIDENCIAS.resolve() and git("status", "--porcelain"):
        sys.exit(
            "El árbol de trabajo tiene cambios sin confirmar. Confirma un commit antes de "
            "exportar a evidencias/ (CONTRATO.md) o usa --salida para un ensayo."
        )
    return commit


def siguiente_id(dir_experimentos: Path, fecha: datetime) -> str:
    prefijo = f"exp-{fecha:%Y-%m-%d}-"
    existentes = [
        int(p.stem.removeprefix(prefijo))
        for p in dir_experimentos.glob(f"{prefijo}*.json")
        if p.stem.removeprefix(prefijo).isdigit()
    ]
    return f"{prefijo}{max(existentes, default=0) + 1:02d}"


def sha256(ruta: Path) -> str:
    h = hashlib.sha256()
    with ruta.open("rb") as f:
        for bloque in iter(lambda: f.read(1 << 20), b""):
            h.update(bloque)
    return h.hexdigest()


def versiones_entorno() -> dict:
    return {
        "python": platform.python_version(),
        "pandas": pd.__version__,
        "numpy": np.__version__,
        "matplotlib": matplotlib.__version__,
    }


def cargar_datos() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    claves = ["code_module", "code_presentation", "id_student"]
    cursos, info, registro = (
        pd.read_csv(DATOS / archivo, na_values="?") for archivo in ARCHIVOS_ENTRADA
    )
    if info.duplicated(claves).any() or registro.duplicated(claves).any():
        raise ValueError("Claves (módulo, presentación, estudiante) duplicadas en OULAD")
    return cursos, info, registro


def presentaciones_por_modulo(cursos: pd.DataFrame, info: pd.DataFrame) -> pd.DataFrame:
    estudiantes = (
        info.groupby(["code_module", "code_presentation"]).size().rename("n_estudiantes")
    )
    return (
        cursos.set_index(["code_module", "code_presentation"])
        .join(estudiantes)
        .reset_index()
        .sort_values(["code_module", "code_presentation"])
    )


def figura_presentaciones(tabla: pd.DataFrame, ruta: Path) -> None:
    pivote = tabla.pivot(
        index="code_module", columns="code_presentation", values="n_estudiantes"
    ).sort_index(axis=1)
    fig, ax = plt.subplots(figsize=(9, 5))
    pivote.plot(kind="bar", ax=ax, width=0.8, colormap="tab10")
    ax.set_xlabel("Módulo")
    ax.set_ylabel("Estudiantes matriculados")
    ax.set_title("Presentaciones por módulo y estudiantes matriculados (OULAD)")
    ax.legend(title="Presentación")
    ax.tick_params(axis="x", rotation=0)
    for modulo_idx, (modulo, fila) in enumerate(pivote.iterrows()):
        ax.annotate(
            f"{fila.notna().sum()} pres.",
            (modulo_idx, fila.max()),
            xytext=(0, 4),
            textcoords="offset points",
            ha="center",
            fontsize=8,
        )
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(ruta, dpi=DPI)
    plt.close(fig)


def distribucion_final_result(info: pd.DataFrame) -> pd.DataFrame:
    conteos = (
        info.groupby(["code_module", "code_presentation"])["final_result"]
        .value_counts()
        .unstack(fill_value=0)
        .reindex(columns=ORDEN_RESULTADOS, fill_value=0)
    )
    conteos.columns.name = None
    return conteos


def figura_final_result(conteos: pd.DataFrame, ruta: Path) -> None:
    proporciones = conteos.div(conteos.sum(axis=1), axis=0)
    etiquetas = [f"{m} {p}" for m, p in proporciones.index]
    fig, ax = plt.subplots(figsize=(9, 8))
    izquierda = pd.Series(0.0, index=proporciones.index)
    for resultado in ORDEN_RESULTADOS:
        ax.barh(
            etiquetas,
            proporciones[resultado],
            left=izquierda,
            color=COLORES_RESULTADOS[resultado],
            label=resultado,
        )
        izquierda += proporciones[resultado]
    ax.invert_yaxis()
    ax.set_xlim(0, 1)
    ax.xaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0))
    ax.set_xlabel("Proporción de estudiantes")
    ax.set_ylabel("Módulo y presentación")
    ax.set_title("Distribución de final_result por presentación (OULAD)")
    ax.legend(ncols=4, loc="upper center", bbox_to_anchor=(0.5, -0.07))
    fig.tight_layout()
    fig.savefig(ruta, dpi=DPI)
    plt.close(fig)


def bajas_por_semana(registro: pd.DataFrame) -> pd.Series:
    """Semana = floor(día / 7): el día 0 cae en la semana 0 y los días -7..-1 en la semana -1."""
    bajas = registro["date_unregistration"].dropna().astype(int)
    semanas = bajas // 7
    return semanas.value_counts().sort_index().reindex(
        range(semanas.min(), semanas.max() + 1), fill_value=0
    )


def figura_bajas(por_semana: pd.Series, ruta: Path) -> None:
    fig, ax = plt.subplots(figsize=(11, 5))
    colores = ["#7570b3" if s < 0 else "#d95f02" for s in por_semana.index]
    ax.bar(por_semana.index, por_semana.values, color=colores, width=0.9)
    ax.axvline(-0.5, color="black", linestyle="--", linewidth=1)
    ax.text(-0.8, ax.get_ylim()[1] * 0.95, "inicio (día 0)", ha="right", fontsize=9)
    ax.set_xlabel("Semana relativa al inicio del módulo-presentación (floor(día / 7))")
    ax.set_ylabel("Bajas (date_unregistration)")
    ax.set_title("Bajas por semana, incluidas las anteriores al día 0 (OULAD)")
    ax.legend(
        handles=[
            matplotlib.patches.Patch(color="#7570b3", label="Antes del día 0"),
            matplotlib.patches.Patch(color="#d95f02", label="Día 0 o posterior"),
        ]
    )
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(ruta, dpi=DPI)
    plt.close(fig)


def calidad_datos(cursos: pd.DataFrame, info: pd.DataFrame, registro: pd.DataFrame) -> dict:
    """Incoherencias entre date_unregistration, final_result y la duración del módulo."""
    claves = ["code_module", "code_presentation"]
    union = info.merge(registro, on=[*claves, "id_student"], validate="1:1").merge(
        cursos, on=claves, validate="m:1"
    )
    baja = union["date_unregistration"]
    con_fecha = baja.notna()
    antes_dia_0 = baja < 0
    tras_fin = baja > union["module_presentation_length"]
    return {
        "bajas_antes_dia_0": {
            "total": int(antes_dia_0.sum()),
            PRESENTACION_REFERENCIA: int(
                (antes_dia_0 & (union["code_presentation"] == PRESENTACION_REFERENCIA)).sum()
            ),
        },
        "bajas_dia_0_o_posterior": int((baja >= 0).sum()),
        "withdrawn_sin_fecha_baja": int(((union["final_result"] == "Withdrawn") & ~con_fecha).sum()),
        "fail_con_fecha_baja": int(((union["final_result"] == "Fail") & con_fecha).sum()),
        "matriculas_sin_fecha_registro": int(union["date_registration"].isna().sum()),
        "bajas_posteriores_duracion_modulo": {
            "definicion": "date_unregistration > module_presentation_length (courses.csv)",
            "total": int(tras_fin.sum()),
            "por_presentacion": [
                {"code_module": m, "code_presentation": p, "n": int(n)}
                for (m, p), n in union[tras_fin].groupby(claves).size().items()
            ],
        },
        "con_fecha_baja": int(con_fecha.sum()),
        "con_fecha_baja_por_final_result": {
            r: int((con_fecha & (union["final_result"] == r)).sum()) for r in ORDEN_RESULTADOS
        },
    }


def bajas_antes_dia_0_por_presentacion(registro: pd.DataFrame) -> list[dict]:
    agrupado = registro.groupby(["code_module", "code_presentation"])
    tabla = pd.DataFrame(
        {
            "n_registros": agrupado.size(),
            "bajas_total": agrupado["date_unregistration"].count(),
            "bajas_antes_dia_0": agrupado["date_unregistration"].apply(lambda s: int((s < 0).sum())),
        }
    ).reset_index()
    return tabla.to_dict(orient="records")


def actualizar_manifest(salida: Path, fecha: datetime, commit: str, id_exp: str, figuras: list[dict]) -> None:
    ruta = salida / "manifest.json"
    manifest = (
        json.loads(ruta.read_text(encoding="utf-8"))
        if ruta.exists()
        else {k: [] for k in ["experimentos", "figuras", "capturas", "arquitectura", "pruebas", "usabilidad"]}
    )
    manifest["generado"] = fecha.isoformat(timespec="seconds")
    manifest["commit"] = commit
    archivo_exp = f"experimentos/{id_exp}.json"
    if archivo_exp not in manifest["experimentos"]:
        manifest["experimentos"].append(archivo_exp)
    nuevas = {f["archivo"] for f in figuras}
    manifest["figuras"] = [f for f in manifest["figuras"] if f["archivo"] not in nuevas] + figuras
    orden = ["generado", "commit", "experimentos", "figuras", "capturas", "arquitectura", "pruebas", "usabilidad"]
    manifest = {k: manifest[k] for k in orden if k in manifest} | {
        k: v for k, v in manifest.items() if k not in orden
    }
    ruta.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--salida", type=Path, default=EVIDENCIAS, help="Carpeta de evidencias (por defecto evidencias/)")
    args = parser.parse_args()

    inicio = time.perf_counter()
    salida: Path = args.salida
    commit = comprobar_arbol_limpio(salida)
    fecha = datetime.now()
    (salida / "experimentos").mkdir(parents=True, exist_ok=True)
    (salida / "figuras").mkdir(parents=True, exist_ok=True)
    id_exp = siguiente_id(salida / "experimentos", fecha)

    cursos, info, registro = cargar_datos()

    presentaciones = presentaciones_por_modulo(cursos, info)
    conteos = distribucion_final_result(info)
    por_semana = bajas_por_semana(registro)

    figuras = [
        (f"figuras/{id_exp}_presentaciones_por_modulo.png",
         "Presentaciones por módulo y estudiantes matriculados en OULAD",
         lambda r: figura_presentaciones(presentaciones, r)),
        (f"figuras/{id_exp}_final_result_por_presentacion.png",
         "Distribución de final_result por módulo-presentación en OULAD",
         lambda r: figura_final_result(conteos, r)),
        (f"figuras/{id_exp}_bajas_por_semana.png",
         "Bajas por semana relativa al inicio, incluidas las anteriores al día 0, en OULAD",
         lambda r: figura_bajas(por_semana, r)),
    ]
    for archivo, _, dibujar in figuras:
        dibujar(salida / archivo)

    totales = info["final_result"].value_counts().reindex(ORDEN_RESULTADOS, fill_value=0)
    experimento = {
        "id": id_exp,
        "fecha": fecha.isoformat(timespec="seconds"),
        "commit": commit,
        "descripcion": (
            "Análisis exploratorio de OULAD: presentaciones por módulo, distribución de "
            "final_result por presentación, bajas por semana (incluidas las anteriores al día 0) "
            "y calidad de datos"
        ),
        "dataset": {
            "nombre": "OULAD",
            "version": "2017",
            "n_registros": int(len(info)),
            "n_variables": int(info.shape[1]),
            "tablas_usadas": ARCHIVOS_ENTRADA,
            "sha256": {archivo: sha256(DATOS / archivo) for archivo in ARCHIVOS_ENTRADA},
            "distribucion_clases": {
                "no_desercion": int(totales.drop("Withdrawn").sum()),
                "desercion": int(totales["Withdrawn"]),
            },
            "distribucion_final_result": {k: int(v) for k, v in totales.items()},
        },
        "exploracion": {
            "n_modulos": int(cursos["code_module"].nunique()),
            "n_presentaciones": int(len(cursos)),
            "presentaciones_por_modulo": {
                m: g["code_presentation"].tolist()
                for m, g in presentaciones.groupby("code_module")
            },
            "detalle_presentaciones": [
                {**fila, "module_presentation_length": int(fila["module_presentation_length"]),
                 "n_estudiantes": int(fila["n_estudiantes"])}
                for fila in presentaciones.to_dict(orient="records")
            ],
            "final_result_por_presentacion": [
                {"code_module": m, "code_presentation": p, **{k: int(v) for k, v in fila.items()}}
                for (m, p), fila in conteos.iterrows()
            ],
            "bajas_por_semana": {
                "definicion_semana": "floor(date_unregistration / 7); el día 0 es el inicio del módulo-presentación",
                "conteos": {str(int(s)): int(n) for s, n in por_semana.items()},
            },
            "bajas_antes_dia_0_por_presentacion": bajas_antes_dia_0_por_presentacion(registro),
        },
        "calidad_datos": calidad_datos(cursos, info, registro),
        "entorno": versiones_entorno(),
        "tiempo_ejecucion_s": round(time.perf_counter() - inicio, 2),
        "figuras": [archivo for archivo, _, _ in figuras],
    }
    (salida / "experimentos" / f"{id_exp}.json").write_text(
        json.dumps(experimento, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    actualizar_manifest(
        salida, fecha, commit, id_exp,
        [{"archivo": a, "descripcion": d, "experimento": id_exp} for a, d, _ in figuras],
    )
    print(f"Exportado {id_exp} en {salida} (commit {commit})")


if __name__ == "__main__":
    main()
