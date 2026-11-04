/**
 * Formato de cifras para la interfaz (docs/diseno-web.md §8): coma decimal y espacio de miles, como api/textos.py, sin
 * Intl para coincidir con la API. Ninguna función calcula métricas: solo presentan los valores que da la API.
 */

const MENOS = '−'; // signo menos tipográfico

function conComa(valor: number, decimales: number): string {
  return valor.toFixed(decimales).replace('.', ',');
}

/** Porcentaje entero («34 %») para ejes y tablas de calibración; «0 %» y «100 %» solo si lo son exactamente (W-12). */
export function porcentaje(p: number): string {
  const entero = Math.round(100 * p);
  if (entero === 0 && p > 0) return '< 1 %';
  if (entero === 100 && p < 1) return '> 99 %';
  return `${entero} %`;
}

/** Probabilidad estimada de un caso: nunca «0 %» ni «100 %», tampoco si el calibrador da 0 o 1 exactos (guardarraíles). */
export function probabilidad(p: number): string {
  const entero = Math.round(100 * p);
  if (entero < 1) return '< 1 %';
  if (entero > 99) return '> 99 %';
  return `${entero} %`;
}

/** Porcentaje con 1 decimal (umbral, tasas): «21,4 %». */
export function porcentaje1(p: number): string {
  return `${conComa(100 * p, 1)} %`;
}

/** Diferencia entre dos proporciones en puntos porcentuales, con su intervalo: «12,3 p. p. [4,1; 20,5]». */
export function puntos(x: number, ic: [number, number] | null = null): string {
  const texto = `${decimal(100 * x, 1)} p. p.`;
  return ic ? `${texto} [${decimal(100 * ic[0], 1)}; ${decimal(100 * ic[1], 1)}]` : texto;
}

/** Decimal con coma y signo menos tipográfico: «−0,125». */
export function decimal(x: number, decimales = 3): string {
  const texto = conComa(Math.abs(x), decimales);
  return x < 0 && Number(texto.replace(',', '.')) !== 0 ? `${MENOS}${texto}` : texto;
}

/** Contribución con signo explícito: «+0,125» o «−0,125». */
export function contribucion(x: number, decimales = 3): string {
  return x > 0 ? `+${decimal(x, decimales)}` : decimal(x, decimales);
}

/** Separador de miles con espacio desde 10 000 (19 023); hasta 4 cifras, sin separador, como textos.miles de la API. */
export function miles(n: number): string {
  return n >= 10000 ? String(n).replace(/\B(?=(\d{3})+(?!\d))/g, ' ') : String(n);
}

/** Intervalo «[0,001; 0,009]» (punto y coma porque la coma es decimal). */
export function intervalo(valores: [number, number], decimales = 3): string {
  return `[${decimal(valores[0], decimales)}; ${decimal(valores[1], decimales)}]`;
}

/** p-valor: «< 0,001» por debajo de 0,001. */
export function pValor(p: number): string {
  return p < 0.001 ? '< 0,001' : conComa(p, 3);
}

/** Duración en segundos: «45 s», «12 min 5 s», «2 h 3 min». */
export function duracion(segundos: number): string {
  const s = Math.round(segundos);
  if (s < 60) return `${s} s`;
  if (s < 3600) return `${Math.floor(s / 60)} min ${s % 60} s`;
  return `${Math.floor(s / 3600)} h ${Math.floor((s % 3600) / 60)} min`;
}

/** Fecha ISO de la API (UTC con zona) en hora local: «dd/mm/aaaa hh:mm». */
export function fecha(iso: string): string {
  const d = new Date(iso);
  const dos = (n: number) => String(n).padStart(2, '0');
  return `${dos(d.getDate())}/${dos(d.getMonth() + 1)}/${d.getFullYear()} ${dos(d.getHours())}:${dos(d.getMinutes())}`;
}
