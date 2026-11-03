import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { Router, provideRouter } from '@angular/router';

import { Columna, Conjunto, CuerpoExperimento, ValidacionExperimento } from '../../api/tipos';
import { TEXTOS } from '../../textos';
import { Configuracion } from './configuracion';

function columna(nombre: string, tipo: Columna['tipo'], valores: string[] = [], distintos = valores.length): Columna {
  return { nombre, tipo, faltantes: 0, proporcion_faltantes: 0, valores_distintos: distintos,
    valores_frecuentes: valores.map((valor, i) => ({ valor, n: 100 - i })) };
}

const CONJUNTO: Conjunto = {
  id: 3, nombre_archivo: 'datos.csv', momento: 'semana 4', n_filas: 12000, n_columnas: 5, sha256: 'abc',
  creado_en: '2026-11-03T10:00:00+00:00', aviso_privacidad: 'aviso', avisos: [],
  columnas: [
    columna('resultado', 'categorica', ['Pass', 'Withdrawn']),
    columna('cohorte', 'categorica', ['2013B', '2013J', '2014B']),
    columna('sexo', 'categorica', ['F', 'M']),
    columna('clics', 'numerica', [], 900),
    columna('codigo', 'categorica', [], 12000),
  ],
};

const ESQUEMA: ValidacionExperimento = {
  filas_entrenamiento: 9000, filas_prueba: 3000, filas_sin_objetivo: 0, positivos_entrenamiento: 2700,
  prevalencia_entrenamiento: 0.3, variables: { numericas: ['clics'], categoricas: [] },
  excluidas_automaticamente: [{ columna: 'cohorte', motivo: 'motivo de la API' }],
  validacion: { tipo: 'agrupada_estratificada', k: 5, semilla: 42, columna_grupo: 'cohorte', n_grupos: 3 },
  cohorte_prueba: { modo: 'valores', columna: 'cohorte', valores: ['2014B'], filas: 3000, metodo: 'método de la API' },
  presupuesto: { modo: 'demostracion', familias: ['rl', 'lgbm'], n_trials_por_familia: 5, n_bootstrap: 200 },
  avisos: ['aviso de demostración de la API'],
};

async function renderizar() {
  TestBed.configureTestingModule({
    imports: [Configuracion],
    providers: [provideRouter([]), provideHttpClient(), provideHttpClientTesting()],
  });
  const fixture = TestBed.createComponent(Configuracion);
  fixture.componentRef.setInput('conjunto', '3');
  fixture.detectChanges();
  const http = TestBed.inject(HttpTestingController);
  http.expectOne('/api/conjuntos/3').flush(CONJUNTO);
  await fixture.whenStable();
  const html = fixture.nativeElement as HTMLElement;
  const estable = () => fixture.whenStable();

  async function elegir(selector: string, valor: string) {
    const campo = html.querySelector<HTMLSelectElement>(selector)!;
    campo.value = valor;
    campo.dispatchEvent(new Event('change'));
    await estable();
  }
  async function pulsar(elemento: Element | null | undefined) {
    (elemento as HTMLElement).click();
    await estable();
  }
  const fila = (nombre: string) =>
    [...html.querySelectorAll('tbody tr')].find((f) => f.querySelector('th')?.textContent?.trim() === nombre)!;
  const boton = (texto: string) =>
    [...html.querySelectorAll('button')].find((b) => b.textContent?.trim() === texto) as HTMLButtonElement;
  const radio = (valor: string) => html.querySelector(`input[type="radio"][value="${valor}"]`);
  const casilla = (texto: string) =>
    [...html.querySelectorAll('label')].find((l) => l.textContent?.includes(texto))!.querySelector('input');
  return { html, http, estable, elegir, pulsar, fila, boton, radio, casilla };
}

describe('Configuracion', () => {
  it('compone el cuerpo del formulario, muestra el esquema efectivo y entrena con el cuerpo validado', async () => {
    const { html, http, estable, elegir, pulsar, fila, boton, radio, casilla } = await renderizar();
    const entrenar = boton(TEXTOS.configuracion.entrenar);
    expect(entrenar.disabled).toBe(true);

    await elegir('#objetivo', 'resultado');
    expect([...html.querySelectorAll('#clase-positiva option')].map((o) => o.textContent?.trim()))
      .toEqual([TEXTOS.configuracion.elegirValor, 'Pass (100)', 'Withdrawn (99)']);
    expect(fila('resultado')).toBeUndefined(); // la objetivo no aparece entre las variables
    await elegir('#clase-positiva', 'Withdrawn');
    await elegir('#columna-grupo', 'cohorte');
    await pulsar(radio('valores'));
    await elegir('#cohorte-columna', 'cohorte');
    await pulsar(casilla('2014B'));
    await pulsar(fila('codigo').querySelectorAll('input')[0]);
    await pulsar(fila('sexo').querySelectorAll('input')[1]);
    expect(html.textContent).not.toContain(TEXTOS.apiCopias.avisoDemostracion);
    await pulsar(radio('demostracion'));
    expect(html.textContent).toContain(TEXTOS.apiCopias.avisoDemostracion); // visible al elegirla
    const descripcion = html.querySelector<HTMLTextAreaElement>('#descripcion')!;
    descripcion.value = '  prueba  ';
    descripcion.dispatchEvent(new Event('input'));
    await estable();

    await pulsar(boton(TEXTOS.configuracion.comprobar));
    const esperado: CuerpoExperimento = {
      conjunto_id: 3, objetivo: 'resultado', clase_positiva: 'Withdrawn', excluidas: ['codigo'], sensibles: ['sexo'],
      columna_grupo: 'cohorte', cohorte_prueba: { modo: 'valores', columna: 'cohorte', valores: ['2014B'] },
      presupuesto: 'demostracion', descripcion: 'prueba',
    };
    const validacion = http.expectOne('/api/experimentos/validacion');
    expect(validacion.request.body).toEqual(esperado);
    validacion.flush(ESQUEMA);
    await estable();
    await new Promise((r) => setTimeout(r)); // afterNextRender
    expect(document.activeElement?.id).toBe('esquema');

    const texto = (html.textContent ?? '').replace(/\s+/g, ' ');
    for (const t of ['9000', '2700 (30,0 %)', 'cohorte: motivo de la API', 'aviso de demostración de la API',
      'validación cruzada agrupada y estratificada de 5 pliegues · cohorte (3 grupos)',
      'método de la API · cohorte: 2014B · 3000 filas', '5 ensayos por familia', '200 réplicas bootstrap']) {
      expect(texto).toContain(t);
    }
    expect(entrenar.disabled).toBe(false);

    const navegar = vi.spyOn(TestBed.inject(Router), 'navigate').mockResolvedValue(true);
    await pulsar(entrenar);
    const crear = http.expectOne('/api/experimentos');
    expect(crear.request.method).toBe('POST');
    expect(crear.request.body).toEqual(esperado);
    crear.flush({ id: 'web-2026-11-03-01', estado: 'en_cola' }, { status: 202, statusText: 'Accepted' });
    await estable();
    expect(navegar).toHaveBeenCalledWith(['/experimentos', 'web-2026-11-03-01']);
  });

  it('si la configuración cambia tras comprobarla, «Entrenar» se desactiva y lo dice', async () => {
    const { html, http, estable, elegir, pulsar, boton } = await renderizar();
    await elegir('#objetivo', 'resultado');
    await elegir('#clase-positiva', 'Pass');
    await pulsar(boton(TEXTOS.configuracion.comprobar));
    http.expectOne('/api/experimentos/validacion').flush(ESQUEMA);
    await estable();
    expect(boton(TEXTOS.configuracion.entrenar).disabled).toBe(false);
    await elegir('#clase-positiva', 'Withdrawn');
    expect(boton(TEXTOS.configuracion.entrenar).disabled).toBe(true);
    expect(html.textContent).toContain(TEXTOS.configuracion.cambiada);
    expect(html.textContent).not.toContain(TEXTOS.configuracion.esquema);
  });

  it('al cambiar el objetivo se vacía la clase y se quita de grupo, excluidas y sensibles', async () => {
    const { html, http, elegir, pulsar, fila, boton } = await renderizar();
    await elegir('#columna-grupo', 'sexo');
    await pulsar(fila('sexo').querySelectorAll('input')[0]);
    await elegir('#objetivo', 'resultado');
    await elegir('#clase-positiva', 'Pass');
    await elegir('#objetivo', 'sexo');
    expect(html.querySelector<HTMLSelectElement>('#clase-positiva')!.value).toBe('');
    await elegir('#clase-positiva', 'F');
    await pulsar(boton(TEXTOS.configuracion.comprobar));
    const cuerpo = http.expectOne('/api/experimentos/validacion').request.body as CuerpoExperimento;
    expect([cuerpo.objetivo, cuerpo.clase_positiva, cuerpo.columna_grupo, cuerpo.excluidas])
      .toEqual(['sexo', 'F', null, []]);
  });

  it('con más de 20 valores distintos, la clase positiva se escribe', async () => {
    const { html, elegir } = await renderizar();
    await elegir('#objetivo', 'codigo');
    expect(html.querySelector('input#clase-positiva[type="text"]')).not.toBeNull();
  });

  it('cada 422 de la API se muestra tal cual, con sus detalles, y no deja entrenar', async () => {
    const { html, http, estable, elegir, pulsar, boton } = await renderizar();
    await elegir('#objetivo', 'resultado');
    await elegir('#clase-positiva', 'Pass');
    await pulsar(boton(TEXTOS.configuracion.comprobar));
    http.expectOne('/api/experimentos/validacion').flush(
      { error: 'La columna de grupo «x» tiene 2 valores distintos.', detalles: ['detalle'] },
      { status: 422, statusText: 'Unprocessable Entity' });
    await estable();
    const alerta = html.querySelector('[role="alert"]')?.textContent ?? '';
    expect(alerta).toContain('La columna de grupo «x» tiene 2 valores distintos.');
    expect(alerta).toContain('detalle');
    expect(boton(TEXTOS.configuracion.entrenar).disabled).toBe(true);
    expect(boton(TEXTOS.configuracion.comprobar).disabled).toBe(false);
  });

  it('sin objetivo o sin valores de la cohorte no llama a la API', async () => {
    const { html, http, elegir, pulsar, boton, radio } = await renderizar();
    await pulsar(boton(TEXTOS.configuracion.comprobar));
    expect(html.querySelector('[role="alert"]')?.textContent).toContain(TEXTOS.configuracion.faltaObjetivo);
    await elegir('#objetivo', 'resultado');
    await elegir('#clase-positiva', 'Pass');
    await pulsar(radio('valores'));
    await pulsar(boton(TEXTOS.configuracion.comprobar));
    expect(html.querySelector('[role="alert"]')?.textContent).toContain(TEXTOS.configuracion.faltanValores);
    http.expectNone('/api/experimentos/validacion');
  });
});
