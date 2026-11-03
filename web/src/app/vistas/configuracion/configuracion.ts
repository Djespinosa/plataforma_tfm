import {
  Component,
  DestroyRef,
  ElementRef,
  Injector,
  OnInit,
  afterNextRender,
  computed,
  inject,
  input,
  signal,
} from '@angular/core';
import { takeUntilDestroyed, toSignal } from '@angular/core/rxjs-interop';
import { FormControl, NonNullableFormBuilder, ReactiveFormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { map } from 'rxjs';

import { ConjuntosService } from '../../api/conjuntos.service';
import { ErrorLegible, leerError } from '../../api/errores';
import { ExperimentosService } from '../../api/experimentos.service';
import { Columna, Conjunto, CuerpoExperimento, ValidacionExperimento } from '../../api/tipos';
import { Aviso } from '../../comun/aviso';
import { miles, porcentaje1 } from '../../formato';
import { TEXTOS, nombreModelo, textoValidacion } from '../../textos';

/** Con más valores distintos, la clase positiva se escribe (la API solo da los 20 más frecuentes). */
const MAX_VALORES_LISTADOS = 20;

@Component({
  selector: 'app-configuracion',
  imports: [ReactiveFormsModule, Aviso],
  templateUrl: './configuracion.html',
})
export class Configuracion implements OnInit {
  /** Id del conjunto (parámetro de la ruta). */
  readonly conjunto = input.required<string>();

  protected readonly t = TEXTOS;
  protected readonly miles = miles;
  protected readonly porcentaje1 = porcentaje1;
  protected readonly nombreModelo = nombreModelo;
  protected readonly maxValores = MAX_VALORES_LISTADOS;
  protected readonly datos = signal<Conjunto | null>(null);
  protected readonly errorCarga = signal<ErrorLegible | null>(null);
  protected readonly error = signal<ErrorLegible | null>(null);
  protected readonly comprobando = signal(false);
  protected readonly enviando = signal(false);
  /** Última respuesta de /validacion y el cuerpo (JSON) con que se pidió. */
  protected readonly resultado = signal<{ cuerpo: string; esquema: ValidacionExperimento } | null>(null);

  protected readonly form = inject(NonNullableFormBuilder).group({
    objetivo: '',
    clasePositiva: '',
    columnaGrupo: '',
    cohorteModo: 'ninguna' as 'ninguna' | 'valores' | 'aleatoria',
    cohorteColumna: '',
    cohorteValores: [[] as string[]],
    excluidas: [[] as string[]],
    sensibles: [[] as string[]],
    presupuesto: 'completo' as 'completo' | 'demostracion',
    descripcion: '',
  });

  protected readonly valor = toSignal(this.form.valueChanges.pipe(map(() => this.form.getRawValue())), {
    initialValue: this.form.getRawValue(),
  });

  /** Columnas que se pueden elegir como grupo, excluidas o sensibles: todas menos la objetivo. */
  protected readonly otras = computed(() =>
    (this.datos()?.columnas ?? []).filter((c) => c.nombre !== this.valor().objetivo));

  protected readonly columnaObjetivo = computed(() => this.columna(this.valor().objetivo));
  protected readonly columnaCohorte = computed(() => this.columna(this.valor().cohorteColumna));

  /** Cuerpo de la petición con los valores actuales del formulario (docs/diseno-api.md §4.2). */
  protected readonly cuerpo = computed<CuerpoExperimento>(() => {
    const v = this.valor();
    return {
      conjunto_id: Number(this.conjunto()),
      objetivo: v.objetivo,
      clase_positiva: v.clasePositiva,
      excluidas: v.excluidas,
      sensibles: v.sensibles,
      columna_grupo: v.columnaGrupo || null,
      cohorte_prueba:
        v.cohorteModo === 'aleatoria'
          ? { modo: 'aleatoria' }
          : v.cohorteModo === 'valores'
            ? { modo: 'valores', columna: v.cohorteColumna, valores: v.cohorteValores }
            : null,
      presupuesto: v.presupuesto,
      descripcion: v.descripcion.trim() || null,
    };
  });

  /** El esquema mostrado corresponde a la configuración actual: solo entonces se puede entrenar. */
  protected readonly vigente = computed(() => this.resultado()?.cuerpo === JSON.stringify(this.cuerpo()));

  private readonly conjuntos = inject(ConjuntosService);
  private readonly experimentos = inject(ExperimentosService);
  private readonly router = inject(Router);
  private readonly destruir = inject(DestroyRef);
  private readonly inyector = inject(Injector);
  private readonly elemento = inject<ElementRef<HTMLElement>>(ElementRef);

  constructor() {
    // Al cambiar el objetivo: la clase positiva anterior ya no vale y el objetivo no puede ser grupo, excluido ni
    // sensible (422 de la API); al cambiar la columna de la cohorte, sus valores tampoco.
    const c = this.form.controls;
    c.objetivo.valueChanges.pipe(takeUntilDestroyed()).subscribe((objetivo) => {
      c.clasePositiva.setValue('');
      for (const columna of [c.columnaGrupo, c.cohorteColumna]) if (columna.value === objetivo) columna.setValue('');
      for (const lista of [c.excluidas, c.sensibles]) lista.setValue(lista.value.filter((n) => n !== objetivo));
    });
    c.cohorteColumna.valueChanges.pipe(takeUntilDestroyed()).subscribe(() => c.cohorteValores.setValue([]));
  }

  ngOnInit(): void {
    this.conjuntos
      .detalle(Number(this.conjunto()))
      .pipe(takeUntilDestroyed(this.destruir))
      .subscribe({ next: (d) => this.datos.set(d), error: (e) => this.errorCarga.set(leerError(e)) });
  }

  protected marcado(control: FormControl<string[]>, valor: string): boolean {
    return control.value.includes(valor);
  }

  protected alternar(control: FormControl<string[]>, valor: string, evento: Event): void {
    const marcar = (evento.target as HTMLInputElement).checked;
    control.setValue(marcar ? [...control.value, valor] : control.value.filter((v) => v !== valor));
  }

  protected comprobar(): void {
    const cuerpo = this.cuerpo();
    if (!cuerpo.objetivo || !cuerpo.clase_positiva) {
      this.error.set({ mensaje: this.t.configuracion.faltaObjetivo, detalles: [] });
      return;
    }
    const cohorte = cuerpo.cohorte_prueba;
    if (cohorte?.modo === 'valores' && (!cohorte.columna || !cohorte.valores.length)) {
      this.error.set({ mensaje: this.t.configuracion.faltanValores, detalles: [] });
      return;
    }
    this.comprobando.set(true);
    this.error.set(null);
    this.resultado.set(null);
    this.experimentos
      .validar(cuerpo)
      .pipe(takeUntilDestroyed(this.destruir))
      .subscribe({
        next: (esquema) => {
          this.resultado.set({ cuerpo: JSON.stringify(cuerpo), esquema });
          this.comprobando.set(false);
          // El esquema aparece debajo del formulario: el foco va a su título para que se anuncie (como en la carga).
          afterNextRender(() => this.elemento.nativeElement.querySelector<HTMLElement>('#esquema')?.focus(),
            { injector: this.inyector });
        },
        error: (e) => {
          this.error.set(leerError(e));
          this.comprobando.set(false);
        },
      });
  }

  protected entrenar(): void {
    const resultado = this.resultado();
    if (!resultado || !this.vigente()) return;
    this.enviando.set(true);
    this.error.set(null);
    this.experimentos
      .crear(JSON.parse(resultado.cuerpo) as CuerpoExperimento)
      .pipe(takeUntilDestroyed(this.destruir))
      .subscribe({
        next: (e) => void this.router.navigate(['/experimentos', e.id]),
        error: (e) => {
          this.error.set(leerError(e));
          this.enviando.set(false);
        },
      });
  }

  protected textoValidacion(v: ValidacionExperimento['validacion']): string {
    return textoValidacion(v.tipo, v.k);
  }

  private columna(nombre: string): Columna | null {
    return this.datos()?.columnas.find((c) => c.nombre === nombre) ?? null;
  }
}
