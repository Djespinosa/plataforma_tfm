import { KeyValuePipe } from '@angular/common';
import {
  Component,
  DestroyRef,
  ElementRef,
  Injector,
  OnInit,
  afterNextRender,
  computed,
  inject,
  input,
  signal,
} from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { forkJoin } from 'rxjs';

import { ErrorLegible, leerError } from '../../api/errores';
import { ExperimentosService } from '../../api/experimentos.service';
import {
  AtributoEquidad,
  EvaluacionModelo,
  EvaluacionPrueba,
  Evaluacion as RespuestaEvaluacion,
  ExperimentoDetalle,
  FilaMetricas,
} from '../../api/tipos';
import { Aviso } from '../../comun/aviso';
import { GraficoCalibracion } from '../../comun/grafico-calibracion';
import { PieDecision } from '../../comun/pie-decision';
import { decimal, fecha, intervalo, miles, pValor, porcentaje1, puntos } from '../../formato';
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
  protected readonly fecha = fecha;
  protected readonly respuesta = signal<RespuestaEvaluacion | null>(null);
  protected readonly experimento = signal<ExperimentoDetalle | null>(null);
  protected readonly error = signal<ErrorLegible | null>(null);
  /** Evaluación única en la cohorte de prueba (§4.7): la guardada en el experimento o la recién hecha. */
  protected readonly prueba = signal<EvaluacionPrueba | null>(null);
  protected readonly confirmado = signal(false);
  protected readonly evaluandoPrueba = signal(false);
  protected readonly errorPrueba = signal<ErrorLegible | null>(null);

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

  /** RF-09: el navegador descarga por el proxy; la API pone el nombre del archivo. */
  protected readonly exportar = computed(() => `/api/experimentos/${encodeURIComponent(this.id())}/evaluacion/exportar`);

  /** Solo en los entrenados en la plataforma con cohorte reservada y sin evaluar; nunca en los importados. */
  protected readonly puedeEvaluarPrueba = computed(() => {
    const e = this.experimento();
    return !!e && e.origen === 'web' && !!e.configuracion['cohorte_prueba'] && !this.prueba();
  });

  private readonly experimentos = inject(ExperimentosService);
  private readonly router = inject(Router);
  private readonly ruta = inject(ActivatedRoute);
  private readonly destruir = inject(DestroyRef);
  private readonly inyector = inject(Injector);
  private readonly elemento = inject<ElementRef<HTMLElement>>(ElementRef);

  ngOnInit(): void {
    forkJoin({ evaluacion: this.experimentos.evaluacion(this.id()), detalle: this.experimentos.detalle(this.id()) })
      .pipe(takeUntilDestroyed(this.destruir))
      .subscribe({
        next: ({ evaluacion, detalle }) => {
          this.respuesta.set(evaluacion);
          this.experimento.set(detalle);
          this.prueba.set(detalle.evaluacion_prueba);
        },
        error: (e) => this.error.set(leerError(e)),
      });
  }

  protected elegir(modeloId: number): void {
    void this.router.navigate([], { relativeTo: this.ruta, queryParams: { modelo: modeloId }, replaceUrl: true });
  }

  protected evaluarPrueba(): void {
    if (!this.confirmado() || this.evaluandoPrueba()) return;
    this.evaluandoPrueba.set(true);
    this.errorPrueba.set(null);
    this.experimentos
      .evaluarPrueba(this.id())
      .pipe(takeUntilDestroyed(this.destruir))
      .subscribe({
        next: (p) => {
          this.prueba.set(p);
          this.evaluandoPrueba.set(false);
          // El botón desaparece al mostrarse el resultado: el foco va al título de la sección (como en la carga).
          afterNextRender(
            () => this.elemento.nativeElement.querySelector<HTMLElement>('#evaluacion-prueba')?.focus(),
            { injector: this.inyector },
          );
        },
        error: (e) => {
          this.errorPrueba.set(leerError(e));
          this.evaluandoPrueba.set(false);
        },
      });
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
