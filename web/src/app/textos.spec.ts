import { CODIGO, NOTA, cadenas, problemas } from './pruebas/vocabulario';
import { TEXTOS, nombreModelo, tituloRuta } from './textos';

describe('textos', () => {
  it('ningún texto propio usa el vocabulario prohibido ni códigos de decisión', () => {
    const valores = [...cadenas(TEXTOS), nombreModelo('rl'), nombreModelo('desconocido'), tituloRuta('x')];
    expect(valores.length).toBeGreaterThan(30);
    expect(valores.flatMap(problemas)).toEqual([]);
  });

  it('el detector encuentra los prohibidos, salvo en la nota fija de causalidad', () => {
    expect(problemas('Riesgo alto debido a las conexiones (D41).')).toEqual([
      '«debido a» en: Riesgo alto debido a las conexiones (D41).',
      'código en: Riesgo alto debido a las conexiones (D41).',
    ]);
    expect(problemas(NOTA)).toEqual([]);
    expect(problemas(`${NOTA} La causa es otra.`)).toHaveLength(1);
    expect('P-18'.match(CODIGO)).toEqual(['P-18']);
  });
});
