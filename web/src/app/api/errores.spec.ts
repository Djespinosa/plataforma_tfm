import { HttpErrorResponse } from '@angular/common/http';

import { TEXTOS } from '../textos';
import { leerError } from './errores';

describe('leerError', () => {
  it('muestra el mensaje y los detalles de la API tal cual', () => {
    const e = new HttpErrorResponse({ status: 422, error: { error: 'Faltan columnas.', detalles: ['x1', 3, 'x2'] } });
    expect(leerError(e)).toEqual({ mensaje: 'Faltan columnas.', detalles: ['x1', 'x2'] });
    expect(leerError(new HttpErrorResponse({ status: 500, error: { error: 'Error interno.' } }))).toEqual({
      mensaje: 'Error interno.',
      detalles: [],
    });
  });

  it('sin conexión: cualquier respuesta HTTP sin el cuerpo de la API', () => {
    for (const e of [
      new HttpErrorResponse({ status: 0 }),
      new HttpErrorResponse({ status: 500, error: null }), // proxy de desarrollo de Angular con Flask parado
      new HttpErrorResponse({ status: 504, error: 'texto de un proxy' }),
    ]) {
      expect(leerError(e)).toEqual({ mensaje: TEXTOS.errores.sinConexion, detalles: [] });
    }
  });

  it('lo que no es una respuesta HTTP: mensaje genérico', () => {
    expect(leerError(new Error('x')).mensaje).toBe(TEXTOS.errores.inesperado);
  });
});
