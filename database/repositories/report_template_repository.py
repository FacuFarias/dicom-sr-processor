from __future__ import annotations

from config.settings import settings
from models.report_template import ReportTemplate


def _row_to_template(row) -> ReportTemplate:
    return ReportTemplate(
        id=row[0],
        name=row[1],
        facility_id=row[2],
        parser_family=row[3],
        template_body=row[4],
        is_active=row[5],
    )


def insert_report_template(connection, template: ReportTemplate) -> int:
    query = f"""
        INSERT INTO {settings.db_schema}.report_template (
            name,
            facility_id,
            parser_family,
            template_body,
            is_active,
            created_at,
            updated_at
        ) VALUES (%s, %s, %s, %s, %s, NOW(), NOW())
        RETURNING id;
    """

    with connection.cursor() as cursor:
        cursor.execute(
            query,
            (
                template.name,
                template.facility_id,
                template.parser_family,
                template.template_body,
                template.is_active,
            ),
        )
        return int(cursor.fetchone()[0])


def get_active_template_for_parser_family(connection, facility_id: int, parser_family: str):
    query = f"""
        SELECT id, name, facility_id, parser_family, template_body, is_active
          FROM {settings.db_schema}.report_template
         WHERE facility_id = %s
           AND parser_family = %s
           AND is_active = TRUE
         ORDER BY id DESC
         LIMIT 1;
    """

    with connection.cursor() as cursor:
        cursor.execute(query, (facility_id, parser_family))
        row = cursor.fetchone()

    if row is None:
        return None
    return _row_to_template(row)


def save_rendered_report(connection, sr_document_id: int, template_id: int, rendered_text: str) -> int:
    query = f"""
        INSERT INTO {settings.db_schema}.sr_rendered_report (
            sr_document_id,
            template_id,
            rendered_text,
            created_at
        ) VALUES (%s, %s, %s, NOW())
        RETURNING id;
    """

    with connection.cursor() as cursor:
        cursor.execute(query, (sr_document_id, template_id, rendered_text))
        return int(cursor.fetchone()[0])
