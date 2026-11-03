import { Component, DestroyRef, OnInit, inject, input, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { Router } from '@angular/router';
import { switchMap, tap } from 'rxjs';

import { ErrorLegible, leerError } from '../../api/errores';
import { ExperimentosService } from '../../api/experimentos.service';
import { ModelosService } from '../../api/modelos.service';
import { PrediccionesService } from '../../api/predicciones.service';
import { ExperimentoDetalle, ModeloDetalle } from '../../api/tipos';
import { Aviso } from '../../comun/aviso';
import { TEXTOS, nombreModelo } from '../../textos';

@Component({
  selector: 'app-prediccion',
  imports: [Aviso],
  templateUrl: './prediccion.html',
})
export class Prediccion implements OnInit {
  /** Id del modelo (parámetro de la ruta). */
  readonly modelo = input.required<string>();

  protected readonly t = TEXTOS;
  protected readonly nombreModelo = nombreModelo;
  protected readonly detalle = signal<ModeloDetalle | null>(null);
  protected readonly experimento = signal<ExperimentoDetalle | null>(null);
  protected readonly errorCarga = signal<ErrorLegible | null>(null);
  protected readonly errorEnvio = signal<ErrorLegible | null>(null);
  protected readonly enviando = signal(false);
  protected readonly archivo = signal<File | null>(null);
  protected readonly columnaId = signal('');

  private readonly modelos = inject(ModelosService);
  private readonly experimentos = inject(ExperimentosService);
  private readonly predicciones = inject(PrediccionesService);
  private readonly router = inject(Router);
  private readonly destruir = inject(DestroyRef);

  ngOnInit(): void {
    this.modelos
      .detalle(Number(this.modelo()))
      .pipe(
        tap((m) => this.detalle.set(m)),
        switchMap((m) => this.experimentos.detalle(m.experimento_id)),
        takeUntilDestroyed(this.destruir),
      )
      .subscribe({ next: (e) => this.experimento.set(e), error: (e) => this.errorCarga.set(leerError(e)) });
  }

  protected elegirArchivo(evento: Event): void {
    this.archivo.set((evento.target as HTMLInputElement).files?.[0] ?? null);
  }

  protected enviar(evento: Event): void {
    evento.preventDefault();
    const archivo = this.archivo();
    if (!archivo) {
      this.errorEnvio.set({ mensaje: this.t.prediccion.sinArchivo, detalles: [] });
      return;
    }
    this.enviando.set(true);
    this.errorEnvio.set(null);
    this.predicciones
      .predecir(Number(this.modelo()), archivo, this.columnaId())
      .pipe(takeUntilDestroyed(this.destruir))
      .subscribe({
        next: (lote) => void this.router.navigate(['/predicciones', lote.lote_id]),
        error: (e) => {
          this.errorEnvio.set(leerError(e));
          this.enviando.set(false);
        },
      });
  }
}
