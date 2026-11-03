import { Component, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { RouterLink } from '@angular/router';

import { ErrorLegible, leerError } from '../../api/errores';
import { ExperimentosService } from '../../api/experimentos.service';
import { ExperimentoHistorial } from '../../api/tipos';
import { Aviso } from '../../comun/aviso';
import { duracion, fecha, miles } from '../../formato';
import { TEXTOS } from '../../textos';

@Component({
  selector: 'app-historial',
  imports: [RouterLink, Aviso],
  templateUrl: './historial.html',
})
export class Historial {
  protected readonly t = TEXTOS;
  protected readonly fecha = fecha;
  protected readonly duracion = duracion;
  protected readonly miles = miles;
  protected readonly experimentos = signal<ExperimentoHistorial[] | null>(null);
  protected readonly error = signal<ErrorLegible | null>(null);

  constructor() {
    inject(ExperimentosService)
      .historial()
      .pipe(takeUntilDestroyed())
      .subscribe({ next: (e) => this.experimentos.set(e), error: (e) => this.error.set(leerError(e)) });
  }
}
