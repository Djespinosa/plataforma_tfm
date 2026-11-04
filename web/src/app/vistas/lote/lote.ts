import { Component, DestroyRef, OnInit, computed, inject, input, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { RouterLink } from '@angular/router';

import { ErrorLegible, leerError } from '../../api/errores';
import { PrediccionesService } from '../../api/predicciones.service';
import { Lote as RespuestaLote } from '../../api/tipos';
import { Aviso } from '../../comun/aviso';
import { PieDecision } from '../../comun/pie-decision';
import { miles, porcentaje1, probabilidad } from '../../formato';
import { TEXTOS, textoMarcados, textoMostrando, textoPagina } from '../../textos';
import { Columna, Direccion, filtrar, ordenar, paginar } from './lista';

@Component({
  selector: 'app-lote',
  imports: [RouterLink, Aviso, PieDecision],
  templateUrl: './lote.html',
})
export class Lote implements OnInit {
  /** Id del lote (parámetro de la ruta). */
  readonly lote = input.required<string>();

  protected readonly t = TEXTOS;
  protected readonly probabilidad = probabilidad;
  protected readonly porcentaje1 = porcentaje1;
  protected readonly textoMostrando = textoMostrando;
  protected readonly textoPagina = textoPagina;
  protected readonly respuesta = signal<RespuestaLote | null>(null);
  protected readonly error = signal<ErrorLegible | null>(null);

  protected readonly columna = signal<Columna>('probabilidad');
  protected readonly direccion = signal<Direccion>('descendente');
  protected readonly soloMarcados = signal(false);
  protected readonly identificador = signal('');
  protected readonly minimoPct = signal(0);
  protected readonly pagina = signal(1);

  protected readonly vista = computed(() => {
    const r = this.respuesta();
    const filas = r ? r.filas : [];
    const filtradas = filtrar(filas, {
      soloMarcados: this.soloMarcados(),
      identificador: this.identificador(),
      minimoPct: this.minimoPct(),
    });
    return paginar(ordenar(filtradas, this.columna(), this.direccion()), this.pagina());
  });

  protected readonly marcados = computed(() => {
    const l = this.respuesta()?.lote;
    return l ? textoMarcados(miles(l.n_alertas), miles(l.n_filas), porcentaje1(l.tasa_alerta)) : '';
  });

  private readonly predicciones = inject(PrediccionesService);
  private readonly destruir = inject(DestroyRef);

  ngOnInit(): void {
    this.predicciones
      .lote(Number(this.lote()))
      .pipe(takeUntilDestroyed(this.destruir))
      .subscribe({ next: (r) => this.respuesta.set(r), error: (e) => this.error.set(leerError(e)) });
  }

  protected ordenarPor(columna: Columna): void {
    if (this.columna() === columna) {
      this.direccion.set(this.direccion() === 'ascendente' ? 'descendente' : 'ascendente');
    } else {
      this.columna.set(columna);
      this.direccion.set(columna === 'probabilidad' ? 'descendente' : 'ascendente');
    }
    this.pagina.set(1);
  }

  protected ariaSort(columna: Columna): string {
    return this.columna() === columna ? (this.direccion() === 'ascendente' ? 'ascending' : 'descending') : 'none';
  }

  protected cambiarFiltro(accion: () => void): void {
    accion();
    this.pagina.set(1);
  }

  protected leerMinimo(valor: string): number {
    const n = Number(valor.replace(',', '.'));
    return Number.isFinite(n) ? Math.min(Math.max(n, 0), 100) : 0;
  }
}
