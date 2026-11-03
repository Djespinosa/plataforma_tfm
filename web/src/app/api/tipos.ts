/**
 * Respuestas de la API (docs/diseno-api.md §4), con los nombres de campo tal cual. Se amplía en cada incremento con las
 * rutas que usa.
 */

/** GET /api/estado */
export interface Estado {
  motor_bd: string;
  trabajador_activo: boolean | null;
  commit: string | null;
}

export type Origen = 'web' | 'importado';
export type Explicador = 'lineal' | 'arbol' | 'permutacion';
export type EstadoExperimento = 'en_cola' | 'en_curso' | 'completado' | 'fallido' | 'interrumpido';

/** GET /api/conjuntos (cada elemento) */
export interface ConjuntoResumen {
  id: number;
  nombre_archivo: string;
  momento: string | null;
  n_filas: number;
  n_columnas: number;
  creado_en: string;
}

export interface Columna {
  nombre: string;
  tipo: 'numerica' | 'categorica';
  faltantes: number;
  proporcion_faltantes: number;
  valores_distintos: number;
  valores_frecuentes: { valor: string; n: number }[];
}

/** POST /api/conjuntos → 201 y GET /api/conjuntos/{id} */
export interface Conjunto extends ConjuntoResumen {
  sha256: string;
  columnas: Columna[];
  avisos: string[];
  aviso_privacidad: string;
}

export type CohortePrueba = null | { modo: 'aleatoria' } | { modo: 'valores'; columna: string; valores: string[] };

/** Cuerpo de POST /api/experimentos/validacion y POST /api/experimentos */
export interface CuerpoExperimento {
  conjunto_id: number;
  objetivo: string;
  clase_positiva: string;
  excluidas: string[];
  sensibles: string[];
  columna_grupo: string | null;
  cohorte_prueba: CohortePrueba;
  presupuesto: 'completo' | 'demostracion';
  descripcion: string | null;
}

/** POST /api/experimentos/validacion → 200 (esquema efectivo) */
export interface ValidacionExperimento {
  filas_entrenamiento: number;
  filas_prueba: number;
  filas_sin_objetivo: number;
  positivos_entrenamiento: number;
  prevalencia_entrenamiento: number;
  variables: { numericas: string[]; categoricas: string[] };
  excluidas_automaticamente: { columna: string; motivo: string }[];
  validacion: { tipo: string; k: number; semilla: number; columna_grupo: string | null; n_grupos: number | null };
  cohorte_prueba:
    | null
    | { modo: 'aleatoria' | 'valores'; columna?: string; valores?: string[]; filas: number; metodo: string };
  presupuesto: { modo: string; familias: string[]; n_trials_por_familia: number; n_bootstrap: number };
  avisos: string[];
}

/** GET /api/modelos (cada elemento) */
export interface Modelo {
  id: number;
  experimento_id: string;
  origen: Origen;
  momento: string | null;
  familia: string;
  umbral: number;
  explicador: Explicador;
  creado_en: string;
}

/** GET /api/modelos/{id} */
export interface ModeloDetalle extends Modelo {
  columnas: { numericas: string[]; categoricas: string[] };
}

/** GET /api/experimentos/{id} (los campos que usa la interfaz) */
export interface ExperimentoDetalle {
  id: string;
  origen: Origen;
  estado: EstadoExperimento;
  descripcion: string | null;
  configuracion: { presupuesto: { modo: string }; avisos?: string[] } & Record<string, unknown>;
  modelos: { id: number; momento: string | null; familia: string }[];
  etapa: string | null;
  progreso: { completadas: number; total: number } | null;
  latido_en: string | null;
  sin_respuesta: boolean;
  aviso_sin_respuesta: string | null;
  error: string | null;
  duracion_s: number | null;
  reintento_de: string | null;
  /** Solo en los entrenados en la plataforma y completados (los importados traen `procedencia`). */
  reproducibilidad: Reproducibilidad | null;
}

export interface Reproducibilidad {
  commit: string | null;
  arbol_limpio: boolean | null;
  semillas: Record<string, number>;
  versiones: Record<string, string>;
  sha256_datos: string;
}

/** GET /api/experimentos (cada elemento), del más reciente al más antiguo */
export interface ExperimentoHistorial {
  id: string;
  origen: Origen;
  estado: EstadoExperimento;
  creado_en: string;
  duracion_s: number | null;
  descripcion: string | null;
  conjunto: { id: number; nombre_archivo: string; momento: string | null } | null;
  /** null en los importados. */
  objetivo: string | null;
  presupuesto: string;
  reintento_de: string | null;
  modelos: { id: number; momento: string | null; familia: string }[];
}

/** POST /api/modelos/{id}/predicciones → 201 */
export interface LoteCreado {
  lote_id: number;
  modelo_id: number;
  n_filas: number;
  n_alertas: number;
  tasa_alerta: number;
  umbral: number;
  columnas_ignoradas: string[];
  explicaciones: 'completas' | 'bajo_demanda';
  aviso_rendimiento: string;
  aviso_decision: string;
}

export interface FilaLote {
  fila: number;
  identificador: string | null;
  probabilidad: number;
  alerta: boolean;
  sugerencia: string | null;
}

/** GET /api/predicciones/{lote_id} */
export interface Lote {
  lote: {
    id: number;
    modelo_id: number;
    nombre_archivo: string;
    n_filas: number;
    n_alertas: number;
    tasa_alerta: number;
    umbral: number;
    columna_id: string | null;
    columnas_ignoradas: string[];
    explicaciones: 'completas' | 'bajo_demanda';
    creado_en: string;
  };
  filas: FilaLote[];
  textos: { probabilidad: string; sugerencia: string };
  aviso_rendimiento: string;
  aviso_decision: string;
}

export interface SinContribucion {
  variable: string;
  motivo: string;
}

/** GET /api/modelos/{id}/explicacion-global */
export interface ExplicacionGlobal {
  modelo_id: number;
  explicador: Explicador;
  escala: string;
  fuente: string | null;
  /** null si el modelo no tiene filas de referencia (entonces llega motivo). */
  variables: { variable: string; importancia_media_abs: number }[] | null;
  sin_contribucion: SinContribucion[];
  motivo?: string;
  avisos: { escala: string; causalidad: string; decision: string };
  aviso_decision: string;
}

export interface Contribucion {
  variable: string;
  valor: string;
  contribucion: number;
  extrema: boolean;
}

/** GET /api/predicciones/{lote}/filas/{fila}/explicacion */
export interface ExplicacionLocal {
  fila: number;
  identificador: string | null;
  probabilidad: number;
  alerta: boolean;
  sugerencia: string | null;
  escala: string;
  valor_base: number;
  log_odds: number;
  explicador: Explicador;
  aumentan: Contribucion[];
  reducen: Contribucion[];
  resto: { n_variables: number; suma: number };
  todas: Contribucion[];
  sin_contribucion: SinContribucion[];
  hay_extremas: boolean;
  avisos: { escala: string; causalidad: string; decision: string; extrema?: string };
  aviso_rendimiento: string;
  aviso_decision: string;
}

export interface FilaMetricas {
  modelo: string;
  papel: 'desplegado' | 'candidato' | 'referencia';
  roc_auc_oof: number | null;
  roc_auc_media: number | null;
  roc_auc_desv: number | null;
  pr_auc_oof: number | null;
  brier_oof: number | null;
  calibracion: string | null;
}

export interface PuntoCurva {
  predicha: number;
  observada: number;
}

export interface Subgrupo {
  n: number;
  /** Positivos del subgrupo (la clave es la de la API). */
  retiros: number;
  sensibilidad: number | null;
  sensibilidad_ic95: [number, number] | null;
  tasa_falsos_positivos: number | null;
  tasa_falsos_positivos_ic95: [number, number] | null;
  solo_descriptiva: boolean;
}

export interface AtributoEquidad {
  subgrupos: Record<string, Subgrupo>;
  diferencia_sensibilidad: number | null;
  diferencia_sensibilidad_ic95: [number, number] | null;
  diferencia_tasa_falsos_positivos: number | null;
  diferencia_tasa_falsos_positivos_ic95: [number, number] | null;
}

/** Evaluación de un modelo (un momento) en GET /api/experimentos/{id}/evaluacion. */
export interface EvaluacionModelo {
  modelo_id: number;
  momento: string | null;
  n: number;
  positivos: number;
  candidatos: FilaMetricas[];
  referencias: FilaMetricas[];
  contraste: {
    modelo_a: string;
    modelo_b: string;
    diferencia: number;
    ic95_bootstrap: [number, number];
    delong_p: number;
    delong_p_holm: number;
    lectura: string;
    lectura_texto: string;
    holm_sobre: number;
  };
  parsimonia: {
    mejor: string;
    margen: number;
    candidatos: { modelo: string; roc_auc_oof: number; perdida: number; ic95_bootstrap: [number, number]; cumple: boolean }[];
  };
  desplegado: { modelo: string; mejor: string; limite_superior: number | null; motivo_texto: string };
  punto_operacion: {
    umbral: number;
    sensibilidad: number;
    precision: number | null;
    tasa_alerta: number;
    tasa_falsos_positivos: number;
    /** [[VN, FP], [FN, VP]] */
    matriz_confusion: [[number, number], [number, number]];
    textos: { sensibilidad: string; precision: string; tasa_alerta: string };
  };
  calibracion: {
    metodo: string | null;
    brier_sin_calibrar: number | null;
    brier_calibrado: number | null;
    curva: { calibrada: PuntoCurva[]; sin_calibrar: PuntoCurva[] | null } | null;
    texto: string;
    motivo?: string;
  };
  equidad: { texto: string; atributos: Record<string, AtributoEquidad> } | null;
  textos: { roc_auc: string; pr_auc: string };
}

/** GET /api/experimentos/{id}/evaluacion */
export interface Evaluacion {
  experimento: string;
  origen: Origen;
  fuente: 'validacion_cruzada';
  aviso_fuente: string;
  presupuesto: { modo: string; familias: string[]; n_trials_por_familia: number; apilamiento: boolean; n_bootstrap: number };
  validacion: { tipo: string; k: number; semilla: number; columna_grupo: string | null; n_grupos?: number | null };
  modelos: EvaluacionModelo[];
  aviso_decision: string;
}
