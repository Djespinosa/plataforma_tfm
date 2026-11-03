import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';

import { LOTE } from '../../pruebas/fixtures';
import { TEXTOS } from '../../textos';
import { Lote } from './lote';

describe('Lote', () => {
  it('ofrece la descarga del CSV del lote completo (RF-09) como enlace directo a la API', async () => {
    TestBed.configureTestingModule({
      imports: [Lote],
      providers: [provideRouter([]), provideHttpClient(), provideHttpClientTesting()],
    });
    const fixture = TestBed.createComponent(Lote);
    fixture.componentRef.setInput('lote', '7');
    fixture.detectChanges();
    TestBed.inject(HttpTestingController).expectOne('/api/predicciones/7').flush(LOTE);
    await fixture.whenStable();
    const enlace = (fixture.nativeElement as HTMLElement).querySelector('a[href="/api/predicciones/7/exportar"]');
    expect(enlace?.hasAttribute('download')).toBe(true);
    expect(enlace?.textContent?.trim()).toBe(TEXTOS.lote.descargar);
  });
});
