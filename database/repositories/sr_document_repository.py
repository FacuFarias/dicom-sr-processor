from __future__ import annotations

import json
from types import SimpleNamespace

from config.settings import settings
from models.sr_document import SRDocument
from services.parser_versioning_service import should_mark_for_reprocessing


ALLOWED_STATUSES = {"received", "processed", "failed", "unsupported"}


def insert_sr_document(connection, sr_document: SRDocument) -> int:
    query = f"""
        INSERT INTO {settings.db_schema}.sr_document (
            sop_instance_uid,
            study_instance_uid,
            series_instance_uid,
            sop_class_uid,
            manufacturer,
            manufacturer_model_name,
            institution_name,
            station_name,
            software_versions,
            parser_key,
            parser_name,
            parser_family,
            parser_version,
            raw_metadata_json,
            status,
            received_at,
            processing_started_at,
            processing_finished_at,
            needs_reprocessing,
            processing_error
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s,
            COALESCE(%s, NOW()), %s, %s, %s, %s
        )
        RETURNING id;
    """

    with connection.cursor() as cursor:
        cursor.execute(
            query,
            (
                sr_document.sop_instance_uid,
                sr_document.study_instance_uid,
                sr_document.series_instance_uid,
                sr_document.sop_class_uid,
                sr_document.manufacturer,
                sr_document.manufacturer_model_name,
                sr_document.institution_name,
                sr_document.station_name,
                sr_document.software_versions,
                sr_document.parser_key,
                sr_document.parser_name,
                sr_document.parser_family,
                sr_document.parser_version,
                json.dumps(sr_document.raw_metadata_json, default=str),
                sr_document.status,
                sr_document.received_at,
                sr_document.processing_started_at,
                sr_document.processing_finished_at,
                sr_document.needs_reprocessing,
                sr_document.processing_error,
            ),
        )
        sr_document_id = cursor.fetchone()[0]

    return int(sr_document_id)


def update_sr_document_status(
    connection,
    sr_document_id: int,
    status: str,
    error_message: str | None = None,
) -> None:
    if status not in ALLOWED_STATUSES:
        raise ValueError(f"Estado inválido: {status}")

    query = f"""
        UPDATE {settings.db_schema}.sr_document
           SET status = %s,
               processing_error = COALESCE(%s, processing_error),
               processing_finished_at = NOW(),
               updated_at = NOW()
         WHERE id = %s;
    """

    with connection.cursor() as cursor:
        cursor.execute(query, (status, error_message, sr_document_id))


def mark_documents_for_reprocessing(
    connection,
    parser_family,
    new_version,
    compatibility_level: str = "compatible",
) -> int:
    query = f"""
        SELECT id, parser_family, parser_version, status
          FROM {settings.db_schema}.sr_document
         WHERE parser_family = %s
           AND parser_version IS NOT NULL
           AND status NOT IN ('failed', 'unsupported')
           AND COALESCE(needs_reprocessing, FALSE) = FALSE;
    """

    updated_ids: list[int] = []
    with connection.cursor() as cursor:
        cursor.execute(query, (parser_family,))
        rows = cursor.fetchall()

        latest_manifest = SimpleNamespace(
            parser_family=parser_family,
            parser_version=new_version,
            compatibility_level=compatibility_level,
            is_active=True,
        )

        for row in rows:
            doc = SimpleNamespace(
                id=row[0],
                parser_family=row[1],
                parser_version=row[2],
                status=row[3],
            )
            if should_mark_for_reprocessing(doc, latest_manifest):
                updated_ids.append(int(doc.id))

        if updated_ids:
            cursor.execute(
                f"""
                UPDATE {settings.db_schema}.sr_document
                   SET needs_reprocessing = TRUE,
                       updated_at = NOW()
                 WHERE id = ANY(%s);
                """,
                (updated_ids,),
            )

    return len(updated_ids)
