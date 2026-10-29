"""Funciones comunes para exportar a evidencias/ según evidencias/CONTRATO.md."""

from __future__ import annotations

import hashlib
import importlib
import json
import platform
import subprocess
import sys
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
DATOS = RAIZ / "data" / "raw" / "oulad"
EVIDENCIAS = RAIZ / "evidencias"
SECCIONES_MANIFEST = ["experimentos", "figuras", "capturas", "arquitectura", "pruebas", "usabilidad"]


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


def ruta_registrada(carpeta: Path) -> str:
    """Carpeta real de unas salidas tal como se registra en el JSON: relativa a la raíz del repositorio si está dentro
    (data/procesado/oof en una exportación) y absoluta si no (la carpeta de un ensayo)."""
    real = carpeta.resolve()
    return (real.relative_to(RAIZ) if real.is_relative_to(RAIZ) else real).as_posix()


def versiones_entorno(*modulos: str) -> dict:
    """Versión de Python y de cada módulo; la clave es el nombre del paquete (scikit-learn para sklearn)."""
    nombres = {"sklearn": "scikit-learn"}
    return {"python": platform.python_version()} | {
        nombres.get(m, m): importlib.import_module(m).__version__ for m in modulos
    }


def hardware() -> dict:
    """Procesador, núcleos y memoria del equipo que ejecuta el experimento, sin su nombre."""
    import joblib

    cpu = platform.processor()
    if sys.platform == "win32":
        import ctypes
        import winreg

        clave = r"HARDWARE\DESCRIPTION\System\CentralProcessor\0"
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, clave) as k:
            cpu = winreg.QueryValueEx(k, "ProcessorNameString")[0].strip()

        class EstadoMemoria(ctypes.Structure):
            _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                        ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                        ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                        ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                        ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]

        estado = EstadoMemoria(dwLength=ctypes.sizeof(EstadoMemoria))
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(estado))
        memoria = estado.ullTotalPhys
    else:
        import os

        memoria = os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES")
    return {"procesador": cpu, "nucleos_fisicos": joblib.cpu_count(only_physical_cores=True),
            "nucleos_logicos": joblib.cpu_count(), "memoria_gb": round(memoria / 2**30, 1),
            "sistema": f"{platform.system()} {platform.release()}"}


def actualizar_manifest(
    salida: Path,
    fecha: datetime,
    commit: str,
    id_exp: str,
    figuras: list[dict],
    pruebas: list[dict] | None = None,
) -> None:
    ruta = salida / "manifest.json"
    manifest = (
        json.loads(ruta.read_text(encoding="utf-8"))
        if ruta.exists()
        else {k: [] for k in SECCIONES_MANIFEST}
    )
    manifest["generado"] = fecha.isoformat(timespec="seconds")
    manifest["commit"] = commit
    archivo_exp = f"experimentos/{id_exp}.json"
    if archivo_exp not in manifest["experimentos"]:
        manifest["experimentos"].append(archivo_exp)
    for seccion, nuevas in (("figuras", figuras), ("pruebas", pruebas or [])):
        archivos = {f["archivo"] for f in nuevas}
        manifest[seccion] = [f for f in manifest.get(seccion, []) if f["archivo"] not in archivos] + nuevas
    orden = ["generado", "commit", *SECCIONES_MANIFEST]
    manifest = {k: manifest[k] for k in orden if k in manifest} | {
        k: v for k, v in manifest.items() if k not in orden
    }
    ruta.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def escribir_json(ruta: Path, datos: dict) -> None:
    ruta.write_text(json.dumps(datos, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
