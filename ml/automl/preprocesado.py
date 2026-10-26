"""Preprocesamiento que se ajusta dentro del Pipeline de cada pliegue (skill rigor-ml §2)."""

from __future__ import annotations

from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler


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


class DescartarVacias(TransformerMixin, BaseEstimator):
    """Quita las columnas sin ningún valor en las filas de ajuste (p. ej., antelacion_media en la semana 0, cuando aún
    no vence ninguna evaluación). Se ajusta por pliegue como el resto del Pipeline."""

    def fit(self, X, y=None):
        self.columnas_ = [c for c in X.columns if X[c].notna().any()]
        return self

    def transform(self, X):
        return X[self.columnas_]

    def get_feature_names_out(self, input_features=None):
        return self.columnas_


def codificador(numericas: list[str], categoricas: list[str], imputar_mediana: list[str], escalar: bool) -> ColumnTransformer:
    """Entrada numérica para los modelos.

    - Categóricas: faltante como categoría propia ("faltante") y codificación one-hot; categorías nuevas → todo ceros.
    - Con escalar (RL y MLP): todas las numéricas se imputan por la mediana con indicador de faltante y se estandarizan.
    - Sin escalar (árboles): solo `imputar_mediana` (D28) se imputa; los demás vacíos son estructurales (p. ej., sin
      entregas no hay nota media) y los modelos de árboles los tratan de forma nativa.
    - Las columnas sin ningún valor en las filas de ajuste se descartan (SimpleImputer lo hace por defecto en la rama
      con escalado; DescartarVacias en la de árboles).
    """
    categorico = make_pipeline(
        SimpleImputer(strategy="constant", fill_value="faltante"),
        OneHotEncoder(handle_unknown="ignore", sparse_output=False),
    )
    if escalar:
        numerico = [("numericas", make_pipeline(SimpleImputer(strategy="median", add_indicator=True), StandardScaler()),
                     numericas)]
    else:
        resto = [c for c in numericas if c not in imputar_mediana]
        numerico = [("mediana", SimpleImputer(strategy="median"), imputar_mediana), ("numericas", DescartarVacias(), resto)]
    return ColumnTransformer(
        [*numerico, ("categoricas", categorico, categoricas)],
        verbose_feature_names_out=False,
    ).set_output(transform="pandas")
