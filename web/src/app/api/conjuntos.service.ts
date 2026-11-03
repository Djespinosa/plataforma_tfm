import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import { Conjunto, ConjuntoResumen } from './tipos';

@Injectable({ providedIn: 'root' })
export class ConjuntosService {
  private readonly http = inject(HttpClient);

  /** POST /api/conjuntos con los campos «archivo» y, si se indica, «momento». */
  subir(archivo: File, momento: string): Observable<Conjunto> {
    const datos = new FormData();
    datos.append('archivo', archivo);
    if (momento.trim()) datos.append('momento', momento.trim());
    return this.http.post<Conjunto>('/api/conjuntos', datos);
  }

  listar(): Observable<ConjuntoResumen[]> {
    return this.http.get<ConjuntoResumen[]>('/api/conjuntos');
  }

  detalle(id: number): Observable<Conjunto> {
    return this.http.get<Conjunto>(`/api/conjuntos/${id}`);
  }
}
