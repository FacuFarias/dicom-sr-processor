# DICOM SR Processor

Procesador de DICOM Structured Reports con descubrimiento de parsers, extracción de variables, mapeo semántico, plantillas de informes y persistencia PostgreSQL.

## Instalación

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Completar la conexión a una base propia.
set -a
. ./.env
set +a
python main.py --help
```

`config/settings.py` lee variables del entorno. La base y los archivos DICOM no se incluyen en Git. Las migraciones están en `database/migrations/`; el procesador también configura su esquema mediante `ensure_schema`.

## Verificación sin base de datos

```bash
pip install -r requirements-dev.txt
python -m pytest tests/test_startup.py tests/test_parser_matching.py tests/test_sr_extraction.py -q
```

Los tests de persistencia/versionado/mapeo requieren una **base de pruebas separada** y pueden truncar tablas. Los tests de muestras SR requieren archivos locales que no se publican.

## Documentación

- `CLASE_DICOM_SR_PROCESSOR.md`
- `IMPLEMENTACION_TECNICA_DICOM_SR_PROCESSOR.md`
- `PLAYBOOK_PROCESAR_SR.md`
- `GUIA_FRONT_VARIABLE_DEFINITIONS.md`
