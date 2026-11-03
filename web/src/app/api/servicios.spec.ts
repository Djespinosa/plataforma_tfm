import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';

import { EstadoService } from './estado.service';
import { ExperimentosService } from './experimentos.service';
import { ModelosService } from './modelos.service';
import { PrediccionesService } from './predicciones.service';

describe('servicios de la API', () => {
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({ providers: [provideHttpClient(), provideHttpClientTesting()] });
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  it('GET de estado, modelos, experimento y lote con sus rutas', () => {
    TestBed.inject(EstadoService).estado().subscribe();
    TestBed.inject(ModelosService).listar().subscribe();
    TestBed.inject(ModelosService).detalle(3).subscribe();
    TestBed.inject(ExperimentosService).detalle('exp 1/2').subscribe();
    TestBed.inject(PrediccionesService).lote(7).subscribe();
    for (const url of ['/api/estado', '/api/modelos', '/api/modelos/3', '/api/experimentos/exp%201%2F2',
      '/api/predicciones/7']) {
      expect(http.expectOne(url).request.method).toBe('GET');
    }
  });

  it('POST de predicciones con FormData: archivo y columna_id solo si se indica', () => {
    const archivo = new File(['a,b\n1,2\n'], 'lote.csv', { type: 'text/csv' });
    const servicio = TestBed.inject(PrediccionesService);
    servicio.predecir(4, archivo, ' matricula ').subscribe();
    servicio.predecir(4, archivo, '  ').subscribe();
    const [con, sin] = http.match('/api/modelos/4/predicciones');
    for (const peticion of [con, sin]) {
      expect(peticion.request.method).toBe('POST');
      expect((peticion.request.body as FormData).get('archivo')).toBe(archivo);
    }
    expect((con.request.body as FormData).get('columna_id')).toBe('matricula');
    expect((sin.request.body as FormData).has('columna_id')).toBe(false);
  });
});
