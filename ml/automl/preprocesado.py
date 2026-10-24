"""Preprocesamiento que se ajusta dentro del Pipeline de cada pliegue (skill rigor-ml §2)."""

from __future__ import annotations

from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer


def imputador_mediana(columnas: list[str]) -> ColumnTransformer:
    """Imputa por la mediana las columnas indicadas y deja pasar el resto sin cambios.

    Como primer paso de un Pipeline, la mediana se calcula solo con las filas con que se ajusta: las de entrenamiento
    del pliegue en la validación cruzada y todo el entrenamiento en el modelo final (D28 para date_registration).
    El indicador de faltante lo aporta el conjunto de datos (falta_date_registration en OULAD).
    """
    return ColumnTransformer(
        [("mediana", SimpleImputer(strategy="median"), columnas)],
        remainder="passthrough",
        verbose_feature_names_out=False,
    ).set_output(transform="pandas")
