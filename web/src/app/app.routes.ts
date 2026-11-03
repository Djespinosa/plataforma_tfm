import { Routes } from '@angular/router';

import { TEXTOS, tituloRuta } from './textos';
import { Carga } from './vistas/carga/carga';
import { Configuracion } from './vistas/configuracion/configuracion';
import { Evaluacion } from './vistas/evaluacion/evaluacion';
import { ExplicacionGlobal } from './vistas/explicacion-global/explicacion-global';
import { ExplicacionLocal } from './vistas/explicacion-local/explicacion-local';
import { Historial } from './vistas/historial/historial';
import { Inicio } from './vistas/inicio/inicio';
import { Lote } from './vistas/lote/lote';
import { Modelos } from './vistas/modelos/modelos';
import { NoEncontrada } from './vistas/no-encontrada/no-encontrada';
import { Prediccion } from './vistas/prediccion/prediccion';
import { Seguimiento } from './vistas/seguimiento/seguimiento';

/** Rutas de docs/diseno-web.md §3.1; data.paso es el paso del flujo (1-6) que se marca en la cabecera. */
export const routes: Routes = [
  { path: '', component: Inicio, title: tituloRuta(TEXTOS.inicio.titulo) },
  { path: 'datos', component: Carga, title: tituloRuta(TEXTOS.carga.titulo), data: { paso: 1 } },
  {
    path: 'datos/:conjunto/configuracion',
    component: Configuracion,
    title: tituloRuta(TEXTOS.configuracion.titulo),
    data: { paso: 2 },
  },
  { path: 'experimentos', component: Historial, title: tituloRuta(TEXTOS.historial.titulo) },
  {
    path: 'experimentos/:id',
    component: Seguimiento,
    title: tituloRuta(TEXTOS.seguimiento.titulo),
    data: { paso: 3 },
  },
  {
    path: 'experimentos/:id/evaluacion',
    component: Evaluacion,
    title: tituloRuta(TEXTOS.evaluacion.titulo),
    data: { paso: 4 },
  },
  { path: 'modelos', component: Modelos, title: tituloRuta(TEXTOS.modelos.titulo), data: { paso: 5 } },
  {
    path: 'modelos/:modelo/prediccion',
    component: Prediccion,
    title: tituloRuta(TEXTOS.prediccion.titulo),
    data: { paso: 5 },
  },
  { path: 'predicciones/:lote', component: Lote, title: tituloRuta(TEXTOS.lote.titulo), data: { paso: 5 } },
  {
    path: 'modelos/:modelo/explicacion',
    component: ExplicacionGlobal,
    title: tituloRuta(TEXTOS.explicacionGlobal.titulo),
    data: { paso: 6 },
  },
  {
    path: 'predicciones/:lote/filas/:fila',
    component: ExplicacionLocal,
    title: tituloRuta(TEXTOS.explicacionLocal.titulo),
    data: { paso: 6 },
  },
  { path: '**', component: NoEncontrada, title: tituloRuta(TEXTOS.noEncontrada.titulo) },
];
