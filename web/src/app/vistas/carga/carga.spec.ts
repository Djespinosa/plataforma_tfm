import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';

import { Conjunto, ConjuntoResumen } from '../../api/tipos';
import { TEXTOS } from '../../textos';
import { Carga } from './carga';

const ANTERIOR: ConjuntoResumen = {
  id: 3, nombre_archivo: 'anterior.csv', momento: null, n_filas: 12000, n_columnas: 9,
  creado_en: '2026-11-01T10:00:00+00:00',
};
const NUEVO: Conjunto = {
  id: 4, nombre_archivo: 'nuevo.csv', momento: 'semana 4', n_filas: 1000, n_columnas: 2, sha256: 'abc',
  creado_en: '2026-11-03T10:00:00+00:00', aviso_privacidad: 'aviso de la API',
  avisos: ['La columna «codigo» parece un identificador.'],
  columnas: [
    { nombre: 'codigo', tipo: 'categorica', faltantes: 0, proporcion_faltantes: 0, valores_distintos: 1000,
      valores_frecuentes: [] },
    { nombre: 'edad', tipo: 'numerica', faltantes: 3, proporcion_faltantes: 0.003, valores_distintos: 40,
      valores_frecuentes: [] },
  ],
};

async function renderizar(lista: ConjuntoResumen[] = [ANTERIOR]) {
  TestBed.configureTestingModule({
    imports: [Carga],
    providers: [provideRouter([]), provideHttpClient(), provideHttpClientTesting()],
  });
  const fixture = TestBed.createComponent(Carga);
  const http = TestBed.inject(HttpTestingController);
  http.expectOne('/api/conjuntos').flush(lista);
  await fixture.whenStable();
  const html = fixture.nativeElement as HTMLElement;

  /** Elige un archivo, escribe el momento y envía el formulario; devuelve la petición POST. */
  async function enviar(archivo: File | null, momento = '') {
    const campo = html.querySelector<HTMLInputElement>('#archivo')!;
    Object.defineProperty(campo, 'files', { value: archivo ? [archivo] : [], configurable: true });
    campo.dispatchEvent(new Event('change'));
    const texto = html.querySelector<HTMLInputElement>('#momento')!;
    texto.value = momento;
    texto.dispatchEvent(new Event('input'));
    html.querySelector('form')!.dispatchEvent(new Event('submit'));
    await fixture.whenStable();
  }
  return { html, http, fixture, enviar };
}

function filas(tabla: HTMLTableElement) {
  return [...tabla.querySelectorAll('tbody tr')].map((f) =>
    [...f.querySelectorAll('th, td')].map((c) => c.textContent?.replace(/\s+/g, ' ').trim()));
}

function tabla(html: HTMLElement, titulo: string) {
  return [...html.querySelectorAll('table')].find((t) => t.caption?.textContent?.trim() === titulo)!;
}

describe('Carga', () => {
  it('muestra el aviso de privacidad antes del formulario y los conjuntos ya cargados con su enlace', async () => {
    const { html } = await renderizar();
    const aviso = html.querySelector('app-aviso')!;
    expect(aviso.textContent).toContain(TEXTOS.apiCopias.avisoPrivacidad);
    expect(aviso.compareDocumentPosition(html.querySelector('form')!) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(filas(tabla(html, TEXTOS.carga.tablaAnteriores))[0].slice(0, 4))
      .toEqual(['anterior.csv', TEXTOS.modelos.sinMomento, '12 000', '9']);
    expect(html.querySelector('a[href="/datos/3/configuracion"]')?.textContent?.trim()).toBe(TEXTOS.carga.configurar);
  });

  it('sin conjuntos, lo dice', async () => {
    const { html } = await renderizar([]);
    expect(html.textContent).toContain(TEXTOS.carga.ninguno);
  });

  it('sube archivo y momento; muestra el resumen, los avisos de la API y las columnas, y lo añade a la lista', async () => {
    const { html, http, enviar } = await renderizar();
    const archivo = new File(['﻿codigo;edad\n'], 'nuevo.csv', { type: 'text/csv' });
    await enviar(archivo, ' semana 4 ');
    const peticion = http.expectOne('/api/conjuntos');
    expect(peticion.request.method).toBe('POST');
    const cuerpo = peticion.request.body as FormData;
    expect(cuerpo.get('archivo')).toBe(archivo); // el archivo va tal cual: la API detecta el «;» y el BOM
    expect(cuerpo.get('momento')).toBe('semana 4');
    expect(html.querySelector('button[type="submit"]')?.hasAttribute('disabled')).toBe(true);
    peticion.flush(NUEVO, { status: 201, statusText: 'Created' });
    await new Promise((r) => setTimeout(r)); // afterNextRender
    const texto = html.textContent ?? '';
    expect(texto).toContain('La columna «codigo» parece un identificador.');
    expect(filas(tabla(html, TEXTOS.carga.tablaColumnas))).toEqual([
      ['codigo', TEXTOS.carga.tipos.categorica, '0 (0,0 %)', '1000'],
      ['edad', TEXTOS.carga.tipos.numerica, '3 (0,3 %)', '40'],
    ]);
    expect(document.activeElement?.id).toBe('archivo-cargado');
    expect(filas(tabla(html, TEXTOS.carga.tablaAnteriores)).map((f) => f[0])).toEqual(['nuevo.csv', 'anterior.csv']);
    expect(html.querySelectorAll('a[href="/datos/4/configuracion"]')).toHaveLength(2);
    expect(html.querySelector('button[type="submit"]')?.hasAttribute('disabled')).toBe(false);
  });

  it('un 415 o un 422 de la API se muestran tal cual, con sus detalles, y se puede reintentar', async () => {
    const { html, http, enviar } = await renderizar();
    const archivo = new File(['x'], 'malo.csv');
    await enviar(archivo);
    http.expectOne('/api/conjuntos').flush({ error: 'El archivo debe ser un CSV en UTF-8.' },
      { status: 415, statusText: 'Unsupported Media Type' });
    await new Promise((r) => setTimeout(r));
    expect(html.querySelector('[role="alert"]')?.textContent).toContain('El archivo debe ser un CSV en UTF-8.');

    await enviar(archivo);
    http.expectOne('/api/conjuntos').flush({ error: 'Hay columnas con el mismo nombre: a.', detalles: ['detalle 1'] },
      { status: 422, statusText: 'Unprocessable Entity' });
    await new Promise((r) => setTimeout(r));
    const alerta = html.querySelector('[role="alert"]')?.textContent ?? '';
    expect(alerta).toContain('Hay columnas con el mismo nombre: a.');
    expect(alerta).toContain('detalle 1');
    expect(html.querySelector('button[type="submit"]')?.hasAttribute('disabled')).toBe(false);
  });

  it('sin archivo no envía nada', async () => {
    const { html, http, enviar } = await renderizar();
    await enviar(null);
    http.expectNone('/api/conjuntos');
    expect(html.querySelector('[role="alert"]')?.textContent).toContain(TEXTOS.carga.sinArchivo);
  });
});
