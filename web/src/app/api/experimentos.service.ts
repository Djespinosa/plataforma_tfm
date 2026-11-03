import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import {
  CuerpoExperimento,
  Evaluacion,
  ExperimentoDetalle,
  EvaluacionPrueba,
  ExperimentoHistorial,
  ValidacionExperimento,
} from './tipos';

@Injectable({ providedIn: 'root' })
export class ExperimentosService {
  private readonly http = inject(HttpClient);

  historial(): Observable<ExperimentoHistorial[]> {
    return this.http.get<ExperimentoHistorial[]>('/api/experimentos');
  }

  validar(cuerpo: CuerpoExperimento): Observable<ValidacionExperimento> {
    return this.http.post<ValidacionExperimento>('/api/experimentos/validacion', cuerpo);
  }

  /** POST /api/experimentos → 202 con el experimento en cola. */
  crear(cuerpo: CuerpoExperimento): Observable<ExperimentoDetalle> {
    return this.http.post<ExperimentoDetalle>('/api/experimentos', cuerpo);
  }

  /** POST /api/experimentos/{id}/evaluacion-prueba con la confirmación explícita (§4.7). */
  evaluarPrueba(id: string): Observable<EvaluacionPrueba> {
    return this.http.post<EvaluacionPrueba>(`/api/experimentos/${encodeURIComponent(id)}/evaluacion-prueba`, {
      confirmar: true,
    });
  }

  /** POST /api/experimentos/{id}/reintentar → 202 con el experimento nuevo. */
  reintentar(id: string): Observable<ExperimentoDetalle> {
    return this.http.post<ExperimentoDetalle>(`/api/experimentos/${encodeURIComponent(id)}/reintentar`, null);
  }

  detalle(id: string): Observable<ExperimentoDetalle> {
    return this.http.get<ExperimentoDetalle>(`/api/experimentos/${encodeURIComponent(id)}`);
  }

  evaluacion(id: string): Observable<Evaluacion> {
    return this.http.get<Evaluacion>(`/api/experimentos/${encodeURIComponent(id)}/evaluacion`);
  }
}
