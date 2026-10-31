"""Exporta a evidencias/pruebas/ el informe de las pruebas de la API (docs/diseno-api.md §10, evidencias/CONTRATO.md):
todas las de api/tests en un proceso nuevo (unitarias en SQLite y funcionales contra el PostgreSQL del contenedor, sin
ninguna omitida), con la cobertura de api/ y ml/automl/. Escribe <id>_pruebas.xml (JUnit sin hostname),
<id>_cobertura.json (coverage.py) y <id>_resumen.json, y los añade a manifest.json. Solo desde un árbol limpio.

    python -m api.exportar_pruebas                    # a evidencias/
    python -m api.exportar_pruebas --salida carpeta   # ensayo, con cambios sin confirmar
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import datetime
from pathlib import Path
from urllib.parse import quote, quote_plus, urlsplit

from dotenv import load_dotenv
from sqlalchemy import make_url

from api import RAIZ  # también pone ml/ en sys.path
from evidencias import EVIDENCIAS, SECCIONES_MANIFEST, comprobar_arbol_limpio, escribir_json, versiones_entorno

COBERTURA = ("api", "ml/automl")


def siguiente_id(carpeta: Path, fecha: datetime) -> str:
    prefijo = f"api-{fecha:%Y-%m-%d}-"
    existentes = [int(n) for p in carpeta.glob(f"{prefijo}*_pruebas.xml")
                  if (n := p.name.removeprefix(prefijo).removesuffix("_pruebas.xml")).isdigit()]
    return f"{prefijo}{max(existentes, default=0) + 1:02d}"


def ejecutar(junit: Path, cobertura: Path) -> list[str]:
    comando = [sys.executable, "-m", "pytest", "api/tests", "-q", "-p", "no:cacheprovider", "--tb=short",
               f"--junitxml={junit}", *(f"--cov={c}" for c in COBERTURA), f"--cov-report=json:{cobertura}"]
    codigo = subprocess.run(comando, cwd=RAIZ).returncode
    if codigo != 0:
        sys.exit(f"Las pruebas han fallado (código {codigo}); no se exporta.")
    return comando


def limpiar_junit(junit: Path) -> dict:
    """Quita el hostname y devuelve el resumen; aborta si alguna prueba se omitió (p. ej. sin PostgreSQL)."""
    arbol = ET.parse(junit)
    for suite in arbol.getroot().iter("testsuite"):
        suite.attrib.pop("hostname", None)
    arbol.write(junit, encoding="utf-8", xml_declaration=True)
    suite = next(arbol.getroot().iter("testsuite"))
    total, fallos, errores, omitidas = (int(suite.get(k, 0)) for k in ("tests", "failures", "errors", "skipped"))
    if omitidas or fallos or errores:
        sys.exit(f"{omitidas} omitidas, {fallos + errores} fallidas: no se exporta (¿está levantado PostgreSQL?).")
    propiedades = suite.find("properties")
    motor_bd = next((p.get("value") for p in propiedades if p.get("name") == "motor_bd_funcionales"),
                    None) if propiedades is not None else None
    if motor_bd is None:
        sys.exit("El JUnit no registra el motor de base de datos: no se exporta.")
    requisitos = Counter(p.get("value") for caso in suite.iter("testcase") for p in caso.iter("property")
                         if p.get("name") == "requisito")
    # Solo las funcionales (y las unitarias marcadas «postgres») usan PostgreSQL; el resto, SQLite en memoria.
    return {"superadas": total, "fallidas": 0, "omitidas": 0, "funcionales": sum(requisitos.values()),
            "motor_bd_funcionales": motor_bd, "funcionales_por_requisito": dict(sorted(requisitos.items()))}


def resumir_cobertura(cobertura: Path) -> dict:
    archivos = json.loads(cobertura.read_text(encoding="utf-8"))["files"]
    if any(Path(nombre).is_absolute() for nombre in archivos):
        sys.exit("La cobertura lleva rutas absolutas (con el nombre del usuario): no se exporta.")
    por_paquete = {}
    for paquete in COBERTURA:
        resumenes = [a["summary"] for nombre, a in archivos.items()
                     if Path(nombre).as_posix().startswith(paquete + "/")]
        lineas = sum(r["num_statements"] for r in resumenes)
        cubiertas = sum(r["covered_lines"] for r in resumenes)
        por_paquete[paquete] = {"archivos": len(resumenes), "lineas": lineas, "cubiertas": cubiertas,
                                "porcentaje": round(100 * cubiertas / lineas, 1)}
    return por_paquete


def sin_contrasena(*rutas: Path) -> None:
    texto = os.environ.get("DATABASE_URL_PRUEBAS")
    contrasena = make_url(texto).password if texto else None
    if not contrasena:
        return
    # Decodificada, codificada de las dos formas y tal como está escrita en la URL (con «+» o «%2F» propios).
    formas = {contrasena, quote_plus(contrasena), quote(contrasena, safe=""), urlsplit(texto).password}
    for ruta in rutas:
        contenido = ruta.read_text(encoding="utf-8")
        if any(forma in contenido for forma in formas):
            sys.exit(f"{ruta.name} contiene la contraseña de la base de datos: no se exporta.")


def leer_manifest(salida: Path) -> dict:
    """El manifest actual (o uno vacío si aún no existe), leído antes de ejecutar nada: si no se puede leer, no se
    llega a escribir ningún archivo."""
    ruta = salida / "manifest.json"
    manifest = json.loads(ruta.read_text(encoding="utf-8")) if ruta.exists() else {k: [] for k in SECCIONES_MANIFEST}
    manifest.setdefault("pruebas", [])
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--salida", type=Path, default=EVIDENCIAS)
    args = parser.parse_args()
    load_dotenv(RAIZ / ".env")
    commit = comprobar_arbol_limpio(args.salida)
    manifest = leer_manifest(args.salida)
    entorno = versiones_entorno("pytest", "flask", "sqlalchemy", "psycopg", "sklearn", "coverage")
    fecha = datetime.now()
    carpeta = args.salida / "pruebas"
    carpeta.mkdir(parents=True, exist_ok=True)
    id_ = siguiente_id(carpeta, fecha)
    nombres = {k: f"{id_}_{k}" for k in ("pruebas.xml", "cobertura.json", "resumen.json")}

    # Los tres archivos se preparan en una carpeta temporal y solo se mueven a evidencias/ cuando todo ha ido bien.
    with tempfile.TemporaryDirectory() as temporal:
        junit, cobertura, resumen_json = (Path(temporal) / n for n in nombres.values())
        comando = ejecutar(junit, cobertura)
        resumen = limpiar_junit(junit)
        resumen_cobertura = resumir_cobertura(cobertura)
        sin_contrasena(junit, cobertura)
        escribir_json(resumen_json, {
            "id": id_, "fecha": fecha.isoformat(timespec="seconds"), "commit": commit,
            "comando": " ".join(["python", *comando[1:]]).replace(temporal, "<temporal>"),  # sin rutas del equipo
            "entorno": entorno, **resumen, "cobertura": resumen_cobertura,
            "informes": {"junit": f"pruebas/{nombres['pruebas.xml']}",
                         "cobertura": f"pruebas/{nombres['cobertura.json']}"},
        })
        for origen in (junit, cobertura, resumen_json):
            shutil.move(origen, carpeta / origen.name)

    descripcion = (f"de todas las pruebas de api/tests (unitarias en SQLite salvo las marcadas postgres; "
                   f"{resumen['funcionales']} funcionales contra {resumen['motor_bd_funcionales']})")
    manifest["generado"], manifest["commit"] = fecha.isoformat(timespec="seconds"), commit
    manifest["pruebas"] += [
        {"archivo": f"pruebas/{nombres['pruebas.xml']}", "descripcion": f"JUnit {descripcion}", "id": id_},
        {"archivo": f"pruebas/{nombres['cobertura.json']}", "descripcion": "Cobertura de api/ y ml/automl/ "
         + descripcion, "id": id_},
        {"archivo": f"pruebas/{nombres['resumen.json']}", "descripcion": "Resumen: superadas, motor, requisitos y "
         "cobertura", "id": id_},
    ]
    escribir_json(args.salida / "manifest.json", manifest)
    print(f"{id_}: {resumen['superadas']} pruebas superadas ({resumen['funcionales']} funcionales); cobertura "
          + ", ".join(f"{p} {c['porcentaje']} %" for p, c in resumen_cobertura.items()) + f". En {carpeta}.")


if __name__ == "__main__":
    main()
