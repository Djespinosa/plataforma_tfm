import { Component, computed, input } from '@angular/core';

import { TEXTOS } from '../textos';

export type TipoAviso = 'informacion' | 'cautela' | 'error';

/**
 * Aviso con icono y título de texto (nunca solo color, docs/diseno-web.md §7). Los errores llevan role="alert"; el resto,
 * role="note". El contenido (texto de la API o de textos.ts) va proyectado.
 */
@Component({
  selector: 'app-aviso',
  template: `
    <div class="aviso" [class]="'aviso aviso-' + tipo()" [attr.role]="tipo() === 'error' ? 'alert' : 'note'">
      <p class="aviso-titulo"><span aria-hidden="true">{{ icono() }}</span> {{ titulo() }}</p>
      <div class="aviso-cuerpo"><ng-content /></div>
    </div>
  `,
})
export class Aviso {
  readonly tipo = input<TipoAviso>('informacion');
  protected readonly titulo = computed(() => TEXTOS.avisos[this.tipo()]);
  protected readonly icono = computed(() => ({ informacion: 'ℹ', cautela: '⚠', error: '✖' })[this.tipo()]);
}
