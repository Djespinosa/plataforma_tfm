/**
 * Vocabulario prohibido de la skill guardarrailes-interfaz: la misma lista y la misma excepción que
 * api/tests/test_textos.py (la nota fija de causalidad, que niega la causalidad, puede empezar un texto).
 */
export const PROHIBIDOS = [
  'va a abandonar',
  'abandonará',
  'seguro',
  'causa',
  'motivo',
  'porque',
  'por qué',
  'debido a',
  'provoca',
  'alto riesgo',
  'en riesgo',
  'predicción de fracaso',
];
export const CODIGO = /\bD-?\d+|P-\d+/g;
export const NOTA =
  'Estos factores describen cómo llegó el modelo a su estimación. No son causas comprobadas ni sustituyen el ' +
  'conocimiento del equipo docente sobre el estudiante.';

/** Términos prohibidos y códigos de decisión encontrados en un texto. */
export function problemas(texto: string): string[] {
  let minusculas = texto.toLowerCase();
  if (texto.startsWith(NOTA)) minusculas = minusculas.slice(NOTA.length);
  return [
    ...PROHIBIDOS.filter((p) => minusculas.includes(p)).map((p) => `«${p}» en: ${texto}`),
    ...(texto.match(CODIGO) ?? []).map(() => `código en: ${texto}`),
  ];
}

/** Todas las cadenas de un valor (objetos y listas anidados). */
export function cadenas(valor: unknown): string[] {
  if (typeof valor === 'string') return [valor];
  if (Array.isArray(valor)) return valor.flatMap(cadenas);
  if (valor !== null && typeof valor === 'object') return Object.values(valor).flatMap(cadenas);
  return [];
}
