import { KeyValuePipe } from '@angular/common';
import { Component, DestroyRef, OnInit, computed, inject, input, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { forkJoin } from 'rxjs';

import { ErrorLegible, leerError } from '../../api/errores';
import { ExperimentosService } from '../../api/experimentos.service';
import {
  AtributoEquidad,
  EvaluacionModelo,
  Evaluacion as RespuestaEvaluacion,
  ExperimentoDetalle,
  FilaMetricas,
} from '../../api/tipos';
import { Aviso } from '../../comun/aviso';
import { GraficoCalibracion } from '../../comun/grafico-calibracion';
import { PieDecision } from '../../comun/pie-decision';
import { decimal, intervalo, miles, pValor, porcentaje1, puntos } from '../../formato';
import { TEXTOS, nombreModelo, textoValidacion } from '../../textos';

@Component({
  selector: 'app-evaluacion',
  imports: [KeyValuePipe, RouterLink, Aviso, GraficoCalibracion, PieDecision],
  templateUrl: './evaluacion.html',
})
export class Evaluacion implements OnInit {
  /** Id del experimento (parámetro de la ruta) y modelo elegido (?modelo=, opcional). */
  readonly id = input.required<string>();
  readonly modelo = input<string | undefined>();

  protected readonly t = TEXTOS;
  protected readonly nombreModelo = nombreModelo;
  protected readonly decimal = decimal;
  protected readonly intervalo = intervalo;
  protected readonly miles = miles;
  protected readonly pValor = pValor;
  protected readonly porcentaje1 = porcentaje1;
  protected readonly respuesta = signal<RespuestaEvaluacion | null>(null);
  protected readonly experimento = signal<ExperimentoDetalle | null>(null);
  protected readonly error = signal<ErrorLegible | null>(null);

  /** El modelo elegido en ?modelo=, o el primero si no se indica o no es de este experimento. */
  protected readonly elegido = computed<EvaluacionModelo | null>(() => {
    const modelos = this.respuesta()?.modelos ?? [];
    return modelos.find((m) => String(m.modelo_id) === this.modelo()) ?? modelos[0] ?? null;
  });

  protected readonly filaDesplegado = computed<FilaMetricas | null>(() => {
    const m = this.elegido();
    return m ? (m.candidatos.find((c) => c.modelo === m.desplegado.modelo) ?? null) : null;
  });

  protected readonly validacion = computed(() => {
    const r = this.respuesta();
    return r ? textoValidacion(r.validacion.tipo, r.validacion.k) : '';
  });

  protected readonly demostracion = computed(() => this.respuesta()?.presupuesto.modo === 'demostracion');

  private readonly experimentos = inject(ExperimentosService);
  private readonly router = inject(Router);
  private readonly ruta = inject(ActivatedRoute);
  private readonly destruir = inject(DestroyRef);

  ngOnInit(): void {
    forkJoin({ evaluacion: this.experimentos.evaluacion(this.id()), detalle: this.experimentos.detalle(this.id()) })
      .pipe(takeUntilDestroyed(this.destruir))
      .subscribe({
        next: ({ evaluacion, detalle }) => {
          this.respuesta.set(evaluacion);
          this.experimento.set(detalle);
        },
        error: (e) => this.error.set(leerError(e)),
      });
  }

  protected elegir(modeloId: number): void {
    void this.router.navigate([], { relativeTo: this.ruta, queryParams: { modelo: modeloId }, replaceUrl: true });
  }

  protected subgrupos(atributo: AtributoEquidad) {
    return Object.entries(atributo.subgrupos).map(([nombre, s]) => ({ nombre, ...s }));
  }

  protected opcional(valor: number | null, decimales = 3): string {
    return valor === null ? this.t.evaluacion.sinValor : decimal(valor, decimales);
  }

  protected opcionalPct(valor: number | null): string {
    return valor === null ? this.t.evaluacion.sinValor : porcentaje1(valor);
  }

  /** Diferencia de equidad en puntos porcentuales, como las proporciones de la tabla, que van en %. */
  protected diferencia(valor: number | null, ic: [number, number] | null): string {
    return valor === null ? this.t.evaluacion.sinValor : puntos(valor, ic);
  }

  /** Intervalo de una proporción en %, como el valor al que acompaña: «[69,3 %; 72,8 %]». */
  protected intervaloPct(valor: [number, number] | null): string {
    return valor === null ? '' : `[${porcentaje1(valor[0])}; ${porcentaje1(valor[1])}]`;
  }
}
