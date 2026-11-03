/**
 * Todos los textos propios de la interfaz (docs/diseno-web.md §8; skill guardarrailes-interfaz). Las plantillas no llevan
 * texto literal. Los textos que devuelve la API (avisos, lecturas, errores…) se muestran tal cual y no están aquí, salvo
 * las cuatro copias literales marcadas, que hacen falta antes de llamar a la API (decisión W-6).
 */

// copia literal de api/textos.py: AVISO_PRIVACIDAD_CARGA
const AVISO_PRIVACIDAD_CARGA =
  'No suba datos personales identificables sin autorización. La plataforma no envía datos a servicios externos.';
// copia literal de api/textos.py: AVISO_DEMOSTRACION
const AVISO_DEMOSTRACION =
  'Presupuesto reducido de demostración: los resultados no son comparables con los de un entrenamiento completo.';
// copia literal de api/textos.py: TEXTO_PREVIO_PRUEBA
const TEXTO_PREVIO_PRUEBA = 'Esta evaluación se hace una sola vez y no cambia el modelo ni el umbral.';
// copia literal de api/textos.py: NOMBRES_MODELOS
const NOMBRES_MODELOS: Record<string, string> = {
  rl: 'regresión logística',
  rl_optimizada: 'regresión logística optimizada',
  rf: 'bosque aleatorio',
  gb: 'potenciación de gradiente (scikit-learn)',
  xgb: 'XGBoost',
  lgbm: 'LightGBM',
  catboost: 'CatBoost',
  mlp: 'red neuronal (perceptrón multicapa)',
  apilamiento: 'apilamiento de modelos',
  rl_defecto: 'regresión logística por defecto',
  mayoritaria: 'clase mayoritaria',
};

export const TEXTOS = {
  aplicacion: {
    nombre: 'Plataforma de apoyo al seguimiento académico',
    saltar: 'Saltar al contenido',
    navegacionPasos: 'Pasos del flujo',
  },
  pasos: ['Datos', 'Configuración', 'Entrenamiento', 'Evaluación', 'Estimación', 'Explicación'],
  pasoActual: '(paso actual)',
  inicio: {
    titulo: 'Inicio',
    introduccion:
      'La plataforma estima, a partir de datos tabulares, la probabilidad de que un caso pertenezca a la clase ' +
      'elegida y explica qué variables contribuyen a cada estimación. Es una herramienta de apoyo: la decisión ' +
      'corresponde siempre a las personas.',
    usarModelo: 'Usar un modelo ya entrenado',
    usarModeloAyuda: 'Estime una cohorte con un modelo desplegado y consulte su evaluación y sus explicaciones.',
    entrenar: 'Entrenar con mis datos',
    entrenarAyuda: 'Cargue un CSV, configure la validación y entrene un modelo nuevo.',
    historial: 'Ver los experimentos anteriores',
    historialAyuda: 'Consulte el estado y los resultados de cada entrenamiento y reintente los que no terminaron.',
    estadoServidor: 'Estado del servidor',
    baseDatos: 'Base de datos',
    trabajador: 'Proceso de entrenamiento',
    trabajadorActivo: 'en marcha',
    trabajadorInactivo: 'detenido: los entrenamientos esperarán en cola hasta que se inicie',
    trabajadorDesconocido: 'no disponible con esta base de datos',
    version: 'Versión del código',
    comprobando: 'Comprobando el servidor…',
  },
  modelos: {
    titulo: 'Modelos desplegados',
    introduccion:
      'Modelos ya entrenados y listos para estimar. Cada uno conserva la evaluación con la que se eligió y su umbral.',
    tabla: 'Modelos desplegados',
    experimento: 'Experimento',
    momento: 'Momento',
    familia: 'Modelo',
    origen: 'Origen',
    umbral: 'Umbral de alerta',
    acciones: 'Acciones',
    verEvaluacion: 'Ver evaluación',
    verExplicacion: 'Ver explicación global',
    estimar: 'Estimar una cohorte',
    ninguno: 'Todavía no hay modelos desplegados. Entrene uno con sus datos o importe un modelo ya preparado.',
    sinMomento: 'sin indicar',
    cargando: 'Cargando los modelos…',
  },
  carga: {
    titulo: 'Datos para entrenar',
    introduccion:
      'Cargue un CSV con una fila por caso y una columna con el resultado que se quiere anticipar. En el paso ' +
      'siguiente elegirá esa columna y las variables.',
    archivo: 'Archivo CSV con los datos de entrenamiento',
    archivoAyuda: 'CSV en UTF-8 separado por comas o por punto y coma, con una fila de encabezado.',
    momento: 'Momento de predicción (opcional)',
    momentoAyuda: 'Por ejemplo, «semana 4». Solo sirve para reconocer el conjunto y los modelos que se entrenen con él.',
    enviar: 'Cargar el archivo',
    enviando: 'Cargando…',
    sinArchivo: 'Elija un archivo CSV.',
    cargado: 'Archivo cargado',
    filas: 'Filas',
    columnas: 'Columnas',
    tablaColumnas: 'Columnas del archivo',
    columna: 'Columna',
    tipo: 'Tipo',
    tipos: { numerica: 'numérica', categorica: 'categórica' },
    faltantes: 'Valores vacíos',
    distintos: 'Valores distintos',
    configurar: 'Configurar el entrenamiento',
    anteriores: 'Conjuntos ya cargados',
    tablaAnteriores: 'Conjuntos ya cargados, del más reciente al más antiguo',
    nombreArchivo: 'Archivo',
    fecha: 'Cargado el',
    acciones: 'Acciones',
    ninguno: 'Todavía no se ha cargado ningún conjunto.',
    cargando: 'Cargando los conjuntos…',
  },
  configuracion: {
    titulo: 'Configurar el entrenamiento',
    conjunto: 'Conjunto de datos',
    objetivoGrupo: 'Qué se quiere anticipar',
    objetivo: 'Columna objetivo',
    objetivoAyuda: 'La columna con el resultado que el modelo aprenderá a estimar.',
    elegirColumna: 'Elija una columna',
    clasePositiva: 'Clase que se quiere anticipar',
    clasePositivaAyuda:
      'Los casos con este valor cuentan como positivos; todos los demás valores, como negativos. Las filas sin valor ' +
      'en la columna objetivo no se usan.',
    clasePositivaTexto: 'Escriba el valor tal como aparece en el archivo.',
    elegirValor: 'Elija un valor',
    validacionGrupo: 'Validación',
    columnaGrupo: 'Columna de grupo (opcional)',
    columnaGrupoAyuda:
      'Si varias filas están relacionadas (por ejemplo, el mismo estudiante o la misma cohorte), indique la columna ' +
      'que las agrupa: así la validación nunca reparte un mismo grupo entre entrenamiento y evaluación.',
    ninguna: 'Ninguna',
    cohorteGrupo: 'Cohorte de prueba (opcional)',
    cohorteAyuda:
      'Filas que se apartan antes de entrenar y solo se usan, una vez, para la evaluación final en datos no vistos.',
    cohorteNinguna: 'Ninguna: solo validación cruzada',
    cohorteValores: 'Las filas con ciertos valores de una columna (por ejemplo, la cohorte más reciente)',
    cohorteAleatoria: 'El 20 % de las filas, al azar (solo sin columna de grupo)',
    cohorteColumna: 'Columna que define la cohorte',
    cohorteValoresLeyenda: 'Valores que forman la cohorte de prueba',
    cohorteMasValores: 'Solo se listan los 20 valores más frecuentes de esta columna.',
    variablesGrupo: 'Variables',
    variablesAyuda:
      'Por defecto se usan todas las columnas salvo la objetivo. Marque las que no deben usarse. Las sensibles (por ' +
      'ejemplo, sexo o discapacidad) tampoco se usan para estimar: sirven para comparar los resultados por subgrupo.',
    tablaVariables: 'Columnas del conjunto',
    columna: 'Columna',
    tipo: 'Tipo',
    excluir: 'No usar',
    sensible: 'Sensible',
    presupuestoGrupo: 'Presupuesto de búsqueda',
    presupuestoCompleto: 'Completo (recomendado)',
    presupuestoDemostracion: 'Demostración: búsqueda reducida, más rápida',
    descripcion: 'Descripción (opcional)',
    descripcionAyuda: 'Una nota para reconocer el experimento en el historial.',
    comprobar: 'Comprobar la configuración',
    comprobando: 'Comprobando…',
    entrenar: 'Entrenar',
    enviando: 'Enviando…',
    entrenarAyuda: '«Entrenar» se activa cuando la configuración actual se ha comprobado sin errores.',
    faltaObjetivo: 'Elija la columna objetivo y la clase que se quiere anticipar.',
    faltanValores: 'Elija la columna y al menos un valor de la cohorte de prueba.',
    cambiada: 'La configuración ha cambiado desde la última comprobación; vuelva a comprobarla.',
    esquema: 'Configuración comprobada',
    filasEntrenamiento: 'Filas de entrenamiento',
    filasPrueba: 'Filas de la cohorte de prueba',
    filasSinObjetivo: 'Filas sin valor en la columna objetivo (no se usan)',
    positivos: 'Positivos en entrenamiento',
    numericas: 'Variables numéricas',
    categoricas: 'Variables categóricas',
    excluidasAutomaticamente: 'Columnas que no se usan para estimar',
    validacion: 'Validación',
    grupos: 'grupos',
    cohorte: 'Cohorte de prueba',
    filas: 'filas',
    presupuesto: 'Presupuesto',
    modos: { completo: 'completo', demostracion: 'demostración' } as Record<string, string | undefined>,
    ensayos: 'ensayos por familia',
    familias: 'familias de modelos',
    replicas: 'réplicas bootstrap',
    cargando: 'Cargando el conjunto…',
  },
  seguimiento: {
    titulo: 'Seguimiento del entrenamiento',
    experimento: 'Experimento',
    estado: 'Estado',
    estados: {
      en_cola: 'En cola: esperando al proceso de entrenamiento',
      en_curso: 'Entrenando',
      completado: 'Completado',
      fallido: 'Ha fallado',
      interrumpido: 'Interrumpido',
    },
    etapa: 'Etapa',
    progreso: 'Progreso',
    ultimoLatido: 'Última señal del proceso',
    duracion: 'Duración',
    reintentoDe: 'Reintento de',
    trabajadorInactivo:
      'El proceso de entrenamiento no está en marcha: el experimento esperará en cola hasta que se inicie.',
    actualizando: 'La página se actualiza sola cada pocos segundos mientras dura el entrenamiento.',
    resultados: 'Resultados',
    verEvaluacion: 'Ver la evaluación',
    reintentar: 'Reintentar con la misma configuración',
    reintentando: 'Reintentando…',
    reproducibilidad: 'Reproducibilidad',
    commit: 'Versión del código',
    arbolLimpio: 'Código sin cambios sin confirmar',
    si: 'sí',
    no: 'no',
    desconocido: 'no consta',
    semillas: 'Semillas',
    versiones: 'Versiones de las bibliotecas',
    huellaDatos: 'Huella SHA-256 de los datos',
    cargando: 'Cargando el experimento…',
  },
  historial: {
    titulo: 'Experimentos anteriores',
    introduccion:
      'Todos los experimentos, del más reciente al más antiguo: los entrenados en la plataforma y los importados. ' +
      'Los que fallaron o se interrumpieron se pueden reintentar desde su página.',
    tabla: 'Experimentos, del más reciente al más antiguo',
    experimento: 'Experimento',
    fecha: 'Creado el',
    estado: 'Estado',
    datos: 'Datos',
    objetivo: 'Objetivo',
    presupuesto: 'Presupuesto',
    modelos: 'Modelos',
    acciones: 'Acciones',
    verExperimento: 'Ver el experimento',
    verEvaluacion: 'Ver la evaluación',
    reintento: 'reintento de',
    noAplica: 'no aplica',
    ninguno: 'Todavía no hay experimentos. Cargue un CSV para entrenar el primero.',
    cargando: 'Cargando los experimentos…',
  },
  origenes: { web: 'entrenado en la plataforma', importado: 'importado' } as Record<string, string>,
  demostracion: 'Entrenamiento de demostración',
  prediccion: {
    titulo: 'Estimar una cohorte',
    modelo: 'Modelo',
    columnasNecesarias: 'Columnas que debe traer el archivo',
    numericas: 'Numéricas',
    categoricas: 'Categóricas',
    columnasAyuda:
      'Las demás columnas del archivo se ignoran; si trae la columna objetivo, tampoco se usa: aquí no se calcula ' +
      'ninguna métrica.',
    archivo: 'Archivo CSV con los casos que se van a estimar',
    archivoAyuda: 'CSV en UTF-8 separado por comas o por punto y coma, con una fila de encabezado.',
    columnaId: 'Columna identificadora (opcional)',
    columnaIdAyuda: 'Solo se muestra en la lista para reconocer cada caso; nunca entra al modelo.',
    enviar: 'Estimar',
    enviando: 'Estimando…',
    sinArchivo: 'Elija un archivo CSV.',
    cargando: 'Cargando el modelo…',
  },
  lote: {
    titulo: 'Probabilidades estimadas',
    resumen: 'Resumen',
    archivo: 'Archivo',
    umbral: 'Umbral de alerta',
    ignoradas: 'Columnas ignoradas',
    ninguna: 'ninguna',
    bajoDemanda: 'La explicación de cada fila se calcula al abrirla (unos segundos).',
    tabla: 'Casos del lote',
    fila: 'Fila',
    identificador: 'Identificador',
    alerta: 'Alerta',
    sugerencia: 'Sugerencia',
    explicacion: 'Explicación',
    verExplicacion: 'Ver la explicación',
    marcado: 'Marcado para seguimiento',
    noMarcado: 'No marcado',
    filtros: 'Filtrar la lista',
    todos: 'Todos los casos',
    soloMarcados: 'Solo los marcados para seguimiento',
    buscar: 'Buscar por identificador',
    minimo: 'Probabilidad mínima (%)',
    ordenarPor: 'Ordenar por',
    anterior: 'Página anterior',
    siguiente: 'Página siguiente',
    cargando: 'Cargando el lote…',
    sinFilas: 'Ningún caso cumple los filtros.',
  },
  detalleTecnico: 'Ver el detalle técnico',
  grafico: { verTabla: 'Ver los datos del gráfico en una tabla' },
  explicacion: { sinContribucion: 'Variables que no intervienen en las estimaciones' },
  explicacionGlobal: {
    titulo: 'Variables que más contribuyen a las estimaciones del modelo',
    modelo: 'Modelo',
    fuente: 'Calculado sobre',
    grafico: 'Contribución media de cada variable (las 15 mayores)',
    graficoDescripcion:
      'Barras horizontales: cuanto más larga la barra, más contribuye en promedio la variable a las estimaciones del ' +
      'modelo, hacia arriba o hacia abajo.',
    variable: 'Variable',
    importancia: 'Contribución media (valor absoluto)',
    tablaCompleta: 'Todas las variables, de mayor a menor contribución media',
    posicion: 'Posición',
    cargando: 'Cargando la explicación global…',
  },
  explicacionLocal: {
    titulo: 'Explicación de una estimación',
    estimacion: 'Estimación',
    fila: 'Fila del archivo',
    factores: 'Factores que más contribuyen a esta estimación',
    aumentan: 'Aumentan la estimación',
    reducen: 'Reducen la estimación',
    extrema: '(inusualmente grande)',
    ninguna: 'Ninguna entre las cinco de mayor contribución.',
    grafico: 'Contribución de cada factor a esta estimación',
    graficoDescripcion:
      'Barras horizontales a partir de un eje central: hacia la derecha (relleno liso) las variables que aumentan la ' +
      'estimación y hacia la izquierda (relleno rayado) las que la reducen; el valor con signo va junto a cada barra.',
    variableValor: 'Variable y valor',
    contribucion: 'Contribución',
    escala: 'Escala de las contribuciones',
    valorBase: 'Valor base',
    logOdds: 'Salida del modelo antes de calibrar',
    todas: 'Contribución de todas las variables',
    valor: 'Valor',
    volver: 'Volver a la lista del lote',
    cargando: 'Calculando la explicación…',
  },
  calibracion: {
    titulo: 'Curva de calibración',
    descripcion:
      'Cada punto compara la probabilidad estimada por el modelo en un grupo de casos (eje horizontal) con la ' +
      'proporción de positivos observada en ese grupo (eje vertical). Cuanto más cerca de la diagonal, mejor ' +
      'calibradas están las probabilidades.',
    ejeX: 'Probabilidad estimada',
    ejeY: 'Proporción observada de positivos',
    calibrada: 'Probabilidad calibrada (la que muestra la plataforma)',
    sinCalibrar: 'Antes de calibrar',
    diagonal: 'Calibración perfecta (diagonal)',
  },
  evaluacion: {
    titulo: 'Evaluación del modelo',
    elegirMomento: 'Elegir el momento',
    resumen: 'Resumen',
    desplegado: 'Modelo desplegado',
    puntoOperacion: 'Con el umbral de alerta elegido',
    umbral: 'Umbral de alerta',
    ordenacion: 'Capacidad para ordenar los casos',
    rocAuc: 'ROC-AUC (out-of-fold)',
    calibracion: 'Calibración',
    modelosComparados: 'Modelos comparados',
    casos: 'Casos',
    positivos: 'Positivos',
    papel: 'Papel',
    papeles: { desplegado: 'desplegado', candidato: 'candidato', referencia: 'referencia' },
    rocAucPliegues: 'ROC-AUC por pliegue (media ± desv.)',
    prAuc: 'PR-AUC',
    brier: 'Brier',
    metodoCalibracion: 'Método de calibración',
    contraste: 'Comparación con la regresión logística optimizada',
    comparados: 'Modelos comparados',
    diferencia: 'Diferencia de ROC-AUC e intervalo del 95 %',
    pDelong: 'p de DeLong',
    pHolm: 'p corregido (Holm)',
    holmSobre: 'Holm sobre',
    parsimonia: 'Elección del modelo más simple',
    parsimoniaTabla: 'Pérdida de ROC-AUC frente al mejor e intervalo del 95 %',
    perdida: 'Pérdida e intervalo del 95 %',
    cumple: 'Dentro del margen',
    si: 'sí',
    no: 'no',
    matriz: 'Casos marcados y no marcados',
    marcados: 'Marcados para seguimiento',
    noMarcados: 'No marcados',
    positivosReales: 'Positivos reales',
    negativosReales: 'Negativos reales',
    tasaFalsosPositivos: 'Tasa de falsos positivos',
    brierSinCalibrar: 'Brier antes de calibrar',
    brierCalibrado: 'Brier calibrado',
    equidad: 'Resultados por subgrupo',
    subgrupo: 'Subgrupo',
    sensibilidad: 'Sensibilidad e intervalo del 95 %',
    nota: 'Nota',
    soloDescriptiva: 'solo descriptiva (subgrupo pequeño)',
    diferenciaSensibilidad: 'Diferencia máxima de sensibilidad',
    diferenciaFalsosPositivos: 'diferencia máxima de tasa de falsos positivos',
    validacionPresupuesto: 'Validación y presupuesto',
    validacion: 'Validación',
    presupuesto: 'Presupuesto',
    ensayos: 'ensayos por familia',
    replicas: 'réplicas bootstrap',
    sinValor: 'no aplica',
    cargando: 'Cargando la evaluación…',
  },
  noEncontrada: {
    titulo: 'Página no encontrada',
    texto: 'La dirección no corresponde a ninguna vista de la plataforma.',
    volver: 'Volver al inicio',
  },
  avisos: {
    informacion: 'Información',
    cautela: 'Atención',
    error: 'Error',
  },
  errores: {
    sinConexion: 'No se puede conectar con el servidor de la plataforma. Compruebe que la API está en marcha.',
    inesperado: 'El servidor ha respondido de forma inesperada. Inténtelo de nuevo.',
  },
  apiCopias: {
    avisoPrivacidad: AVISO_PRIVACIDAD_CARGA,
    avisoDemostracion: AVISO_DEMOSTRACION,
    textoPrevioPrueba: TEXTO_PREVIO_PRUEBA,
  },
};

export function nombreModelo(modelo: string): string {
  return NOMBRES_MODELOS[modelo] ?? modelo;
}

export function textoMarcados(marcados: string, total: string, porcentaje: string): string {
  return `Se marcan para seguimiento ${marcados} de ${total} casos (${porcentaje}).`;
}

export function textoProbabilidad(porcentaje: string): string {
  return `Probabilidad estimada por el modelo: ${porcentaje}`;
}

export function textoResto(variables: number, suma: string): string {
  return `Otras ${variables} variables suman ${suma} en la escala del modelo.`;
}

const VALIDACIONES: Record<string, string> = {
  agrupada: 'validación cruzada agrupada',
  agrupada_estratificada: 'validación cruzada agrupada y estratificada',
  estratificada: 'validación cruzada estratificada',
};

export function textoValidacion(tipo: string, k: number): string {
  return `${VALIDACIONES[tipo] ?? tipo} de ${k} pliegues`;
}

export function textoMostrando(desde: number, hasta: number, total: number): string {
  return `Mostrando ${desde}-${hasta} de ${total}`;
}

export function textoPagina(pagina: number, paginas: number): string {
  return `Página ${pagina} de ${paginas}`;
}

export function tituloRuta(titulo: string): string {
  return `${titulo} · ${TEXTOS.aplicacion.nombre}`;
}

export function textoEtapas(completadas: number, total: number): string {
  return `${completadas} de ${total} etapas`;
}
