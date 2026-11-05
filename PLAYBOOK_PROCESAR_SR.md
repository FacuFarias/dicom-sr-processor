# Playbook: "Procesame este SR"

Este documento define el procedimiento completo para cuando se solicita:

`procesame este SR`

Objetivo:
1. Crear parser nuevo (si no existe).
2. Registrar parser en `dicom_sr.parser_manifest`.
3. Procesar el archivo `.dcm`.
4. Generar variables mapeables genericas/contextuales en `dicom_sr.facility_variable_mapping`.
5. Publicar catalogo jerarquico (arbol) para seleccion de variables en criterios estructurados.

---

## 1) Prerrequisitos

- Proyecto: `/var/www/dicom_sr_processor`
- Entorno virtual activo: `.venv`
- DB: `pacsdb` (schema `dicom_sr`)

Comandos base:

```bash
cd /var/www/dicom_sr_processor
. .venv/bin/activate
```

---

## 2) Inspeccionar SR y resolver estrategia de parser

1. Revisar metadata y perfil:

```bash
python - <<'PY'
from dicom.dicom_reader import read_dicom_metadata
print(read_dicom_metadata('sr_examples/<archivo>.dcm'))
PY
```

2. Ver conceptos para detectar contexto clinico:

```bash
python - <<'PY'
import pydicom
from collections import Counter

p='sr_examples/<archivo>.dcm'
ds=pydicom.dcmread(p)
ctr=Counter()

def walk(seq):
    for item in seq or []:
        cns=getattr(item,'ConceptNameCodeSequence',None)
        if cns:
            c=cns[0]
            cv=str(getattr(c,'CodeValue',''))
            cs=str(getattr(c,'CodingSchemeDesignator',''))
            cm=str(getattr(c,'CodeMeaning',''))
            ctr[(cv,cs,cm)] += 1
        nested=getattr(item,'ContentSequence',None)
        if nested:
            walk(nested)

walk(getattr(ds,'ContentSequence',None))
for (cv,cs,cm),n in ctr.most_common(120):
    print(f'{cv}|{cs}|{cm}|{n}')
PY
```

3. Decidir:
- Si ya existe parser compatible, reutilizar.
- Si no, crear parser dedicado con nombre relacionado al estudio (por ejemplo `...Carotid...`).

---

## 3) Crear parser (si aplica)

Crear archivo en `parsers/`, ejemplo:

`parsers/ge_vivid_s70_carotid_sr_parser.py`

Plantilla minima:

```python
from __future__ import annotations

from parsers.base_parser import BaseSRParser


class GEVividS70CarotidSRParser(BaseSRParser):
    parser_name = "GEVividS70CarotidSRParser"
    parser_version = "1.0.0"
    parser_family = "ge_vivids70_carotid_sr"
    compatibility_level = "strict"
    is_active = True

    supported_manufacturers = ["ge_healthcare_ultrasound"]
    supported_institutions = ["cardiology_and_fitness"]
    supported_models = ["vivid_s70"]
    supported_sop_class_uids = ["1.2.840.10008.5.1.4.1.1.88.33"]
    supported_content_profiles = ["vascular_doppler_sr"]

    def parse(self, dataset):
        extracted = super().parse(dataset)
        return [
            v for v in extracted
            if v.concept_code_value is not None
            and v.value_type in {"NUM", "TEXT", "CODE", "CONTAINER"}
        ]
```

Opcional recomendado:
- Agregar test en `tests/test_sr_examples_parser_resolution.py` para asegurar que el SR nuevo resuelve al parser esperado.

---

## 4) Registrar parser en manifest

Importante: que exista archivo `.py` NO significa que aparezca en UI. Debe estar en tabla `parser_manifest`.

Registrar todos los parsers cargados:

```bash
python - <<'PY'
from database.connection import get_connection, ensure_schema
from core.parser_loader import load_parsers
from main import register_loaded_parsers

conn = get_connection()
try:
    ensure_schema(conn)
    register_loaded_parsers(conn, load_parsers())
    conn.commit()
finally:
    conn.close()
PY
```

Validar:

```bash
PGPASSWORD=pacs psql -h localhost -U pacs -d pacsdb -P pager=off -c \
"SELECT id, parser_name, parser_version, parser_family, is_active, updated_at
   FROM dicom_sr.parser_manifest
  ORDER BY updated_at DESC, id DESC;"
```

---

## 5) Procesar el SR

Esto inserta `sr_document` + `sr_extracted_variable`.

```bash
python main.py sr_examples/<archivo>.dcm
```

Validar estado:

```bash
PGPASSWORD=pacs psql -h localhost -U pacs -d pacsdb -P pager=off -c \
"SELECT id, sop_instance_uid, parser_family, parser_name, parser_version, status
   FROM dicom_sr.sr_document
  ORDER BY id DESC
  LIMIT 10;"
```

---

## 6) Generar variables mapeables (catalogo)

Construir referencia semantica y sincronizar `facility_variable_mapping`:

```bash
python scripts/build_variable_semantic_reference.py
```

Validar conteos por parser family:

```bash
PGPASSWORD=pacs psql -h localhost -U pacs -d pacsdb -P pager=off -c \
"SELECT source_type, count(*)
   FROM dicom_sr.facility_variable_mapping
  WHERE parser_family='<parser_family>'
    AND active=TRUE
  GROUP BY source_type
  ORDER BY source_type;"
```

Listar variables generadas:

```bash
PGPASSWORD=pacs psql -h localhost -U pacs -d pacsdb -P pager=off -c \
"SELECT canonical_name, concept_code_value, concept_code_scheme, source_type
   FROM dicom_sr.facility_variable_mapping
  WHERE parser_family='<parser_family>'
    AND active=TRUE
  ORDER BY canonical_name;"
```

Validar que existan los 3 `source_type` esperados de la infraestructura actual:

- `private_99gems`
- `standard_numeric`
- `standard_numeric_contextual`

---

## 7) Publicar catalogo para selector jerarquico (UI tipo arbol)

La pantalla de criterios estructurados usa endpoints de `structured_reports_controller.py`
para mostrar las variables en formato arbol, no lista plana.

Endpoints clave:

- `GET /api/structured-reports/parsers/<parser_manifest_id>/variables/tree`
- `GET /api/structured-reports/variables/nodes/<node_id>`
- `GET /api/structured-reports/variables/nodes/<node_id>/children`
- `POST /api/structured-reports/variables/resolve`

Comportamiento esperado:

1. El arbol agrupa por `source_type` y contexto clinico (vaso/segmento/lateralidad/traza).
2. Solo nodos hoja (`type=variable`) son seleccionables.
3. Al seleccionar una hoja se devuelve `variable_key` y metadatos (`unit`, `semantic_signature`).

Nota:

- Es normal ver nodos `NA` cuando el SR no trae un contexto clinico especifico.
- Es normal ver nodos numericos de traza (por ejemplo `2`, `3`, `7`) derivados de `ContentSequence[x]`.

---

## 8) Convencion de naming para reportes

Para variables contextuales usar formato:

`Vaso-Segmento-Lateralidad-Traza-Variable`

Ejemplo:

`Common Carotid Artery-Distal-Right-Traza-2-3-Peak Systolic Velocity`

Notas:
- `Traza` se deriva de la ruta `ContentSequence[x].ContentSequence[y]`.
- Si falta segmento en el SR, puede aparecer `NA` en esa posicion.

---

## 9) Checklist final de exito

- Parser existe en `parsers/*.py`.
- Parser visible en `dicom_sr.parser_manifest`.
- SR procesado con `status='processed'`.
- Existen filas para `parser_family` en `dicom_sr.facility_variable_mapping`.
- Variables contextuales siguen formato `Vaso-Segmento-Lateralidad-Traza-Variable`.
- El endpoint `.../variables/tree` devuelve nodos con `type=group` y `type=variable`.
- Criterios nuevos guardan `variable`, `variable_key`, `variable_node_id`, `variable_label`.

---

## 10) Comando rapido end-to-end

Reemplazar `<archivo>.dcm` y `<parser_family>`:

```bash
cd /var/www/dicom_sr_processor
. .venv/bin/activate

python - <<'PY'
from database.connection import get_connection, ensure_schema
from core.parser_loader import load_parsers
from main import register_loaded_parsers

conn = get_connection()
try:
    ensure_schema(conn)
    register_loaded_parsers(conn, load_parsers())
    conn.commit()
finally:
    conn.close()
PY

python main.py sr_examples/<archivo>.dcm
python scripts/build_variable_semantic_reference.py

PGPASSWORD=pacs psql -h localhost -U pacs -d pacsdb -P pager=off -c \
"SELECT source_type, count(*)
   FROM dicom_sr.facility_variable_mapping
  WHERE parser_family='<parser_family>'
    AND active=TRUE
  GROUP BY source_type
  ORDER BY source_type;"
```
