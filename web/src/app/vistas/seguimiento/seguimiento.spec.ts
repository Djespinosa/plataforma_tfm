import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { Router, provideRouter } from '@angular/router';

import { ExperimentoDetalle } from '../../api/tipos';
import { TEXTOS } from '../../textos';
import { SONDEO_MS, Seguimiento } from './seguimiento';

const URL = '/api/experimentos/web-1';

function experimento(cambios: Partial<ExperimentoDetalle> = {}): ExperimentoDetalle {
  return {
    id: 'web-1', origen: 'web', estado: 'en_curso', descripcion: null,
    configuracion: { presupuesto: { modo: 'completo' } }, modelos: [], etapa: 'Búsqueda: LightGBM',
    progreso: { completadas: 2, total: 5 }, latido_en: '2026-11-03T10:00:00+00:00', sin_respuesta: false,
    aviso_sin_respuesta: null, error: null, duracion_s: null, reintento_de: null, reproducibilidad: null,
    ...cambios,
  };
}

let fixture: ComponentFixture<Seguimiento>;
let http: HttpTestingController;

async function renderizar(trabajadorActivo: boolean | null = true) {
  vi.useFakeTimers();
  TestBed.configureTestingModule({
    imports: [Seguimiento],
    providers: [provideRouter([]), provideHttpClient(), provideHttpClientTesting()],
  });
  fixture = TestBed.createComponent(Seguimiento);
  fixture.componentRef.setInput('id', 'web-1');
  fixture.detectChanges();
  http = TestBed.inject(HttpTestingController);
  http.expectOne('/api/estado').flush({ motor_bd: 'postgresql', trabajador_activo: trabajadorActivo, commit: null });
  await vi.advanceTimersByTimeAsync(0);
  return fixture.nativeElement as HTMLElement;
}

/** Responde la lectura pendiente y pinta. */
function responder(cuerpo: ExperimentoDetalle | { error: string }, estado = 200) {
  http.expectOne(URL).flush(cuerpo, { status: estado, statusText: estado === 200 ? 'OK' : 'Error' });
  fixture.detectChanges();
}

async function siguiente() {
  await vi.advanceTimersByTimeAsync(SONDEO_MS);
}

afterEach(() => {
  http.verify();
  vi.useRealTimers();
});

describe('Seguimiento', () => {
  it('sondea cada 3 s mientras está en cola o en curso y para al completar, con los enlaces', async () => {
    const html = await renderizar();
    responder(experimento({ estado: 'en_cola', etapa: null, progreso: null }));
    expect(html.querySelector('[role="status"]')?.textContent).toContain(TEXTOS.seguimiento.estados.en_cola);
    await siguiente();
    responder(experimento());
    const estado = html.querySelector('[role="status"]')?.textContent ?? '';
    expect(estado).toContain(TEXTOS.seguimiento.estados.en_curso);
    expect(estado).toContain('Búsqueda: LightGBM');
    const barra = html.querySelector<HTMLProgressElement>('progress')!;
    expect([barra.max, barra.value]).toEqual([5, 2]);
    expect(html.textContent).toContain('2 de 5 etapas');
    await siguiente();
    responder(experimento({
      estado: 'completado', etapa: null, progreso: { completadas: 5, total: 5 }, duracion_s: 725,
      modelos: [{ id: 9, momento: 'semana 4', familia: 'rl' }],
    }));
    expect(html.textContent).toContain('12 min 5 s');
    expect(html.querySelector('a[href="/experimentos/web-1/evaluacion"]')).not.toBeNull();
    expect(html.querySelector('a[href="/modelos/9/prediccion"]')).not.toBeNull();
    expect(html.querySelector('a[href="/modelos/9/explicacion"]')).not.toBeNull();
    await siguiente();
    await siguiente();
    http.expectNone(URL); // el sondeo ha parado
  });

  it('en cola con el proceso detenido avisa; en demostración, la etiqueta y los avisos', async () => {
    const html = await renderizar(false);
    responder(experimento({
      estado: 'en_cola', configuracion: { presupuesto: { modo: 'demostracion' }, avisos: ['aviso de la API'] },
    }));
    const texto = html.textContent ?? '';
    expect(texto).toContain(TEXTOS.seguimiento.trabajadorInactivo);
    expect(texto).toContain(TEXTOS.demostracion);
    expect(texto).toContain('aviso de la API');
  });

  it('muestra el aviso de la API cuando el proceso no responde', async () => {
    const html = await renderizar();
    responder(experimento({ sin_respuesta: true, aviso_sin_respuesta: 'El proceso no responde (API).' }));
    expect(html.textContent).toContain('El proceso no responde (API).');
  });

  it('un error de red no corta el sondeo; un 404 sí', async () => {
    const html = await renderizar();
    responder(experimento());
    await siguiente();
    http.expectOne(URL).error(new ProgressEvent('error'), { status: 0 });
    fixture.detectChanges();
    expect(html.querySelector('[role="alert"]')?.textContent).toContain(TEXTOS.errores.sinConexion);
    expect(html.textContent).toContain('Búsqueda: LightGBM'); // se conserva lo último recibido
    await siguiente();
    responder(experimento());
    expect(html.querySelector('[role="alert"]')).toBeNull();
    await siguiente();
    responder({ error: 'No existe el experimento web-1.' }, 404);
    expect(html.querySelector('[role="alert"]')?.textContent).toContain('No existe el experimento web-1.');
    await siguiente();
    http.expectNone(URL);
  });

  it('fallido: el error tal cual y «Reintentar» lleva al experimento nuevo; un 409 se muestra', async () => {
    const html = await renderizar();
    responder(experimento({ estado: 'fallido', error: 'Error de la API al entrenar.' }));
    expect(html.querySelector('[role="alert"]')?.textContent).toContain('Error de la API al entrenar.');
    await siguiente();
    http.expectNone(URL); // el sondeo para también en fallido
    const boton = [...html.querySelectorAll('button')].find((b) => b.textContent?.includes(TEXTOS.seguimiento.reintentar))!;

    boton.click();
    fixture.detectChanges();
    expect(boton.disabled).toBe(true);
    http.expectOne(`${URL}/reintentar`).flush({ error: 'Este experimento ya se ha reintentado (web-2).' },
      { status: 409, statusText: 'Conflict' });
    fixture.detectChanges();
    expect(html.textContent).toContain('Este experimento ya se ha reintentado (web-2).');
    expect(boton.disabled).toBe(false);

    const navegar = vi.spyOn(TestBed.inject(Router), 'navigate').mockResolvedValue(true);
    boton.click();
    const peticion = http.expectOne(`${URL}/reintentar`);
    expect(peticion.request.method).toBe('POST');
    peticion.flush(experimento({ id: 'web-3', estado: 'en_cola', reintento_de: 'web-1' }));
    expect(navegar).toHaveBeenCalledWith(['/experimentos', 'web-3']);
  });

  it('al cambiar el id (tras reintentar) vuelve a sondear el nuevo', async () => {
    await renderizar();
    responder(experimento({ estado: 'fallido' }));
    fixture.componentRef.setInput('id', 'web-3');
    fixture.detectChanges();
    await vi.advanceTimersByTimeAsync(0);
    http.expectOne('/api/experimentos/web-3').flush(experimento({ id: 'web-3', estado: 'en_cola' }));
    await siguiente();
    expect(http.match('/api/experimentos/web-3')).toHaveLength(1);
  });

  it('una lectura que tarda más de 3 s no se cancela ni se duplica', async () => {
    const html = await renderizar();
    const lenta = http.expectOne(URL);
    await siguiente();
    await siguiente();
    expect(lenta.cancelled).toBe(false);
    http.expectNone(URL);
    lenta.flush(experimento());
    fixture.detectChanges();
    expect(html.textContent).toContain('Búsqueda: LightGBM');
    await siguiente();
    responder(experimento({ estado: 'completado' }));
  });

  it('la reproducibilidad va en el detalle técnico', async () => {
    const html = await renderizar();
    responder(experimento({
      estado: 'completado', reproducibilidad: { commit: 'abc1234', arbol_limpio: true, sha256_datos: 'f00',
        semillas: { modelos: 42 }, versiones: { python: '3.13.1' } },
    }));
    const detalle = html.querySelector('details')?.textContent?.replace(/\s+/g, ' ') ?? '';
    for (const t of ['abc1234', TEXTOS.seguimiento.si, 'f00', 'modelos = 42', 'python 3.13.1']) {
      expect(detalle).toContain(t);
    }
  });
});
