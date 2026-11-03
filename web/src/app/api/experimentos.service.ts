import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import { CuerpoExperimento, Evaluacion, ExperimentoDetalle, ValidacionExperimento } from './tipos';

@Injectable({ providedIn: 'root' })
export class ExperimentosService {
  private readonly http = inject(HttpClient);

  validar(cuerpo: CuerpoExperimento): Observable<ValidacionExperimento> {
    return this.http.post<ValidacionExperimento>('/api/experimentos/validacion', cuerpo);
  }

  /** POST /api/experimentos → 202 con el experimento en cola. */
  crear(cuerpo: CuerpoExperimento): Observable<ExperimentoDetalle> {
    return this.http.post<ExperimentoDetalle>('/api/experimentos', cuerpo);
  }

  detalle(id: string): Observable<ExperimentoDetalle> {
    return this.http.get<ExperimentoDetalle>(`/api/experimentos/${encodeURIComponent(id)}`);
  }

  evaluacion(id: string): Observable<Evaluacion> {
    return this.http.get<Evaluacion>(`/api/experimentos/${encodeURIComponent(id)}/evaluacion`);
  }
}
