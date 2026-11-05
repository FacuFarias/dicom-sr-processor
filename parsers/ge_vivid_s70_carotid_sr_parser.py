from __future__ import annotations

from parsers.base_parser import BaseSRParser


class GEVividS70CarotidSRParser(BaseSRParser):
    parser_name = "GEVividS70CarotidSRParser"
    parser_version = "1.0.0"
    parser_family = "ge_vivids70_carotid_sr"
    compatibility_level = "strict"
    is_active = True

    supported_manufacturers = ["ge_healthcare_ultrasound"]
    supported_institutions = ["cardiology_and_fitness"]
    supported_models = ["vivid_s70"]
    supported_sop_class_uids = ["1.2.840.10008.5.1.4.1.1.88.33"]
    supported_content_profiles = ["vascular_doppler_sr"]

    def parse(self, dataset):
        extracted = super().parse(dataset)

        filtered = []
        for variable in extracted:
            if variable.concept_code_value is None:
                continue
            if variable.value_type not in {"NUM", "TEXT", "CODE", "CONTAINER"}:
                continue
            filtered.append(variable)

        return filtered