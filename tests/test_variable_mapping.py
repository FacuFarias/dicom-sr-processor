from __future__ import annotations

import uuid

import pytest

from database.connection import ensure_schema, get_connection
from database.repositories.facility_mapping_repository import (
    insert_facility_variable_mapping,
)
from database.repositories.variable_definition_repository import (
    insert_variable_definition,
)
from models.extracted_variable import ExtractedVariable
from models.facility_variable_mapping import FacilityVariableMapping
from models.variable_definition import VariableDefinition
from services.variable_mapping_service import map_extracted_variables


@pytest.fixture()
def db_connection():
    connection = get_connection()
    ensure_schema(connection)

    with connection.cursor() as cursor:
        cursor.execute("TRUNCATE TABLE dicom_sr.facility_variable_mapping RESTART IDENTITY CASCADE;")
        cursor.execute("TRUNCATE TABLE dicom_sr.variable_definition RESTART IDENTITY CASCADE;")
    connection.commit()

    try:
        yield connection
    finally:
        with connection.cursor() as cursor:
            cursor.execute(
                "TRUNCATE TABLE dicom_sr.facility_variable_mapping RESTART IDENTITY CASCADE;"
            )
            cursor.execute("TRUNCATE TABLE dicom_sr.variable_definition RESTART IDENTITY CASCADE;")
        connection.commit()
        connection.close()


@pytest.fixture()
def seed_minimal_mapping_data(db_connection):
    definition_id = insert_variable_definition(
        db_connection,
        VariableDefinition(
            canonical_code="heart_rate",
            canonical_name="Heart Rate",
            unit="bpm",
            value_type="NUM",
            description="Frecuencia cardiaca canónica",
            active=True,
        ),
    )

    mapping_id = insert_facility_variable_mapping(
        db_connection,
        FacilityVariableMapping(
            facility_id=1,
            parser_key="siemens|hospital_central|acuson|1.2.840.10008.5.1.4.1.1.88.33",
            concept_code_value="8867-4",
            concept_code_scheme="LN",
            dicom_path_pattern=None,
            canonical_variable_definition_id=definition_id,
            facility_description="Frecuencia cardíaca",
            active=True,
        ),
    )

    db_connection.commit()

    return {
        "definition_id": definition_id,
        "mapping_id": mapping_id,
    }


def test_mapping_exitoso(seed_minimal_mapping_data, db_connection):
    variable = ExtractedVariable(
        concept_code_value="8867-4",
        concept_code_scheme="LN",
        dicom_path="ContentSequence[0]",
        value_numeric=72,
    )

    mapped = map_extracted_variables(
        connection=db_connection,
        facility_id=1,
        parser_key="siemens|hospital_central|acuson|1.2.840.10008.5.1.4.1.1.88.33",
        variables=[variable],
    )

    assert len(mapped) == 1
    assert mapped[0].mapping_status == "mapped"
    assert mapped[0].canonical_code == "heart_rate"
    assert mapped[0].canonical_name == "Heart Rate"
    assert mapped[0].facility_description == "Frecuencia cardíaca"


def test_mapping_sin_coincidencia_queda_unmapped(seed_minimal_mapping_data, db_connection):
    variable = ExtractedVariable(
        concept_code_value="9999-9",
        concept_code_scheme="LN",
        dicom_path="ContentSequence[1]",
    )

    mapped = map_extracted_variables(
        connection=db_connection,
        facility_id=1,
        parser_key="siemens|hospital_central|acuson|1.2.840.10008.5.1.4.1.1.88.33",
        variables=[variable],
    )

    assert mapped[0].mapping_status == "unmapped"
    assert mapped[0].canonical_variable_definition_id is None


def test_mapping_ambiguo_no_asigna_canonico(db_connection):
    def_id_1 = insert_variable_definition(
        db_connection,
        VariableDefinition(
            canonical_code="heart_rate_a",
            canonical_name="Heart Rate A",
            unit="bpm",
            value_type="NUM",
            description="A",
            active=True,
        ),
    )
    def_id_2 = insert_variable_definition(
        db_connection,
        VariableDefinition(
            canonical_code="heart_rate_b",
            canonical_name="Heart Rate B",
            unit="bpm",
            value_type="NUM",
            description="B",
            active=True,
        ),
    )

    common_parser_key = "siemens|hospital_central|acuson|1.2.840.10008.5.1.4.1.1.88.33"

    insert_facility_variable_mapping(
        db_connection,
        FacilityVariableMapping(
            facility_id=1,
            parser_key=common_parser_key,
            concept_code_value="8867-4",
            concept_code_scheme="LN",
            canonical_variable_definition_id=def_id_1,
            facility_description="FC A",
            active=True,
        ),
    )
    insert_facility_variable_mapping(
        db_connection,
        FacilityVariableMapping(
            facility_id=1,
            parser_key=common_parser_key,
            concept_code_value="8867-4",
            concept_code_scheme="LN",
            canonical_variable_definition_id=def_id_2,
            facility_description="FC B",
            active=True,
        ),
    )
    db_connection.commit()

    variable = ExtractedVariable(
        concept_code_value="8867-4",
        concept_code_scheme="LN",
        dicom_path="ContentSequence[0]",
    )

    mapped = map_extracted_variables(
        connection=db_connection,
        facility_id=1,
        parser_key=common_parser_key,
        variables=[variable],
    )

    assert mapped[0].mapping_status == "ambiguous"
    assert mapped[0].canonical_variable_definition_id is None
    assert mapped[0].canonical_code is None


def test_matching_por_dicom_path_pattern_refina_match(db_connection):
    definition_id = insert_variable_definition(
        db_connection,
        VariableDefinition(
            canonical_code=f"heart_rate_{uuid.uuid4().hex[:8]}",
            canonical_name="Heart Rate",
            unit="bpm",
            value_type="NUM",
            description="Path refined",
            active=True,
        ),
    )

    parser_key = "siemens|hospital_central|acuson|1.2.840.10008.5.1.4.1.1.88.33"

    insert_facility_variable_mapping(
        db_connection,
        FacilityVariableMapping(
            facility_id=1,
            parser_key=parser_key,
            concept_code_value="8867-4",
            concept_code_scheme="LN",
            dicom_path_pattern="ContentSequence[1]*",
            canonical_variable_definition_id=definition_id,
            facility_description="No debería matchear",
            active=True,
        ),
    )

    insert_facility_variable_mapping(
        db_connection,
        FacilityVariableMapping(
            facility_id=1,
            parser_key=parser_key,
            concept_code_value="8867-4",
            concept_code_scheme="LN",
            dicom_path_pattern="ContentSequence[0]*",
            canonical_variable_definition_id=definition_id,
            facility_description="Coincidencia por path",
            active=True,
        ),
    )
    db_connection.commit()

    variable = ExtractedVariable(
        concept_code_value="8867-4",
        concept_code_scheme="LN",
        dicom_path="ContentSequence[0].ContentSequence[2]",
    )

    mapped = map_extracted_variables(
        connection=db_connection,
        facility_id=1,
        parser_key=parser_key,
        variables=[variable],
    )

    assert mapped[0].mapping_status == "mapped"
    assert mapped[0].facility_description == "Coincidencia por path"
