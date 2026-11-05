# Estructura base para resolver a qué variable corresponde cada valor numérico SR

## Objetivo
Disponer de una base semántica donde un valor numérico extraído (por ejemplo `ContentSequence[4].ContentSequence[18]`) se resuelva a una variable clínica identificable.

## Tabla creada
Se creó la tabla:

- `dicom_sr.sr_variable_semantic_reference`

Campos clave:

- `semantic_signature` (única): firma estable para identificar la variable semántica.
- `source_type`: `private_99gems`, `standard_numeric` o `standard_numeric_contextual`.
- `parser_family`, `parser_key`.
- `parameter_id`, `preferred_display_name`, `parameter_attribute`, `study_type` (contexto GE privado).
- `resolved_label`: etiqueta resultante.
- `unit`.
- `parent_path_pattern`, `sample_dicom_path` (trazabilidad por ruta DICOM).
- `sample_numeric_variable_id`.
- `occurrence_count`.

## Cómo se llena
Script:

- `scripts/build_variable_semantic_reference.py`

Construcción:

1. Para GE privado (`43128` + `99GEMS`):
   - Busca hermanos del mismo bloque padre.
   - Usa `43131` (parameter_id), `43133` (display name), `43130` (attribute), `43145` (study type), unidad.
   - Genera firma semántica y etiqueta resuelta.

2. Para numéricos estándar:
   - Usa `concept_code_value/scheme/meaning` + unidad + parser.

3. Para numéricos estándar contextuales:
   - Usa `concept_code_*` + unidad + parser + contexto clínico.
   - Contexto típico: vaso, segmento/topografía, lateralidad, traza, modo de imagen.

4. Upsert por `semantic_signature` para actualizar ocurrencias.

## Relación con selector jerárquico (UI)

La infraestructura actual de criterios estructurados no consume solo una lista plana.

- El backend construye un arbol de nodos (`group`/`variable`) a partir de `source_type` y etiquetas contextuales.
- La UI selecciona un nodo hoja y guarda:
  - `variable` (legacy)
  - `variable_key`
  - `variable_node_id`
  - `variable_label`

Esto permite navegación tipo n8n y compatibilidad con criterios previos.

## Ejecución
Desde la raíz del proyecto:

- `DB_HOST=localhost DB_PORT=5432 DB_NAME=pacsdb DB_USER=pacs DB_PASS=pacs .venv/bin/python scripts/build_variable_semantic_reference.py`

## Ejemplo validado
Para la fila `sr_extracted_variable.id = 74`:

- `dicom_path`: `ContentSequence[4].ContentSequence[18]`
- `parameter_id`: `SP/2D/ThyroidDistH`
- `preferred_display_name`: `H`
- `parameter_attribute`: `Side=Rt`
- `study_type`: `SmallParts/2D/ThyroidVolume`

Se resolvió contra `sr_variable_semantic_reference.id = 3` con:

- `resolved_label = H`
- `parent_path_pattern = ContentSequence[*]`

## Nota de diseño
La ruta exacta (`ContentSequence[4].ContentSequence[18]`) no es estable entre estudios. Por eso la firma semántica se construye con contexto clínico/técnico del bloque y no solo con índice de ruta.

Notas adicionales de infraestructura actual:

- Ver nodos `NA` en el arbol es válido cuando el SR no trae una dimensión contextual (ejemplo: lateralidad o segmento).
- Ver nodos numéricos (ejemplo `3`, `7`) también es válido: representan índices de traza derivados de `ContentSequence`.
