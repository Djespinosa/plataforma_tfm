import { FilaLote } from '../../api/tipos';
import { filtrar, ordenar, paginar } from './lista';

const filas: FilaLote[] = [
  { fila: 1, identificador: 'A-10', probabilidad: 0.2, alerta: false },
  { fila: 2, identificador: 'a-2', probabilidad: 0.8, alerta: true },
  { fila: 3, identificador: null, probabilidad: 0.5, alerta: true },
  { fila: 4, identificador: 'B-1', probabilidad: 0.5, alerta: true },
];
const numeros = (f: FilaLote[]) => f.map((x) => x.fila);

describe('lista del lote', () => {
  it('ordena por probabilidad, fila e identificador, con desempate por fila', () => {
    expect(numeros(ordenar(filas, 'probabilidad', 'descendente'))).toEqual([2, 3, 4, 1]);
    expect(numeros(ordenar(filas, 'probabilidad', 'ascendente'))).toEqual([1, 3, 4, 2]);
    expect(numeros(ordenar(filas, 'fila', 'descendente'))).toEqual([4, 3, 2, 1]);
    // Orden natural y sin distinguir mayúsculas: a-2 antes que A-10; sin identificador, primero.
    expect(numeros(ordenar(filas, 'identificador', 'ascendente'))).toEqual([3, 2, 1, 4]);
    expect(numeros(filas)).toEqual([1, 2, 3, 4]); // no modifica la lista original
  });

  it('filtra por alerta, identificador (contiene, sin mayúsculas) y probabilidad mínima', () => {
    const sinFiltro = { soloMarcados: false, identificador: '', minimoPct: 0 };
    expect(numeros(filtrar(filas, sinFiltro))).toEqual([1, 2, 3, 4]);
    expect(numeros(filtrar(filas, { ...sinFiltro, soloMarcados: true }))).toEqual([2, 3, 4]);
    expect(numeros(filtrar(filas, { ...sinFiltro, identificador: ' a-' }))).toEqual([1, 2]);
    expect(numeros(filtrar(filas, { ...sinFiltro, minimoPct: 50 }))).toEqual([2, 3, 4]);
    // Con el redondeo de la tabla: 0,29 se lee «29 %» (100 × 0,29 = 28,999…) y 0,296 se lee «30 %».
    const bordes: FilaLote[] = [
      { fila: 1, identificador: null, probabilidad: 0.29, alerta: false },
      { fila: 2, identificador: null, probabilidad: 0.296, alerta: false },
    ];
    expect(numeros(filtrar(bordes, { ...sinFiltro, minimoPct: 29 }))).toEqual([1, 2]);
    expect(numeros(filtrar(bordes, { ...sinFiltro, minimoPct: 30 }))).toEqual([2]);
  });

  it('pagina de 50 en 50 y ajusta la página al intervalo válido', () => {
    const muchas = Array.from({ length: 120 }, (_, i) => i);
    expect(paginar(muchas, 1)).toMatchObject({ pagina: 1, paginas: 3, desde: 1, hasta: 50, total: 120 });
    expect(paginar(muchas, 3)).toMatchObject({ pagina: 3, desde: 101, hasta: 120 });
    expect(paginar(muchas, 9).pagina).toBe(3);
    expect(paginar([], 1)).toMatchObject({ pagina: 1, paginas: 1, desde: 0, hasta: 0, total: 0 });
  });
});
