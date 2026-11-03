import { Component, input } from '@angular/core';

import { TEXTOS } from '../textos';

/** Los seis pasos del flujo como lista ordenada; el actual con aria-current="step" y texto, no solo estilo. */
@Component({
  selector: 'app-pasos',
  template: `
    <nav class="pasos" [attr.aria-label]="t.aplicacion.navegacionPasos">
      <ol>
        @for (paso of t.pasos; track paso; let i = $index) {
          <li [attr.aria-current]="i + 1 === actual() ? 'step' : null" [class.actual]="i + 1 === actual()">
            {{ paso }}
            @if (i + 1 === actual()) {
              <span class="solo-lectores">{{ t.pasoActual }}</span>
            }
          </li>
        }
      </ol>
    </nav>
  `,
})
export class Pasos {
  /** Paso actual (1-6) o null fuera del flujo. */
  readonly actual = input<number | null>(null);
  protected readonly t = TEXTOS;
}
