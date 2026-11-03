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
