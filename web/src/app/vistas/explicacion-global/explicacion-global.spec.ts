import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';

import { ExplicacionGlobal as Respuesta, ModeloDetalle } from '../../api/tipos';
import { ExplicacionGlobal } from './explicacion-global';

const MODELO: ModeloDetalle = {
  id: 2, experimento_id: 'exp-1', origen: 'importado', momento: null, familia: 'rl', umbral: 0.2,
  explicador: 'lineal', creado_en: '2026-11-03T10:00:00+00:00', columnas: { numericas: [], categoricas: [] },
};
const AVISOS = { escala: 'texto de la API: escala', causalidad: 'texto de la API: causalidad', decision: 'd' };

async function renderizar(respuesta: Respuesta): Promise<HTMLElement> {
  TestBed.configureTestingModule({
    imports: [ExplicacionGlobal],
    providers: [provideRouter([]), provideHttpClient(), provideHttpClientTesting()],
  });
  const fixture = TestBed.createComponent(ExplicacionGlobal);
  fixture.componentRef.setInput('modelo', '2');
  fixture.detectChanges();
  const http = TestBed.inject(HttpTestingController);
  http.expectOne('/api/modelos/2/explicacion-global').flush(respuesta);
  http.expectOne('/api/modelos/2').flush(MODELO);
  await fixture.whenStable();
  return fixture.nativeElement as HTMLElement;
}

describe('ExplicacionGlobal', () => {
  it('15 barras en el resumen, todas las variables en el detalle y las sin contribución aparte', async () => {
    const variables = Array.from({ length: 20 }, (_, i) => ({ variable: `v${i}`, importancia_media_abs: 1 - i / 20 }));
    const html = await renderizar({
      modelo_id: 2, explicador: 'lineal', escala: 'log-odds', fuente: 'texto de la API: fuente', variables,
      sin_contribucion: [{ variable: 'z', motivo: 'texto de la API: sin contribución' }], avisos: AVISOS,
      aviso_decision: 'texto de la API: decisión',
    });
    expect(html.querySelectorAll('figure tbody tr').length).toBe(15);
    expect(html.querySelectorAll('svg[role="img"] g').length).toBe(15);
    expect(html.querySelectorAll('details:not(figure details) tbody tr').length).toBe(20);
    const texto = html.textContent ?? '';
    for (const t of ['texto de la API: fuente', 'z: texto de la API: sin contribución', AVISOS.escala, AVISOS.causalidad,
      'texto de la API: decisión']) {
      expect(texto).toContain(t);
    }
  });

  it('sin filas de referencia: muestra el motivo de la API y ningún gráfico', async () => {
    const html = await renderizar({
      modelo_id: 2, explicador: 'lineal', escala: 'log-odds', fuente: null, variables: null, sin_contribucion: [],
      motivo: 'texto de la API: sin referencia', avisos: AVISOS, aviso_decision: 'd',
    });
    expect(html.textContent).toContain('texto de la API: sin referencia');
    expect(html.querySelector('svg')).toBeNull();
  });
});
