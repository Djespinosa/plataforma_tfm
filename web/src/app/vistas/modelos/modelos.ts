import { Component, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { RouterLink } from '@angular/router';

import { ErrorLegible, leerError } from '../../api/errores';
import { ModelosService } from '../../api/modelos.service';
import { Modelo } from '../../api/tipos';
import { Aviso } from '../../comun/aviso';
import { porcentaje1 } from '../../formato';
import { TEXTOS, nombreModelo } from '../../textos';

@Component({
  selector: 'app-modelos',
  imports: [RouterLink, Aviso],
  templateUrl: './modelos.html',
})
export class Modelos {
  protected readonly t = TEXTOS;
  protected readonly nombreModelo = nombreModelo;
  protected readonly porcentaje1 = porcentaje1;
  protected readonly modelos = signal<Modelo[] | null>(null);
  protected readonly error = signal<ErrorLegible | null>(null);

  constructor() {
    inject(ModelosService)
      .listar()
      .pipe(takeUntilDestroyed())
      .subscribe({ next: (m) => this.modelos.set(m), error: (e) => this.error.set(leerError(e)) });
  }
}
