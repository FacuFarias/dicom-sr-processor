from __future__ import annotations

from dataclasses import dataclass
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config.settings import settings
from database.connection import ensure_schema, get_connection


@dataclass
class SemanticCandidate:
    semantic_signature: str
    parser_family: str | None
    parser_key: str | None
    source_type: str
    parent_path_pattern: str | None
    sample_dicom_path: str | None
    concept_code_value: str | None
    concept_code_scheme: str | None
    concept_code_meaning: str | None
    parameter_id: str | None
    preferred_display_name: str | None
    parameter_attribute: str | None
    study_type: str | None
    resolved_label: str | None
    unit: str | None
    first_seen_sr_document_id: int | None
    last_seen_sr_document_id: int | None
    sample_numeric_variable_id: int | None
    occurrence_count: int


def _normalize_text(value: str | None) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _path_to_pattern(path: str | None) -> str | None:
    if path is None:
        return None
    return re.sub(r"\[[0-9]+\]", "[*]", path)


def _build_private_signature(
    parser_family: str | None,
    parser_key: str | None,
    parameter_id: str | None,
    parameter_attribute: str | None,
    study_type: str | None,
    unit: str | None,
) -> str:
    parts = [
        "private_99gems",
        _normalize_text(parser_family).lower(),
        _normalize_text(parser_key).lower(),
        _normalize_text(parameter_id).lower(),
        _normalize_text(parameter_attribute).lower(),
        _normalize_text(study_type).lower(),
        _normalize_text(unit).lower(),
    ]
    return "|".join(parts)


def _build_standard_signature(
    parser_family: str | None,
    parser_key: str | None,
    concept_code_value: str | None,
    concept_code_scheme: str | None,
    concept_code_meaning: str | None,
    unit: str | None,
) -> str:
    parts = [
        "standard_numeric",
        _normalize_text(parser_family).lower(),
        _normalize_text(parser_key).lower(),
        _normalize_text(concept_code_value).lower(),
        _normalize_text(concept_code_scheme).lower(),
        _normalize_text(concept_code_meaning).lower(),
        _normalize_text(unit).lower(),
    ]
    return "|".join(parts)


def _build_standard_contextual_signature(
    parser_family: str | None,
    parser_key: str | None,
    concept_code_value: str | None,
    concept_code_scheme: str | None,
    concept_code_meaning: str | None,
    unit: str | None,
    vascular_structure: str | None,
    topographical_modifier: str | None,
    laterality: str | None,
    trace_label: str | None,
    image_mode: str | None,
) -> str:
    parts = [
        "standard_numeric_contextual",
        _normalize_text(parser_family).lower(),
        _normalize_text(parser_key).lower(),
        _normalize_text(concept_code_value).lower(),
        _normalize_text(concept_code_scheme).lower(),
        _normalize_text(concept_code_meaning).lower(),
        _normalize_text(vascular_structure).lower(),
        _normalize_text(topographical_modifier).lower(),
        _normalize_text(laterality).lower(),
        _normalize_text(trace_label).lower(),
        _normalize_text(image_mode).lower(),
        _normalize_text(unit).lower(),
    ]
    return "|".join(parts)


def _build_standard_contextual_label(
    vascular_structure: str | None,
    topographical_modifier: str | None,
    laterality: str | None,
    trace_label: str | None,
    concept_code_meaning: str | None,
) -> str:
    # Canonical key requested for report generation: Vaso-Segmento-Lateralidad-Traza-Variable
    parts = [
        _normalize_text(vascular_structure) or "NA",
        _normalize_text(topographical_modifier) or "NA",
        _normalize_text(laterality) or "NA",
        _normalize_text(trace_label) or "NA",
        _normalize_text(concept_code_meaning) or "NA",
    ]
    return "-".join(parts)


def _build_trace_label_from_path(measurement_path: str | None) -> str:
    normalized = _normalize_text(measurement_path)
    if not normalized:
        return "Traza-NA"

    match = re.match(r"^ContentSequence\[(\d+)\]\.ContentSequence\[(\d+)\]$", normalized)
    if match:
        return f"Traza-{match.group(1)}-{match.group(2)}"

    return f"Traza-{normalized}"


def _build_private_label(
    parameter_id: str | None,
    preferred_display_name: str | None,
    parameter_attribute: str | None,
    study_type: str | None,
) -> str:
    core = _normalize_text(parameter_id) or _normalize_text(preferred_display_name)
    if not core:
        core = "private_measurement"

    details: list[str] = []
    preferred = _normalize_text(preferred_display_name)
    attribute = _normalize_text(parameter_attribute)
    study = _normalize_text(study_type)

    if preferred and preferred.lower() not in core.lower():
        details.append(f"display={preferred}")
    if attribute:
        details.append(attribute)
    if study:
        details.append(study)

    if not details:
        return core
    return f"{core} | {' | '.join(details)}"


def _build_private_candidates(connection) -> list[SemanticCandidate]:
    query = f"""
        WITH numeric_private AS (
            SELECT
                sev.id AS numeric_variable_id,
                sev.sr_document_id,
                sd.parser_family,
                sd.parser_key,
                sev.concept_code_value,
                sev.concept_code_scheme,
                sev.concept_code_meaning,
                sev.value_unit,
                sev.dicom_path AS sample_dicom_path,
                regexp_replace(sev.dicom_path, '\\.[^.]+\\[[0-9]+\\]$', '') AS parent_path
            FROM {settings.db_schema}.sr_extracted_variable sev
            JOIN {settings.db_schema}.sr_document sd ON sd.id = sev.sr_document_id
            WHERE sev.value_numeric IS NOT NULL
              AND sev.concept_code_value = '43128'
              AND sev.concept_code_scheme = '99GEMS'
        ),
        sibling_context AS (
            SELECT
                np.numeric_variable_id,
                np.sr_document_id,
                np.parser_family,
                np.parser_key,
                np.concept_code_value,
                np.concept_code_scheme,
                np.concept_code_meaning,
                np.value_unit,
                np.parent_path,
                np.sample_dicom_path,
                MAX(CASE WHEN s.concept_code_value = '43131' AND s.concept_code_scheme = '99GEMS' THEN s.value_text END) AS parameter_id,
                MAX(CASE WHEN s.concept_code_value = '43133' AND s.concept_code_scheme = '99GEMS' THEN s.value_text END) AS preferred_display_name,
                MAX(CASE WHEN s.concept_code_value = '43130' AND s.concept_code_scheme = '99GEMS' THEN s.value_text END) AS parameter_attribute,
                MAX(CASE WHEN s.concept_code_value = '43145' AND s.concept_code_scheme = '99GEMS' THEN s.value_text END) AS study_type
            FROM numeric_private np
                        JOIN {settings.db_schema}.sr_extracted_variable s
              ON s.sr_document_id = np.sr_document_id
             AND regexp_replace(s.dicom_path, '\\.[^.]+\\[[0-9]+\\]$', '') = np.parent_path
            GROUP BY
                np.numeric_variable_id,
                np.sr_document_id,
                np.parser_family,
                np.parser_key,
                np.concept_code_value,
                np.concept_code_scheme,
                np.concept_code_meaning,
                np.value_unit,
                np.parent_path,
                np.sample_dicom_path
        )
        SELECT
            parser_family,
            parser_key,
            concept_code_value,
            concept_code_scheme,
            concept_code_meaning,
            parameter_id,
            preferred_display_name,
            parameter_attribute,
            study_type,
            value_unit,
            MIN(parent_path) AS parent_path,
            MIN(sample_dicom_path) AS sample_dicom_path,
            MIN(sr_document_id) AS first_seen_sr_document_id,
            MAX(sr_document_id) AS last_seen_sr_document_id,
            MIN(numeric_variable_id) AS sample_numeric_variable_id,
            COUNT(*) AS occurrence_count
        FROM sibling_context
        GROUP BY
            parser_family,
            parser_key,
            concept_code_value,
            concept_code_scheme,
            concept_code_meaning,
            parameter_id,
            preferred_display_name,
            parameter_attribute,
            study_type,
            value_unit;
    """

    candidates: list[SemanticCandidate] = []
    with connection.cursor() as cursor:
        cursor.execute(query)
        rows = cursor.fetchall()

    for row in rows:
        (
            parser_family,
            parser_key,
            concept_code_value,
            concept_code_scheme,
            concept_code_meaning,
            parameter_id,
            preferred_display_name,
            parameter_attribute,
            study_type,
            unit,
            parent_path,
            sample_dicom_path,
            first_seen,
            last_seen,
            sample_var_id,
            occurrence_count,
        ) = row

        semantic_meaning = _build_private_label(
            parameter_id=parameter_id,
            preferred_display_name=preferred_display_name,
            parameter_attribute=parameter_attribute,
            study_type=study_type,
        )
        resolved_label = semantic_meaning
        semantic_signature = _build_private_signature(
            parser_family,
            parser_key,
            parameter_id,
            parameter_attribute,
            study_type,
            unit,
        )

        candidates.append(
            SemanticCandidate(
                semantic_signature=semantic_signature,
                parser_family=parser_family,
                parser_key=parser_key,
                source_type="private_99gems",
                parent_path_pattern=_path_to_pattern(parent_path),
                sample_dicom_path=sample_dicom_path,
                concept_code_value=concept_code_value,
                concept_code_scheme=concept_code_scheme,
                concept_code_meaning=semantic_meaning,
                parameter_id=parameter_id,
                preferred_display_name=preferred_display_name,
                parameter_attribute=parameter_attribute,
                study_type=study_type,
                resolved_label=resolved_label,
                unit=unit,
                first_seen_sr_document_id=first_seen,
                last_seen_sr_document_id=last_seen,
                sample_numeric_variable_id=sample_var_id,
                occurrence_count=int(occurrence_count or 0),
            )
        )

    return candidates


def _build_standard_candidates(connection) -> list[SemanticCandidate]:
    query = f"""
        SELECT
            sd.parser_family,
            sd.parser_key,
            sev.concept_code_value,
            sev.concept_code_scheme,
            sev.concept_code_meaning,
            sev.value_unit,
            MIN(sev.dicom_path) AS sample_dicom_path,
            MIN(sev.sr_document_id) AS first_seen_sr_document_id,
            MAX(sev.sr_document_id) AS last_seen_sr_document_id,
            MIN(sev.id) AS sample_numeric_variable_id,
            COUNT(*) AS occurrence_count
        FROM {settings.db_schema}.sr_extracted_variable sev
        JOIN {settings.db_schema}.sr_document sd ON sd.id = sev.sr_document_id
        WHERE sev.value_numeric IS NOT NULL
          AND NOT (sev.concept_code_value = '43128' AND sev.concept_code_scheme = '99GEMS')
        GROUP BY
            sd.parser_family,
            sd.parser_key,
            sev.concept_code_value,
            sev.concept_code_scheme,
            sev.concept_code_meaning,
            sev.value_unit;
    """

    candidates: list[SemanticCandidate] = []
    with connection.cursor() as cursor:
        cursor.execute(query)
        rows = cursor.fetchall()

    for row in rows:
        (
            parser_family,
            parser_key,
            concept_code_value,
            concept_code_scheme,
            concept_code_meaning,
            unit,
            sample_dicom_path,
            first_seen,
            last_seen,
            sample_var_id,
            occurrence_count,
        ) = row

        semantic_signature = _build_standard_signature(
            parser_family,
            parser_key,
            concept_code_value,
            concept_code_scheme,
            concept_code_meaning,
            unit,
        )

        candidates.append(
            SemanticCandidate(
                semantic_signature=semantic_signature,
                parser_family=parser_family,
                parser_key=parser_key,
                source_type="standard_numeric",
                parent_path_pattern=_path_to_pattern(sample_dicom_path),
                sample_dicom_path=sample_dicom_path,
                concept_code_value=concept_code_value,
                concept_code_scheme=concept_code_scheme,
                concept_code_meaning=concept_code_meaning,
                parameter_id=None,
                preferred_display_name=None,
                parameter_attribute=None,
                study_type=None,
                resolved_label=concept_code_meaning,
                unit=unit,
                first_seen_sr_document_id=first_seen,
                last_seen_sr_document_id=last_seen,
                sample_numeric_variable_id=sample_var_id,
                occurrence_count=int(occurrence_count or 0),
            )
        )

    return candidates


def _build_standard_contextual_candidates(connection) -> list[SemanticCandidate]:
    contextual_families_sql = "'ge_logiqf_vascular_sr', 'ge_vivids70_carotid_sr'"

    query = f"""
        WITH numeric_standard AS (
            SELECT
                sev.id AS numeric_variable_id,
                sev.sr_document_id,
                sd.parser_family,
                sd.parser_key,
                sev.concept_code_value,
                sev.concept_code_scheme,
                sev.concept_code_meaning,
                sev.value_unit,
                sev.dicom_path,
                regexp_replace(sev.dicom_path, '\\.[^.]+\\[[0-9]+\\]$', '') AS measurement_path,
                substring(sev.dicom_path from '^(ContentSequence\\[[0-9]+\\])') AS finding_root
            FROM {settings.db_schema}.sr_extracted_variable sev
            JOIN {settings.db_schema}.sr_document sd ON sd.id = sev.sr_document_id
            WHERE sev.value_numeric IS NOT NULL
                              AND sd.parser_family IN ({contextual_families_sql})
              AND NOT (sev.concept_code_value = '43128' AND sev.concept_code_scheme = '99GEMS')
        ),
        contextualized AS (
            SELECT
                n.numeric_variable_id,
                n.sr_document_id,
                n.parser_family,
                n.parser_key,
                n.concept_code_value,
                n.concept_code_scheme,
                n.concept_code_meaning,
                n.value_unit,
                n.dicom_path,
                                n.measurement_path,
                                n.finding_root,
                vessel.vascular_structure,
                                site.finding_site,
                topo.topographical_modifier,
                lat.laterality,
                mode.image_mode
            FROM numeric_standard n
            LEFT JOIN LATERAL (
                                SELECT s.concept_code_meaning AS vascular_structure
                FROM {settings.db_schema}.sr_extracted_variable s
                WHERE s.sr_document_id = n.sr_document_id
                                    AND s.dicom_path = n.measurement_path
                  AND s.concept_code_meaning IN (
                    'Common Carotid Artery',
                    'Internal Carotid Artery',
                    'External Carotid Artery',
                    'Vertebral Artery'
                  )
                LIMIT 1
            ) vessel ON true
                        LEFT JOIN LATERAL (
                                SELECT COALESCE(
                                        s.value_text,
                                        s.value_json #>> '{{raw_item_json,0040A168,Value,0,00080104,Value,0}}'
                                ) AS finding_site
                                FROM {settings.db_schema}.sr_extracted_variable s
                                WHERE s.sr_document_id = n.sr_document_id
                                    AND n.finding_root IS NOT NULL
                                    AND s.dicom_path LIKE n.finding_root || '.%'
                                    AND s.concept_code_meaning = 'Finding Site'
                                ORDER BY LENGTH(s.dicom_path) ASC
                                LIMIT 1
                        ) site ON true
            LEFT JOIN LATERAL (
                SELECT COALESCE(
                    s.value_text,
                    s.value_json #>> '{{raw_item_json,0040A168,Value,0,00080104,Value,0}}'
                ) AS topographical_modifier
                FROM {settings.db_schema}.sr_extracted_variable s
                WHERE s.sr_document_id = n.sr_document_id
                                    AND s.dicom_path LIKE n.measurement_path || '.%'
                                    AND s.concept_code_meaning = 'Topographical Modifier'
                ORDER BY LENGTH(s.dicom_path) DESC
                LIMIT 1
            ) topo ON true
            LEFT JOIN LATERAL (
                SELECT COALESCE(
                    s.value_text,
                    s.value_json #>> '{{raw_item_json,0040A168,Value,0,00080104,Value,0}}'
                ) AS laterality
                FROM {settings.db_schema}.sr_extracted_variable s
                WHERE s.sr_document_id = n.sr_document_id
                                    AND n.finding_root IS NOT NULL
                                    AND s.dicom_path LIKE n.finding_root || '.%'
                  AND s.concept_code_meaning = 'Laterality'
                                ORDER BY LENGTH(s.dicom_path) ASC
                LIMIT 1
            ) lat ON true
            LEFT JOIN LATERAL (
                SELECT COALESCE(
                    s.value_text,
                    s.value_json #>> '{{raw_item_json,0040A168,Value,0,00080104,Value,0}}'
                ) AS image_mode
                FROM {settings.db_schema}.sr_extracted_variable s
                WHERE s.sr_document_id = n.sr_document_id
                                    AND n.finding_root IS NOT NULL
                                    AND s.dicom_path LIKE n.finding_root || '.%'
                  AND s.concept_code_meaning = 'Image Mode'
                                ORDER BY LENGTH(s.dicom_path) ASC
                LIMIT 1
            ) mode ON true
        )
        SELECT
            parser_family,
            parser_key,
            concept_code_value,
            concept_code_scheme,
            concept_code_meaning,
            value_unit,
            measurement_path,
            vascular_structure,
            finding_site,
            topographical_modifier,
            laterality,
            image_mode,
            MIN(dicom_path) AS sample_dicom_path,
            MIN(sr_document_id) AS first_seen_sr_document_id,
            MAX(sr_document_id) AS last_seen_sr_document_id,
            MIN(numeric_variable_id) AS sample_numeric_variable_id,
            COUNT(*) AS occurrence_count
        FROM contextualized
        GROUP BY
            parser_family,
            parser_key,
            concept_code_value,
            concept_code_scheme,
            concept_code_meaning,
            value_unit,
            measurement_path,
            vascular_structure,
            finding_site,
            topographical_modifier,
            laterality,
            image_mode;
    """

    candidates: list[SemanticCandidate] = []
    with connection.cursor() as cursor:
        cursor.execute(query)
        rows = cursor.fetchall()

    for row in rows:
        (
            parser_family,
            parser_key,
            concept_code_value,
            concept_code_scheme,
            concept_code_meaning,
            unit,
            measurement_path,
            vascular_structure,
            finding_site,
            topographical_modifier,
            laterality,
            image_mode,
            sample_dicom_path,
            first_seen,
            last_seen,
            sample_var_id,
            occurrence_count,
        ) = row

        trace_label = _build_trace_label_from_path(measurement_path)

        resolved_label = _build_standard_contextual_label(
            vascular_structure=vascular_structure,
            topographical_modifier=topographical_modifier,
            laterality=laterality,
            trace_label=trace_label,
            concept_code_meaning=concept_code_meaning,
        )

        semantic_signature = _build_standard_contextual_signature(
            parser_family=parser_family,
            parser_key=parser_key,
            concept_code_value=concept_code_value,
            concept_code_scheme=concept_code_scheme,
            concept_code_meaning=concept_code_meaning,
            unit=unit,
            vascular_structure=vascular_structure,
            topographical_modifier=topographical_modifier,
            laterality=laterality,
            trace_label=trace_label,
            image_mode=image_mode,
        )

        candidates.append(
            SemanticCandidate(
                semantic_signature=semantic_signature,
                parser_family=parser_family,
                parser_key=parser_key,
                source_type="standard_numeric_contextual",
                parent_path_pattern=_path_to_pattern(sample_dicom_path),
                sample_dicom_path=sample_dicom_path,
                concept_code_value=concept_code_value,
                concept_code_scheme=concept_code_scheme,
                concept_code_meaning=resolved_label,
                parameter_id=None,
                preferred_display_name=None,
                parameter_attribute=None,
                study_type=None,
                resolved_label=resolved_label,
                unit=unit,
                first_seen_sr_document_id=first_seen,
                last_seen_sr_document_id=last_seen,
                sample_numeric_variable_id=sample_var_id,
                occurrence_count=int(occurrence_count or 0),
            )
        )

    return candidates


def upsert_semantic_candidates(connection, candidates: list[SemanticCandidate]) -> int:
    if not candidates:
        return 0

    query = f"""
        INSERT INTO {settings.db_schema}.sr_variable_semantic_reference (
            semantic_signature,
            parser_family,
            parser_key,
            source_type,
            parent_path_pattern,
            sample_dicom_path,
            concept_code_value,
            concept_code_scheme,
            concept_code_meaning,
            parameter_id,
            preferred_display_name,
            parameter_attribute,
            study_type,
            resolved_label,
            unit,
            first_seen_sr_document_id,
            last_seen_sr_document_id,
            sample_numeric_variable_id,
            occurrence_count,
            active,
            updated_at
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, true, NOW()
        )
        ON CONFLICT (semantic_signature)
        DO UPDATE SET
            parser_family = EXCLUDED.parser_family,
            parser_key = EXCLUDED.parser_key,
            source_type = EXCLUDED.source_type,
            parent_path_pattern = EXCLUDED.parent_path_pattern,
            sample_dicom_path = EXCLUDED.sample_dicom_path,
            concept_code_value = EXCLUDED.concept_code_value,
            concept_code_scheme = EXCLUDED.concept_code_scheme,
            concept_code_meaning = EXCLUDED.concept_code_meaning,
            parameter_id = EXCLUDED.parameter_id,
            preferred_display_name = EXCLUDED.preferred_display_name,
            parameter_attribute = EXCLUDED.parameter_attribute,
            study_type = EXCLUDED.study_type,
            resolved_label = EXCLUDED.resolved_label,
            unit = EXCLUDED.unit,
            first_seen_sr_document_id = LEAST(
                COALESCE({settings.db_schema}.sr_variable_semantic_reference.first_seen_sr_document_id, EXCLUDED.first_seen_sr_document_id),
                COALESCE(EXCLUDED.first_seen_sr_document_id, {settings.db_schema}.sr_variable_semantic_reference.first_seen_sr_document_id)
            ),
            last_seen_sr_document_id = GREATEST(
                COALESCE({settings.db_schema}.sr_variable_semantic_reference.last_seen_sr_document_id, EXCLUDED.last_seen_sr_document_id),
                COALESCE(EXCLUDED.last_seen_sr_document_id, {settings.db_schema}.sr_variable_semantic_reference.last_seen_sr_document_id)
            ),
            sample_numeric_variable_id = COALESCE({settings.db_schema}.sr_variable_semantic_reference.sample_numeric_variable_id, EXCLUDED.sample_numeric_variable_id),
            occurrence_count = EXCLUDED.occurrence_count,
            active = true,
            updated_at = NOW();
    """

    with connection.cursor() as cursor:
        for candidate in candidates:
            cursor.execute(
                query,
                (
                    candidate.semantic_signature,
                    candidate.parser_family,
                    candidate.parser_key,
                    candidate.source_type,
                    candidate.parent_path_pattern,
                    candidate.sample_dicom_path,
                    candidate.concept_code_value,
                    candidate.concept_code_scheme,
                    candidate.concept_code_meaning,
                    candidate.parameter_id,
                    candidate.preferred_display_name,
                    candidate.parameter_attribute,
                    candidate.study_type,
                    candidate.resolved_label,
                    candidate.unit,
                    candidate.first_seen_sr_document_id,
                    candidate.last_seen_sr_document_id,
                    candidate.sample_numeric_variable_id,
                    candidate.occurrence_count,
                ),
            )

    return len(candidates)


def rebuild_extracted_variable_semantic_map(connection) -> int:
    delete_query = f"DELETE FROM {settings.db_schema}.sr_extracted_variable_semantic_map;"

    insert_query = f"""
        WITH private_numeric AS (
            SELECT
                sev.id AS sr_extracted_variable_id,
                sev.sr_document_id,
                sev.value_unit,
                sd.parser_family,
                sd.parser_key,
                regexp_replace(sev.dicom_path, '\\.[^.]+\\[[0-9]+\\]$', '') AS parent_path
            FROM {settings.db_schema}.sr_extracted_variable sev
            JOIN {settings.db_schema}.sr_document sd ON sd.id = sev.sr_document_id
            WHERE sev.value_numeric IS NOT NULL
              AND sev.concept_code_value = '43128'
              AND sev.concept_code_scheme = '99GEMS'
        ),
        private_context AS (
            SELECT
                pn.sr_extracted_variable_id,
                pn.value_unit,
                pn.parser_family,
                pn.parser_key,
                MAX(CASE WHEN s.concept_code_value = '43131' AND s.concept_code_scheme = '99GEMS' THEN s.value_text END) AS parameter_id,
                MAX(CASE WHEN s.concept_code_value = '43130' AND s.concept_code_scheme = '99GEMS' THEN s.value_text END) AS parameter_attribute,
                MAX(CASE WHEN s.concept_code_value = '43145' AND s.concept_code_scheme = '99GEMS' THEN s.value_text END) AS study_type
            FROM private_numeric pn
            JOIN {settings.db_schema}.sr_extracted_variable s
              ON s.sr_document_id = pn.sr_document_id
             AND regexp_replace(s.dicom_path, '\\.[^.]+\\[[0-9]+\\]$', '') = pn.parent_path
            GROUP BY
                pn.sr_extracted_variable_id,
                pn.value_unit,
                pn.parser_family,
                pn.parser_key
        ),
        private_signatures AS (
            SELECT
                pc.sr_extracted_variable_id,
                concat_ws('|',
                    'private_99gems',
                    lower(coalesce(pc.parser_family, '')),
                    lower(coalesce(pc.parser_key, '')),
                    lower(coalesce(pc.parameter_id, '')),
                    lower(coalesce(pc.parameter_attribute, '')),
                    lower(coalesce(pc.study_type, '')),
                    lower(coalesce(pc.value_unit, ''))
                ) AS semantic_signature
            FROM private_context pc
        ),
        standard_signatures AS (
            SELECT
                sev.id AS sr_extracted_variable_id,
                concat_ws('|',
                    'standard_numeric',
                    lower(coalesce(sd.parser_family, '')),
                    lower(coalesce(sd.parser_key, '')),
                    lower(coalesce(sev.concept_code_value, '')),
                    lower(coalesce(sev.concept_code_scheme, '')),
                    lower(coalesce(sev.concept_code_meaning, '')),
                    lower(coalesce(sev.value_unit, ''))
                ) AS semantic_signature
            FROM {settings.db_schema}.sr_extracted_variable sev
            JOIN {settings.db_schema}.sr_document sd ON sd.id = sev.sr_document_id
            WHERE sev.value_numeric IS NOT NULL
              AND NOT (sev.concept_code_value = '43128' AND sev.concept_code_scheme = '99GEMS')
        ),
        all_signatures AS (
            SELECT sr_extracted_variable_id, semantic_signature FROM private_signatures
            UNION ALL
            SELECT sr_extracted_variable_id, semantic_signature FROM standard_signatures
        )
        INSERT INTO {settings.db_schema}.sr_extracted_variable_semantic_map (
            sr_extracted_variable_id,
            semantic_reference_id,
            semantic_signature,
            updated_at
        )
        SELECT
            s.sr_extracted_variable_id,
            r.id AS semantic_reference_id,
            s.semantic_signature,
            NOW()
        FROM all_signatures s
        JOIN {settings.db_schema}.sr_variable_semantic_reference r
          ON r.semantic_signature = s.semantic_signature;
    """

    with connection.cursor() as cursor:
        cursor.execute(delete_query)
        cursor.execute(insert_query)
        return cursor.rowcount if cursor.rowcount is not None else 0


def sync_facility_variable_mapping(connection) -> int:
    select_query = f"""
        SELECT
            parser_family,
            parser_key,
            semantic_signature,
            source_type,
            concept_code_value,
            concept_code_scheme,
            concept_code_meaning,
            resolved_label,
            unit
        FROM {settings.db_schema}.sr_variable_semantic_reference
        WHERE active = true;
    """

    find_query = f"""
        SELECT id
                FROM {settings.db_schema}.facility_variable_mapping
        WHERE parser_family = %s
          AND semantic_signature = %s
          AND facility_id IS NULL
        LIMIT 1;
    """

    insert_query = f"""
        INSERT INTO {settings.db_schema}.facility_variable_mapping (
            parser_family,
            parser_key,
            semantic_signature,
            source_type,
            concept_code_value,
            concept_code_scheme,
            concept_code_meaning,
            canonical_name,
            canonical_code,
            unit,
            facility_id,
            facility_name,
            facility_code,
            base_variable_id,
            use_for_runtime_mapping,
            active,
            updated_at
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NULL, NULL, NULL, NULL, %s, true, NOW()
        );
    """

    update_query = f"""
        UPDATE {settings.db_schema}.facility_variable_mapping
        SET parser_key = %s,
            source_type = %s,
            concept_code_value = %s,
            concept_code_scheme = %s,
            concept_code_meaning = %s,
            canonical_name = %s,
            unit = %s,
            use_for_runtime_mapping = %s,
            active = true,
            updated_at = NOW()
        WHERE id = %s;
    """

    with connection.cursor() as cursor:
        cursor.execute(select_query)
        rows = cursor.fetchall()

        processed = 0
        for row in rows:
            (
                parser_family,
                parser_key,
                semantic_signature,
                source_type,
                concept_code_value,
                concept_code_scheme,
                concept_code_meaning,
                resolved_label,
                unit,
            ) = row

            canonical_name = resolved_label or concept_code_meaning or semantic_signature
            canonical_code = (
                f"{parser_family}::{semantic_signature}"
                if parser_family and semantic_signature
                else semantic_signature
            )
            use_for_runtime_mapping = source_type != "standard_numeric_contextual"

            cursor.execute(find_query, (parser_family, semantic_signature))
            existing = cursor.fetchone()

            if existing is None:
                cursor.execute(
                    insert_query,
                    (
                        parser_family,
                        parser_key,
                        semantic_signature,
                        source_type,
                        concept_code_value,
                        concept_code_scheme,
                        concept_code_meaning,
                        canonical_name,
                        canonical_code,
                        unit,
                        use_for_runtime_mapping,
                    ),
                )
            else:
                cursor.execute(
                    update_query,
                    (
                        parser_key,
                        source_type,
                        concept_code_value,
                        concept_code_scheme,
                        concept_code_meaning,
                        canonical_name,
                        unit,
                        use_for_runtime_mapping,
                        existing[0],
                    ),
                )

            processed += 1

        return processed


def main() -> None:
    connection = get_connection()
    try:
        ensure_schema(connection)

        private_candidates = _build_private_candidates(connection)
        standard_candidates = _build_standard_candidates(connection)
        standard_contextual_candidates = _build_standard_contextual_candidates(connection)
        all_candidates = (
            private_candidates
            + standard_candidates
            + standard_contextual_candidates
        )

        total_upserted = upsert_semantic_candidates(connection, all_candidates)
        total_links = rebuild_extracted_variable_semantic_map(connection)
        total_catalog_rows = sync_facility_variable_mapping(connection)
        connection.commit()

        print(f"Candidatos privados 99GEMS: {len(private_candidates)}")
        print(f"Candidatos numéricos estándar: {len(standard_candidates)}")
        print(f"Candidatos numéricos contextuales: {len(standard_contextual_candidates)}")
        print(f"Registros upsertados en base semántica: {total_upserted}")
        print(f"Links fila-a-fila reconstruidos: {total_links}")
        print(f"Variables base sincronizadas por parser: {total_catalog_rows}")
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


if __name__ == "__main__":
    main()
