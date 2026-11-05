# Clase tecnica: Como funciona `dicom_sr_processor`

## 1) Objetivo de esta clase

Este documento explica, de punta a punta, como funciona el sistema `dicom_sr_processor` para procesar DICOM Structured Reports (SR) en NextRIS.

Esta pensado para personas que:

- no conocen el proyecto,
- quieren entender la arquitectura real,
- necesitan operar, extender o depurar el flujo,
- van a trabajar en backend, frontend o base de datos.

Al terminar esta clase deberias poder:

1. Explicar que es un DICOM SR y por que no se procesa como texto simple.
2. Entender como el sistema elige parser automaticamente.
3. Entender como se extraen, normalizan y mapean variables.
4. Entender como se construye el catalogo semantico y el arbol de variables.
5. Entender como se guardan y evalunan criterios estructurados.
6. Depurar errores frecuentes en produccion.

---

## 2) Contexto: que problema resuelve

En imagenes medicas, los equipos (ultrasonido, ecocardio, vascular, etc.) generan reportes en formato DICOM SR.

Un SR no es un bloque de texto plano. Es un arbol de nodos clinicos con:

- conceptos codificados,
- valores numericos,
- unidades,
- modificadores de contexto (lado, segmento, sitio anatomico, etc.).

Si dos equipos distintos generan el mismo concepto clinico, la estructura y etiquetas pueden variar. Por eso se necesita:

1. Seleccionar parser correcto por perfil tecnico del SR.
2. Extraer todo de forma uniforme.
3. Construir una capa semantica estable para no depender de la ruta cruda del nodo.
4. Exponer variables en una UI usable para reglas/criterios.

---

## 3) Vista general de arquitectura

Sistema distribuido en 3 piezas principales:

1. `dicom_sr_processor` (motor SR standalone, Python)
2. `nextris-dev-react` (backend Flask API, endpoints SR)
3. `nextris-front-react` (frontend React, criterios y selector de variables)

Flujo de alto nivel:

1. Llega archivo `.dcm`.
2. Se lee metadata DICOM.
3. Se construye fingerprint.
4. Se cargan parsers dinamicamente.
5. Se elige parser por compatibilidad + scoring.
6. Se extraen variables SR recursivamente.
7. Se persisten `sr_document` y `sr_extracted_variable`.
8. Se construye base semantica (`sr_variable_semantic_reference`).
9. Se sincroniza catalogo mapeable (`facility_variable_mapping`).
10. Backend API construye arbol de variables para la UI.
11. Usuario crea criterios estructurados en frontend.

---

## 4) Fundamentos DICOM SR (minimo necesario)

### 4.1 `ContentSequence`

Es la columna vertebral del SR. Es un arbol anidado.

Ejemplo conceptual:

- Finding
  - Internal Carotid Artery
    - Peak Systolic Velocity = 125 cm/s
    - End Diastolic Velocity = 42 cm/s

### 4.2 `ConceptNameCodeSequence`

Define el concepto clinico codificado de cada nodo:

- `CodeValue`
- `CodingSchemeDesignator`
- `CodeMeaning`

### 4.3 `ValueType`

Tipo del valor del nodo:

- `NUM`, `TEXT`, `CODE`, `CONTAINER`, etc.

### 4.4 Unidades

En `NUM`, la unidad suele venir en `MeasurementUnitsCodeSequence`.

### 4.5 `dicom_path`

Ruta tecnica del nodo (`ContentSequence[4].ContentSequence[18]`).

Importante:

- sirve para trazabilidad,
- no siempre es estable entre estudios,
- no debe ser el unico identificador semantico.

---

## 5) Seleccion de parser (matching y scoring)

### 5.1 Carga dinamica de parsers

Los parsers viven en `parsers/*.py` y heredan de `BaseSRParser`.

Se cargan en runtime con `core/parser_loader.py`.

### 5.2 Fingerprint

`core/fingerprint.py` normaliza metadata y produce un fingerprint con:

- manufacturer
- institution_name
- manufacturer_model_name
- sop_class_uid
- content_profile

### 5.3 Compatibilidad del parser

Cada parser declara:

- `supported_manufacturers`
- `supported_institutions`
- `supported_models`
- `supported_sop_class_uids`
- `supported_content_profiles`

`*` actua como wildcard.

### 5.4 Scoring de especificidad

Resolver parser no es solo "primero que matchea". Se puntua:

- manufacturer: +4
- institution: +3
- model: +2
- sop_class_uid: +5
- content_profile: +1

Gana el parser compatible con mayor score.

---

## 6) Extraccion de variables

`parsers/base_parser.py` implementa recorrido recursivo del arbol:

1. Camina `ContentSequence`.
2. Construye `ExtractedVariable` por nodo.
3. Guarda:
   - concepto,
   - tipo,
   - valor,
   - unidad,
   - `dicom_path`,
   - `raw_item_json`.

Salida: lista uniforme de variables extraidas.

---

## 7) Persistencia principal en base de datos

Schema principal: `dicom_sr`.

### 7.1 `sr_document`

1 fila por SR procesado.

Campos tipicos:

- UIDs (`sop_instance_uid`, `study_instance_uid`, etc.)
- `parser_name`, `parser_family`, `parser_version`
- estado (`received`, `processed`, `unsupported`, `failed`)
- `processing_error`
- `raw_metadata_json`

### 7.2 `sr_extracted_variable`

1 fila por variable extraida.

Campos tipicos:

- concepto codificado
- `value_numeric` / `value_text`
- `value_unit`
- `dicom_path`
- relacion a `sr_document_id`

---

## 8) Capa semantica: por que existe y como se construye

Script clave:

- `scripts/build_variable_semantic_reference.py`

Construye `sr_variable_semantic_reference` y sincroniza `facility_variable_mapping`.

### 8.1 Tipos semanticos (`source_type`)

1. `private_99gems`
   - mediciones privadas GE por codigos 99GEMS.

2. `standard_numeric`
   - medicion numerica estandar (concepto + unidad + parser).

3. `standard_numeric_contextual`
   - medicion estandar + contexto clinico:
     - vaso,
     - segmento/topografia,
     - lateralidad,
     - traza,
     - modo de imagen.

### 8.2 `semantic_signature`

Es la firma estable de una variable semantica.

Se usa para:

- deduplicar,
- versionar,
- reconstruir mapas,
- enlazar variable extraida con referencia semantica.

### 8.3 Por que aparece `NA`

Si falta contexto en el SR, el label contextual usa `NA`.

Ejemplo:

- `NA-Proximal-Left-Traza-3-ICA/CCA velocity ratio`

No es error necesariamente. Es ausencia de contexto en el documento fuente.

### 8.4 Por que aparecen nodos `3`, `7`, etc.

Esos numeros reflejan posicion/traza derivada de la ruta de medicion.

- no son concepto clinico por si mismos,
- si ayudan a diferenciar mediciones repetidas en el mismo estudio.

---

## 9) Catalogo mapeable y runtime mapping

Tabla: `facility_variable_mapping`.

Contiene variables base para mapping por parser/facility.

Busqueda runtime (`variable_mapping_service.py`):

- filtra por `parser_key`, `facility_id` o global,
- compara concepto y unidad,
- puntua candidatos,
- devuelve estado:
  - `mapped`
  - `unmapped`
  - `ambiguous`

---

## 10) Criterios estructurados y arbol de variables

Este es el puente con la UI.

### 10.1 Endpoints relevantes (Flask)

Controlador:

- `nextris-dev-react/apps/home/controllers/structured_reports_controller.py`

Endpoints:

1. `GET /api/structured-reports/parsers/<parser_manifest_id>/variables/tree`
2. `GET /api/structured-reports/variables/nodes/<node_id>`
3. `GET /api/structured-reports/variables/nodes/<node_id>/children`
4. `POST /api/structured-reports/variables/resolve`

### 10.2 Estructura de nodo

Nodos de arbol:

- `type=group`: agrupadores (source_type/contexto)
- `type=variable`: hojas seleccionables

Metadata de hoja:

- `variable_key`
- `variable_name`
- `unit`
- `source_type`
- `semantic_signature`

### 10.3 Guardado de condicion (compatibilidad)

Al guardar criterio, cada condicion conserva:

- `variable` (legacy)
- `variable_key`
- `variable_node_id`
- `variable_label`
- `operator`
- `value` (+ `value_to` si between)

Esto evita romper criterios viejos mientras se usa la UI nueva de arbol.

---

## 11) Frontend SR: estructura y estilo

Archivo principal de criterios:

- `nextris-front-react/src/modules/reportes-estructurados/ConceptosCriteriosTab.tsx`

Archivo de servicios API:

- `nextris-front-react/src/services/criteria.service.ts`

### 11.1 UX del selector de variable

- arbol navegable (estilo n8n),
- expand/collapse,
- busqueda,
- seleccion de hoja,
- drag and drop al campo de condicion.

### 11.2 Restricciones de entrada

Campo variable:

- no editable manualmente,
- solo seleccion por arbol o drag/drop,
- boton `X` para limpiar variable completa.

### 11.3 Estilos importantes

- soporte dark mode real,
- contrastes legibles,
- control dual (variable + clear) en formato pill.

---

## 12) Ejemplo completo end-to-end

## 12.1 Procesar SR

```bash
cd /var/www/dicom_sr_processor
. .venv/bin/activate

python main.py sr_examples/1.2.840.113619.2.423.963336823046.1772718953.332.dcm
```

## 12.2 Reconstruir capa semantica

```bash
python scripts/build_variable_semantic_reference.py
```

## 12.3 Verificar conteos por `source_type`

```bash
PGPASSWORD=pacs psql -h localhost -U pacs -d pacsdb -P pager=off -c \
"SELECT source_type, count(*)
   FROM dicom_sr.facility_variable_mapping
  WHERE parser_family='ge_logiqf_vascular_sr'
    AND active=TRUE
  GROUP BY source_type
  ORDER BY source_type;"
```

## 12.4 Verificar arbol para frontend

```bash
curl -H "Authorization: Bearer <TOKEN>" \
  "http://localhost:5001/api/structured-reports/parsers/<PARSER_MANIFEST_ID>/variables/tree"
```

Esperado:

- nodos `group` y `variable`,
- hojas con `metadata.variable_key`.

---

## 13) Guia de extension: agregar parser nuevo

1. Inspeccionar SR real.
2. Crear parser en `parsers/`.
3. Definir `supported_*` y `supported_content_profiles`.
4. Registrar parser en manifest.
5. Procesar archivo.
6. Ejecutar `build_variable_semantic_reference.py`.
7. Verificar endpoints de arbol.
8. Crear/editar criterios en frontend.

Checklist rapido:

- parser resuelve bien,
- SR queda `processed`,
- `source_type` esperados existen,
- arbol se muestra en UI,
- criterio guarda `variable_node_id`.

---

## 14) Guia de debug (incidentes frecuentes)

### 14.1 "No aparece parser en UI"

Causa comun:

- parser en archivo `.py` pero no registrado en `parser_manifest`.

Accion:

- correr registro de parsers y validar tabla.

### 14.2 "No hay variables en el arbol"

Causas comunes:

- no se corrio `build_variable_semantic_reference.py`,
- parser_family sin filas activas en `facility_variable_mapping`,
- filtro de parser equivocado.

### 14.3 "Aparecen rutas NA"

No siempre es bug.

- puede faltar contexto real en SR,
- revisar si nodos `Finding Site`, `Laterality`, `Topographical Modifier` existen.

### 14.4 "Criterio no matchea"

Revisar:

- variable key usada por condicion,
- tipo de operador,
- valores numericos parseables,
- `between` con ambos limites.

---

## 15) Calidad y validacion

Minimo recomendado antes de merge:

1. Frontend:

```bash
cd /var/www/nextris-front-react
npm run build
```

2. Backend controller SR (sintaxis):

```bash
cd /var/www/nextris-dev-react
python3 -m py_compile apps/home/controllers/structured_reports_controller.py
```

3. Verificacion funcional:

- procesar 1 SR real,
- reconstruir semantica,
- ver arbol,
- crear criterio,
- evaluar criterio con payload de variables.

---

## 16) Preguntas de clase (para evaluar comprension)

1. Por que `dicom_path` no alcanza para identificar una variable clinica estable?
2. Diferencia exacta entre `standard_numeric` y `standard_numeric_contextual`.
3. Que problema resuelve `semantic_signature`?
4. Por que guardamos `variable` y `variable_node_id` al mismo tiempo?
5. Cuando un `NA` es esperable y cuando podria indicar bug?

---

## 17) Resumen final en una frase

`dicom_sr_processor` convierte un arbol DICOM SR heterogeneo en un sistema semantico estable, trazable y operable (DB + API + UI), permitiendo reglas clinicas estructuradas sin romper compatibilidad historica.
