import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { Type } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';

import { ValidacionExperimento } from '../api/tipos';
import { Carga } from '../vistas/carga/carga';
import { Configuracion } from '../vistas/configuracion/configuracion';
import { Evaluacion } from '../vistas/evaluacion/evaluacion';
import { ExplicacionGlobal } from '../vistas/explicacion-global/explicacion-global';
import { ExplicacionLocal } from '../vistas/explicacion-local/explicacion-local';
import { Historial } from '../vistas/historial/historial';
import { Inicio } from '../vistas/inicio/inicio';
import { Lote } from '../vistas/lote/lote';
import { Modelos } from '../vistas/modelos/modelos';
import { NoEncontrada } from '../vistas/no-encontrada/no-encontrada';
import { Prediccion } from '../vistas/prediccion/prediccion';
import { Seguimiento } from '../vistas/seguimiento/seguimiento';
import * as F from './fixtures';
import { problemas } from './vocabulario';

/**
 * Renderiza cada vista con respuestas sintéticas cuyos textos de la API son «texto de la API» y busca el vocabulario
 * prohibido en el texto visible (docs/diseno-web.md §9): cubre el texto literal que se cuele en una plantilla y las
 * frases que componen las vistas, además de las cadenas de TEXTOS que ya recorre textos.spec.ts. El contenido de los
 * <details> cerrados también está en textContent.
 */

const ESQUEMA: ValidacionExperimento = {
  filas_entrenamiento: 80, filas_prueba: 20, filas_sin_objetivo: 1, positivos_entrenamiento: 30,
  prevalencia_entrenamiento: 0.375, variables: { numericas: ['x1'], categoricas: [] },
  excluidas_automaticamente: [{ columna: 'g', motivo: F.API }],
  validacion: { tipo: 'agrupada_estratificada', k: 5, semilla: 42, columna_grupo: 'g', n_grupos: 6 },
  cohorte_prueba: { modo: 'valores', columna: 'g', valores: ['g1'], filas: 20, metodo: F.API },
  presupuesto: { modo: 'demostracion', familias: ['rl'], n_trials_por_familia: 5, n_bootstrap: 200 },
  avisos: [F.API],
};

const RESPUESTAS: Record<string, unknown> = {
  '/api/estado': F.ESTADO,
  '/api/modelos': [F.MODELO],
  '/api/modelos/2': F.MODELO_DETALLE,
  '/api/modelos/2/explicacion-global': F.EXPLICACION_GLOBAL,
  '/api/experimentos': F.HISTORIAL,
  '/api/experimentos/exp-1': F.EXPERIMENTO,
  '/api/experimentos/exp-1/evaluacion': F.EVALUACION,
  '/api/experimentos/validacion': ESQUEMA,
  '/api/predicciones/7': F.LOTE,
  '/api/predicciones/7/filas/1/explicacion': F.EXPLICACION_LOCAL,
  '/api/conjuntos': F.CONJUNTOS,
  '/api/conjuntos/3': F.CONJUNTO,
};

/** Responde todas las peticiones pendientes (y las que provoquen) con RESPUESTAS. */
async function responder(fixture: ComponentFixture<unknown>, respuestas = RESPUESTAS) {
  const http = TestBed.inject(HttpTestingController);
  for (let ronda = 0; ronda < 5; ronda++) {
    await new Promise((r) => setTimeout(r)); // el timer(0) del sondeo
    for (const peticion of http.match(() => true)) {
      const url = peticion.request.url;
      if (!(url in respuestas)) throw new Error(`sin respuesta sintética para ${url}`);
      peticion.flush(respuestas[url] as object);
    }
    fixture.detectChanges();
    await fixture.whenStable();
  }
}

async function renderizar<T>(componente: Type<T>, entradas: Record<string, string> = {},
  respuestas = RESPUESTAS) {
  TestBed.configureTestingModule({
    imports: [componente],
    providers: [provideRouter([]), provideHttpClient(), provideHttpClientTesting()],
  });
  const fixture = TestBed.createComponent(componente);
  for (const [nombre, valor] of Object.entries(entradas)) fixture.componentRef.setInput(nombre, valor);
  fixture.detectChanges();
  await responder(fixture as ComponentFixture<unknown>, respuestas);
  return fixture;
}

function comprobar(fixture: ComponentFixture<unknown>) {
  const html = fixture.nativeElement as HTMLElement;
  const texto = (html.textContent ?? '').replace(/\s+/g, ' ');
  expect(texto.length).toBeGreaterThan(50); // la vista se ha renderizado con datos
  expect(texto).not.toMatch(/\{\{|undefined|NaN|\[object Object\]/);
  expect(problemas(texto)).toEqual([]);
}

describe('vocabulario renderizado', () => {
  const casos: [string, Type<unknown>, Record<string, string>][] = [
    ['inicio', Inicio, {}],
    ['modelos', Modelos, {}],
    ['estimación', Prediccion, { modelo: '2' }],
    ['lote', Lote, { lote: '7' }],
    ['explicación global', ExplicacionGlobal, { modelo: '2' }],
    ['explicación local', ExplicacionLocal, { lote: '7', fila: '1' }],
    ['evaluación', Evaluacion, { id: 'exp-1' }],
    ['evaluación de otro momento (sin curva)', Evaluacion, { id: 'exp-1', modelo: '3' }],
    ['seguimiento completado', Seguimiento, { id: 'exp-1' }],
    ['historial', Historial, {}],
    ['carga', Carga, {}],
    ['configuración', Configuracion, { conjunto: '3' }],
  ];
  for (const [nombre, componente, entradas] of casos) {
    it(nombre, async () => comprobar(await renderizar(componente, entradas)));
  }

  it('no encontrada', async () => comprobar(await renderizar(NoEncontrada)));

  it('evaluación con la evaluación única ya hecha', async () => {
    comprobar(await renderizar(Evaluacion, { id: 'exp-1' },
      { ...RESPUESTAS, '/api/experimentos/exp-1': { ...F.EXPERIMENTO, evaluacion_prueba: F.EVALUACION_PRUEBA } }));
  });

  it('seguimiento fallido y sin respuesta', async () => {
    comprobar(await renderizar(Seguimiento, { id: 'exp-1' },
      { ...RESPUESTAS, '/api/experimentos/exp-1': F.EXPERIMENTO_FALLIDO }));
  });

  it('carga tras subir un archivo', async () => {
    const fixture = await renderizar(Carga);
    const html = fixture.nativeElement as HTMLElement;
    const campo = html.querySelector<HTMLInputElement>('#archivo')!;
    Object.defineProperty(campo, 'files', { value: [new File(['y,x1\n'], 'datos.csv')] });
    campo.dispatchEvent(new Event('change'));
    html.querySelector('form')!.dispatchEvent(new Event('submit'));
    await responder(fixture as ComponentFixture<unknown>, { ...RESPUESTAS, '/api/conjuntos': F.CONJUNTO });
    expect(html.querySelector('#archivo-cargado')).not.toBeNull();
    comprobar(fixture as ComponentFixture<unknown>);
  });

  it('configuración comprobada, con cohorte y demostración', async () => {
    const fixture = await renderizar(Configuracion, { conjunto: '3' });
    const html = fixture.nativeElement as HTMLElement;
    const elegir = async (selector: string, valor: string) => {
      const campo = html.querySelector<HTMLSelectElement>(selector)!;
      campo.value = valor;
      campo.dispatchEvent(new Event('change'));
      await fixture.whenStable();
    };
    await elegir('#objetivo', 'y');
    await elegir('#clase-positiva', 'p');
    html.querySelector<HTMLInputElement>('input[value="demostracion"]')!.click();
    html.querySelector<HTMLButtonElement>('button[type="submit"]')!.click();
    await responder(fixture as ComponentFixture<unknown>);
    expect(html.querySelector('#esquema')).not.toBeNull();
    comprobar(fixture as ComponentFixture<unknown>);
  });
});
