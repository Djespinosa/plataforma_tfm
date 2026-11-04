# Modelo de datos (PostgreSQL 16)

6 tablas de `api/tablas.py`, creadas por la migración Alembic `0001_inicial` (una prueba compara columnas, claves e índices, y los CHECK por nombre). DDL que compila SQLAlchemy para PostgreSQL.

## `conjunto_datos`

```sql
CREATE TABLE conjunto_datos (
	id SERIAL NOT NULL,
	nombre_archivo TEXT NOT NULL,
	momento TEXT,
	ruta TEXT NOT NULL,
	sha256 VARCHAR(64) NOT NULL,
	n_filas INTEGER NOT NULL,
	n_columnas INTEGER NOT NULL,
	columnas JSONB NOT NULL,
	avisos JSONB NOT NULL,
	creado_en TIMESTAMP WITH TIME ZONE NOT NULL,
	CONSTRAINT pk_conjunto_datos PRIMARY KEY (id),
	CONSTRAINT ck_conjunto_datos_sha256 CHECK (length(sha256) = 64 AND trim(sha256, '0123456789abcdef') = '')
);
```

## `experimento`

```sql
CREATE TABLE experimento (
	id TEXT NOT NULL,
	origen TEXT NOT NULL,
	conjunto_id INTEGER,
	sha256_datos VARCHAR(64),
	cohorte_prueba_clave VARCHAR(64),
	descripcion TEXT,
	configuracion JSONB NOT NULL,
	estado TEXT NOT NULL,
	etapa TEXT,
	progreso JSONB,
	error TEXT,
	latido_en TIMESTAMP WITH TIME ZONE,
	creado_en TIMESTAMP WITH TIME ZONE NOT NULL,
	iniciado_en TIMESTAMP WITH TIME ZONE,
	terminado_en TIMESTAMP WITH TIME ZONE,
	duracion_s DOUBLE PRECISION,
	reproducibilidad JSONB,
	procedencia JSONB,
	evaluacion_prueba JSONB,
	reintento_de TEXT,
	CONSTRAINT pk_experimento PRIMARY KEY (id),
	CONSTRAINT ck_experimento_origen CHECK (origen IN ('web', 'importado')),
	CONSTRAINT ck_experimento_estado CHECK (estado IN ('en_cola', 'en_curso', 'completado', 'fallido', 'interrumpido')),
	CONSTRAINT ck_experimento_sha256_datos CHECK (length(sha256_datos) = 64 AND trim(sha256_datos, '0123456789abcdef') = ''),
	CONSTRAINT ck_experimento_evaluacion_prueba CHECK (evaluacion_prueba IS NULL OR (origen = 'web' AND estado = 'completado' AND conjunto_id IS NOT NULL AND sha256_datos IS NOT NULL AND cohorte_prueba_clave IS NOT NULL)),
	CONSTRAINT fk_experimento_conjunto_id FOREIGN KEY(conjunto_id) REFERENCES conjunto_datos (id),
	CONSTRAINT fk_experimento_reintento_de FOREIGN KEY(reintento_de) REFERENCES experimento (id)
);
CREATE UNIQUE INDEX uq_experimento_evaluacion_prueba ON experimento (sha256_datos, cohorte_prueba_clave) WHERE evaluacion_prueba IS NOT NULL;
```

## `modelo`

```sql
CREATE TABLE modelo (
	id SERIAL NOT NULL,
	experimento_id TEXT NOT NULL,
	momento TEXT,
	familia TEXT NOT NULL,
	ruta_paquete TEXT NOT NULL,
	sha256_paquete VARCHAR(64) NOT NULL,
	umbral DOUBLE PRECISION NOT NULL,
	metodo_calibracion TEXT,
	columnas JSONB NOT NULL,
	explicador TEXT NOT NULL,
	evaluacion JSONB NOT NULL,
	explicacion_global JSONB,
	creado_en TIMESTAMP WITH TIME ZONE NOT NULL,
	CONSTRAINT pk_modelo PRIMARY KEY (id),
	CONSTRAINT ck_modelo_explicador CHECK (explicador IN ('lineal', 'arbol', 'permutacion')),
	CONSTRAINT fk_modelo_experimento_id FOREIGN KEY(experimento_id) REFERENCES experimento (id)
);
```

## `lote_prediccion`

```sql
CREATE TABLE lote_prediccion (
	id SERIAL NOT NULL,
	modelo_id INTEGER NOT NULL,
	nombre_archivo TEXT NOT NULL,
	ruta TEXT NOT NULL,
	sha256 VARCHAR(64) NOT NULL,
	n_filas INTEGER NOT NULL,
	columna_id TEXT,
	columnas_ignoradas JSONB NOT NULL,
	umbral DOUBLE PRECISION NOT NULL,
	n_alertas INTEGER NOT NULL,
	creado_en TIMESTAMP WITH TIME ZONE NOT NULL,
	CONSTRAINT pk_lote_prediccion PRIMARY KEY (id),
	CONSTRAINT fk_lote_prediccion_modelo_id FOREIGN KEY(modelo_id) REFERENCES modelo (id)
);
```

## `prediccion`

```sql
CREATE TABLE prediccion (
	lote_id INTEGER NOT NULL,
	fila INTEGER NOT NULL,
	identificador TEXT,
	probabilidad DOUBLE PRECISION NOT NULL,
	alerta BOOLEAN NOT NULL,
	log_odds DOUBLE PRECISION NOT NULL,
	base_log_odds DOUBLE PRECISION NOT NULL,
	valores JSONB NOT NULL,
	CONSTRAINT pk_prediccion PRIMARY KEY (lote_id, fila),
	CONSTRAINT fk_prediccion_lote_id FOREIGN KEY(lote_id) REFERENCES lote_prediccion (id)
);
```

## `explicacion`

```sql
CREATE TABLE explicacion (
	lote_id INTEGER NOT NULL,
	fila INTEGER NOT NULL,
	contribuciones JSONB NOT NULL,
	explicador TEXT NOT NULL,
	error_aditividad DOUBLE PRECISION,
	creado_en TIMESTAMP WITH TIME ZONE NOT NULL,
	CONSTRAINT pk_explicacion PRIMARY KEY (lote_id, fila),
	CONSTRAINT fk_explicacion_prediccion FOREIGN KEY(lote_id, fila) REFERENCES prediccion (lote_id, fila),
	CONSTRAINT ck_explicacion_explicador CHECK (explicador IN ('lineal', 'arbol', 'permutacion'))
);
```

## Disparadores de la evaluación única en la cohorte de prueba (D-2)

Copiados de la migración `0001_inicial`. En SQLite (pruebas unitarias) hay disparadores equivalentes, con los mismos mensajes. Protegen frente a errores de la aplicación, no frente a un superusuario de la base de datos; otra cohorte que se solape por valores o un archivo modificado (otro SHA-256) sí permiten otra evaluación (limitaciones declaradas en `docs/diseno-api.md` §3).

```sql
CREATE FUNCTION evaluacion_prueba_unica() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'UPDATE' THEN
        IF NEW.id IS DISTINCT FROM OLD.id THEN
            RAISE EXCEPTION 'El identificador de un experimento no cambia nunca.'
                USING ERRCODE = 'check_violation';
        END IF;
    END IF;
    IF TG_OP <> 'INSERT' THEN
        IF OLD.evaluacion_prueba IS NOT NULL THEN
            IF TG_OP = 'DELETE' THEN
                RAISE EXCEPTION 'La evaluación en la cohorte de prueba ya se hizo; se usa una sola vez.'
                    USING ERRCODE = 'check_violation';
            END IF;
            IF NEW.evaluacion_prueba IS DISTINCT FROM OLD.evaluacion_prueba THEN
                RAISE EXCEPTION 'La evaluación en la cohorte de prueba ya se hizo; se usa una sola vez.'
                    USING ERRCODE = 'check_violation';
            END IF;
            IF NEW.configuracion IS DISTINCT FROM OLD.configuracion
               OR NEW.conjunto_id IS DISTINCT FROM OLD.conjunto_id
               OR NEW.sha256_datos IS DISTINCT FROM OLD.sha256_datos
               OR NEW.cohorte_prueba_clave IS DISTINCT FROM OLD.cohorte_prueba_clave THEN
                RAISE EXCEPTION 'El experimento ya se evaluó en la cohorte de prueba; su configuración y sus modelos no se pueden cambiar.'
                    USING ERRCODE = 'check_violation';
            END IF;
        END IF;
    END IF;
    IF TG_OP = 'DELETE' THEN
        RETURN OLD;
    END IF;
    -- Al evaluar (o crear ya evaluado). Si ya estaba evaluado, conjunto_id y sha256_datos no han cambiado (arriba) y el
    -- SHA-256 del conjunto tampoco (conjunto_datos_inmutable), así que solo puede fallar en la transición NULL -> no NULL.
    -- Con sha256_datos o conjunto_id NULL, «<>» no es cierto y quien rechaza es el CHECK evaluacion_prueba.
    IF NEW.evaluacion_prueba IS NOT NULL
       AND NEW.sha256_datos <> (SELECT sha256 FROM conjunto_datos WHERE id = NEW.conjunto_id) THEN
        RAISE EXCEPTION 'El SHA-256 de los datos del experimento no coincide con el de su conjunto de datos; no se puede evaluar en la cohorte de prueba.'
            USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END
$$;
CREATE TRIGGER evaluacion_prueba_unica BEFORE INSERT OR UPDATE OR DELETE ON experimento
FOR EACH ROW EXECUTE FUNCTION evaluacion_prueba_unica();
```

```sql
CREATE FUNCTION modelo_evaluado_congelado() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP <> 'INSERT' THEN
        IF EXISTS (SELECT 1 FROM experimento WHERE id = OLD.experimento_id AND evaluacion_prueba IS NOT NULL) THEN
            RAISE EXCEPTION 'El experimento ya se evaluó en la cohorte de prueba; su configuración y sus modelos no se pueden cambiar.'
                USING ERRCODE = 'check_violation';
        END IF;
    END IF;
    IF TG_OP = 'DELETE' THEN
        RETURN OLD;
    END IF;
    IF EXISTS (SELECT 1 FROM experimento WHERE id = NEW.experimento_id AND evaluacion_prueba IS NOT NULL) THEN
        RAISE EXCEPTION 'El experimento ya se evaluó en la cohorte de prueba; su configuración y sus modelos no se pueden cambiar.'
            USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END
$$;
CREATE TRIGGER modelo_evaluado_congelado BEFORE INSERT OR UPDATE OR DELETE ON modelo
FOR EACH ROW EXECUTE FUNCTION modelo_evaluado_congelado();
```

```sql
CREATE FUNCTION conjunto_datos_inmutable() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.ruta IS DISTINCT FROM OLD.ruta OR NEW.sha256 IS DISTINCT FROM OLD.sha256 THEN
        RAISE EXCEPTION 'La ruta y el SHA-256 de un conjunto de datos no cambian nunca.'
            USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END
$$;
CREATE TRIGGER conjunto_datos_inmutable BEFORE UPDATE ON conjunto_datos
FOR EACH ROW EXECUTE FUNCTION conjunto_datos_inmutable();
```
