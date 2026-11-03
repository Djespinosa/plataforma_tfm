import { Component, DestroyRef, ElementRef, Injector, afterNextRender, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { RouterLink } from '@angular/router';

import { ConjuntosService } from '../../api/conjuntos.service';
import { ErrorLegible, leerError } from '../../api/errores';
import { Conjunto, ConjuntoResumen } from '../../api/tipos';
import { Aviso } from '../../comun/aviso';
import { fecha, miles, porcentaje1 } from '../../formato';
import { TEXTOS } from '../../textos';

@Component({
  selector: 'app-carga',
  imports: [RouterLink, Aviso],
  templateUrl: './carga.html',
})
export class Carga {
  protected readonly t = TEXTOS;
  protected readonly fecha = fecha;
  protected readonly miles = miles;
  protected readonly porcentaje1 = porcentaje1;
  protected readonly conjuntos = signal<ConjuntoResumen[] | null>(null);
  protected readonly errorLista = signal<ErrorLegible | null>(null);
  protected readonly errorEnvio = signal<ErrorLegible | null>(null);
  protected readonly cargado = signal<Conjunto | null>(null);
  protected readonly enviando = signal(false);
  protected readonly archivo = signal<File | null>(null);
  protected readonly momento = signal('');

  private readonly servicio = inject(ConjuntosService);
  private readonly destruir = inject(DestroyRef);
  private readonly inyector = inject(Injector);
  private readonly elemento = inject<ElementRef<HTMLElement>>(ElementRef);

  constructor() {
    this.servicio
      .listar()
      .pipe(takeUntilDestroyed())
      .subscribe({ next: (c) => this.conjuntos.set(c), error: (e) => this.errorLista.set(leerError(e)) });
  }

  protected elegirArchivo(evento: Event): void {
    this.archivo.set((evento.target as HTMLInputElement).files?.[0] ?? null);
  }

  protected enviar(evento: Event): void {
    evento.preventDefault();
    const archivo = this.archivo();
    if (!archivo) {
      this.errorEnvio.set({ mensaje: this.t.carga.sinArchivo, detalles: [] });
      return;
    }
    this.enviando.set(true);
    this.errorEnvio.set(null);
    this.cargado.set(null);
    this.servicio
      .subir(archivo, this.momento())
      .pipe(takeUntilDestroyed(this.destruir))
      .subscribe({
        next: (c) => {
          this.cargado.set(c);
          // El nuevo conjunto encabeza la lista, como en GET /api/conjuntos (del más reciente al más antiguo).
          this.conjuntos.update((lista) => (lista ? [c, ...lista] : lista));
          this.enviando.set(false);
          // El resumen aparece debajo del formulario: el foco va a su título para que se anuncie y se vea.
          afterNextRender(() => this.elemento.nativeElement.querySelector<HTMLElement>('#archivo-cargado')?.focus(),
            { injector: this.inyector });
        },
        error: (e) => {
          this.errorEnvio.set(leerError(e));
          this.enviando.set(false);
        },
      });
  }
}
