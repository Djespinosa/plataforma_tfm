/**
 * Orden, filtro y paginación de la lista de un lote (docs/diseno-web.md §6, RF-05): funciones puras sobre las filas que
 * da la API, sin calcular nada del modelo.
 */
import { FilaLote } from '../../api/tipos';

export type Columna = 'probabilidad' | 'fila' | 'identificador';
export type Direccion = 'ascendente' | 'descendente';

export interface Filtro {
  soloMarcados: boolean;
  identificador: string;
  /** Probabilidad mínima en % (0-100). */
  minimoPct: number;
}

export const POR_PAGINA = 50;

export function ordenar(filas: FilaLote[], columna: Columna, direccion: Direccion): FilaLote[] {
  const signo = direccion === 'ascendente' ? 1 : -1;
  const valor = (f: FilaLote) => (columna === 'identificador' ? (f.identificador ?? '') : f[columna]);
  // Desempate por número de fila, para que el orden sea estable y reproducible.
  return [...filas].sort((a, b) => {
    const va = valor(a);
    const vb = valor(b);
    const comparacion =
      typeof va === 'string' && typeof vb === 'string'
        ? va.localeCompare(vb, 'es', { numeric: true })
        : (va as number) - (vb as number);
    return comparacion !== 0 ? signo * comparacion : a.fila - b.fila;
  });
}

export function filtrar(filas: FilaLote[], filtro: Filtro): FilaLote[] {
  const buscado = filtro.identificador.trim().toLowerCase();
  return filas.filter(
    (f) =>
      (!filtro.soloMarcados || f.alerta) &&
      (!buscado || (f.identificador ?? '').toLowerCase().includes(buscado)) &&
      // El mismo redondeo que la tabla (porcentaje entero): una fila que se lee «30 %» pasa el mínimo 30.
      Math.round(100 * f.probabilidad) >= filtro.minimoPct,
  );
}

/** Página 1..n (se ajusta al intervalo válido) con sus límites para «Mostrando X-Y de Z». */
export function paginar<T>(filas: T[], pagina: number, porPagina = POR_PAGINA) {
  const paginas = Math.max(1, Math.ceil(filas.length / porPagina));
  const actual = Math.min(Math.max(1, pagina), paginas);
  const desde = (actual - 1) * porPagina;
  return {
    filas: filas.slice(desde, desde + porPagina),
    pagina: actual,
    paginas,
    desde: filas.length ? desde + 1 : 0,
    hasta: Math.min(desde + porPagina, filas.length),
    total: filas.length,
  };
}
