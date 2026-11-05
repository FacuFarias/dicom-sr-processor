from __future__ import annotations

import uuid

from database.connection import ensure_schema, get_connection
from database.repositories.report_template_repository import (
    get_active_template_for_parser_family,
    insert_report_template,
    save_rendered_report,
)
from database.repositories.sr_document_repository import insert_sr_document
from models.extracted_variable import ExtractedVariable
from models.report_template import ReportTemplate
from models.sr_document import SRDocument
from services.report_template_service import build_report_context, render_template


def test_render_template_replaces_canonical_value():
    variables = [
        ExtractedVariable(
            canonical_code="heart_rate",
            value_numeric=72,
            value_unit="bpm",
        )
    ]
    context = build_report_context(
        metadata={"patient_name": "NANCY", "patient_id": "782288"},
        variables=variables,
    )

    rendered = render_template(
        "Paciente: {{ patient_name }} / FC: {{ heart_rate }}",
        context,
    )

    assert "Paciente: NANCY" in rendered
    assert "FC: 72 bpm" in rendered


def test_build_context_uses_concept_fallback_key():
    variables = [
        ExtractedVariable(
            concept_code_scheme="LN",
            concept_code_value="11726-7",
            value_numeric=50.5,
            value_unit="cm/s",
        )
    ]
    context = build_report_context(metadata={}, variables=variables)
    assert context.get("concept_ln_11726_7") == "50.5 cm/s"


def test_report_template_repository_insert_select_and_render_save():
    connection = get_connection()
    try:
        ensure_schema(connection)
        unique_name = f"Template_{uuid.uuid4().hex[:10]}"

        template_id = insert_report_template(
            connection,
            ReportTemplate(
                name=unique_name,
                facility_id=1,
                parser_family="ge_logiqf_vascular_sr",
                template_body="Hola {{ patient_name }}",
                is_active=True,
            ),
        )
        connection.commit()

        template = get_active_template_for_parser_family(
            connection,
            facility_id=1,
            parser_family="ge_logiqf_vascular_sr",
        )
        assert template is not None
        assert template.id is not None

        sr_document_id = insert_sr_document(
            connection,
            SRDocument(
                sop_instance_uid=f"1.2.3.{uuid.uuid4()}",
                parser_name="GELogiqFMyCareSRParser",
                parser_family="ge_logiqf_vascular_sr",
                parser_version="1.0.0",
                status="processed",
                raw_metadata_json={"source": "test_report_templates"},
            ),
        )

        rendered_id = save_rendered_report(
            connection,
            sr_document_id=sr_document_id,
            template_id=template_id,
            rendered_text="Hola NANCY",
        )
        connection.commit()

        assert rendered_id > 0
    finally:
        connection.close()
