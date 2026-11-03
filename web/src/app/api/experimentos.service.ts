import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import { ExperimentoDetalle } from './tipos';

@Injectable({ providedIn: 'root' })
export class ExperimentosService {
  private readonly http = inject(HttpClient);

  detalle(id: string): Observable<ExperimentoDetalle> {
    return this.http.get<ExperimentoDetalle>(`/api/experimentos/${encodeURIComponent(id)}`);
  }
}
