import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';

import { App } from './app';
import { routes } from './app.routes';
import { TEXTOS } from './textos';

describe('App', () => {
  beforeEach(() => {
    TestBed.configureTestingModule({
      imports: [App],
      providers: [provideRouter(routes), provideHttpClient(), provideHttpClientTesting()],
    });
  });

  it('muestra la cabecera, el enlace para saltar al contenido y los seis pasos', async () => {
    const fixture = TestBed.createComponent(App);
    await fixture.whenStable();
    const html = fixture.nativeElement as HTMLElement;
    expect(html.querySelector('a.saltar')?.textContent).toContain(TEXTOS.aplicacion.saltar);
    expect(html.querySelectorAll('.pasos li').length).toBe(6);
    expect(html.querySelector('main#contenido')).not.toBeNull();
  });
});
