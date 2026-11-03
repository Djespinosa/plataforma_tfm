"""Textos visibles de la API (docs/diseno-api.md §7; skill guardarrailes-interfaz). Ninguna ruta escribe texto fuera de
aquí, salvo los ValueError de ml/."""

from __future__ import annotations

ERROR_INTERNO = "Error interno de la plataforma. Inténtelo de nuevo; si persiste, consulte el registro del servidor."
ERROR_BD_NO_DISPONIBLE = "La base de datos no está disponible."
ERROR_RUTA_NO_EXISTE = "No existe la ruta solicitada."
ERROR_METODO_NO_PERMITIDO = "Esta ruta no admite el método solicitado."
ERROR_PETICION = "La petición no se ha podido atender."

# Conjuntos de datos (RF-01, §4.1)
AVISO_PRIVACIDAD_CARGA = ("No suba datos personales identificables sin autorización. La plataforma no envía datos a "
                          "servicios externos.")
ERROR_SIN_ARCHIVO = "No se ha recibido ningún archivo."
ERROR_NO_CSV = "El archivo debe ser un CSV en UTF-8 separado por comas o por punto y coma."
ERROR_SIN_FILAS = "El archivo no tiene filas de datos."
ERROR_POCAS_COLUMNAS = "Se necesitan al menos 2 columnas."


def error_columnas_repetidas(nombres: list[str]) -> str:
    return f"Hay columnas con el mismo nombre: {', '.join(nombres)}."


def error_tamano_maximo(mb: int) -> str:
    return f"El archivo supera el tamaño máximo de {mb} MB."


def error_no_existe(recurso: str, id_: object) -> str:
    return f"No existe el {recurso} {id_}."


def aviso_identificador(columna: str) -> str:
    return (f"La columna «{columna}» parece un identificador; excluirla de las variables protege la privacidad y evita "
            "que el modelo memorice filas.")


def aviso_columna_vacia(columna: str) -> str:
    return f"La columna «{columna}» no tiene ningún valor."


def aviso_columna_constante(columna: str) -> str:
    return f"La columna «{columna}» tiene el mismo valor en todas las filas; no aporta información al modelo."


# Resultados (§4, §4.3)
AVISO_DECISION = ("Herramienta de apoyo a la decisión. Las estimaciones pueden equivocarse; la decisión corresponde "
                  "siempre al personal académico y debe orientarse a ofrecer apoyo.")
AVISO_FUENTE_VALIDACION = ("Métricas de validación cruzada sobre los datos de entrenamiento (predicciones out-of-fold), "
                           "no de una cohorte de prueba.")
TEXTO_ROC_AUC = ("Capacidad del modelo para ordenar a quien tiene el resultado positivo por encima de quien no (0,5 = "
                 "azar; 1 = perfecta).")
TEXTO_CALIBRACION = "Cuando el modelo estima un 30 %, aproximadamente 3 de cada 10 casos son positivos."
SIN_CURVA_CALIBRACION = "Las predicciones out-of-fold del experimento de origen no están disponibles en este equipo."
ERROR_NO_TERMINADO = "El experimento aún no ha terminado (estado: {estado})."
ESTADOS_LLANOS = {"en_cola": "en cola", "en_curso": "en curso", "completado": "completado", "fallido": "fallido",
                  "interrumpido": "interrumpido"}
NOMBRES_MODELOS = {
    "rl": "regresión logística", "rl_optimizada": "regresión logística optimizada", "rf": "bosque aleatorio",
    "gb": "potenciación de gradiente (scikit-learn)", "xgb": "XGBoost", "lgbm": "LightGBM", "catboost": "CatBoost",
    "mlp": "red neuronal (perceptrón multicapa)", "apilamiento": "apilamiento de modelos",
    "rl_defecto": "regresión logística por defecto", "mayoritaria": "clase mayoritaria",
}
LECTURAS = {
    "ventaja_relevante": ("El mejor modelo AutoML ordena mejor que la regresión logística optimizada, con una diferencia "
                          "relevante (al menos 0,02)."),
    "detectable_sin_relevancia": "Hay una diferencia detectable, pero menor que 0,02: sin relevancia práctica.",
    "equivalencia_practica": ("El intervalo de la diferencia queda dentro de ±0,02: rendimiento equivalente en la "
                              "práctica."),
    "no_concluyente": "Los datos no permiten concluir si hay diferencia.",
    "desventaja_relevante": ("La regresión logística optimizada ordena mejor que el mejor modelo AutoML, con una "
                             "diferencia relevante (al menos 0,02)."),
}


# Cohorte de prueba reservada (§4.7)
TEXTO_PREVIO_PRUEBA = "Esta evaluación se hace una sola vez y no cambia el modelo ni el umbral."
AVISO_FUENTE_PRUEBA = ("Métricas en la cohorte de prueba reservada, calculadas una sola vez con el modelo y el umbral "
                       "fijados en el entrenamiento; estas filas no intervinieron en el entrenamiento ni en la "
                       "elección del modelo.")
ERROR_CONFIRMAR = ("La evaluación en la cohorte de prueba debe confirmarse («confirmar»: true). " + TEXTO_PREVIO_PRUEBA)
ERROR_SIN_COHORTE = "Este experimento no tiene cohorte de prueba reservada."
ERROR_DATOS_YA_EVALUADOS = ("Estos datos ya se evaluaron con esta cohorte de prueba en otro experimento; la cohorte de "
                            "prueba se usa una sola vez.")
ERROR_PRUEBA_UNA_CLASE = "La cohorte de prueba solo tiene casos de una clase: no se pueden calcular las métricas."
SIN_MARCADOS = "Con este umbral no se marca a ningún caso; la precisión no se puede calcular."
ERROR_COHORTE_DISTINTA = "Las filas de la cohorte de prueba no coinciden con las reservadas al entrenar."


def error_ya_evaluado(fecha: str) -> str:
    return f"La evaluación en la cohorte de prueba ya se hizo ({fecha}); se usa una sola vez."


def coma(valor: float, decimales: int = 2) -> str:
    return f"{valor:.{decimales}f}".replace(".", ",")


def nombre_modelo(modelo: str) -> str:
    return NOMBRES_MODELOS.get(modelo, modelo)


def error_ya_reintentado(id_: str) -> str:
    return f"Este experimento ya se ha reintentado ({id_}); si el reintento falla, reintente ese."


def error_no_terminado(estado: str) -> str:
    return ERROR_NO_TERMINADO.format(estado=ESTADOS_LLANOS.get(estado, estado))


def texto_pr_auc(prevalencia: float) -> str:
    return (f"Resume la precisión del modelo a lo largo de todos los umbrales; un modelo al azar obtendría la proporción "
            f"de casos positivos ({round(100 * prevalencia)} %).")


def textos_punto_operacion(sensibilidad: float, precision: float | None, tasa_alerta: float) -> dict:
    # precision es None si el umbral no marca a ningún caso (posible en la cohorte de prueba).
    return {"sensibilidad": f"De cada 10 casos positivos, el modelo marca a {round(10 * sensibilidad)}.",
            "precision": (f"De cada 10 marcados, {round(10 * precision)} son positivos." if precision is not None
                          else SIN_MARCADOS),
            "tasa_alerta": f"Se marcaría al {round(100 * tasa_alerta)} % de los casos."}


def texto_motivo(desplegado: str, mejor: str, limite_superior: float | None, margen: float) -> str:
    if desplegado == mejor:
        return f"Se despliega {nombre_modelo(desplegado)}: es el modelo con la ROC-AUC más alta."
    return (f"Se despliega {nombre_modelo(desplegado)}: es el modelo más simple cuya pérdida de ROC-AUC frente al mejor "
            f"({nombre_modelo(mejor)}) tiene un límite superior del intervalo del 95 % ({coma(limite_superior, 4)}) por "
            f"debajo de {coma(margen)}.")


def texto_sensibles(variables: list[str]) -> str:
    return (f"Las variables sensibles ({', '.join(variables)}) no se usan para predecir; se muestran las métricas por "
            "subgrupo.")


def descripcion_importado(experimento: str, evaluacion_de: str) -> str:
    return (f"Modelos finales de {experimento}, preparados con los scripts de ml/; las métricas son las de validación "
            f"cruzada de {evaluacion_de}.")


# Predicción (RF-05, §4.4)
TEXTO_PROBABILIDAD = "Probabilidad estimada por el modelo"
SUGERENCIA = "Sugerencia: priorizar contacto de apoyo"
AVISO_RENDIMIENTO = ("Estas estimaciones no miden el rendimiento del modelo. Si las filas formaron parte de su "
                     "entrenamiento, como los datos de demostración, están dentro de la muestra y solo sirven para "
                     "mostrar el funcionamiento de la plataforma.")
ERROR_NO_DESPLEGADO = "Este modelo no está desplegado y no puede usarse para predecir."
ERROR_PAQUETE_DISTINTO = "El archivo del modelo no coincide con el registrado."


def error_max_filas(n: int, maximo: int) -> str:
    return f"El archivo tiene {miles(n)} filas; el máximo por lote es {miles(maximo)}."


def error_faltan_columnas(columnas: list[str]) -> str:
    return f"Faltan columnas que el modelo necesita: {', '.join(columnas)}."


def error_no_numerica(columna: str, fila: int, valor: str) -> str:
    return f"La columna «{columna}» debe ser numérica (fila {fila}: «{valor}»)."


def error_columna_id(columna: str) -> str:
    return f"La columna identificadora «{columna}» no existe."


def error_fila_no_existe(fila: int, lote: int) -> str:
    return f"No existe la fila {fila} del lote {lote}."


# Explicaciones (RF-06, §4.5)
ESCALA = "log-odds sin calibrar"
SIN_DATO = "sin dato"
AVISO_ESCALA = ("Las contribuciones están en la escala interna del modelo (log-odds, antes de calibrar). Indican cuánto "
                "empuja cada variable la estimación hacia arriba o hacia abajo; no suman la probabilidad mostrada, que "
                "está calibrada.")
AVISO_CAUSALIDAD = ("Estos factores describen cómo llegó el modelo a su estimación. No son causas comprobadas ni "
                    "sustituyen el conocimiento del equipo docente sobre el estudiante. La probabilidad es una "
                    "estimación, no una certeza, y la decisión corresponde siempre a las personas.")
AVISO_EXTREMA = ("Algunas contribuciones son inusualmente grandes (más de 5 unidades en la escala del modelo). Suelen "
                 "deberse a un valor poco habitual de la variable en comparación con los datos de entrenamiento; "
                 "interprételas con cautela. La probabilidad mostrada no cambia.")
SIN_CONTRIBUCION = "Sin valores en los datos de entrenamiento: no interviene en la estimación."
SIN_REFERENCIA = ("No hay filas de entrenamiento de referencia para este modelo en este equipo; la explicación global no "
                  "está disponible.")


def miles(n: int) -> str:
    """Separador de miles con espacio (19 023); hasta 4 cifras, sin separador."""
    return f"{n:,}".replace(",", " ") if n >= 10000 else str(n)


def fuente_global(n_filas: int) -> str:
    return f"filas de entrenamiento (n = {miles(n_filas)})"


# Configuración y entrenamiento (RF-02, RF-03, §4.2 y §5)
ERROR_JSON = "La petición no es JSON válido."
ERROR_PRESUPUESTO = "El presupuesto debe ser «completo» o «demostracion»."
ERROR_SIN_VARIABLES = "No queda ninguna variable para entrenar tras las exclusiones."
ERROR_OBJETIVO_EXCLUIDO = "La columna objetivo no puede ser también de grupo, excluida ni sensible."
ERROR_COHORTE = ("La cohorte de prueba debe ser {\"modo\": \"aleatoria\"} o {\"modo\": \"valores\", \"columna\": …, "
                 "\"valores\": [...]} con al menos un valor.")
ERROR_CONJUNTO_CAMBIADO = "El archivo del conjunto ha cambiado desde que se cargó."
ERROR_PLIEGUES_DISTINTOS = "Los pliegues de validación no coinciden con los calculados al configurar el experimento."
ERROR_CONFIGURACION = "No se puede preparar la validación con estos datos y esta configuración."
CARACTERES_NO_ADMITIDOS = '[ ] < " , : { }'
ERROR_ENTRENAMIENTO = "El entrenamiento ha fallado por un error interno."
ERROR_INTERRUMPIDO = ("El proceso de entrenamiento se detuvo antes de terminar (cierre o reinicio). Puede reintentarlo: se "
                      "creará un experimento nuevo con la misma configuración.")
ERROR_REINTENTO = "Solo se puede reintentar un experimento fallido o interrumpido."
ERROR_TRABAJADOR_ACTIVO = "Ya hay un proceso de entrenamiento en marcha."
SIN_RESPUESTA = "El proceso de entrenamiento no responde. Compruebe que está en marcha."
AVISO_SIN_GRUPO = ("Sin columna de grupo, los pliegues se forman al azar (estratificados). Si hay filas relacionadas, como "
                   "el mismo estudiante en varias cohortes o estudiantes de una misma cohorte, las métricas pueden "
                   "sobreestimar el rendimiento en una cohorte nueva.")
AVISO_DEMOSTRACION = ("Presupuesto reducido de demostración: los resultados no son comparables con los de un "
                      "entrenamiento completo.")
EXCLUIDA_GRUPO = "columna de grupo"
EXCLUIDA_COHORTE = "define la cohorte de prueba"
COHORTE_VALORES = "filas cuyo valor está en la lista"
COHORTE_ALEATORIA = "20 % de las filas al azar, estratificado por la clase, con semilla"
ETAPAS = {"referencias": "Referencias", "apilamiento": "Apilamiento",
          "comparacion": "Comparación y elección del modelo", "final": "Modelo final",
          "global": "Explicación global", "equidad": "Equidad"}


def error_falta_campo(campo: str) -> str:
    return f"Falta el campo «{campo}»."


def error_lista_columnas(campo: str) -> str:
    return f"El campo «{campo}» debe ser una lista de nombres de columna."


def error_nombre_columna(columna: str) -> str:
    return (f"El nombre de la columna «{columna}» contiene caracteres que algunos modelos no admiten "
            f"({CARACTERES_NO_ADMITIDOS}); cámbielo en el archivo o exclúyala.")


def error_valores_columna(columna: str) -> str:
    return (f"La columna «{columna}» tiene valores con caracteres que algunos modelos no admiten "
            f"({CARACTERES_NO_ADMITIDOS}); sustitúyalos en el archivo o exclúyala.")


def error_objetivo_no_existe(columna: str) -> str:
    return f"La columna objetivo «{columna}» no existe en el conjunto."


def error_clase_positiva(clase: str) -> str:
    return f"La clase positiva «{clase}» no aparece en la columna objetivo."


def error_columnas_desconocidas(columnas: list[str]) -> str:
    return f"Columnas desconocidas: {', '.join(columnas)}."


def aviso_sin_objetivo(n: int) -> str:
    return f"{miles(n)} filas no tienen valor en la columna objetivo y no se usan."


def aviso_excluida(columna: str, motivo: str) -> str:
    return f"La columna «{columna}» no se usa para predecir: {motivo}."


def etapa_familia(familia: str, numero: int, total: int) -> str:
    return f"Optimizando {nombre_modelo(familia)} (familia {numero} de {total})"
