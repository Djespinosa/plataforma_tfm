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

export function tituloRuta(titulo: string): string {
  return `${titulo} · ${TEXTOS.aplicacion.nombre}`;
}
