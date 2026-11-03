import { Component, computed, input } from '@angular/core';

import { TEXTOS } from '../textos';

export interface Barra {
  etiqueta: string;
  valor: number;
  /** Valor ya formateado (con signo si conSigno), que se escribe junto a la barra y en la tabla. */
  texto: string;
}

let siguienteId = 0;

const ANCHO = 720;
const ETIQUETAS = 260; // ancho reservado a los nombres de variable
const VALORES = 80; // ancho reservado al valor escrito
const ALTO_FILA = 24;

/**
 * Barras horizontales en SVG (docs/diseno-web.md §7): sin signo (importancia global) o con signo (contribuciones,
 * hacia la derecha las que aumentan la estimación y hacia la izquierda las que la reducen). El valor va escrito junto a
 * cada barra, y el sentido se distingue por la posición respecto al eje y el relleno (liso o rayado), no solo por el
 * color. La misma información va en una tabla dentro de un details.
 */
@Component({
  selector: 'app-grafico-barras',
  template: `
    <figure class="grafico">
      <svg role="img" [attr.aria-labelledby]="id + '-titulo ' + id + '-desc'" [attr.viewBox]="'0 0 ' + ancho + ' ' + alto()"
           width="100%" preserveAspectRatio="xMinYMin meet">
        <title [attr.id]="id + '-titulo'">{{ titulo() }}</title>
        <desc [attr.id]="id + '-desc'">{{ descripcion() }}</desc>
        <defs>
          <pattern [attr.id]="id + '-rayado'" width="6" height="6" patternUnits="userSpaceOnUse"
                   patternTransform="rotate(45)">
            <rect width="6" height="6" fill="#ffffff" />
            <line x1="0" y1="0" x2="0" y2="6" stroke="#8a5300" stroke-width="3" />
          </pattern>
        </defs>
        @if (conSigno()) {
          <line [attr.x1]="eje()" [attr.x2]="eje()" y1="0" [attr.y2]="alto()" stroke="#1a1a1a" stroke-width="1" />
        }
        @for (b of geometria(); track b.etiqueta; let i = $index) {
          <g [attr.transform]="'translate(0,' + i * altoFila + ')'">
            <text x="0" y="16" font-size="13" fill="#1a1a1a">{{ b.etiquetaCorta }}</text>
            <rect [attr.x]="b.x" y="4" [attr.width]="b.ancho" height="16"
                  [attr.fill]="b.valor < 0 ? 'url(#' + id + '-rayado)' : '#1d4f91'"
                  [attr.stroke]="b.valor < 0 ? '#8a5300' : '#1d4f91'" />
            <text [attr.x]="b.xTexto" y="16" font-size="13" fill="#1a1a1a"
                  [attr.text-anchor]="b.valor < 0 ? 'end' : 'start'">{{ b.texto }}</text>
          </g>
        }
      </svg>
      <details>
        <summary>{{ t.grafico.verTabla }}</summary>
        <div class="tabla-contenedor" tabindex="0" [attr.aria-label]="titulo()">
          <table>
            <caption>{{ titulo() }}</caption>
            <thead>
              <tr>
                <th scope="col">{{ cabeceraEtiqueta() }}</th>
                <th scope="col" class="numero">{{ cabeceraValor() }}</th>
              </tr>
            </thead>
            <tbody>
              @for (b of barras(); track b.etiqueta) {
                <tr>
                  <th scope="row">{{ b.etiqueta }}</th>
                  <td class="numero">{{ b.texto }}</td>
                </tr>
              }
            </tbody>
          </table>
        </div>
      </details>
    </figure>
  `,
})
export class GraficoBarras {
  readonly barras = input.required<Barra[]>();
  readonly titulo = input.required<string>();
  readonly descripcion = input.required<string>();
  readonly cabeceraEtiqueta = input.required<string>();
  readonly cabeceraValor = input.required<string>();
  readonly conSigno = input(false);

  protected readonly t = TEXTOS;
  protected readonly id = `grafico-barras-${siguienteId++}`;
  protected readonly ancho = ANCHO;
  protected readonly altoFila = ALTO_FILA;
  protected readonly alto = computed(() => Math.max(1, this.barras().length) * ALTO_FILA);

  /** Posición x del eje 0: a la izquierda sin signo; en el centro de la zona de barras con signo. */
  protected readonly eje = computed(() =>
    this.conSigno() ? ETIQUETAS + (ANCHO - ETIQUETAS) / 2 : ETIQUETAS,
  );

  protected readonly geometria = computed(() => {
    const barras = this.barras();
    const maximo = Math.max(...barras.map((b) => Math.abs(b.valor)), Number.EPSILON);
    // Espacio para la barra más larga y su valor escrito al lado.
    const espacio = this.conSigno() ? (ANCHO - ETIQUETAS) / 2 - VALORES : ANCHO - ETIQUETAS - VALORES;
    const eje = this.eje();
    return barras.map((b) => {
      const ancho = (Math.abs(b.valor) / maximo) * espacio;
      const x = b.valor < 0 ? eje - ancho : eje;
      return {
        ...b,
        etiquetaCorta: b.etiqueta.length > 34 ? `${b.etiqueta.slice(0, 33)}…` : b.etiqueta,
        x,
        ancho,
        xTexto: b.valor < 0 ? x - 4 : x + ancho + 4,
      };
    });
  });
}
