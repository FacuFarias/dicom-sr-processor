from __future__ import annotations

from database.repositories.facility_mapping_repository import find_candidate_mappings


def map_extracted_variables(connection, facility_id, parser_key, variables):
    mapped_variables = []

    for variable in variables:
        candidates = find_candidate_mappings(
            connection=connection,
            facility_id=facility_id,
            parser_key=parser_key,
            extracted_variable=variable,
        )

        if len(candidates) == 1:
            mapping = candidates[0]
            variable.canonical_variable_definition_id = None
            variable.facility_description = (
                mapping.facility_name
                or mapping.canonical_name
                or mapping.concept_code_meaning
            )
            variable.mapping_status = "mapped"
            variable.canonical_code = mapping.canonical_code
            variable.canonical_name = mapping.canonical_name

        elif len(candidates) == 0:
            variable.canonical_variable_definition_id = None
            variable.canonical_code = None
            variable.canonical_name = None
            variable.facility_description = None
            variable.mapping_status = "unmapped"

        else:
            variable.canonical_variable_definition_id = None
            variable.canonical_code = None
            variable.canonical_name = None
            variable.facility_description = None
            variable.mapping_status = "ambiguous"
            print(
                "Mapping ambiguo para variable "
                f"{getattr(variable, 'dicom_path', None)} "
                f"con {len(candidates)} candidatos"
            )

        mapped_variables.append(variable)

    return mapped_variables
