import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';

import { ExplicacionLocal as Respuesta } from '../../api/tipos';
import { TEXTOS } from '../../textos';
import { ExplicacionLocal } from './explicacion-local';

const RESPUESTA: Respuesta = {
  fila: 4,
  identificador: 'A-3',
  probabilidad: 0.343,
  alerta: true,
  escala: 'texto de la API: escala',
  valor_base: -1.2,
  log_odds: -0.4,
  explicador: 'lineal',
  aumentan: [
    { variable: 'x1', valor: '12', contribucion: 0.8, extrema: false },
    { variable: 'x2', valor: 'sin dato', contribucion: 6.1, extrema: true },
  ],
  reducen: [{ variable: 'c', valor: 'b', contribucion: -0.25, extrema: false }],
  resto: { n_variables: 3, suma: -0.05 },
  todas: [],
  sin_contribucion: [{ variable: 'z', motivo: 'texto de la API: sin contribución' }],
  hay_extremas: true,
  avisos: {
    escala: 'texto de la API: aviso de escala',
    causalidad: 'texto de la API: nota de causalidad',
    decision: 'texto de la API: decisión',
    extrema: 'texto de la API: aviso de extrema',
  },
  aviso_rendimiento: 'texto de la API: aviso de rendimiento',
  aviso_decision: 'texto de la API: aviso de decisión',
};

describe('ExplicacionLocal', () => {
  it('muestra la probabilidad, los factores por signo, las extremas, el resto y todos los avisos', async () => {
    TestBed.configureTestingModule({
      imports: [ExplicacionLocal],
      providers: [provideRouter([]), provideHttpClient(), provideHttpClientTesting()],
    });
    const fixture = TestBed.createComponent(ExplicacionLocal);
    fixture.componentRef.setInput('lote', '7');
    fixture.componentRef.setInput('fila', '4');
    fixture.detectChanges();
    TestBed.inject(HttpTestingController).expectOne('/api/predicciones/7/filas/4/explicacion').flush(RESPUESTA);
    await fixture.whenStable();

    const html = fixture.nativeElement as HTMLElement;
    const texto = html.textContent ?? '';
    expect(texto).toContain('Probabilidad estimada por el modelo: 34 %');
    expect(texto).toContain(TEXTOS.lote.marcado);
    const listas = [...html.querySelectorAll('.factores ul')].map((ul) => ul.textContent?.replace(/\s+/g, ' '));
    expect(listas[0]).toContain('x1: 12 (+0,800)');
    expect(listas[0]).toContain(`x2: sin dato (+6,100) ${TEXTOS.explicacionLocal.extrema}`);
    expect(listas[1]).toContain('c: b (−0,250)');
    expect(texto).toContain('Otras 3 variables suman −0,050 en la escala del modelo.');
    for (const aviso of [RESPUESTA.aviso_rendimiento, RESPUESTA.avisos.escala, RESPUESTA.avisos.causalidad,
      RESPUESTA.avisos.extrema!, RESPUESTA.aviso_decision, RESPUESTA.sin_contribucion[0].motivo]) {
      expect(texto).toContain(aviso);
    }
    // Gráfico con signo: una barra por factor y su tabla equivalente.
    expect(html.querySelectorAll('svg[role="img"] rect').length).toBe(4); // 3 barras + fondo del patrón
    expect(html.querySelectorAll('figure tbody tr').length).toBe(3);
  });
});
