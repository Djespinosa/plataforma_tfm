/**
 * Respuestas sintéticas con la forma de docs/diseno-api.md §4, sin datos de OULAD. Todos los textos que da la API son
 * «texto de la API»: así, al renderizar una vista, solo quedan los textos propios (textos.ts y las plantillas).
 */
import {
  Conjunto,
  ConjuntoResumen,
  Estado,
  Evaluacion,
  EvaluacionModelo,
  EvaluacionPrueba,
  ExperimentoDetalle,
  ExperimentoHistorial,
  ExplicacionGlobal,
  ExplicacionLocal,
  FilaMetricas,
  Lote,
  Modelo,
  ModeloDetalle,
} from '../api/tipos';

export const API = 'texto de la API';
const FECHA = '2026-11-03T10:00:00+00:00';

export const ESTADO: Estado = { motor_bd: 'postgresql 16', trabajador_activo: false, commit: 'abc1234' };

export const MODELO: Modelo = {
  id: 2, experimento_id: 'exp-1', origen: 'web', momento: 'semana 4', familia: 'rl', umbral: 0.2,
  explicador: 'lineal', creado_en: FECHA,
};
export const MODELO_DETALLE: ModeloDetalle = { ...MODELO, columnas: { numericas: ['x1'], categoricas: ['c'] } };

export const EXPERIMENTO: ExperimentoDetalle = {
  id: 'exp-1', origen: 'web', estado: 'completado', descripcion: 'nota', etapa: null,
  configuracion: { presupuesto: { modo: 'demostracion' }, avisos: [API], cohorte_prueba: { modo: 'aleatoria' } },
  modelos: [{ id: 2, momento: 'semana 4', familia: 'rl' }], progreso: { completadas: 5, total: 5 }, latido_en: FECHA,
  sin_respuesta: false, aviso_sin_respuesta: null, error: null, duracion_s: 725, reintento_de: 'exp-0',
  reproducibilidad: { commit: 'abc1234', arbol_limpio: true, semillas: { modelos: 42 }, versiones: { python: '3.13' },
    sha256_datos: 'f00' },
  evaluacion_prueba: null,
};

export const EVALUACION_PRUEBA: EvaluacionPrueba = {
  fecha: FECHA, modelo_id: 2, n: 200, positivos: 40, roc_auc: 0.71, pr_auc: 0.33, brier: 0.15,
  punto_operacion: { umbral: 0.15, sensibilidad: 0.7, precision: null, tasa_alerta: 0.45, tasa_falsos_positivos: 0.4,
    matriz_confusion: [[96, 64], [12, 28]], textos: { sensibilidad: API, precision: API, tasa_alerta: API } },
  fuente: 'cohorte_prueba', aviso_fuente: API, textos: { roc_auc: API, pr_auc: API }, aviso_decision: API,
};

/** Mismo experimento, fallido, con el proceso sin responder (los dos avisos y el botón de reintento). */
export const EXPERIMENTO_FALLIDO: ExperimentoDetalle = {
  ...EXPERIMENTO, estado: 'fallido', sin_respuesta: true, aviso_sin_respuesta: API, error: API, reproducibilidad: null,
};

export const HISTORIAL: ExperimentoHistorial[] = [
  { id: 'exp-1', origen: 'web', estado: 'completado', creado_en: FECHA, duracion_s: 725, descripcion: 'nota',
    conjunto: { id: 3, nombre_archivo: 'datos.csv', momento: 'semana 4' }, objetivo: 'y', presupuesto: 'demostracion',
    reintento_de: 'exp-0', modelos: [{ id: 2, momento: 'semana 4', familia: 'rl' }] },
  { id: 'exp-0', origen: 'importado', estado: 'interrumpido', creado_en: FECHA, duracion_s: null, descripcion: null,
    conjunto: null, objetivo: null, presupuesto: 'completo', reintento_de: null, modelos: [] },
];

const fila = (modelo: string, papel: FilaMetricas['papel']): FilaMetricas => ({
  modelo, papel, roc_auc_oof: 0.7, roc_auc_media: 0.69, roc_auc_desv: 0.02, pr_auc_oof: 0.3, brier_oof: 0.14,
  calibracion: papel === 'referencia' ? null : 'platt',
});

const MODELO_EVALUADO: EvaluacionModelo = {
  modelo_id: 2, momento: 'semana 4', n: 12000, positivos: 2000,
  candidatos: [fila('rl', 'desplegado'), fila('lgbm', 'candidato')], referencias: [fila('mayoritaria', 'referencia')],
  contraste: { modelo_a: 'lgbm', modelo_b: 'rl_optimizada', diferencia: 0.003, ic95_bootstrap: [-0.002, 0.007],
    delong_p: 0.26, delong_p_holm: 0.52, lectura: 'equivalencia_practica', lectura_texto: API, holm_sobre: 2 },
  parsimonia: { mejor: 'lgbm', margen: 0.02,
    candidatos: [{ modelo: 'rl', roc_auc_oof: 0.7, perdida: 0.003, ic95_bootstrap: [-0.002, 0.007], cumple: true }] },
  desplegado: { modelo: 'rl', mejor: 'lgbm', limite_superior: 0.007, motivo_texto: API },
  punto_operacion: { umbral: 0.15, sensibilidad: 0.7, precision: 0.26, tasa_alerta: 0.49, tasa_falsos_positivos: 0.45,
    matriz_confusion: [[11, 22], [33, 44]], textos: { sensibilidad: API, precision: API, tasa_alerta: API } },
  calibracion: { metodo: 'platt', brier_sin_calibrar: 0.2, brier_calibrado: 0.14, texto: API,
    curva: { calibrada: [{ predicha: 0.1, observada: 0.12 }], sin_calibrar: [{ predicha: 0.1, observada: 0.2 }] } },
  equidad: { texto: API, atributos: { a: {
    subgrupos: {
      p: { n: 600, retiros: 120, sensibilidad: 0.62, sensibilidad_ic95: [0.55, 0.69], tasa_falsos_positivos: 0.4,
        tasa_falsos_positivos_ic95: [0.36, 0.44], solo_descriptiva: false },
      q: { n: 4, retiros: 0, sensibilidad: null, sensibilidad_ic95: null, tasa_falsos_positivos: 0.5,
        tasa_falsos_positivos_ic95: null, solo_descriptiva: true },
    },
    diferencia_sensibilidad: 0.12, diferencia_sensibilidad_ic95: [0.04, 0.2], diferencia_tasa_falsos_positivos: null,
    diferencia_tasa_falsos_positivos_ic95: null } } },
  textos: { roc_auc: API, pr_auc: API },
};

export const EVALUACION: Evaluacion = {
  experimento: 'exp-1', origen: 'web', fuente: 'validacion_cruzada', aviso_fuente: API,
  presupuesto: { modo: 'demostracion', familias: ['rl', 'lgbm'], n_trials_por_familia: 5, apilamiento: true,
    n_bootstrap: 200 },
  validacion: { tipo: 'agrupada_estratificada', k: 5, semilla: 42, columna_grupo: 'g' },
  modelos: [MODELO_EVALUADO, { ...MODELO_EVALUADO, modelo_id: 3, momento: 'semana 8', calibracion: {
    ...MODELO_EVALUADO.calibracion, curva: null, motivo: API } }],
  aviso_decision: API,
};

export const LOTE: Lote = {
  lote: { id: 7, modelo_id: 2, nombre_archivo: 'casos.csv', n_filas: 2, n_alertas: 1, tasa_alerta: 0.5, umbral: 0.2,
    columna_id: 'codigo', columnas_ignoradas: ['y'], explicaciones: 'bajo_demanda', creado_en: FECHA },
  filas: [
    { fila: 1, identificador: 'A-1', probabilidad: 0.34, alerta: true, sugerencia: API },
    { fila: 2, identificador: 'A-2', probabilidad: 0.05, alerta: false, sugerencia: null },
  ],
  textos: { probabilidad: API, sugerencia: API },
  aviso_rendimiento: API,
  aviso_decision: API,
};

const AVISOS = { escala: API, causalidad: API, decision: API };

export const EXPLICACION_GLOBAL: ExplicacionGlobal = {
  modelo_id: 2, explicador: 'lineal', escala: API, fuente: API,
  variables: [{ variable: 'x1', importancia_media_abs: 0.4 }, { variable: 'c', importancia_media_abs: 0.1 }],
  sin_contribucion: [{ variable: 'z', motivo: API }], avisos: AVISOS, aviso_decision: API,
};

export const EXPLICACION_LOCAL: ExplicacionLocal = {
  fila: 1, identificador: 'A-1', probabilidad: 0.34, alerta: true, sugerencia: API, escala: API, valor_base: -1.2,
  log_odds: -0.4, explicador: 'lineal',
  aumentan: [{ variable: 'x1', valor: '12', contribucion: 6.1, extrema: true }],
  reducen: [{ variable: 'c', valor: 'b', contribucion: -0.25, extrema: false }],
  resto: { n_variables: 3, suma: -0.05 },
  todas: [{ variable: 'x1', valor: '12', contribucion: 6.1, extrema: true }],
  sin_contribucion: [{ variable: 'z', motivo: API }], hay_extremas: true,
  avisos: { ...AVISOS, extrema: API }, aviso_rendimiento: API, aviso_decision: API,
};

export const CONJUNTOS: ConjuntoResumen[] = [
  { id: 3, nombre_archivo: 'datos.csv', momento: null, n_filas: 100, n_columnas: 3, creado_en: FECHA },
];

export const CONJUNTO: Conjunto = {
  ...CONJUNTOS[0], sha256: 'f00', aviso_privacidad: API, avisos: [API],
  columnas: [
    { nombre: 'y', tipo: 'categorica', faltantes: 0, proporcion_faltantes: 0, valores_distintos: 2,
      valores_frecuentes: [{ valor: 'p', n: 60 }, { valor: 'q', n: 40 }] },
    { nombre: 'x1', tipo: 'numerica', faltantes: 2, proporcion_faltantes: 0.02, valores_distintos: 50,
      valores_frecuentes: [] },
  ],
};
