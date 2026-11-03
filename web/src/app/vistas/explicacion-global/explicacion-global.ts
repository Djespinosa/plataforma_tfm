import { Component, DestroyRef, OnInit, computed, inject, input, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { RouterLink } from '@angular/router';
import { forkJoin } from 'rxjs';

import { ErrorLegible, leerError } from '../../api/errores';
import { ModelosService } from '../../api/modelos.service';
import { ExplicacionGlobal as RespuestaGlobal, ModeloDetalle } from '../../api/tipos';
import { Aviso } from '../../comun/aviso';
import { Barra, GraficoBarras } from '../../comun/grafico-barras';
import { PieDecision } from '../../comun/pie-decision';
import { decimal } from '../../formato';
import { TEXTOS, nombreModelo } from '../../textos';

/** Variables del resumen (barras); la tabla completa va en el detalle (RF-07). */
const EN_RESUMEN = 15;

@Component({
  selector: 'app-explicacion-global',
  imports: [RouterLink, Aviso, GraficoBarras, PieDecision],
  templateUrl: './explicacion-global.html',
})
export class ExplicacionGlobal implements OnInit {
  /** Id del modelo (parámetro de la ruta). */
  readonly modelo = input.required<string>();

  protected readonly t = TEXTOS;
  protected readonly nombreModelo = nombreModelo;
  protected readonly decimal = decimal;
  protected readonly respuesta = signal<RespuestaGlobal | null>(null);
  protected readonly detalle = signal<ModeloDetalle | null>(null);
  protected readonly error = signal<ErrorLegible | null>(null);

  protected readonly barras = computed<Barra[]>(() =>
    (this.respuesta()?.variables ?? []).slice(0, EN_RESUMEN).map((v) => ({
      etiqueta: v.variable,
      valor: v.importancia_media_abs,
      texto: decimal(v.importancia_media_abs),
    })),
  );

  private readonly modelos = inject(ModelosService);
  private readonly destruir = inject(DestroyRef);

  ngOnInit(): void {
    const id = Number(this.modelo());
    forkJoin({ global: this.modelos.explicacionGlobal(id), detalle: this.modelos.detalle(id) })
      .pipe(takeUntilDestroyed(this.destruir))
      .subscribe({
        next: ({ global, detalle }) => {
          this.respuesta.set(global);
          this.detalle.set(detalle);
        },
        error: (e) => this.error.set(leerError(e)),
      });
  }
}
