import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import { Lote, LoteCreado } from './tipos';

@Injectable({ providedIn: 'root' })
export class PrediccionesService {
  private readonly http = inject(HttpClient);

  /** POST /api/modelos/{id}/predicciones con los campos «archivo» y, si se indica, «columna_id». */
  predecir(modeloId: number, archivo: File, columnaId: string): Observable<LoteCreado> {
    const datos = new FormData();
    datos.append('archivo', archivo);
    if (columnaId.trim()) datos.append('columna_id', columnaId.trim());
    return this.http.post<LoteCreado>(`/api/modelos/${modeloId}/predicciones`, datos);
  }

  lote(id: number): Observable<Lote> {
    return this.http.get<Lote>(`/api/predicciones/${id}`);
  }
}
