"""Diagrama de componentes de la plataforma para el apartado 5.1.2 de la memoria (evidencias/CONTRATO.md, arquitectura).

Dibuja con matplotlib (sin dependencias nuevas) la interfaz Angular, la API Flask, el trabajador, el núcleo ml/automl,
la persistencia (PostgreSQL y archivos) y el flujo de ML en scripts que produce los paquetes desplegados y las
evidencias. Este script es la fuente del diagrama. Escribe arquitectura/arquitectura_componentes.png (300 ppp) y .svg y
los añade a la sección `arquitectura` de manifest.json con {archivo, fuente, descripcion, commit}. Solo desde un árbol
limpio; se ejecuta desde la raíz:

    python -m scripts.diagrama_arquitectura                    # a evidencias/
    python -m scripts.diagrama_arquitectura --salida carpeta   # ensayo, con cambios sin confirmar
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Rectangle  # noqa: E402

from api import RAIZ  # noqa: E402,F401  (pone ml/ en sys.path)
from evidencias import EVIDENCIAS, SECCIONES_MANIFEST, comprobar_arbol_limpio  # noqa: E402

NOMBRE = "arquitectura_componentes"
FUENTE = "scripts/diagrama_arquitectura.py"
DESCRIPCION = ("Diagrama de componentes: interfaz Angular, API Flask, trabajador, núcleo ml/automl, persistencia "
               "(PostgreSQL y archivos) y flujo de ML en scripts")

TINTA, BORDE_ZONA = "#1f2933", "#7b8794"
RELLENOS = {"web": "#dbeafe", "api": "#dcfce7", "ml": "#fef3c7", "datos": "#ede9fe", "fuera": "#f1f5f9"}


def _zona(ax, x0, y0, x1, y1, titulo):
    ax.add_patch(Rectangle((x0, y0), x1 - x0, y1 - y0, fill=False, ec=BORDE_ZONA, lw=0.8, ls=(0, (4, 3))))
    ax.text(x0 + 0.8, y1 - 0.6, titulo, ha="left", va="top", fontsize=7.5, color=BORDE_ZONA, style="italic")


def _caja(ax, x0, y0, x1, y1, titulo, lineas, relleno):
    ax.add_patch(FancyBboxPatch((x0, y0), x1 - x0, y1 - y0, boxstyle="round,pad=0,rounding_size=1.2",
                                fc=RELLENOS[relleno], ec=TINTA, lw=0.9))
    centro = (x0 + x1) / 2
    ax.text(centro, y1 - 1.6, titulo, ha="center", va="top", fontsize=8.5, weight="bold", color=TINTA)
    ax.text(centro, y1 - 5.0, "\n".join(lineas), ha="center", va="top", fontsize=7, color=TINTA, linespacing=1.35)


def _flecha(ax, desde, hasta, texto=None, doble=False, desplazamiento=(1.0, 0.0), ha="left"):
    ax.add_patch(FancyArrowPatch(desde, hasta, arrowstyle="<|-|>" if doble else "-|>", mutation_scale=9,
                                 lw=0.9, color=TINTA, shrinkA=0, shrinkB=0))
    if texto:
        x, y = (desde[0] + hasta[0]) / 2 + desplazamiento[0], (desde[1] + hasta[1]) / 2 + desplazamiento[1]
        ax.text(x, y, texto, ha=ha, va="center", fontsize=6.8, color=TINTA, linespacing=1.3)


def dibujar() -> plt.Figure:
    fig, ax = plt.subplots(figsize=(9, 8.4))
    ax.set_xlim(0, 100)
    ax.set_ylim(-1.5, 90)
    ax.axis("off")

    _zona(ax, 1, 76, 99, 89, "Navegador")
    _caja(ax, 12, 77, 88, 87, "Interfaz web · Angular 21",
          ["carga · configuración · seguimiento · evaluación · modelos · estimación · explicaciones · historial",
           "servicios HTTP · textos de la interfaz · sondeo del entrenamiento cada 3 s"], "web")

    _zona(ax, 1, 46, 99, 69, "Servidor de la plataforma (Python)")
    _caja(ax, 3, 48, 36, 66, "API REST · Flask",
          ["rutas: conjuntos, experimentos,", "modelos, predicciones, estado",
           "servicios: configuración, evaluación,", "explicaciones, paquetes (SHA-256)",
           "textos.py: avisos y guardarraíles"], "api")
    _caja(ax, 40, 48, 62, 66, "Núcleo ML · ml/automl",
          ["validación y partición", "preprocesado", "búsqueda (Optuna)", "calibración y apilamiento",
           "comparación (DeLong, Holm)", "explicación (SHAP) · equidad"], "ml")
    _caja(ax, 66, 48, 97, 66, "Trabajador · flask trabajador",
          ["toma el experimento en cola más antiguo,", "de uno en uno; latido cada 30 s",
           "(sin latido en 2 min, la API avisa)", "al arrancar: en curso → interrumpido",
           "(el usuario puede reintentarlo)", "guarda paquete y predicciones OOF"], "api")

    _zona(ax, 1, 24, 99, 38, "Persistencia")
    _caja(ax, 3, 25.5, 53, 35.5, "PostgreSQL 16 · Docker",
          ["conjunto_datos · experimento (cola y estado) · modelo", "lote_prediccion · prediccion · explicacion"],
          "datos")
    _caja(ax, 57, 25.5, 97, 35.5, "Archivos",
          ["CSV cargados · paquete.joblib y OOF por experimento", "paquetes de ml/ en su sitio (ruta y SHA-256 en modelo)"],
          "datos")

    _zona(ax, 1, -1, 99, 18, "Flujo de ML en scripts (fuera de la aplicación)")
    _caja(ax, 3, 3.5, 18, 15, "OULAD", ["7 CSV", "CC BY 4.0"], "fuera")
    _caja(ax, 22, 3.5, 46, 15, "Scripts de ml/", ["cortes, experimentos,", "SHAP, modelo final", "(usan ml/automl)"],
          "ml")
    _caja(ax, 50, 3.5, 74, 15, "Paquetes", ["modelos desplegados,", "un .joblib por momento"], "fuera")
    _caja(ax, 78, 3.5, 97, 15, "evidencias/", ["resultados, figuras,", "pruebas y capturas", "→ memoria del TFM"],
          "fuera")

    _flecha(ax, (50, 77), (50, 69), "HTTP/JSON en /api (proxy de desarrollo)", doble=True)
    _flecha(ax, (36, 57), (40, 57))
    _flecha(ax, (66, 57), (62, 57))
    _flecha(ax, (30, 48), (54, 38), "tablas (SQLAlchemy) · guarda los CSV\nlee los paquetes (comprueba SHA-256)",
            doble=True, desplazamiento=(-13.5, 0.0), ha="right")
    _flecha(ax, (72, 48), (56, 38), "cola, latido, estado y modelos (tablas)\npaquete y OOF (archivos)", doble=True,
            desplazamiento=(9.5, 0.0))
    _flecha(ax, (18, 9.25), (22, 9.25))
    _flecha(ax, (46, 9.25), (50, 9.25))
    _flecha(ax, (52, 15), (52, 25.5), "flask importar-paquetes: registra experimento y modelos\n"
            "(lee también evidencias/experimentos)", desplazamiento=(1.0, 0.7))
    ax.plot([34, 34, 87.5], [3.5, 0.6, 0.6], color=TINTA, lw=0.9, solid_joinstyle="miter")
    _flecha(ax, (87.5, 0.6), (87.5, 3.5))
    return fig


def registrar(salida: Path, entradas: list[dict], commit: str, fecha: datetime) -> None:
    ruta = salida / "manifest.json"
    manifest = json.loads(ruta.read_text(encoding="utf-8")) if ruta.exists() else {k: [] for k in SECCIONES_MANIFEST}
    archivos = {e["archivo"] for e in entradas}
    manifest["arquitectura"] = [e for e in manifest.get("arquitectura", []) if e["archivo"] not in archivos] + entradas
    manifest["generado"] = fecha.isoformat(timespec="seconds")
    manifest["commit"] = commit
    ruta.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def exportar(salida: Path, commit: str, fecha: datetime) -> list[dict]:
    carpeta = salida / "arquitectura"
    carpeta.mkdir(parents=True, exist_ok=True)
    fig = dibujar()
    fig.savefig(carpeta / f"{NOMBRE}.png", dpi=300, bbox_inches="tight", metadata={"Software": None})
    plt.rcParams["svg.hashsalt"] = NOMBRE  # identificadores fijos: el mismo commit da el mismo SVG
    fig.savefig(carpeta / f"{NOMBRE}.svg", bbox_inches="tight", metadata={"Date": None, "Creator": None})
    plt.close(fig)
    entradas = [{"archivo": f"arquitectura/{NOMBRE}.{ext}", "fuente": FUENTE, "descripcion": DESCRIPCION,
                 "commit": commit} for ext in ("png", "svg")]
    registrar(salida, entradas, commit, fecha)
    return entradas


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--salida", type=Path, default=EVIDENCIAS)
    args = parser.parse_args()
    commit = comprobar_arbol_limpio(args.salida)
    entradas = exportar(args.salida, commit, datetime.now())
    print(f"{len(entradas)} archivos de arquitectura en {args.salida} con el commit {commit}.")


if __name__ == "__main__":
    main()
