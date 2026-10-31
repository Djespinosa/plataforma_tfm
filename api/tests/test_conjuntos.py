"""RF-01: carga y validación de la tabla (docs/diseno-api.md §4.1), con CSV sintéticos."""

import hashlib
import io

import pytest

CSV = "grupo,anio,edad,activo,y\ng1,2013,20,True,si\ng2,2014,,False,no\ng3,,31,True,no\ng4,2014,45,False,si\n"


def subir(cliente, contenido: bytes | str, nombre: str = "tabla.csv", **campos):
    if isinstance(contenido, str):
        contenido = contenido.encode("utf-8")
    return cliente.post("/api/conjuntos", data={"archivo": (io.BytesIO(contenido), nombre), **campos},
                        content_type="multipart/form-data")


def test_sube_guarda_y_resume_la_tabla(cliente, app):
    r = subir(cliente, CSV, momento="  semana 4 ")
    assert r.status_code == 201
    cuerpo = r.get_json()
    huella = hashlib.sha256(CSV.encode()).hexdigest()
    assert cuerpo["id"] == 1 and cuerpo["nombre_archivo"] == "tabla.csv" and cuerpo["momento"] == "semana 4"
    assert cuerpo["sha256"] == huella and cuerpo["n_filas"] == 4 and cuerpo["n_columnas"] == 5
    assert cuerpo["aviso_privacidad"] == ("No suba datos personales identificables sin autorización. La plataforma no "
                                          "envía datos a servicios externos.")
    guardado = app.config["PLATAFORMA_DATOS"] / "conjuntos" / f"{huella}.csv"
    assert guardado.read_bytes() == CSV.encode()
    columnas = {c["nombre"]: c for c in cuerpo["columnas"]}
    assert [c["nombre"] for c in cuerpo["columnas"]] == ["grupo", "anio", "edad", "activo", "y"]
    assert {n: c["tipo"] for n, c in columnas.items()} == {
        "grupo": "categorica", "anio": "numerica", "edad": "numerica", "activo": "categorica", "y": "categorica"}
    # Columna entera con vacíos (pandas la lee como float): valores como en la cohorte de prueba, sin «.0».
    assert columnas["anio"]["valores_frecuentes"] == [{"valor": "2014", "n": 2}, {"valor": "2013", "n": 1}]
    assert columnas["anio"]["faltantes"] == 1 and columnas["anio"]["proporcion_faltantes"] == 0.25
    assert columnas["activo"]["valores_distintos"] == 2


def test_punto_y_coma_y_bom(cliente):
    r = subir(cliente, "﻿a;b\n1;x\n2;y\n".encode("utf-8"))
    assert r.status_code == 201
    assert [c["nombre"] for c in r.get_json()["columnas"]] == ["a", "b"]


def test_avisos_de_identificador_vacia_y_constante(cliente):
    filas = "".join(f"id{i},,7,{i % 2}\n" for i in range(10))
    avisos = subir(cliente, "codigo,nada,fija,y\n" + filas).get_json()["avisos"]
    assert avisos == [
        "La columna «codigo» parece un identificador; excluirla de las variables protege la privacidad y evita que el "
        "modelo memorice filas.",
        "La columna «nada» no tiene ningún valor.",
        "La columna «fija» tiene el mismo valor en todas las filas; no aporta información al modelo.",
    ]


def test_numerica_con_muchos_valores_no_es_identificador(cliente):
    filas = "".join(f"{i},{i % 2}\n" for i in range(10))
    assert subir(cliente, "x,y\n" + filas).get_json()["avisos"] == []


@pytest.mark.parametrize("contenido, codigo, mensaje", [
    ("a,b\n".encode(), 422, "El archivo no tiene filas de datos."),
    (b"", 422, "El archivo no tiene filas de datos."),
    ("a,b,a\n1,2,3\n".encode(), 422, "Hay columnas con el mismo nombre: a."),
    ("solo\n1\n2\n".encode(), 422, "Se necesitan al menos 2 columnas."),
    ("año,b\n1,ñ\n".encode("latin-1"), 415, "El archivo debe ser un CSV en UTF-8 separado por comas o por punto y coma."),
    ('a,b\n1,"2\n'.encode(), 415, "El archivo debe ser un CSV en UTF-8 separado por comas o por punto y coma."),
    # Un campo más en todas las filas: pandas desplazaría las columnas usando la primera como índice.
    ("a,b\n1,2,3\n4,5,6\n".encode(), 415, "El archivo debe ser un CSV en UTF-8 separado por comas o por punto y coma."),
    ("a,b\n0,2,3\n1,5,6\n".encode(), 415, "El archivo debe ser un CSV en UTF-8 separado por comas o por punto y coma."),
    # Con «;» final, el Sniffer no detecta el separador: se rechaza igual (una sola columna con «,»).
    ("a;b\n1;2;\n4;5;\n".encode(), 422, "Se necesitan al menos 2 columnas."),
])
def test_archivos_no_validos(cliente, contenido, codigo, mensaje):
    r = subir(cliente, contenido)
    assert r.status_code == codigo
    assert r.get_json() == {"error": mensaje}


def test_sin_archivo(cliente):
    for datos in ({}, {"archivo": (io.BytesIO(b"a,b\n1,2\n"), "")}):
        r = cliente.post("/api/conjuntos", data=datos, content_type="multipart/form-data")
        assert r.status_code == 400
        assert r.get_json() == {"error": "No se ha recibido ningún archivo."}


def test_archivo_demasiado_grande(app, cliente):
    app.config["MAX_CONTENT_LENGTH"] = 1024
    r = subir(cliente, "a,b\n" + "1,2\n" * 1000)
    assert r.status_code == 413
    assert r.get_json() == {"error": "El archivo supera el tamaño máximo de 50 MB."}


def test_archivo_guardado_truncado_se_reescribe(cliente, app):
    huella = hashlib.sha256(CSV.encode()).hexdigest()
    guardado = app.config["PLATAFORMA_DATOS"] / "conjuntos" / f"{huella}.csv"
    guardado.parent.mkdir(parents=True)
    guardado.write_bytes(CSV.encode()[:10])  # resto de una escritura cortada
    assert subir(cliente, CSV).status_code == 201
    assert guardado.read_bytes() == CSV.encode()
    assert [p.name for p in guardado.parent.iterdir()] == [guardado.name]  # sin temporales


def test_listar_y_detalle(cliente):
    subir(cliente, CSV, nombre="uno.csv")
    segundo = subir(cliente, CSV, nombre="dos.csv").get_json()
    lista = cliente.get("/api/conjuntos").get_json()
    assert [c["nombre_archivo"] for c in lista] == ["dos.csv", "uno.csv"]
    assert set(lista[0]) == {"id", "nombre_archivo", "momento", "n_filas", "n_columnas", "creado_en"}
    assert cliente.get(f"/api/conjuntos/{segundo['id']}").get_json() == segundo


def test_detalle_inexistente(cliente):
    r = cliente.get("/api/conjuntos/99")
    assert r.status_code == 404
    assert r.get_json() == {"error": "No existe el conjunto de datos 99."}


@pytest.mark.postgres
def test_sube_y_lee_en_postgresql(app_postgres):
    cliente = app_postgres.test_client()
    subido = subir(cliente, CSV).get_json()
    assert cliente.get(f"/api/conjuntos/{subido['id']}").get_json() == subido
