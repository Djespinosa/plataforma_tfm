import { Component, input } from '@angular/core';

/** El aviso_decision de la respuesta, al pie de cada vista de resultados (docs/diseno-web.md §6). */
@Component({
  selector: 'app-pie-decision',
  template: `<footer class="pie-decision"><p>{{ texto() }}</p></footer>`,
})
export class PieDecision {
  readonly texto = input.required<string>();
}
