import { Component, DestroyRef, OnInit, computed, inject, input, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { RouterLink } from '@angular/router';

import { ErrorLegible, leerError } from '../../api/errores';
import { PrediccionesService } from '../../api/predicciones.service';
import { ExplicacionLocal as RespuestaLocal } from '../../api/tipos';
import { Aviso } from '../../comun/aviso';
import { Barra, GraficoBarras } from '../../comun/grafico-barras';
import { PieDecision } from '../../comun/pie-decision';
import { contribucion, decimal, probabilidad as formatoProbabilidad } from '../../formato';
import { TEXTOS, textoProbabilidad, textoResto } from '../../textos';

@Component({
  selector: 'app-explicacion-local',
  imports: [RouterLink, Aviso, GraficoBarras, PieDecision],
  templateUrl: './explicacion-local.html',
})
export class ExplicacionLocal implements OnInit {
  /** Id del lote y número de fila (parámetros de la ruta). */
  readonly lote = input.required<string>();
  readonly fila = input.required<string>();

  protected readonly t = TEXTOS;
  protected readonly contribucion = contribucion;
  protected readonly decimal = decimal;
  protected readonly respuesta = signal<RespuestaLocal | null>(null);
  protected readonly error = signal<ErrorLegible | null>(null);

  protected readonly probabilidad = computed(() => {
    const r = this.respuesta();
    return r ? textoProbabilidad(formatoProbabilidad(r.probabilidad)) : '';
  });

  protected readonly resto = computed(() => {
    const r = this.respuesta();
    return r && r.resto.n_variables ? textoResto(r.resto.n_variables, contribucion(r.resto.suma)) : '';
  });

  /** Las que aumentan y las que reducen la estimación, en barras con signo (de mayor a menor contribución). */
  protected readonly barras = computed<Barra[]>(() => {
    const r = this.respuesta();
    if (!r) return [];
    return [...r.aumentan, ...r.reducen]
      .sort((a, b) => b.contribucion - a.contribucion)
      .map((c) => ({ etiqueta: `${c.variable}: ${c.valor}`, valor: c.contribucion, texto: contribucion(c.contribucion) }));
  });

  private readonly predicciones = inject(PrediccionesService);
  private readonly destruir = inject(DestroyRef);

  ngOnInit(): void {
    this.predicciones
      .explicacionLocal(Number(this.lote()), Number(this.fila()))
      .pipe(takeUntilDestroyed(this.destruir))
      .subscribe({ next: (r) => this.respuesta.set(r), error: (e) => this.error.set(leerError(e)) });
  }
}
