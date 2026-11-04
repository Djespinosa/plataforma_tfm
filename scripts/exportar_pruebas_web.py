"""Exporta a evidencias/pruebas/ el informe de las pruebas de la interfaz (docs/diseno-web.md §9, evidencias/CONTRATO.md).

Ejecuta todas las pruebas Vitest de web/ (`npx --no ng test --watch=false --reporters=junit`) y escribe
interfaz-AAAA-MM-DD-NN_pruebas.xml (JUnit sin hostname, que Vitest pone en cada testsuite) e
interfaz-AAAA-MM-DD-NN_resumen.json (prefijo distinto de los experimentos web-AAAA-MM-DD-NN),
y los añade a manifest.json. No exporta nada si alguna prueba falla o se omite, ni si el informe lleva rutas del equipo.
Sin cobertura en la Entrega 2 (W-8). Solo desde un árbol limpio; se ejecuta desde la raíz:

    python -m scripts.exportar_pruebas_web                    # a evidencias/
    python -m scripts.exportar_pruebas_web --salida carpeta   # ensayo, con cambios sin confirmar
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

from api import RAIZ  # noqa: F401  (pone ml/ en sys.path)
from evidencias import EVIDENCIAS, SECCIONES_MANIFEST, comprobar_arbol_limpio, escribir_json

WEB = RAIZ / "web"
# --no: si falta el CLI local, npx falla en lugar de descargar e instalar un paquete del registro.
COMANDO = ["npx", "--no", "ng", "test", "--watch=false", "--reporters=junit"]


def siguiente_id(carpeta: Path, fecha: datetime) -> str:
    prefijo = f"interfaz-{fecha:%Y-%m-%d}-"
    existentes = [int(n) for p in carpeta.glob(f"{prefijo}*_pruebas.xml")
                  if (n := p.name.removeprefix(prefijo).removesuffix("_pruebas.xml")).isdigit()]
    return f"{prefijo}{max(existentes, default=0) + 1:02d}"


def limpiar_junit(junit: Path) -> dict:
    """Quita el hostname de cada testsuite y devuelve el resumen; error si algo falla, se omite o lleva rutas locales."""
    arbol = ET.parse(junit)
    raiz = arbol.getroot()
    for suite in raiz.iter("testsuite"):
        suite.attrib.pop("hostname", None)
    suites = list(raiz.iter("testsuite"))
    total = sum(int(s.get("tests", 0)) for s in suites)
    fallidas = sum(int(s.get("failures", 0)) + int(s.get("errors", 0)) for s in suites)
    omitidas = sum(int(s.get("skipped", 0)) for s in suites)
    if not total or fallidas or omitidas:
        raise ValueError(f"{total} pruebas, {fallidas} fallidas y {omitidas} omitidas: no se exporta.")
    arbol.write(junit, encoding="utf-8", xml_declaration=True)
    texto = junit.read_text(encoding="utf-8")
    if "hostname=" in texto or str(Path.home()) in texto or Path.home().as_posix() in texto:
        raise ValueError("El JUnit lleva el nombre del equipo o rutas del usuario: no se exporta.")
    return {"superadas": total, "fallidas": 0, "omitidas": 0, "archivos": len(suites)}


def versiones_web() -> dict:
    """Versiones instaladas en web/node_modules (las que se ejecutan), no las declaradas en package.json."""
    def instalada(nombre: str) -> str:
        return json.loads((WEB / "node_modules" / nombre / "package.json").read_text(encoding="utf-8"))["version"]

    nodo = subprocess.run(["node", "--version"], capture_output=True, text=True, check=True).stdout.strip()
    return {"node": nodo.removeprefix("v"),
            **{n: instalada(n) for n in ("@angular/core", "vitest", "jsdom", "typescript")}}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--salida", type=Path, default=EVIDENCIAS)
    args = parser.parse_args()
    commit = comprobar_arbol_limpio(args.salida)
    ruta_manifest = args.salida / "manifest.json"
    manifest = (json.loads(ruta_manifest.read_text(encoding="utf-8")) if ruta_manifest.exists()
                else {k: [] for k in SECCIONES_MANIFEST})
    fecha = datetime.now()
    carpeta = args.salida / "pruebas"
    carpeta.mkdir(parents=True, exist_ok=True)
    id_ = siguiente_id(carpeta, fecha)

    # Se prepara en una carpeta temporal y solo se mueve a evidencias/ cuando todo ha ido bien.
    with tempfile.TemporaryDirectory() as temporal:
        junit = Path(temporal) / f"{id_}_pruebas.xml"
        npx = shutil.which("npx") or "npx"
        codigo = subprocess.run([npx, *COMANDO[1:], f"--output-file={junit}"], cwd=WEB).returncode
        if codigo != 0 or not junit.exists():
            sys.exit(f"Las pruebas web han fallado (código {codigo}); no se exporta.")
        try:
            resumen = limpiar_junit(junit)
        except ValueError as e:
            sys.exit(str(e))
        resumen_json = Path(temporal) / f"{id_}_resumen.json"
        escribir_json(resumen_json, {
            "id": id_, "fecha": fecha.isoformat(timespec="seconds"), "commit": commit,
            "comando": " ".join([*COMANDO, "--output-file=<temporal>"]), "carpeta": "web",
            "entorno": versiones_web(), **resumen, "cobertura": None,
            "motivos_null": {"cobertura": "sin cobertura en la Entrega 2 (docs/diseno-web.md, W-8)"},
            "informes": {"junit": f"pruebas/{junit.name}"},
        })
        for origen in (junit, resumen_json):
            shutil.move(origen, carpeta / origen.name)

    manifest["generado"], manifest["commit"] = fecha.isoformat(timespec="seconds"), commit
    manifest.setdefault("pruebas", [])
    manifest["pruebas"] += [
        {"archivo": f"pruebas/{id_}_pruebas.xml", "descripcion": f"JUnit de todas las pruebas Vitest de web/ "
         f"({resumen['superadas']} en {resumen['archivos']} archivos)", "id": id_},
        {"archivo": f"pruebas/{id_}_resumen.json", "descripcion": "Resumen: superadas, entorno y comando", "id": id_},
    ]
    escribir_json(ruta_manifest, manifest)
    print(f"{id_}: {resumen['superadas']} pruebas web superadas en {resumen['archivos']} archivos. En {carpeta}.")


if __name__ == "__main__":
    main()
