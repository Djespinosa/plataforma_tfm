import { Component, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { RouterLink } from '@angular/router';

import { ErrorLegible, leerError } from '../../api/errores';
import { EstadoService } from '../../api/estado.service';
import { Estado } from '../../api/tipos';
import { Aviso } from '../../comun/aviso';
import { TEXTOS } from '../../textos';

@Component({
  selector: 'app-inicio',
  imports: [RouterLink, Aviso],
  templateUrl: './inicio.html',
})
export class Inicio {
  protected readonly t = TEXTOS;
  protected readonly estado = signal<Estado | null>(null);
  protected readonly error = signal<ErrorLegible | null>(null);

  constructor() {
    inject(EstadoService)
      .estado()
      .pipe(takeUntilDestroyed())
      .subscribe({ next: (e) => this.estado.set(e), error: (e) => this.error.set(leerError(e)) });
  }

  protected trabajador(e: Estado): string {
    if (e.trabajador_activo === null) return this.t.inicio.trabajadorDesconocido;
    return e.trabajador_activo ? this.t.inicio.trabajadorActivo : this.t.inicio.trabajadorInactivo;
  }
}
