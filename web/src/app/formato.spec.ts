import { contribucion, decimal, fecha, intervalo, miles, pValor, porcentaje, porcentaje1, puntos } from './formato';

describe('formato', () => {
  it('porcentaje entero sin sugerir certeza en los extremos', () => {
    expect(porcentaje(0.344)).toBe('34 %');
    expect(porcentaje(0.003)).toBe('< 1 %');
    expect(porcentaje(0.996)).toBe('> 99 %');
    expect(porcentaje(0)).toBe('0 %');
    expect(porcentaje(1)).toBe('100 %');
  });

  it('porcentaje con un decimal y coma', () => {
    expect(porcentaje1(0.213612)).toBe('21,4 %');
  });

  it('decimal con coma y signo menos tipográfico', () => {
    expect(decimal(0.1254)).toBe('0,125');
    expect(decimal(-0.1254)).toBe('−0,125');
    expect(decimal(-0.0001)).toBe('0,000');
    expect(contribucion(0.5, 2)).toBe('+0,50');
    expect(contribucion(-0.5, 2)).toBe('−0,50');
  });

  it('miles con espacio desde 10 000, como la API', () => {
    expect(miles(9999)).toBe('9999');
    expect(miles(19023)).toBe('19 023');
    expect(miles(1234567)).toBe('1 234 567');
  });

  it('intervalo con punto y coma y p-valor', () => {
    expect(intervalo([-0.0123, 0.0046])).toBe('[−0,012; 0,005]');
    expect(pValor(0.0004)).toBe('< 0,001');
    expect(pValor(0.0412)).toBe('0,041');
  });

  it('diferencias de proporciones en puntos porcentuales', () => {
    expect(puntos(0.123, [0.041, 0.205])).toBe('12,3 p. p. [4,1; 20,5]');
    expect(puntos(-0.05)).toBe('−5,0 p. p.');
  });

  it('fecha en hora local', () => {
    const iso = new Date(2026, 10, 3, 9, 5).toISOString();
    expect(fecha(iso)).toBe('03/11/2026 09:05');
  });
});
