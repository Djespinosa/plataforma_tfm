import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { Router, provideRouter } from '@angular/router';

import { Evaluacion as Respuesta, EvaluacionModelo, ExperimentoDetalle } from '../../api/tipos';
import { TEXTOS } from '../../textos';
import { Evaluacion } from './evaluacion';

function modelo(id: number, momento: string, conCurva: boolean): EvaluacionModelo {
  const fila = (m: string, papel: 'desplegado' | 'candidato' | 'referencia') => ({
    modelo: m, papel, roc_auc_oof: 0.7, roc_auc_media: 0.69, roc_auc_desv: 0.02, pr_auc_oof: 0.3, brier_oof: 0.14,
    calibracion: papel === 'referencia' ? null : 'platt',
  });
  return {
    modelo_id: id, momento, n: 1000, positivos: 200,
    candidatos: [fila('rl', 'desplegado'), fila('lgbm', 'candidato')],
    referencias: [fila('mayoritaria', 'referencia')],
    contraste: {
      modelo_a: 'lgbm', modelo_b: 'rl_optimizada', diferencia: 0.003, ic95_bootstrap: [-0.002, 0.007],
      delong_p: 0.26, delong_p_holm: 0.52, lectura: 'equivalencia_practica', lectura_texto: `lectura ${momento}`,
      holm_sobre: 2,
    },
    parsimonia: {
      mejor: 'lgbm', margen: 0.02,
      candidatos: [{ modelo: 'rl', roc_auc_oof: 0.7, perdida: 0.003, ic95_bootstrap: [-0.002, 0.007], cumple: true }],
    },
    desplegado: { modelo: 'rl', mejor: 'lgbm', limite_superior: 0.007, motivo_texto: `motivo de la API ${momento}` },
    punto_operacion: {
      umbral: 0.15, sensibilidad: 0.7, precision: 0.26, tasa_alerta: 0.49, tasa_falsos_positivos: 0.45,
      matriz_confusion: [[11, 22], [33, 44]],
      textos: { sensibilidad: 'texto sensibilidad', precision: 'texto precisión', tasa_alerta: 'texto tasa' },
    },
    calibracion: {
      metodo: 'platt', brier_sin_calibrar: 0.2, brier_calibrado: 0.14,
      curva: conCurva ? { calibrada: [{ predicha: 0.1, observada: 0.12 }, { predicha: 0.5, observada: 0.45 }],
        sin_calibrar: null } : null,
      texto: 'texto de calibración', ...(conCurva ? {} : { motivo: 'sin predicciones out-of-fold' }),
    },
    equidad: id === 1 ? {
      texto: 'texto de equidad',
      atributos: {
        sexo: {
          subgrupos: {
            F: { n: 600, retiros: 120, sensibilidad: 0.62, sensibilidad_ic95: [0.55, 0.69], tasa_falsos_positivos: 0.4,
              tasa_falsos_positivos_ic95: [0.36, 0.44], solo_descriptiva: false },
            X: { n: 4, retiros: 0, sensibilidad: null, sensibilidad_ic95: null, tasa_falsos_positivos: 0.5,
              tasa_falsos_positivos_ic95: null, solo_descriptiva: true },
          },
          diferencia_sensibilidad: 0.123, diferencia_sensibilidad_ic95: [0.041, 0.205],
          diferencia_tasa_falsos_positivos: null, diferencia_tasa_falsos_positivos_ic95: null,
        },
      },
    } : null,
    textos: { roc_auc: 'texto ROC-AUC', pr_auc: 'texto PR-AUC' },
  };
}

const RESPUESTA: Respuesta = {
  experimento: 'exp-1', origen: 'importado', fuente: 'validacion_cruzada', aviso_fuente: 'aviso de la fuente',
  presupuesto: { modo: 'completo', familias: ['rl', 'lgbm'], n_trials_por_familia: 50, apilamiento: true,
    n_bootstrap: 2000 },
  validacion: { tipo: 'agrupada', k: 5, semilla: 42, columna_grupo: null },
  modelos: [modelo(1, 'momento A', true), modelo(2, 'momento B', false)],
  aviso_decision: 'aviso de decisión',
};
const DETALLE = { id: 'exp-1', origen: 'importado', estado: 'completado', descripcion: null,
  configuracion: { presupuesto: { modo: 'completo' } }, modelos: [] } as ExperimentoDetalle;

async function renderizar(elegido?: string, error = false) {
  TestBed.configureTestingModule({
    imports: [Evaluacion],
    providers: [provideRouter([]), provideHttpClient(), provideHttpClientTesting()],
  });
  const fixture = TestBed.createComponent(Evaluacion);
  fixture.componentRef.setInput('id', 'exp-1');
  fixture.componentRef.setInput('modelo', elegido);
  fixture.detectChanges();
  const http = TestBed.inject(HttpTestingController);
  if (error) {
    http.expectOne('/api/experimentos/exp-1/evaluacion').flush({ error: 'texto de la API: no terminado' },
      { status: 409, statusText: 'Conflict' });
    expect(http.expectOne('/api/experimentos/exp-1').cancelled).toBe(true); // forkJoin cancela la otra petición
  } else {
    http.expectOne('/api/experimentos/exp-1/evaluacion').flush(RESPUESTA);
    http.expectOne('/api/experimentos/exp-1').flush(DETALLE);
  }
  await fixture.whenStable();
  return fixture.nativeElement as HTMLElement;
}

describe('Evaluacion', () => {
  it('sin ?modelo= muestra el primero, con los textos de la API tal cual y la curva', async () => {
    const html = await renderizar();
    const botones = [...html.querySelectorAll('.selector button')];
    expect(botones.map((b) => b.getAttribute('aria-pressed'))).toEqual(['true', 'false']);
    const texto = html.textContent ?? '';
    for (const t of ['aviso de la fuente', 'motivo de la API momento A', 'texto sensibilidad', 'texto precisión',
      'texto tasa', 'texto ROC-AUC', 'lectura momento A', 'texto de calibración', 'aviso de decisión']) {
      expect(texto).toContain(t);
    }
    expect(texto).toContain('Umbral de alerta: 15,0 %');
    expect(html.querySelector('app-grafico-calibracion svg')).not.toBeNull();
  });

  it('con ?modelo= muestra ese modelo; sin curva, el motivo; la matriz con encabezados en su sitio', async () => {
    const html = await renderizar('2');
    const texto = html.textContent ?? '';
    expect(texto).toContain('motivo de la API momento B');
    expect(texto).toContain('sin predicciones out-of-fold');
    expect(html.querySelector('app-grafico-calibracion')).toBeNull();
    // [[VN, FP], [FN, VP]] → fila «positivos reales»: VP marcados y FN no marcados.
    const filas = [...html.querySelectorAll('table')].find((t) => t.caption?.textContent?.includes('Casos marcados'))!
      .querySelectorAll('tbody tr');
    expect([...filas[0].querySelectorAll('td')].map((c) => c.textContent?.trim())).toEqual(['44', '33']);
    expect([...filas[1].querySelectorAll('td')].map((c) => c.textContent?.trim())).toEqual(['22', '11']);
  });

  it('equidad: proporciones e intervalos en %, diferencias en puntos porcentuales, nulos y solo descriptiva', async () => {
    const html = await renderizar();
    const texto = (html.textContent ?? '').replace(/\s+/g, ' ');
    expect(texto).toContain('texto de equidad');
    const tabla = [...html.querySelectorAll('table')].find((t) => t.caption?.textContent?.trim() === 'sexo')!;
    const celdas = [...tabla.querySelectorAll('tbody tr')].map((f) =>
      [...f.querySelectorAll('th, td')].map((c) => c.textContent?.replace(/\s+/g, ' ').trim()));
    expect(celdas[0]).toEqual(['F', '600', '120', '62,0 % [55,0 %; 69,0 %]', '40,0 % [36,0 %; 44,0 %]', '']);
    expect(celdas[1]).toEqual(['X', '4', '0', TEXTOS.evaluacion.sinValor, '50,0 %', TEXTOS.evaluacion.soloDescriptiva]);
    expect(texto).toContain(`${TEXTOS.evaluacion.diferenciaSensibilidad}: 12,3 p. p. [4,1; 20,5]`);
    expect(texto).toContain(`${TEXTOS.evaluacion.diferenciaFalsosPositivos}: ${TEXTOS.evaluacion.sinValor}`);
  });

  it('el selector cambia ?modelo= sin añadir una entrada al historial', async () => {
    const html = await renderizar();
    const navegar = vi.spyOn(TestBed.inject(Router), 'navigate').mockResolvedValue(true);
    (html.querySelectorAll('.selector button')[1] as HTMLButtonElement).click();
    expect(navegar).toHaveBeenCalledWith([], expect.objectContaining({ queryParams: { modelo: 2 }, replaceUrl: true }));
  });

  it('un error de la API se muestra tal cual', async () => {
    const html = await renderizar(undefined, true);
    expect(html.querySelector('[role="alert"]')?.textContent).toContain('texto de la API: no terminado');
  });
});
