import { Component, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { ActivatedRouteSnapshot, NavigationEnd, Router, RouterLink, RouterOutlet } from '@angular/router';
import { filter } from 'rxjs';

import { Pasos } from './comun/pasos';
import { TEXTOS } from './textos';

@Component({
  selector: 'app-root',
  imports: [RouterOutlet, RouterLink, Pasos],
  templateUrl: './app.html',
})
export class App {
  protected readonly t = TEXTOS;
  protected readonly paso = signal<number | null>(null);
  private readonly router = inject(Router);
  private rutaAnterior: string | null = null;

  constructor() {
    this.router.events
      .pipe(
        filter((e) => e instanceof NavigationEnd),
        takeUntilDestroyed(),
      )
      .subscribe((e) => {
        this.paso.set(pasoDe(this.router.routerState.snapshot.root));
        // El foco va al h1 solo al cambiar de vista: no en la carga inicial ni cuando solo cambian los parámetros de
        // consulta (p. ej. ?modelo= en la evaluación), para no sacar al usuario del control que acaba de usar.
        const ruta = e.urlAfterRedirects.split(/[?#]/)[0];
        if (this.rutaAnterior !== null && ruta !== this.rutaAnterior) {
          setTimeout(() => document.querySelector<HTMLElement>('main h1')?.focus());
        }
        this.rutaAnterior = ruta;
      });
  }

  protected saltarAlContenido(evento: Event): void {
    evento.preventDefault();
    document.querySelector<HTMLElement>('main h1')?.focus();
  }
}

function pasoDe(ruta: ActivatedRouteSnapshot): number | null {
  let actual: ActivatedRouteSnapshot | null = ruta;
  let paso: number | null = null;
  while (actual) {
    paso = (actual.data['paso'] as number | undefined) ?? paso;
    actual = actual.firstChild;
  }
  return paso;
}
