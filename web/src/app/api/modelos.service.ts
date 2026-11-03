import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import { ExplicacionGlobal, Modelo, ModeloDetalle } from './tipos';

@Injectable({ providedIn: 'root' })
export class ModelosService {
  private readonly http = inject(HttpClient);

  listar(): Observable<Modelo[]> {
    return this.http.get<Modelo[]>('/api/modelos');
  }

  detalle(id: number): Observable<ModeloDetalle> {
    return this.http.get<ModeloDetalle>(`/api/modelos/${id}`);
  }

  explicacionGlobal(id: number): Observable<ExplicacionGlobal> {
    return this.http.get<ExplicacionGlobal>(`/api/modelos/${id}/explicacion-global`);
  }
}
