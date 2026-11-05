from __future__ import annotations

from parsers.base_parser import BaseSRParser


class GELogiqFMyCarePrivateParamsSRParser(BaseSRParser):
    parser_name = "GELogiqFMyCarePrivateParamsSRParser"
    parser_version = "1.0.0"
    parser_family = "ge_logiqf_private_params_sr"
    compatibility_level = "strict"
    is_active = True

    supported_manufacturers = ["ge_healthcare"]
    supported_institutions = ["mycare_medical"]
    supported_models = ["logiqf"]
    supported_sop_class_uids = ["1.2.840.10008.5.1.4.1.1.88.33"]
    supported_content_profiles = ["ge_us_private_params"]

    def parse(self, dataset):
        extracted = super().parse(dataset)

        filtered = []
        for variable in extracted:
            if variable.concept_code_value is None:
                continue
            if variable.value_type not in {"NUM", "TEXT", "CODE"}:
                continue
            filtered.append(variable)

        return filtered
