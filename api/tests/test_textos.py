"""Vocabulario prohibido (docs/diseno-api.md §7; skill guardarrailes-interfaz): ningún texto de api/textos.py ni ningún
valor de las respuestas de las rutas presenta la explicación como causa ni el riesgo como certeza, ni lleva códigos de
decisión de la memoria. Solo se miran los valores: las claves JSON (`motivo`, `motivo_texto`) no son texto visible."""

import inspect
import json
import re
from pathlib import Path

import pytest

from api import textos
from test_configuracion import tabla
from test_importar import FINAL, importar_en
from test_importar import entorno  # noqa: F401  (fixture)
from test_predicciones import subir
from test_trabajador import crear, procesar

PROHIBIDOS = ["va a abandonar", "abandonará", "seguro", "causa", "motivo", "porque", "por qué", "debido a", "provoca",
              "alto riesgo", "en riesgo", "predicción de fracaso"]
CODIGO = re.compile(r"\bD-?\d+|P-\d+")  # decisiones de la memoria (D41, P-18) y del diseño de la API (D-4)
SKILL = Path(__file__).resolve().parents[2] / ".claude" / "skills" / "guardarrailes-interfaz" / "SKILL.md"
# Nota fija que niega la causalidad (RE-03): la única excepción, comprobada por igualdad con la skill.
NOTA = re.search(r'Nota fija bajo la explicación: "([^"]+)"', SKILL.read_text(encoding="utf-8")).group(1)
NOTA = " ".join(NOTA.split())
# Valor de ejemplo para cada anotación de los parámetros de las funciones de textos.py.
EJEMPLOS = {"str": "x", "object": "x", "int": 3, "float": 0.25, "float | None": 0.25, "list[str]": ["a", "b"]}


def cadenas(valor):
    if isinstance(valor, str):
        yield valor
    elif isinstance(valor, dict):
        for v in valor.values():
            yield from cadenas(v)
    elif isinstance(valor, (list, tuple)):
        for v in valor:
            yield from cadenas(v)


def problemas(valor) -> list[str]:
    encontrados = []
    for texto in cadenas(valor):
        minusculas = texto.lower()
        if texto.startswith(NOTA):
            minusculas = minusculas.removeprefix(NOTA.lower())
        encontrados += [f"«{p}» en: {texto}" for p in PROHIBIDOS if p in minusculas]
        encontrados += [f"código en: {texto}" for _ in CODIGO.findall(texto)]
    return encontrados


def test_la_nota_de_causalidad_es_la_de_la_skill():
    assert textos.AVISO_CAUSALIDAD.startswith(NOTA)


def test_constantes_y_funciones_de_textos():
    valores = []
    for nombre, valor in vars(textos).items():
        if nombre.startswith("_") or inspect.ismodule(valor):
            continue
        if inspect.isfunction(valor):
            parametros = inspect.signature(valor).parameters.values()
            valores.append(valor(*(EJEMPLOS[p.annotation] for p in parametros if p.default is p.empty)))
        else:
            valores.append(valor)
    assert len(valores) > 50
    assert problemas(valores) == []


def test_respuestas_de_las_rutas(app, cliente, entorno):  # noqa: F811
    respuestas = []
    obtener = lambda ruta: respuestas.append(cliente.get(ruta).get_json())  # noqa: E731
    importar_en(app, entorno)
    id_ = crear(cliente)
    procesar(app)
    obtener("/api/estado")
    obtener("/api/conjuntos")
    obtener("/api/experimentos")
    obtener(f"/api/experimentos/{id_}")
    obtener(f"/api/experimentos/{id_}/evaluacion")
    obtener(f"/api/experimentos/{FINAL}/evaluacion")
    obtener("/api/modelos")
    for modelo in cliente.get("/api/modelos").get_json():
        obtener(f"/api/modelos/{modelo['id']}")
        obtener(f"/api/modelos/{modelo['id']}/explicacion-global")
        r = subir(cliente, modelo["id"], tabla(40, semilla=5).assign(c="a"))  # columnas del web y del importado
        respuestas.append(r.get_json())
        obtener(f"/api/predicciones/{r.get_json()['lote_id']}")
        obtener(f"/api/predicciones/{r.get_json()['lote_id']}/filas/1/explicacion")
        respuestas.append(cliente.get(f"/api/predicciones/{r.get_json()['lote_id']}/exportar").data.decode("utf-8-sig"))
    respuestas.append(cliente.post(f"/api/experimentos/{id_}/reintentar").get_json())  # un error 409
    respuestas.append(cliente.get("/api/no-existe").get_json())
    prueba = f"/api/experimentos/{id_}/evaluacion-prueba"
    respuestas.append(cliente.post(prueba, json={}).get_json())  # 400 sin confirmar
    respuestas.append(cliente.post(prueba, json={"confirmar": True}).get_json())
    respuestas.append(cliente.post(prueba, json={"confirmar": True}).get_json())  # 409: ya se hizo
    respuestas.append(cliente.post(f"/api/experimentos/{FINAL}/evaluacion-prueba", json={"confirmar": True}).get_json())
    respuestas.append(json.loads(cliente.get(f"/api/experimentos/{id_}/evaluacion/exportar").data))
    assert len(respuestas) == 14 + 6 * 3 and all(respuestas)  # 3 modelos: el web y 2 importados
    assert problemas(respuestas) == []


@pytest.mark.parametrize("texto, esperado", [
    ("El modelo predice que va a abandonar.", ["«va a abandonar»"]),
    ("Riesgo alto debido a las pocas conexiones (D41).", ["«debido a»", "código"]),
    (NOTA + " La causa es otra.", ["«causa»"]),
    ("Un 34 % de riesgo seguro; explica por qué abandona (D-4).", ["«seguro»", "«por qué»", "código"]),
])
def test_el_detector_encuentra_los_prohibidos(texto, esperado):
    assert [p.split(" en:")[0] for p in problemas(texto)] == esperado
