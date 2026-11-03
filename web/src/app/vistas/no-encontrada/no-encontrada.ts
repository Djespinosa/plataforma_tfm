import { Component } from '@angular/core';
import { RouterLink } from '@angular/router';

import { TEXTOS } from '../../textos';

@Component({
  selector: 'app-no-encontrada',
  imports: [RouterLink],
  template: `
    <h1 tabindex="-1">{{ t.noEncontrada.titulo }}</h1>
    <p>{{ t.noEncontrada.texto }}</p>
    <p><a routerLink="/">{{ t.noEncontrada.volver }}</a></p>
  `,
})
export class NoEncontrada {
  protected readonly t = TEXTOS;
}
