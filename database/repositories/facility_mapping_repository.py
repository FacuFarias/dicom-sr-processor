from __future__ import annotations

from config.settings import settings
from models.facility_variable_mapping import FacilityVariableMapping


def _row_to_mapping(row) -> FacilityVariableMapping:
    return FacilityVariableMapping(
        id=row[0],
        parser_family=row[1],
        parser_key=row[2],
        semantic_signature=row[3],
        source_type=row[4],
        concept_code_value=row[5],
        concept_code_scheme=row[6],
        concept_code_meaning=row[7],
        canonical_name=row[8],
        canonical_code=row[9],
        unit=row[10],
        facility_id=row[11],
        facility_name=row[12],
        facility_code=row[13],
        base_variable_id=row[14],
        use_for_runtime_mapping=row[15],
        active=row[16],
    )


def insert_facility_variable_mapping(connection, mapping: FacilityVariableMapping) -> int:
    query = f"""
        INSERT INTO {settings.db_schema}.facility_variable_mapping (
            parser_family,
            facility_id,
            parser_key,
            semantic_signature,
            source_type,
            concept_code_value,
            concept_code_scheme,
            concept_code_meaning,
            canonical_name,
            canonical_code,
            unit,
            facility_name,
            facility_code,
            base_variable_id,
            use_for_runtime_mapping,
            active
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id;
    """
    with connection.cursor() as cursor:
        cursor.execute(
            query,
            (
                mapping.parser_family,
                mapping.facility_id,
                mapping.parser_key,
                mapping.semantic_signature,
                mapping.source_type,
                mapping.concept_code_value,
                mapping.concept_code_scheme,
                mapping.concept_code_meaning,
                mapping.canonical_name,
                mapping.canonical_code,
                mapping.unit,
                mapping.facility_name,
                mapping.facility_code,
                mapping.base_variable_id,
                mapping.use_for_runtime_mapping,
                mapping.active,
            ),
        )
        return int(cursor.fetchone()[0])


def _matches_optional(expected, actual) -> bool:
    if expected in (None, ""):
        return True
    return str(expected) == str(actual)


def _score_mapping(mapping: FacilityVariableMapping) -> int:
    score = 0
    if mapping.facility_id:
        score += 20
    if mapping.semantic_signature:
        score += 10
    if mapping.parser_key:
        score += 8
    if mapping.concept_code_value:
        score += 6
    if mapping.concept_code_scheme:
        score += 4
    if mapping.unit:
        score += 2
    return score


def find_candidate_mappings(connection, facility_id, parser_key, extracted_variable) -> list:
    query = f"""
        SELECT id, parser_family, parser_key, semantic_signature, source_type,
               concept_code_value, concept_code_scheme, concept_code_meaning,
               canonical_name, canonical_code, unit,
            facility_id, facility_name, facility_code, base_variable_id,
            use_for_runtime_mapping,
               active
        FROM {settings.db_schema}.facility_variable_mapping
        WHERE active = true
        AND use_for_runtime_mapping = true
          AND parser_key = %s
          AND (facility_id = %s OR facility_id IS NULL);
    """

    with connection.cursor() as cursor:
        cursor.execute(
            query,
            (parser_key, str(facility_id) if facility_id is not None else None),
        )
        rows = cursor.fetchall()

    candidates = []
    for row in rows:
        mapping = _row_to_mapping(row)

        if not _matches_optional(
            mapping.concept_code_value,
            getattr(extracted_variable, "concept_code_value", None),
        ):
            continue

        if not _matches_optional(
            mapping.concept_code_scheme,
            getattr(extracted_variable, "concept_code_scheme", None),
        ):
            continue

        if not _matches_optional(
            mapping.unit,
            getattr(extracted_variable, "value_unit", None),
        ):
            continue

        candidates.append(mapping)

    candidates.sort(key=_score_mapping, reverse=True)

    deduped = []
    seen_signatures = set()
    for candidate in candidates:
        signature = candidate.semantic_signature or f"{candidate.id}"
        if signature in seen_signatures:
            continue
        seen_signatures.add(signature)
        deduped.append(candidate)

    return deduped
