# Procedimiento usado para crear parsers de todos los SR en `sr_examples`

## Referencia rápida (flujo completo actual)

Para el flujo operativo completo cuando se solicita `procesame este SR` (crear parser, registrar en manifest, procesar SR y generar variables mapeables), usar:

- `PLAYBOOK_PROCESAR_SR.md`

## Resultado final
Se cubrieron los 3 archivos de `/var/www/dicom_sr_processor/sr_examples` con parsers seleccionados automáticamente:

- `1.2.840.113619.2.423.963336823046.1772652344.1390.dcm` → `GELogiqFMyCarePrivateParamsSRParser`
- `1.2.840.113619.2.423.963336823046.1772718953.332.dcm` → `GELogiqFMyCareSRParser`
- `1.2.840.113619.2.423.963336823046.1772805879.160.dcm` → `GELogiqFMyCareSRParser`

---

## 1) Inventario inicial de SRs
Se listaron los archivos de ejemplo y se inspeccionó metadato clave (`Manufacturer`, `InstitutionName`, `ManufacturerModelName`, `SOPClassUID`) y conceptos SR.

Hallazgo:
- Los 3 SR comparten la misma huella técnica base (GE + MyCare + LOGIQF + Comprehensive SR).
- Pero existen **2 perfiles de contenido**:
  - `ge_us_private_params` (con conceptos privados `99GEMS` predominantes)
  - `vascular_doppler_sr` (con conceptos LN clínicos como `11726-7` y `11653-3`)

---

## 2) Problema de diseño detectado
Con la arquitectura anterior, el matching usaba solo:
- manufacturer
- institution
- model
- SOPClassUID

Como esos 4 campos eran iguales en los 3 archivos, no se podían diferenciar parsers por tipo de contenido.

---

## 3) Solución aplicada
Se agregó un discriminador de contenido: `content_profile`.

### Cambios implementados

1. **Detección de perfil SR** en metadata
   - Archivo: `dicom/dicom_reader.py`
   - Regla:
     - Si aparecen conceptos LN `11726-7` y `11653-3` → `vascular_doppler_sr`
     - Si no, pero hay esquema `99GEMS` → `ge_us_private_params`
     - Si no aplica → `generic_sr`

2. **Fingerprint extendido**
   - Archivo: `core/fingerprint.py`
   - Se agrega `content_profile` al fingerprint (sin romper `parser_key` existente).

3. **Matching de parser extendido**
   - Archivo: `parsers/base_parser.py`
   - Nuevo atributo opcional: `supported_content_profiles = ["*"]`.
   - `can_parse()` ahora también evalúa `content_profile`.

4. **Scoring de selección actualizado**
   - Archivo: `core/parser_loader.py`
   - Se incorpora `content_profile` al score para desempatar parsers con misma huella técnica.

5. **Parser nuevo para perfil privado**
   - Archivo nuevo: `parsers/ge_logiqf_mycare_private_params_sr_parser.py`
   - Clase: `GELogiqFMyCarePrivateParamsSRParser`
   - `supported_content_profiles = ["ge_us_private_params"]`

6. **Parser vascular ajustado**
   - Archivo: `parsers/ge_logiqf_mycare_sr_parser.py`
   - `parser_version` subió a `1.1.0`
   - `supported_content_profiles = ["vascular_doppler_sr"]`

---

## 4) Validación realizada

### Tests de matching y cobertura real
- `tests/test_parser_matching.py` (actualizado)
- `tests/test_sr_examples_parser_resolution.py` (nuevo)

Ejecuciones:
- `pytest -q tests/test_parser_matching.py tests/test_sr_examples_parser_resolution.py`
- Resultado: `8 passed`

### Regresión completa
- `pytest -q`
- Resultado: `32 passed`

### Verificación directa por archivo
Se ejecutó script de resolución para los 3 `.dcm` y confirmó parser esperado por cada uno.

---

## 5) Archivos modificados/creados

### Modificados
- `dicom/dicom_reader.py`
- `core/fingerprint.py`
- `parsers/base_parser.py`
- `core/parser_loader.py`
- `parsers/ge_logiqf_mycare_sr_parser.py`
- `tests/test_parser_matching.py`

### Nuevos
- `parsers/ge_logiqf_mycare_private_params_sr_parser.py`
- `tests/test_sr_examples_parser_resolution.py`

---

## 6) Cómo repetir este procedimiento para nuevos SR

1. Copiar nuevos `.dcm` a `sr_examples/`.
2. Ejecutar inspección de conceptos para detectar nuevos perfiles.
3. Si el SR comparte huella técnica pero cambia semántica, crear nuevo `content_profile`.
4. Crear parser con `supported_content_profiles` específico.
5. Agregar test de resolución por archivo real.
6. Ejecutar `pytest -q` completo.

---

## 7) Nota operativa
Este enfoque evita crear parsers “por archivo” (no escalable) y crea parsers “por perfil clínico de contenido”, que sí permite mapear correctamente SR nuevos del mismo tipo en producción.

## 8) Infraestructura vigente posterior a este procedimiento

Además del matching de parser por `content_profile`, la infraestructura actual contempla:

1. Generación de `source_type` mixto en catálogo:
   - `private_99gems`
   - `standard_numeric`
   - `standard_numeric_contextual`
2. Publicación de árbol de variables para criterios estructurados:
   - nodos `group` y `variable`
   - selección de hoja con `variable_key`
3. Persistencia de condiciones de criterio con campos nuevos:
   - `variable_node_id`
   - `variable_label`
   - manteniendo `variable` como compatibilidad legacy

Referencia operativa completa:

- `PLAYBOOK_PROCESAR_SR.md`
