import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';

import { ExperimentoHistorial } from '../../api/tipos';
import { TEXTOS } from '../../textos';
import { Historial } from './historial';

const WEB: ExperimentoHistorial = {
  id: 'web-2', origen: 'web', estado: 'interrumpido', creado_en: '2026-11-03T10:00:00+00:00', duracion_s: null,
  descripcion: 'nota', conjunto: { id: 3, nombre_archivo: 'datos.csv', momento: 'semana 4' }, objetivo: 'y',
  presupuesto: 'demostracion', reintento_de: 'web-1', modelos: [],
};
const IMPORTADO: ExperimentoHistorial = {
  id: 'exp-1', origen: 'importado', estado: 'completado', creado_en: '2026-10-29T10:00:00+00:00', duracion_s: 725,
  descripcion: null, conjunto: null, objetivo: null, presupuesto: 'completo', reintento_de: null,
  modelos: [{ id: 1, momento: 'semana 0', familia: 'rl' }, { id: 2, momento: 'semana 4', familia: 'rl' }],
};

async function renderizar(respuesta: ExperimentoHistorial[] | null) {
  TestBed.configureTestingModule({
    imports: [Historial],
    providers: [provideRouter([]), provideHttpClient(), provideHttpClientTesting()],
  });
  const fixture = TestBed.createComponent(Historial);
  const peticion = TestBed.inject(HttpTestingController).expectOne('/api/experimentos');
  if (respuesta) peticion.flush(respuesta);
  else peticion.flush({ error: 'texto de la API' }, { status: 503, statusText: 'Service Unavailable' });
  await fixture.whenStable();
  return fixture.nativeElement as HTMLElement;
}

describe('Historial', () => {
  it('lista web e importados con estado, datos, objetivo, presupuesto y enlaces para reabrirlos', async () => {
    const html = await renderizar([WEB, IMPORTADO]);
    const filas = [...html.querySelectorAll('tbody tr')].map((f) =>
      [...f.querySelectorAll('th, td')].map((c) => c.textContent?.replace(/\s+/g, ' ').trim()));
    expect(filas[0].slice(2, 7)).toEqual([TEXTOS.seguimiento.estados.interrumpido, 'datos.csv · semana 4', 'y',
      TEXTOS.configuracion.modos['demostracion'], '0']);
    expect(filas[0][0]).toContain(`${TEXTOS.historial.reintento} web-1`);
    expect(filas[1].slice(2, 7)).toEqual([`${TEXTOS.seguimiento.estados.completado} 12 min 5 s`,
      TEXTOS.historial.noAplica, TEXTOS.historial.noAplica, TEXTOS.configuracion.modos['completo'], '2']);
    expect(html.querySelector('a[href="/experimentos/web-2"]')).not.toBeNull();
    expect(html.querySelector('a[href="/experimentos/web-2/evaluacion"]')).toBeNull(); // solo si está completado
    expect(html.querySelector('a[href="/experimentos/exp-1"]')).not.toBeNull();
    expect(html.querySelector('a[href="/experimentos/exp-1/evaluacion"]')).not.toBeNull();
  });

  it('sin experimentos lo dice; un error de la API se muestra tal cual', async () => {
    expect((await renderizar([])).textContent).toContain(TEXTOS.historial.ninguno);
    TestBed.resetTestingModule();
    expect((await renderizar(null)).querySelector('[role="alert"]')?.textContent).toContain('texto de la API');
  });
});
