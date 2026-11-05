from __future__ import annotations

from contextlib import closing

from config.settings import settings

try:
    import psycopg2
except ImportError as exc:  # pragma: no cover
    psycopg2 = None
    _import_error = exc
else:
    _import_error = None


def get_connection():
    if psycopg2 is None:
        raise RuntimeError(
            "psycopg2 no está instalado en el entorno actual"
        ) from _import_error

    try:
        connection = psycopg2.connect(
            host=settings.db_host,
            port=settings.db_port,
            dbname=settings.db_name,
            user=settings.db_user,
            password=settings.db_pass,
        )
    except Exception as exc:
        raise RuntimeError(f"No se pudo conectar a PostgreSQL: {exc}") from exc

    connection.autocommit = False
    return connection


def ensure_schema(connection) -> None:
    schema = settings.db_schema

    with closing(connection.cursor()) as cursor:
        cursor.execute(f"CREATE SCHEMA IF NOT EXISTS {schema};")

        cursor.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {schema}.sr_document (
                id BIGSERIAL PRIMARY KEY,
                sop_instance_uid TEXT UNIQUE,
                study_instance_uid TEXT,
                series_instance_uid TEXT,
                sop_class_uid TEXT,
                manufacturer TEXT,
                manufacturer_model_name TEXT,
                institution_name TEXT,
                station_name TEXT,
                software_versions TEXT,
                parser_key TEXT,
                parser_name TEXT,
                parser_family TEXT,
                parser_version TEXT,
                raw_metadata_json JSONB,
                status TEXT NOT NULL DEFAULT 'received',
                processing_error TEXT,
                processing_started_at TIMESTAMPTZ,
                processing_finished_at TIMESTAMPTZ,
                needs_reprocessing BOOLEAN NOT NULL DEFAULT FALSE,
                received_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );
            """
        )

        cursor.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {schema}.sr_extracted_variable (
                id BIGSERIAL PRIMARY KEY,
                sr_document_id BIGINT NOT NULL REFERENCES {schema}.sr_document(id) ON DELETE CASCADE,
                dicom_tag TEXT,
                dicom_description TEXT,
                dicom_path TEXT,
                concept_code_value TEXT,
                concept_code_scheme TEXT,
                concept_code_meaning TEXT,
                facility_description TEXT,
                value_text TEXT,
                value_numeric NUMERIC,
                value_unit TEXT,
                value_datetime TIMESTAMPTZ,
                value_json JSONB,
                sequence_index INTEGER,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );
            """
        )

        cursor.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {schema}.variable_definition (
                id BIGSERIAL PRIMARY KEY,
                canonical_code TEXT UNIQUE NOT NULL,
                canonical_name TEXT NOT NULL,
                unit TEXT,
                value_type TEXT,
                description TEXT,
                active BOOLEAN NOT NULL DEFAULT TRUE,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );
            """
        )

        def table_exists(table_name: str) -> bool:
            cursor.execute(
                """
                SELECT 1
                  FROM information_schema.tables
                 WHERE table_schema = %s
                   AND table_name = %s
                 LIMIT 1;
                """,
                (schema, table_name),
            )
            return cursor.fetchone() is not None

        def column_exists(table_name: str, column_name: str) -> bool:
            cursor.execute(
                """
                SELECT 1
                  FROM information_schema.columns
                 WHERE table_schema = %s
                   AND table_name = %s
                   AND column_name = %s
                 LIMIT 1;
                """,
                (schema, table_name, column_name),
            )
            return cursor.fetchone() is not None

        if (
            table_exists("facility_variable_mapping")
            and column_exists("facility_variable_mapping", "canonical_variable_definition_id")
            and column_exists("facility_variable_mapping", "dicom_path_pattern")
        ):
            cursor.execute(f"DROP TABLE {schema}.facility_variable_mapping CASCADE;")

        if not column_exists("sr_extracted_variable", "canonical_variable_definition_id"):
            cursor.execute(
                f"""
                ALTER TABLE {schema}.sr_extracted_variable
                ADD COLUMN canonical_variable_definition_id BIGINT NULL REFERENCES {schema}.variable_definition(id);
                """
            )

        cursor.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {schema}.parser_manifest (
                id BIGSERIAL PRIMARY KEY,
                parser_name TEXT NOT NULL,
                parser_version TEXT NOT NULL,
                parser_family TEXT NOT NULL,
                compatibility_level TEXT NOT NULL,
                is_active BOOLEAN NOT NULL DEFAULT TRUE,
                supported_manufacturers JSONB NOT NULL DEFAULT '[]'::jsonb,
                supported_institutions JSONB NOT NULL DEFAULT '[]'::jsonb,
                supported_models JSONB NOT NULL DEFAULT '[]'::jsonb,
                supported_sop_class_uids JSONB NOT NULL DEFAULT '[]'::jsonb,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                UNIQUE(parser_name, parser_version)
            );
            """
        )

        cursor.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {schema}.report_template (
                id BIGSERIAL PRIMARY KEY,
                name TEXT NOT NULL,
                facility_id BIGINT NOT NULL,
                parser_family TEXT NOT NULL,
                template_body TEXT NOT NULL,
                is_active BOOLEAN NOT NULL DEFAULT TRUE,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );
            """
        )

        cursor.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {schema}.sr_rendered_report (
                id BIGSERIAL PRIMARY KEY,
                sr_document_id BIGINT NOT NULL REFERENCES {schema}.sr_document(id) ON DELETE CASCADE,
                template_id BIGINT NOT NULL REFERENCES {schema}.report_template(id) ON DELETE CASCADE,
                rendered_text TEXT NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );
            """
        )

        cursor.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {schema}.sr_variable_semantic_reference (
                id BIGSERIAL PRIMARY KEY,
                semantic_signature TEXT NOT NULL UNIQUE,
                parser_family TEXT,
                parser_key TEXT,
                source_type TEXT NOT NULL,
                parent_path_pattern TEXT,
                sample_dicom_path TEXT,
                concept_code_value TEXT,
                concept_code_scheme TEXT,
                concept_code_meaning TEXT,
                parameter_id TEXT,
                preferred_display_name TEXT,
                parameter_attribute TEXT,
                study_type TEXT,
                resolved_label TEXT,
                unit TEXT,
                first_seen_sr_document_id BIGINT REFERENCES {schema}.sr_document(id) ON DELETE SET NULL,
                last_seen_sr_document_id BIGINT REFERENCES {schema}.sr_document(id) ON DELETE SET NULL,
                sample_numeric_variable_id BIGINT REFERENCES {schema}.sr_extracted_variable(id) ON DELETE SET NULL,
                occurrence_count BIGINT NOT NULL DEFAULT 1,
                active BOOLEAN NOT NULL DEFAULT TRUE,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );
            """
        )

        cursor.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {schema}.sr_extracted_variable_semantic_map (
                id BIGSERIAL PRIMARY KEY,
                sr_extracted_variable_id BIGINT NOT NULL UNIQUE REFERENCES {schema}.sr_extracted_variable(id) ON DELETE CASCADE,
                semantic_reference_id BIGINT NOT NULL REFERENCES {schema}.sr_variable_semantic_reference(id) ON DELETE CASCADE,
                semantic_signature TEXT NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );
            """
        )

        if table_exists("parser_mappable_variable") and not table_exists("facility_variable_mapping"):
            cursor.execute(
                f"""
                ALTER TABLE {schema}.parser_mappable_variable
                RENAME TO facility_variable_mapping;
                """
            )

        cursor.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {schema}.facility_variable_mapping (
                id BIGSERIAL PRIMARY KEY,
                parser_family TEXT NOT NULL,
                parser_key TEXT,
                semantic_signature TEXT NOT NULL,
                source_type TEXT,
                concept_code_value TEXT,
                concept_code_scheme TEXT,
                concept_code_meaning TEXT,
                canonical_name TEXT NOT NULL,
                canonical_code TEXT,
                unit TEXT,
                facility_id VARCHAR(45) NULL,
                facility_name TEXT,
                facility_code TEXT,
                base_variable_id BIGINT NULL REFERENCES {schema}.facility_variable_mapping(id) ON DELETE CASCADE,
                use_for_runtime_mapping BOOLEAN NOT NULL DEFAULT TRUE,
                active BOOLEAN NOT NULL DEFAULT TRUE,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );
            """
        )

        if not column_exists("facility_variable_mapping", "parser_key"):
            cursor.execute(
                f"""
                ALTER TABLE {schema}.facility_variable_mapping
                ADD COLUMN parser_key TEXT;
                """
            )

        if not column_exists("facility_variable_mapping", "use_for_runtime_mapping"):
            cursor.execute(
                f"""
                ALTER TABLE {schema}.facility_variable_mapping
                ADD COLUMN use_for_runtime_mapping BOOLEAN NOT NULL DEFAULT TRUE;
                """
            )

        if column_exists("facility_variable_mapping", "facility_id"):
            cursor.execute(
                f"""
                ALTER TABLE {schema}.facility_variable_mapping
                ALTER COLUMN facility_id TYPE VARCHAR(45)
                USING facility_id::VARCHAR(45);
                """
            )

        cursor.execute(
            f"""
            UPDATE {schema}.facility_variable_mapping fvm
               SET parser_key = ref.parser_key
              FROM {schema}.sr_variable_semantic_reference ref
             WHERE fvm.semantic_signature = ref.semantic_signature
               AND (fvm.parser_key IS NULL OR fvm.parser_key = '');
            """
        )

        cursor.execute(
            f"""
            CREATE UNIQUE INDEX IF NOT EXISTS ux_{schema}_fvm_base
            ON {schema}.facility_variable_mapping(parser_family, semantic_signature)
            WHERE facility_id IS NULL;
            """
        )

        cursor.execute(
            f"""
            CREATE UNIQUE INDEX IF NOT EXISTS ux_{schema}_fvm_facility
            ON {schema}.facility_variable_mapping(parser_family, semantic_signature, facility_id)
            WHERE facility_id IS NOT NULL;
            """
        )

        if not column_exists("sr_variable_semantic_reference", "parent_path_pattern"):
            cursor.execute(
                f"""
                ALTER TABLE {schema}.sr_variable_semantic_reference
                ADD COLUMN parent_path_pattern TEXT;
                """
            )

        if not column_exists("sr_variable_semantic_reference", "sample_dicom_path"):
            cursor.execute(
                f"""
                ALTER TABLE {schema}.sr_variable_semantic_reference
                ADD COLUMN sample_dicom_path TEXT;
                """
            )

        if not column_exists("sr_document", "parser_name"):
            cursor.execute(
                f"""
                ALTER TABLE {schema}.sr_document
                ADD COLUMN parser_name TEXT;
                """
            )
        if not column_exists("sr_document", "parser_family"):
            cursor.execute(
                f"""
                ALTER TABLE {schema}.sr_document
                ADD COLUMN parser_family TEXT;
                """
            )
        if not column_exists("sr_document", "processing_started_at"):
            cursor.execute(
                f"""
                ALTER TABLE {schema}.sr_document
                ADD COLUMN processing_started_at TIMESTAMPTZ;
                """
            )
        if not column_exists("sr_document", "processing_finished_at"):
            cursor.execute(
                f"""
                ALTER TABLE {schema}.sr_document
                ADD COLUMN processing_finished_at TIMESTAMPTZ;
                """
            )
        if not column_exists("sr_document", "needs_reprocessing"):
            cursor.execute(
                f"""
                ALTER TABLE {schema}.sr_document
                ADD COLUMN needs_reprocessing BOOLEAN NOT NULL DEFAULT FALSE;
                """
            )
