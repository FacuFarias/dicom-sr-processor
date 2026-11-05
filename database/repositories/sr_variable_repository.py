from __future__ import annotations

import json
from decimal import Decimal, InvalidOperation

from config.settings import settings


def _safe_decimal(value):
    if value is None or value == "":
        return None

    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None


def insert_extracted_variables(connection, sr_document_id: int, variables) -> int:
    query = f"""
        INSERT INTO {settings.db_schema}.sr_extracted_variable (
            sr_document_id,
            canonical_variable_definition_id,
            dicom_tag,
            dicom_description,
            dicom_path,
            concept_code_value,
            concept_code_scheme,
            concept_code_meaning,
            facility_description,
            value_text,
            value_numeric,
            value_unit,
            value_datetime,
            value_json,
            sequence_index,
            created_at
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, NOW()
        );
    """

    inserted = 0
    with connection.cursor() as cursor:
        for variable in variables:
            value_json = {
                "raw_value": getattr(variable, "raw_value", None),
                "value_type": getattr(variable, "value_type", None),
                "raw_item_json": getattr(variable, "raw_item_json", None),
                "mapping_status": getattr(variable, "mapping_status", None),
                "canonical_code": getattr(variable, "canonical_code", None),
                "canonical_name": getattr(variable, "canonical_name", None),
            }

            cursor.execute(
                query,
                (
                    sr_document_id,
                    getattr(variable, "canonical_variable_definition_id", None),
                    getattr(variable, "dicom_tag", None),
                    getattr(variable, "dicom_description", None),
                    getattr(variable, "dicom_path", None),
                    getattr(variable, "concept_code_value", None),
                    getattr(variable, "concept_code_scheme", None),
                    getattr(variable, "concept_code_meaning", None),
                    getattr(variable, "facility_description", None),
                    getattr(variable, "value_text", None),
                    _safe_decimal(getattr(variable, "value_numeric", None)),
                    getattr(variable, "value_unit", None),
                    getattr(variable, "value_datetime", None),
                    json.dumps(value_json, default=str),
                    getattr(variable, "sequence_index", None),
                ),
            )
            inserted += 1

    return inserted
