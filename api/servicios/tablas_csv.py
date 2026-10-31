"""Lectura de los CSV que se suben y resumen de sus columnas (docs/diseno-api.md §4.1)."""

from __future__ import annotations

import csv
import io
from collections import Counter

import pandas as pd

from api import textos
from api.errores import ErrorPlataforma
from automl.validacion import normalizar_valor

MUESTRA_SEPARADOR = 64 * 1024
MAX_VALORES_FRECUENTES = 20
PROPORCION_IDENTIFICADOR = 0.5


def leer_csv(contenido: bytes) -> pd.DataFrame:
    """CSV en UTF-8 (con o sin BOM), separado por «,» o «;» (detectado en los primeros 64 KB), decimal «.». Lanza
    ErrorPlataforma 415 si no es un CSV así y 422 si no tiene filas, tiene columnas repetidas o menos de 2 columnas."""
    try:
        texto = contenido.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise ErrorPlataforma(415, textos.ERROR_NO_CSV) from None
    if not texto.strip():
        raise ErrorPlataforma(422, textos.ERROR_SIN_FILAS)
    try:
        separador = csv.Sniffer().sniff(texto[:MUESTRA_SEPARADOR], delimiters=",;").delimiter
    except csv.Error:
        separador = ","  # una sola columna: no hay separador que detectar (falla abajo por pocas columnas)
    # pandas renombra las columnas repetidas (a, a.1): se comprueban en la cabecera original.
    lector = csv.reader(io.StringIO(texto), delimiter=separador)
    cabecera = next(lector)
    repetidas = sorted(nombre for nombre, n in Counter(cabecera).items() if n > 1)
    if repetidas:
        raise ErrorPlataforma(422, textos.error_columnas_repetidas(repetidas))
    try:
        # Si todas las filas traen más campos que la cabecera (separador al final de línea, índice sin nombre), pandas
        # toma la primera columna como índice y desplaza los datos sin avisar.
        if any(len(fila) > len(cabecera) for fila in lector):
            raise ErrorPlataforma(415, textos.ERROR_NO_CSV)
        datos = pd.read_csv(io.StringIO(texto), sep=separador)
    except (pd.errors.ParserError, csv.Error):
        raise ErrorPlataforma(415, textos.ERROR_NO_CSV) from None
    if datos.shape[1] < 2:
        raise ErrorPlataforma(422, textos.ERROR_POCAS_COLUMNAS)
    if datos.empty:
        raise ErrorPlataforma(422, textos.ERROR_SIN_FILAS)
    return datos


def resumir_columnas(datos: pd.DataFrame) -> tuple[list[dict], list[str]]:
    """(columnas, avisos). Tipo «numerica» si pandas la lee como número (los booleanos no) y «categorica» en otro caso.
    Los valores frecuentes van como texto normalizado (2014.0 → "2014"), el mismo con que se elige la cohorte de prueba."""
    columnas, avisos = [], []
    for nombre in datos.columns:
        serie = datos[nombre]
        numerica = pd.api.types.is_numeric_dtype(serie) and not pd.api.types.is_bool_dtype(serie)
        frecuencias = serie.dropna().map(normalizar_valor).value_counts()
        columnas.append({
            "nombre": nombre,
            "tipo": "numerica" if numerica else "categorica",
            "faltantes": int(serie.isna().sum()),
            "proporcion_faltantes": round(float(serie.isna().mean()), 4),
            "valores_distintos": len(frecuencias),
            "valores_frecuentes": [{"valor": v, "n": int(n)}
                                   for v, n in frecuencias.head(MAX_VALORES_FRECUENTES).items()],
        })
        if frecuencias.empty:
            avisos.append(textos.aviso_columna_vacia(nombre))
        elif len(frecuencias) == 1:
            avisos.append(textos.aviso_columna_constante(nombre))
        elif not numerica and len(frecuencias) > PROPORCION_IDENTIFICADOR * len(serie):
            avisos.append(textos.aviso_identificador(nombre))
    return columnas, avisos
