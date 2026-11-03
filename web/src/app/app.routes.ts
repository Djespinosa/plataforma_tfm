import { Routes } from '@angular/router';

import { TEXTOS, tituloRuta } from './textos';
import { Inicio } from './vistas/inicio/inicio';
import { NoEncontrada } from './vistas/no-encontrada/no-encontrada';

/** Rutas de docs/diseno-web.md §3.1; data.paso es el paso del flujo (1-6) que se marca en la cabecera. */
export const routes: Routes = [
  { path: '', component: Inicio, title: tituloRuta(TEXTOS.inicio.titulo) },
  { path: '**', component: NoEncontrada, title: tituloRuta(TEXTOS.noEncontrada.titulo) },
];
