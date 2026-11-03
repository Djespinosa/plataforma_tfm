import { Component, computed, input } from '@angular/core';

import { PuntoCurva } from '../api/tipos';
import { porcentaje } from '../formato';
import { TEXTOS } from '../textos';

let siguienteId = 0;

const LADO = 320; // área del gráfico (0-1 en ambos ejes)
const MARGEN = 48;
const TOTAL = LADO + 2 * MARGEN;

/**
 * Curva de calibración en SVG (docs/diseno-web.md §7): la calibrada con línea continua y círculos, la sin calibrar (si
 * existe) discontinua con cuadrados y la diagonal punteada; cada trazo se distingue por su forma y su leyenda escrita,
 * no solo por el color. Los mismos puntos van en una tabla dentro de un details.
 */
@Component({
  selector: 'app-grafico-calibracion',
  template: `
    <figure class="grafico grafico-calibracion">
      <svg role="img" [attr.aria-labelledby]="id + '-titulo ' + id + '-desc'" [attr.viewBox]="'0 0 ' + total + ' ' + total"
           width="100%" preserveAspectRatio="xMinYMin meet">
        <title [attr.id]="id + '-titulo'">{{ t.calibracion.titulo }}</title>
        <desc [attr.id]="id + '-desc'">{{ t.calibracion.descripcion }}</desc>
        <rect [attr.x]="margen" [attr.y]="margen" [attr.width]="lado" [attr.height]="lado" fill="none" stroke="#6b6b6b" />
        @for (marca of marcas; track marca) {
          <text [attr.x]="x(marca)" [attr.y]="margen + lado + 16" font-size="12" text-anchor="middle" fill="#1a1a1a">
            {{ porcentaje(marca) }}
          </text>
          <text [attr.x]="margen - 6" [attr.y]="y(marca) + 4" font-size="12" text-anchor="end" fill="#1a1a1a">
            {{ porcentaje(marca) }}
          </text>
        }
        <text [attr.x]="margen + lado / 2" [attr.y]="total - 6" font-size="12" text-anchor="middle" fill="#1a1a1a">
          {{ t.calibracion.ejeX }}
        </text>
        <text [attr.transform]="'translate(12,' + (margen + lado / 2) + ') rotate(-90)'" font-size="12"
              text-anchor="middle" fill="#1a1a1a">{{ t.calibracion.ejeY }}</text>
        <line [attr.x1]="x(0)" [attr.y1]="y(0)" [attr.x2]="x(1)" [attr.y2]="y(1)" stroke="#4a4a4a"
              stroke-dasharray="2 4" />
        @if (sinCalibrar(); as puntos) {
          <polyline [attr.points]="trazo(puntos)" fill="none" stroke="#8a5300" stroke-width="2" stroke-dasharray="6 4" />
          @for (p of puntos; track $index) {
            <rect [attr.x]="x(p.predicha) - 4" [attr.y]="y(p.observada) - 4" width="8" height="8" fill="#8a5300" />
          }
        }
        <polyline [attr.points]="trazo(calibrada())" fill="none" stroke="#1d4f91" stroke-width="2" />
        @for (p of calibrada(); track $index) {
          <circle [attr.cx]="x(p.predicha)" [attr.cy]="y(p.observada)" r="4" fill="#1d4f91" />
        }
      </svg>
      <figcaption>
        <ul class="leyenda">
          <li><span aria-hidden="true">●──</span> {{ t.calibracion.calibrada }}</li>
          @if (sinCalibrar()) {
            <li><span aria-hidden="true">■- -</span> {{ t.calibracion.sinCalibrar }}</li>
          }
          <li><span aria-hidden="true">· · ·</span> {{ t.calibracion.diagonal }}</li>
        </ul>
      </figcaption>
      <details>
        <summary>{{ t.grafico.verTabla }}</summary>
        @for (serie of series(); track serie.nombre) {
          <div class="tabla-contenedor" tabindex="0" [attr.aria-label]="serie.nombre">
            <table>
              <caption>{{ serie.nombre }}</caption>
              <thead>
                <tr>
                  <th scope="col" class="numero">{{ t.calibracion.ejeX }}</th>
                  <th scope="col" class="numero">{{ t.calibracion.ejeY }}</th>
                </tr>
              </thead>
              <tbody>
                @for (p of serie.puntos; track $index) {
                  <tr>
                    <td class="numero">{{ porcentaje(p.predicha) }}</td>
                    <td class="numero">{{ porcentaje(p.observada) }}</td>
                  </tr>
                }
              </tbody>
            </table>
          </div>
        }
      </details>
    </figure>
  `,
})
export class GraficoCalibracion {
  readonly calibrada = input.required<PuntoCurva[]>();
  readonly sinCalibrar = input<PuntoCurva[] | null>(null);

  protected readonly t = TEXTOS;
  protected readonly porcentaje = porcentaje;
  protected readonly id = `grafico-calibracion-${siguienteId++}`;
  protected readonly lado = LADO;
  protected readonly margen = MARGEN;
  protected readonly total = TOTAL;
  protected readonly marcas = [0, 0.25, 0.5, 0.75, 1];

  protected readonly series = computed(() => {
    const series = [{ nombre: this.t.calibracion.calibrada, puntos: this.calibrada() }];
    const sin = this.sinCalibrar();
    if (sin) series.push({ nombre: this.t.calibracion.sinCalibrar, puntos: sin });
    return series;
  });

  protected x(valor: number): number {
    return MARGEN + valor * LADO;
  }

  protected y(valor: number): number {
    return MARGEN + (1 - valor) * LADO;
  }

  protected trazo(puntos: PuntoCurva[]): string {
    return puntos.map((p) => `${this.x(p.predicha)},${this.y(p.observada)}`).join(' ');
  }
}
