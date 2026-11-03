import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import { Estado } from './tipos';

@Injectable({ providedIn: 'root' })
export class EstadoService {
  private readonly http = inject(HttpClient);

  estado(): Observable<Estado> {
    return this.http.get<Estado>('/api/estado');
  }
}
