from __future__ import annotations

import uuid

from database.connection import ensure_schema, get_connection
from database.repositories.parser_repository import (
    get_parser_manifest,
    upsert_parser_manifest,
)
from database.repositories.sr_document_repository import (
    insert_sr_document,
    mark_documents_for_reprocessing,
)
from models.parser_manifest import ParserManifest
from models.sr_document import SRDocument
from parsers.base_parser import BaseSRParser
from services.parser_versioning_service import compare_versions

import main as sr_main


class VersionedTestParser(BaseSRParser):
    parser_name = "VersionedTestParser"
    parser_version = "1.2.0"
    parser_family = "siemens_acuson_sr"
    compatibility_level = "strict"
    is_active = True
    supported_manufacturers = ["siemens"]
    supported_institutions = ["hospital_central"]
    supported_models = ["acuson"]
    supported_sop_class_uids = ["1.2.840.10008.5.1.4.1.1.88.33"]

    def parse(self, dataset):
        return []


def _reset_tables(connection):
    return None


def test_compare_versions_detects_higher_new_version():
    assert compare_versions("1.0.0", "1.0.1") == -1


def test_mark_reprocessing_when_newer_active_version_exists():
    connection = get_connection()
    ensure_schema(connection)
    parser_family = f"siemens_acuson_sr_{uuid.uuid4().hex[:8]}"

    sr_document_id = insert_sr_document(
        connection,
        SRDocument(
            sop_instance_uid=f"1.2.3.{uuid.uuid4()}",
            parser_name="ExampleParser",
            parser_family=parser_family,
            parser_version="1.0.0",
            status="processed",
            raw_metadata_json={"test": True},
        ),
    )

    updated = mark_documents_for_reprocessing(
        connection,
        parser_family=parser_family,
        new_version="1.1.0",
        compatibility_level="compatible",
    )
    connection.commit()

    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT needs_reprocessing FROM dicom_sr.sr_document WHERE id = %s;",
            (sr_document_id,),
        )
        needs_reprocessing = cursor.fetchone()[0]

    connection.close()

    assert updated == 1
    assert needs_reprocessing is True


def test_legacy_parser_does_not_mark_for_reprocessing():
    connection = get_connection()
    ensure_schema(connection)
    parser_family = f"siemens_acuson_sr_{uuid.uuid4().hex[:8]}"

    insert_sr_document(
        connection,
        SRDocument(
            sop_instance_uid=f"1.2.3.{uuid.uuid4()}",
            parser_name="ExampleParser",
            parser_family=parser_family,
            parser_version="1.0.0",
            status="processed",
            raw_metadata_json={"test": True},
        ),
    )

    updated = mark_documents_for_reprocessing(
        connection,
        parser_family=parser_family,
        new_version="1.1.0",
        compatibility_level="legacy",
    )
    connection.commit()
    connection.close()

    assert updated == 0


def test_parser_manifest_is_persisted_correctly():
    connection = get_connection()
    ensure_schema(connection)

    parser_name = f"ExampleParser_{uuid.uuid4().hex[:8]}"
    parser_version = "1.2.0"

    manifest = ParserManifest(
        parser_name=parser_name,
        parser_version=parser_version,
        parser_family="siemens_acuson_sr",
        compatibility_level="strict",
        is_active=True,
        supported_manufacturers=["siemens"],
        supported_institutions=["hospital_central"],
        supported_models=["acuson"],
        supported_sop_class_uids=["1.2.840.10008.5.1.4.1.1.88.33"],
    )

    manifest_id = upsert_parser_manifest(connection, manifest)
    connection.commit()

    stored = get_parser_manifest(connection, parser_name, parser_version)
    connection.close()

    assert manifest_id > 0
    assert stored is not None
    assert stored.parser_family == "siemens_acuson_sr"
    assert stored.parser_version == "1.2.0"


def test_processing_stores_parser_name_family_and_version(monkeypatch):
    connection = get_connection()
    ensure_schema(connection)
    connection.commit()
    connection.close()

    parser = VersionedTestParser()

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
    monkeypatch.setattr(sr_main, "load_parsers", lambda: [parser])
    monkeypatch.setattr(sr_main, "resolve_parser", lambda *_args, **_kwargs: parser)
    monkeypatch.setattr(
        sr_main,
        "map_extracted_variables",
        lambda connection, facility_id, parser_key, variables: variables,
    )

    result = sr_main.process_sr_file("dummy.dcm", facility_id=1)

    check_connection = get_connection()
    with check_connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT parser_name, parser_family, parser_version
              FROM dicom_sr.sr_document
             WHERE id = %s;
            """,
            (result["sr_document_id"],),
        )
        row = cursor.fetchone()
    check_connection.close()

    assert row[0] == "VersionedTestParser"
    assert row[1] == "siemens_acuson_sr"
    assert row[2] == "1.2.0"
