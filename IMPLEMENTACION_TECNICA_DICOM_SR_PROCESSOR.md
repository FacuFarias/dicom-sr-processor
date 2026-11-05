# Implementación técnica: `dicom_sr_processor`

## 1) Resumen ejecutivo

Se construyó un backend modular para procesar DICOM Structured Reports (SR) con enfoque **plugin-based** para parsers, persistencia en PostgreSQL, normalización por facility y control de versionado/reproceso.

El sistema ahora cubre de extremo a extremo:

1. Carga dinámica de parsers desde carpeta.
2. Lectura de metadatos y dataset DICOM.
3. Construcción de fingerprint para selección automática de parser.
4. Extracción recursiva de variables desde `ContentSequence`.
5. Mapeo canónico por facility (mapeada/no mapeada/ambigua).
6. Persistencia transaccional de documento + variables.
7. Registro de manifiestos de parser en BD.
8. Marcado de documentos para reproceso ante nuevas versiones de parser.
9. Publicación de catálogo jerárquico de variables para criterios estructurados (UI tipo árbol).

---

## 2) Arquitectura implementada

### Núcleo de procesamiento

- `main.py`
  - Orquesta el pipeline completo de procesamiento.
  - Permite ejecutar flujo normal por archivo.
  - Incluye modo de chequeo de reproceso: `--check-reprocessing`.

- `core/fingerprint.py`
  - Normaliza metadatos y genera `parser_key`.
  - Estrategia de normalización:
    - `lower()`
    - `strip()`
    - espacios -> `_`
    - fallback a `unknown`

- `core/parser_loader.py`
  - Descubre parsers dinámicamente en `parsers/`.
  - Resuelve parser por scoring de especificidad:
    - manufacturer: +4
    - institution: +3
    - model: +2
    - sop class uid: +5
  - Soporta wildcard `*` (habilita match sin sumar score).
  - Expone utilidades de manifiestos (`get_parser_manifests`).

### Capa DICOM

- `dicom/dicom_reader.py`
  - `read_dicom_dataset(filepath)`
  - `read_dicom_metadata(filepath)`
  - Manejo de errores claro para archivo inexistente/inválido.

### Capa de parsers

- `parsers/base_parser.py`
  - Metadata base obligatoria de parser:
    - `parser_name`
    - `parser_version`
    - `parser_family`
    - `compatibility_level`
    - `is_active`
    - listas de soporte por fabricante/institución/modelo/SOP
  - `can_parse(...)` con criterios de compatibilidad y wildcard.
  - `get_manifest()` serializable para catálogo de parsers.
  - Extracción SR recursiva reusable:
    - recorre `ContentSequence` anidado
    - detecta `ConceptNameCodeSequence`
    - detecta `ValueType`, `TextValue`, `NumericValue`, `MeasuredValueSequence`, `MeasurementUnitsCodeSequence`
    - construye `dicom_path` por nodo
    - devuelve lista homogénea de `ExtractedVariable`

- `parsers/example_parser.py`
  - Parser activo de ejemplo con metadatos reales.
  - Usa extracción base (`super().parse(...)`).

---

## 3) Modelos implementados

### `models/extracted_variable.py`

Modelo uniforme para variables SR extraídas y enriquecidas:

- Campos DICOM crudos:
  - `dicom_tag`, `dicom_description`, `dicom_path`
  - `concept_code_value`, `concept_code_scheme`, `concept_code_meaning`
  - `value_type`, `value_text`, `value_numeric`, `value_unit`, `value_datetime`
  - `sequence_index`, `raw_value`, `raw_item_json`

- Campos de normalización/mapping:
  - `canonical_variable_definition_id`
  - `canonical_code`
  - `canonical_name`
  - `facility_description`
  - `mapping_status` (`mapped`, `unmapped`, `ambiguous`)

- Utilidades:
  - `to_dict()`
  - `__str__()` legible

### `models/sr_document.py`

Documento SR persistible con trazabilidad:

- Identidad/metadatos SR:
  - `sop_instance_uid`, `study_instance_uid`, `series_instance_uid`, `sop_class_uid`
  - `manufacturer`, `manufacturer_model_name`, `institution_name`, `station_name`, `software_versions`

- Trazabilidad parser:
  - `parser_key`
  - `parser_name`
  - `parser_family`
  - `parser_version`

- Estado de proceso:
  - `status` (`received`, `processed`, `failed`, `unsupported`)
  - `processing_started_at`
  - `processing_finished_at`
  - `needs_reprocessing`
  - `processing_error`

- Payload:
  - `raw_metadata_json`

### `models/variable_definition.py`

Definición canónica de variable:

- `canonical_code`, `canonical_name`, `unit`, `value_type`, `description`, `active`

### `models/facility_variable_mapping.py`

Reglas de mapping por facility:

- `facility_id`, `parser_key`
- `concept_code_value`, `concept_code_scheme`
- `dicom_path_pattern`
- `canonical_variable_definition_id`
- `facility_description`, `active`

### `models/parser_manifest.py`

Catálogo/versionado de parser:

- `parser_name`, `parser_version`, `parser_family`
- criterios de soporte
- `compatibility_level`, `is_active`
- `to_dict()`, `equals(...)`, `__str__()`

---

## 4) Persistencia en PostgreSQL

### Conexión y schema

- `database/connection.py`
  - `get_connection()` con `autocommit=False`.
  - `ensure_schema(connection)` idempotente.
  - Crea/ajusta tablas del schema `dicom_sr`.

### Tablas gestionadas

- `dicom_sr.sr_document`
- `dicom_sr.sr_extracted_variable`
- `dicom_sr.variable_definition`
- `dicom_sr.facility_variable_mapping`
- `dicom_sr.parser_manifest`
- `dicom_sr.sr_variable_semantic_reference`
- `dicom_sr.sr_extracted_variable_semantic_map`
- `dicom_sr.structured_criteria`

### Migración

- `database/migrations/001_parser_versioning.sql`
  - Crea `parser_manifest`.
  - Añade columnas de trazabilidad/versionado a `sr_document`.

### Repositorios

- `database/repositories/sr_document_repository.py`
  - `insert_sr_document(...)`
  - `update_sr_document_status(...)`
  - `mark_documents_for_reprocessing(...)`

- `database/repositories/sr_variable_repository.py`
  - `insert_extracted_variables(...)`
  - Guarda columnas tipadas + `value_json` complementario.

- `database/repositories/variable_definition_repository.py`
  - CRUD lógico de definiciones canónicas activas.

- `database/repositories/facility_mapping_repository.py`
  - búsqueda de candidatos por facility/parser/concept/path.
  - `insert_facility_variable_mapping(...)`.

- `database/repositories/parser_repository.py`
  - `upsert_parser_manifest(...)`
  - `get_parser_manifest(...)`
  - `list_active_parsers(...)`
  - `get_latest_parser_version(...)`

---

## 5) Servicios de dominio

### Mapping de variables

- `services/variable_mapping_service.py`
  - `map_extracted_variables(connection, facility_id, parser_key, variables)`

Reglas:

- 1 candidato -> `mapped` + rellena canónico/facility.
- 0 candidatos -> `unmapped`.
- >1 candidato -> `ambiguous` sin asignación automática.

### Versionado de parser

- `services/parser_versioning_service.py`
  - `compare_versions(current_version, new_version)`
    - `-1`: new > current
    - `0`: iguales
    - `1`: current > new
  - `should_mark_for_reprocessing(document, latest_manifest)`
    - marca solo si:
      - misma `parser_family`
      - nueva versión mayor
      - parser nuevo activo
      - compatibilidad distinta de `legacy`

### Criterios estructurados y selector jerárquico

- Controlador API: `apps/home/controllers/structured_reports_controller.py`
- Endpoints principales:
  - `GET /api/structured-reports/parsers/<parser_manifest_id>/variables/tree`
  - `GET /api/structured-reports/variables/nodes/<node_id>`
  - `GET /api/structured-reports/variables/nodes/<node_id>/children`
  - `POST /api/structured-reports/variables/resolve`

Contrato operativo actual:

- El frontend consume un árbol de nodos `group`/`variable`.
- Solo nodos `variable` se pueden seleccionar en una condición.
- Al guardar una condición se preserva compatibilidad legacy y metadatos nuevos:
  - `variable` (legacy key)
  - `variable_key`
  - `variable_node_id`
  - `variable_label`

---

## 6) Flujo principal implementado

Pipeline en `main.py` (modo normal):

1. Leer archivo SR (`read_dicom_dataset`).
2. Extraer metadata (`read_dicom_metadata`).
3. Construir fingerprint (`build_fingerprint`).
4. Cargar parsers dinámicos (`load_parsers`).
5. Registrar manifiestos en BD (`upsert_parser_manifest`).
6. Resolver parser por matching/scoring.
7. Insertar `sr_document` con estado inicial y trazabilidad parser/version.
8. Si no hay parser:
   - estado `unsupported`
   - commit
9. Si hay parser:
   - extraer variables SR
   - mapear por facility
   - guardar variables enriquecidas
  - opcional: construir base semántica y sincronizar catálogo jerárquico para criterios
   - marcar documento `processed`
   - commit
10. Ante error:
    - rollback
    - intentar marcar `failed` con `processing_error`

Modo reproceso:

- `python main.py --check-reprocessing`
  - carga/registro de parsers actuales
  - compara con históricos
  - marca `needs_reprocessing=true` cuando corresponde

---

## 7) Logging incorporado

Se agregaron logs de ejecución para visibilidad operacional:

- archivo recibido
- parsers cargados / parsers registrados
- parser seleccionado y versión
- fingerprint
- cantidades de variables:
  - extraídas
  - mapeadas
  - no mapeadas
  - ambiguas
  - guardadas
- estado final del documento
- errores de procesamiento
- cantidad de documentos marcados para reproceso

---

## 8) Pruebas automatizadas implementadas

### `tests/test_parser_matching.py`

Valida selección de parser por fingerprint y prioridad de parser específico.

### `tests/test_sr_extraction.py`

Valida extracción SR recursiva:

- presencia de lista
- extracción de concepto
- extracción numérica/unidad
- generación de `dicom_path`
- robustez sin `ContentSequence`

### `tests/test_persistence.py`

Valida persistencia transaccional de documentos y variables, estados y JSON.

### `tests/test_variable_mapping.py`

Valida mapping por facility:

- caso mapped
- caso unmapped
- caso ambiguous
- refinamiento por `dicom_path_pattern`

### `tests/test_parser_versioning.py`

Valida versionado/reproceso:

- comparación semántica de versión
- marcado de reproceso por versión mayor
- exclusión por `legacy`
- persistencia de parser manifest
- trazabilidad `parser_name/family/version` en `sr_document`

Resultado actual de validación:

- `22 passed`

---

## 9) Comandos útiles

### Procesar archivo SR

```bash
python main.py /ruta/archivo_sr.dcm --facility-id 1
```

### Revisar reprocesamiento

```bash
python main.py --check-reprocessing
```

### Ejecutar tests

```bash
pytest tests/test_parser_matching.py tests/test_sr_extraction.py tests/test_persistence.py tests/test_variable_mapping.py tests/test_parser_versioning.py
```

---

## 10) Estado funcional alcanzado

Con esta implementación el proyecto quedó preparado para escalar en tres dimensiones:

1. **Escalabilidad de parsers**: nuevos parsers en archivos independientes sin tocar el core.
2. **Normalización clínica**: separación entre dato DICOM crudo, definición canónica y etiqueta facility.
3. **Gobernanza y evolución**: versionado de parser, trazabilidad de procesamiento y estrategia de reproceso controlada.

En términos prácticos, el sistema ya permite operar en modo productivo técnico para ingesta SR, con persistencia auditable, reglas explícitas de compatibilidad y base sólida para evolución incremental.
