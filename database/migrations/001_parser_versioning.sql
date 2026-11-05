CREATE SCHEMA IF NOT EXISTS dicom_sr;

CREATE TABLE IF NOT EXISTS dicom_sr.parser_manifest (
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
    UNIQUE (parser_name, parser_version)
);

ALTER TABLE dicom_sr.sr_document
    ADD COLUMN IF NOT EXISTS parser_name TEXT,
    ADD COLUMN IF NOT EXISTS parser_family TEXT,
    ADD COLUMN IF NOT EXISTS processing_started_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS processing_finished_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS needs_reprocessing BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS processing_error TEXT;
