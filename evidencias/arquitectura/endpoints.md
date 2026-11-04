# Endpoints de la API REST

19 rutas bajo `/api`, JSON UTF-8. Errores: `{"error": "…"}` (y `detalles` si hay varios) con 400, 404, 405, 409, 413, 415, 422, 500 y 503 (cualquier `OperationalError` de la base de datos). Sin autenticación: uso local en `127.0.0.1` (decisión D-1). RF-07 (vista resumida y detallada) no tiene ruta propia: lo resuelve la interfaz con las rutas de RF-04 a RF-06.

| Método | Ruta | Requisito | Descripción |
|---|---|---|---|
| GET | `/api/estado` | — | Estado del sistema: motor de base de datos, trabajador activo y commit del código |
| POST | `/api/conjuntos` | RF-01 | Carga de un CSV: validación y resumen de columnas |
| GET | `/api/conjuntos` | RF-01 | Conjuntos de datos cargados |
| GET | `/api/conjuntos/<int:id_>` | RF-01, RF-02 | Detalle de un conjunto: columnas, tipos, faltantes y valores |
| POST | `/api/experimentos/validacion` | RF-02 | Comprueba una configuración y devuelve el esquema efectivo, sin crear nada |
| POST | `/api/experimentos` | RF-02, RF-03 | Crea un experimento con la configuración y lo deja en cola para el trabajador |
| GET | `/api/experimentos` | RF-08 | Historial de experimentos web e importados |
| GET | `/api/experimentos/<id_>` | RF-03, RF-08 | Detalle y seguimiento de un experimento (estado, etapa, progreso, latido) |
| POST | `/api/experimentos/<id_>/reintentar` | RF-08 | Experimento nuevo con la misma configuración efectiva tras un fallo o una interrupción |
| GET | `/api/experimentos/<id_>/evaluacion` | RF-04 | Evaluación out-of-fold: candidatos, referencias, contraste, desplegado, umbral, calibración y equidad |
| GET | `/api/experimentos/<id_>/evaluacion/exportar` | RF-09 | Descarga de la evaluación en JSON |
| POST | `/api/experimentos/<id_>/evaluacion-prueba` | RF-04 | Evaluación única en la cohorte de prueba reservada (solo experimentos web, con confirmación) |
| GET | `/api/modelos` | RF-05 | Modelos desplegados disponibles para estimar |
| GET | `/api/modelos/<int:id_>` | RF-05 | Detalle de un modelo: columnas necesarias, umbral y explicador |
| GET | `/api/modelos/<int:id_>/explicacion-global` | RF-06 | Explicación global del modelo (media del valor absoluto de SHAP por variable) |
| POST | `/api/modelos/<int:id_>/predicciones` | RF-05 | Estimación de un CSV: probabilidad calibrada y marca de seguimiento por fila |
| GET | `/api/predicciones/<int:lote_id>` | RF-05 | Resultado de un lote de estimaciones |
| GET | `/api/predicciones/<int:lote_id>/exportar` | RF-09 | Descarga de las estimaciones del lote en CSV (UTF-8 con BOM) |
| GET | `/api/predicciones/<int:lote_id>/filas/<int:fila>/explicacion` | RF-06 | Explicación local de una fila (contribuciones SHAP, con las extremas marcadas) |
