import { HttpErrorResponse } from '@angular/common/http';

import { TEXTOS } from '../textos';

export interface ErrorLegible {
  mensaje: string;
  detalles: string[];
}

/**
 * Mensaje de una respuesta de error (docs/diseno-web.md §5). La API responde siempre {"error", "detalles"?}, también en
 * los 500 (api/errores.py): ese cuerpo se muestra tal cual. Una respuesta HTTP sin él no viene de la API (estado 0, o el
 * proxy de desarrollo con Flask parado, que responde 500 sin cuerpo): aviso de conexión. Lo que no es una respuesta
 * HTTP, mensaje genérico.
 */
export function leerError(e: unknown): ErrorLegible {
  if (!(e instanceof HttpErrorResponse)) {
    return { mensaje: TEXTOS.errores.inesperado, detalles: [] };
  }
  const cuerpo: unknown = e.error;
  if (cuerpo !== null && typeof cuerpo === 'object' && typeof (cuerpo as { error?: unknown }).error === 'string') {
    const { error, detalles } = cuerpo as { error: string; detalles?: unknown };
    return {
      mensaje: error,
      detalles: Array.isArray(detalles) ? detalles.filter((d): d is string => typeof d === 'string') : [],
    };
  }
  return { mensaje: TEXTOS.errores.sinConexion, detalles: [] };
}
