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
