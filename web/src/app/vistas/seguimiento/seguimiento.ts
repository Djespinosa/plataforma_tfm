import { KeyValuePipe } from '@angular/common';
import { HttpErrorResponse } from '@angular/common/http';
import { Component, DestroyRef, computed, inject, input, signal } from '@angular/core';
import { takeUntilDestroyed, toObservable } from '@angular/core/rxjs-interop';
import { Router, RouterLink } from '@angular/router';
import { EMPTY, catchError, exhaustMap, of, switchMap, takeWhile, tap, timer } from 'rxjs';

import { ErrorLegible, leerError } from '../../api/errores';
import { EstadoService } from '../../api/estado.service';
import { ExperimentosService } from '../../api/experimentos.service';
import { ExperimentoDetalle } from '../../api/tipos';
import { Aviso } from '../../comun/aviso';
import { duracion, fecha } from '../../formato';
import { TEXTOS, nombreModelo, textoEtapas } from '../../textos';

/** Intervalo del sondeo (docs/diseno-web.md §10). */
export const SONDEO_MS = 3000;

const activo = (e: ExperimentoDetalle) => e.estado === 'en_cola' || e.estado === 'en_curso';

@Component({
  selector: 'app-seguimiento',
  imports: [KeyValuePipe, RouterLink, Aviso],
  templateUrl: './seguimiento.html',
})
export class Seguimiento {
  /** Id del experimento (parámetro de la ruta). */
  readonly id = input.required<string>();

  protected readonly t = TEXTOS;
  protected readonly fecha = fecha;
  protected readonly duracion = duracion;
  protected readonly nombreModelo = nombreModelo;
  protected readonly textoEtapas = textoEtapas;
  protected readonly experimento = signal<ExperimentoDetalle | null>(null);
  protected readonly error = signal<ErrorLegible | null>(null);
  protected readonly trabajadorActivo = signal<boolean | null>(null);
  protected readonly errorReintento = signal<ErrorLegible | null>(null);
  protected readonly reintentando = signal(false);

  protected readonly demostracion = computed(() => this.experimento()?.configuracion.presupuesto.modo === 'demostracion');

  private readonly experimentos = inject(ExperimentosService);
  private readonly router = inject(Router);
  private readonly destruir = inject(DestroyRef);

  constructor() {
    inject(EstadoService)
      .estado()
      .pipe(takeUntilDestroyed())
      .subscribe({ next: (e) => this.trabajadorActivo.set(e.trabajador_activo), error: () => undefined });

    // Sondeo cada 3 s mientras el experimento está en cola o en curso; se reinicia si cambia el id (tras un reintento
    // la ruta es la misma y el componente se reutiliza). Un error de red no corta el sondeo: la API puede reiniciarse
    // sin afectar al trabajador. Un 404 sí lo corta (el experimento no existe). exhaustMap: si una lectura tarda más
    // de 3 s (API ocupada durante el entrenamiento), se espera a que termine en vez de cancelarla en cada tic.
    toObservable(this.id)
      .pipe(
        tap(() => {
          this.experimento.set(null);
          this.error.set(null);
          this.errorReintento.set(null);
          this.reintentando.set(false);
        }),
        switchMap((id) =>
          timer(0, SONDEO_MS).pipe(
            exhaustMap(() =>
              this.experimentos.detalle(id).pipe(
                catchError((e: unknown) => {
                  this.error.set(leerError(e));
                  return e instanceof HttpErrorResponse && e.status === 404 ? of(null) : EMPTY;
                }),
              ),
            ),
            takeWhile((e) => e !== null && activo(e), true),
          ),
        ),
        takeUntilDestroyed(),
      )
      .subscribe((e) => {
        if (e === null) return;
        this.experimento.set(e);
        this.error.set(null);
      });
  }

  protected reintentar(): void {
    this.reintentando.set(true);
    this.errorReintento.set(null);
    this.experimentos
      .reintentar(this.id())
      .pipe(takeUntilDestroyed(this.destruir))
      .subscribe({
        next: (nuevo) => void this.router.navigate(['/experimentos', nuevo.id]),
        error: (e) => {
          this.errorReintento.set(leerError(e));
          this.reintentando.set(false);
        },
      });
  }

  protected sinONo(valor: boolean | null): string {
    return valor === null ? this.t.seguimiento.desconocido : valor ? this.t.seguimiento.si : this.t.seguimiento.no;
  }
}
