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

export function textoMostrando(desde: number, hasta: number, total: number): string {
  return `Mostrando ${desde}-${hasta} de ${total}`;
}

export function textoPagina(pagina: number, paginas: number): string {
  return `Página ${pagina} de ${paginas}`;
}

export function tituloRuta(titulo: string): string {
  return `${titulo} · ${TEXTOS.aplicacion.nombre}`;
}
