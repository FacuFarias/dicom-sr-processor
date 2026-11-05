from __future__ import annotations

import json
import uuid

import pytest

import main as sr_main
from database.connection import ensure_schema, get_connection
from database.repositories.sr_document_repository import (
    insert_sr_document,
)
from database.repositories.sr_variable_repository import insert_extracted_variables
from models.extracted_variable import ExtractedVariable
from models.sr_document import SRDocument
from parsers.base_parser import BaseSRParser


@pytest.fixture()
def db_connection():
    connection = get_connection()
    ensure_schema(connection)

    with connection.cursor() as cursor:
        cursor.execute("TRUNCATE TABLE dicom_sr.sr_extracted_variable RESTART IDENTITY CASCADE;")
        cursor.execute("TRUNCATE TABLE dicom_sr.sr_document RESTART IDENTITY CASCADE;")
    connection.commit()

    try:
        yield connection
    finally:
        with connection.cursor() as cursor:
            cursor.execute(
                "TRUNCATE TABLE dicom_sr.sr_extracted_variable RESTART IDENTITY CASCADE;"
            )
            cursor.execute("TRUNCATE TABLE dicom_sr.sr_document RESTART IDENTITY CASCADE;")
        connection.commit()
        connection.close()


def _new_sr_document(status: str = "received") -> SRDocument:
    token = str(uuid.uuid4())
    return SRDocument(
        sop_instance_uid=f"1.2.3.{token}",
        study_instance_uid=f"2.3.4.{token}",
        series_instance_uid=f"3.4.5.{token}",
        sop_class_uid="1.2.840.10008.5.1.4.1.1.88.33",
        manufacturer="siemens",
        manufacturer_model_name="acuson",
        institution_name="hospital_central",
        station_name="station-a",
        software_versions="1.0",
        parser_key="siemens|hospital_central|acuson|1.2.840.10008.5.1.4.1.1.88.33",
        parser_version="1.0",
        raw_metadata_json={"source": "test"},
        status=status,
    )


def test_insert_sr_document_persists_record(db_connection):
    sr_document_id = insert_sr_document(db_connection, _new_sr_document())
    db_connection.commit()

    with db_connection.cursor() as cursor:
        cursor.execute(
            "SELECT id, status FROM dicom_sr.sr_document WHERE id = %s;",
            (sr_document_id,),
        )
        row = cursor.fetchone()

    assert row is not None
    assert row[0] == sr_document_id
    assert row[1] == "received"


def test_insert_extracted_variables_persists_rows(db_connection):
    sr_document_id = insert_sr_document(db_connection, _new_sr_document())
    variables = [
        ExtractedVariable(
            dicom_tag="0040,A730",
            dicom_description="Content Sequence",
            dicom_path="ContentSequence[0]",
            concept_code_value="12345",
            concept_code_scheme="DCM",
            concept_code_meaning="Heart Rate",
            value_type="NUM",
            value_numeric=72,
            value_unit="bpm",
            raw_value=72,
            raw_item_json={"dummy": True},
            sequence_index=0,
        )
    ]

    inserted = insert_extracted_variables(db_connection, sr_document_id, variables)
    db_connection.commit()

    with db_connection.cursor() as cursor:
        cursor.execute(
            "SELECT COUNT(*) FROM dicom_sr.sr_extracted_variable WHERE sr_document_id = %s;",
            (sr_document_id,),
        )
        count = cursor.fetchone()[0]

    assert inserted == 1
    assert count == 1


def test_document_status_unsupported_when_no_parser(monkeypatch, db_connection):
    monkeypatch.setattr(sr_main, "read_dicom_dataset", lambda _: object())
    monkeypatch.setattr(
        sr_main,
        "read_dicom_metadata",
        lambda _: {
            "manufacturer": "other",
            "institution_name": "other_hospital",
            "manufacturer_model_name": "other_model",
            "station_name": "st-1",
            "software_versions": "2.0",
            "sop_class_uid": "1.2.3",
            "sop_instance_uid": f"1.2.3.{uuid.uuid4()}",
            "study_instance_uid": f"2.3.4.{uuid.uuid4()}",
            "series_instance_uid": f"3.4.5.{uuid.uuid4()}",
        },
    )
    monkeypatch.setattr(sr_main, "load_parsers", lambda: [])

    result = sr_main.process_sr_file("dummy.dcm")

    with db_connection.cursor() as cursor:
        cursor.execute(
            "SELECT status FROM dicom_sr.sr_document WHERE id = %s;",
            (result["sr_document_id"],),
        )
        status = cursor.fetchone()[0]

    assert result["status"] == "unsupported"
    assert status == "unsupported"


def test_error_during_variable_insert_is_controlled(monkeypatch, db_connection):
    class AlwaysMatchParser(BaseSRParser):
        parser_name = "AlwaysMatch"
        parser_version = "1.0"
        supported_manufacturers = ["*"]
        supported_institutions = ["*"]
        supported_models = ["*"]
        supported_sop_class_uids = ["*"]

        def parse(self, dataset):
            return [
                ExtractedVariable(
                    dicom_path="ContentSequence[0]",
                    value_type="TEXT",
                    value_text="demo",
                )
            ]

    monkeypatch.setattr(sr_main, "read_dicom_dataset", lambda _: object())
    monkeypatch.setattr(
        sr_main,
        "read_dicom_metadata",
        lambda _: {
            "manufacturer": "siemens",
            "institution_name": "hospital_central",
            "manufacturer_model_name": "acuson",
            "station_name": "st-1",
            "software_versions": "2.0",
            "sop_class_uid": "1.2.840.10008.5.1.4.1.1.88.33",
            "sop_instance_uid": f"1.2.3.{uuid.uuid4()}",
            "study_instance_uid": f"2.3.4.{uuid.uuid4()}",
            "series_instance_uid": f"3.4.5.{uuid.uuid4()}",
        },
    )
    monkeypatch.setattr(sr_main, "load_parsers", lambda: [AlwaysMatchParser()])

    def _raise_error(*_args, **_kwargs):
        raise RuntimeError("error forzado de inserción")

    monkeypatch.setattr(sr_main, "insert_extracted_variables", _raise_error)

    with pytest.raises(RuntimeError):
        sr_main.process_sr_file("dummy.dcm")

    with db_connection.cursor() as cursor:
        cursor.execute("SELECT COUNT(*) FROM dicom_sr.sr_document;")
        count = cursor.fetchone()[0]

        cursor.execute(
            "SELECT COUNT(*) FROM dicom_sr.sr_document WHERE status = 'failed';"
        )
        failed_count = cursor.fetchone()[0]

    assert count == 0 or failed_count >= 1


def test_value_json_is_persisted_as_valid_json(db_connection):
    sr_document_id = insert_sr_document(db_connection, _new_sr_document())
    variables = [
        ExtractedVariable(
            dicom_path="ContentSequence[0]",
            value_type="NUM",
            value_numeric=99,
            raw_value={"a": 1},
            raw_item_json={"source": "unit-test"},
            sequence_index=0,
        )
    ]
    insert_extracted_variables(db_connection, sr_document_id, variables)
    db_connection.commit()

    with db_connection.cursor() as cursor:
        cursor.execute(
            "SELECT value_json FROM dicom_sr.sr_extracted_variable WHERE sr_document_id = %s;",
            (sr_document_id,),
        )
        stored = cursor.fetchone()[0]

    if isinstance(stored, str):
        stored = json.loads(stored)

    assert isinstance(stored, dict)
    assert "raw_value" in stored
    assert "value_type" in stored
    assert "raw_item_json" in stored
