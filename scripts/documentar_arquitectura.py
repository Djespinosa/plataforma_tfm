"""Modelo de datos y lista de endpoints de la plataforma, generados desde el código (evidencias/CONTRATO.md, arquitectura).

- arquitectura/modelo_datos.md: las 6 tablas de api/tablas.py con el DDL de PostgreSQL que compila SQLAlchemy (columnas,
  claves, CHECK e índices; test_tablas.py compara con la migración 0001_inicial columnas, claves e índices, y los
  CHECK por nombre) y las funciones y
  disparadores de la evaluación única en la cohorte de prueba (D-2), copiados de la migración.
- arquitectura/endpoints.md: método, ruta, requisito y descripción de cada ruta de la API. La tabla RUTAS debe coincidir
  exactamente con las rutas registradas en Flask; si no, no se exporta nada.

Añade los dos archivos a la sección `arquitectura` de manifest.json con {archivo, fuente, descripcion, commit}. Solo desde
un árbol limpio; se ejecuta desde la raíz:

    python -m scripts.documentar_arquitectura                    # a evidencias/
    python -m scripts.documentar_arquitectura --salida carpeta   # ensayo, con cambios sin confirmar
"""

from __future__ import annotations

import argparse
import importlib.util
import sys
import tempfile
from datetime import datetime
from pathlib import Path

from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateIndex, CreateTable

from api import RAIZ, crear_app
from api.configuracion import Pruebas
from api.tablas import Base
from scripts.diagrama_arquitectura import registrar
from evidencias import EVIDENCIAS, comprobar_arbol_limpio

FUENTE = "scripts/documentar_arquitectura.py"
MIGRACION = RAIZ / "api" / "migraciones" / "versions" / "0001_inicial.py"
DISPARADORES = [("FUNCION_EVALUACION_UNICA", "DISPARADOR_EVALUACION_UNICA"),
                ("FUNCION_MODELO_CONGELADO", "DISPARADOR_MODELO_CONGELADO"),
                ("FUNCION_CONJUNTO_INMUTABLE", "DISPARADOR_CONJUNTO_INMUTABLE")]

# (método, ruta) → (requisitos, descripción). Requisitos de docs/diseno-api.md §1; RF-07 no tiene ruta propia.
RUTAS: dict[tuple[str, str], tuple[str, str]] = {
    ("GET", "/api/estado"): ("—", "Estado del sistema: motor de base de datos, trabajador activo y commit del código"),
    ("POST", "/api/conjuntos"): ("RF-01", "Carga de un CSV: validación y resumen de columnas"),
    ("GET", "/api/conjuntos"): ("RF-01", "Conjuntos de datos cargados"),
    ("GET", "/api/conjuntos/<int:id_>"): ("RF-01, RF-02", "Detalle de un conjunto: columnas, tipos, faltantes y valores"),
    ("POST", "/api/experimentos/validacion"): ("RF-02", "Comprueba una configuración y devuelve el esquema efectivo, sin crear nada"),
    ("POST", "/api/experimentos"): ("RF-02, RF-03", "Crea un experimento con la configuración y lo deja en cola para el trabajador"),
    ("GET", "/api/experimentos"): ("RF-08", "Historial de experimentos web e importados"),
    ("GET", "/api/experimentos/<id_>"): ("RF-03, RF-08", "Detalle y seguimiento de un experimento (estado, etapa, progreso, latido)"),
    ("POST", "/api/experimentos/<id_>/reintentar"): ("RF-08", "Experimento nuevo con la misma configuración efectiva tras un fallo o una interrupción"),
    ("GET", "/api/experimentos/<id_>/evaluacion"): ("RF-04", "Evaluación out-of-fold: candidatos, referencias, contraste, desplegado, umbral, calibración y equidad"),
    ("GET", "/api/experimentos/<id_>/evaluacion/exportar"): ("RF-09", "Descarga de la evaluación en JSON"),
    ("POST", "/api/experimentos/<id_>/evaluacion-prueba"): ("RF-04", "Evaluación única en la cohorte de prueba reservada (solo experimentos web, con confirmación)"),
    ("GET", "/api/modelos"): ("RF-05", "Modelos desplegados disponibles para estimar"),
    ("GET", "/api/modelos/<int:id_>"): ("RF-05", "Detalle de un modelo: columnas necesarias, umbral y explicador"),
    ("GET", "/api/modelos/<int:id_>/explicacion-global"): ("RF-06", "Explicación global del modelo (media del valor absoluto de SHAP por variable)"),
    ("POST", "/api/modelos/<int:id_>/predicciones"): ("RF-05", "Estimación de un CSV: probabilidad calibrada y marca de seguimiento por fila"),
    ("GET", "/api/predicciones/<int:lote_id>"): ("RF-05", "Resultado de un lote de estimaciones"),
    ("GET", "/api/predicciones/<int:lote_id>/exportar"): ("RF-09", "Descarga de las estimaciones del lote en CSV (UTF-8 con BOM)"),
    ("GET", "/api/predicciones/<int:lote_id>/filas/<int:fila>/explicacion"): ("RF-06", "Explicación local de una fila (contribuciones SHAP, con las extremas marcadas)"),
}


def rutas_registradas() -> set[tuple[str, str]]:
    with tempfile.TemporaryDirectory() as datos:
        app = crear_app(Pruebas(datos=Path(datos)))  # SQLite en memoria: no toca ninguna base de datos
        rutas = {(m, r.rule) for r in app.url_map.iter_rules() if r.rule.startswith("/api/")
                 for m in r.methods - {"HEAD", "OPTIONS"}}
        app.extensions["bd_motor"].dispose()
    return rutas


def endpoints_md(registradas: set[tuple[str, str]]) -> str:
    faltan, sobran = registradas - RUTAS.keys(), RUTAS.keys() - registradas
    if faltan or sobran:
        raise ValueError(f"RUTAS no coincide con la API. Sin documentar: {sorted(faltan)}; inexistentes: {sorted(sobran)}")
    filas = [f"| {m} | `{r}` | {req} | {d} |" for (m, r), (req, d) in RUTAS.items()]
    return "\n".join([
        "# Endpoints de la API REST", "",
        f"{len(RUTAS)} rutas bajo `/api`, JSON UTF-8. Errores: `{{\"error\": \"…\"}}` (y `detalles` si hay varios) con 400, "
        "404, 405, 409, 413, 415, 422, 500 y 503 (cualquier `OperationalError` de la base de datos). Sin autenticación: uso "
        "local en `127.0.0.1` (decisión D-1). RF-07 (vista resumida y detallada) no tiene ruta propia: lo resuelve la "
        "interfaz con las rutas de RF-04 a RF-06.", "",
        "| Método | Ruta | Requisito | Descripción |", "|---|---|---|---|", *filas, ""])


def modelo_datos_md() -> str:
    spec = importlib.util.spec_from_file_location("migracion_0001", MIGRACION)
    migracion = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migracion)
    dialecto = postgresql.dialect()
    partes = ["# Modelo de datos (PostgreSQL 16)", "",
              f"{len(Base.metadata.tables)} tablas de `api/tablas.py`, creadas por la migración Alembic `0001_inicial` "
              "(una prueba compara columnas, claves e índices, y los CHECK por nombre). DDL que compila SQLAlchemy para PostgreSQL.", ""]
    for tabla in Base.metadata.sorted_tables:
        compilado = str(CreateTable(tabla).compile(dialect=dialecto)).strip()
        ddl = "\n".join(linea.rstrip() for linea in compilado.splitlines())
        indices = [str(CreateIndex(i).compile(dialect=dialecto)).strip() for i in sorted(tabla.indexes, key=lambda i: i.name)]
        partes += [f"## `{tabla.name}`", "", "```sql", ddl + ";", *(i + ";" for i in indices), "```", ""]
    partes += ["## Disparadores de la evaluación única en la cohorte de prueba (D-2)", "",
               "Copiados de la migración `0001_inicial`. En SQLite (pruebas unitarias) hay disparadores equivalentes, con los "
               "mismos mensajes. Protegen frente a errores de la aplicación, no frente a un superusuario de la base de "
               "datos; otra cohorte que se solape por valores o un archivo modificado (otro SHA-256) sí permiten otra "
               "evaluación (limitaciones declaradas en `docs/diseno-api.md` §3).", ""]
    for funcion, disparador in DISPARADORES:
        partes += ["```sql", getattr(migracion, funcion).strip() + ";", getattr(migracion, disparador).strip() + ";",
                   "```", ""]
    return "\n".join(partes)


def exportar(salida: Path, commit: str, fecha: datetime) -> list[dict]:
    textos = {"endpoints.md": (endpoints_md(rutas_registradas()), "Endpoints de la API: método, ruta, requisito y descripción"),
              "modelo_datos.md": (modelo_datos_md(), "Modelo de datos: DDL de las 6 tablas (claves, CHECK, índices) "
                                  "y disparadores de la evaluación única (D-2)")}
    carpeta = salida / "arquitectura"
    carpeta.mkdir(parents=True, exist_ok=True)
    entradas = []
    for nombre, (texto, descripcion) in textos.items():
        (carpeta / nombre).write_text(texto, encoding="utf-8", newline="\n")
        entradas.append({"archivo": f"arquitectura/{nombre}", "fuente": FUENTE, "descripcion": descripcion,
                         "commit": commit})
    registrar(salida, entradas, commit, fecha)
    return entradas


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--salida", type=Path, default=EVIDENCIAS)
    args = parser.parse_args()
    commit = comprobar_arbol_limpio(args.salida)
    try:
        entradas = exportar(args.salida, commit, datetime.now())
    except ValueError as e:
        sys.exit(str(e))
    print(f"{len(entradas)} archivos de arquitectura en {args.salida} con el commit {commit}.")


if __name__ == "__main__":
    main()
