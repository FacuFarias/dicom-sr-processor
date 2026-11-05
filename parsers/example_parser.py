from __future__ import annotations

from parsers.base_parser import BaseSRParser


class ExampleParser(BaseSRParser):
    parser_name = "ExampleParser"
    parser_version = "1.0.0"
    parser_family = "siemens_acuson_sr"
    compatibility_level = "strict"
    is_active = True
    supported_manufacturers = ["siemens"]
    supported_institutions = ["hospital_central"]
    supported_models = ["acuson"]
    supported_sop_class_uids = ["1.2.840.10008.5.1.4.1.1.88.33"]

    def parse(self, dataset):
        return super().parse(dataset)
