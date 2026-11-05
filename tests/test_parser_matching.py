from core.parser_loader import resolve_parser
from parsers.base_parser import BaseSRParser
from parsers.example_parser import ExampleParser
from parsers.ge_logiqf_mycare_private_params_sr_parser import (
    GELogiqFMyCarePrivateParamsSRParser,
)
from parsers.ge_logiqf_mycare_sr_parser import GELogiqFMyCareSRParser


class GenericSiemensParser(BaseSRParser):
    parser_name = "GenericSiemensParser"
    parser_version = "1.0"
    supported_manufacturers = ["siemens"]
    supported_institutions = ["*"]
    supported_models = ["*"]
    supported_sop_class_uids = ["*"]

    def parse(self, dataset):
        return []


class SpecificSiemensParser(BaseSRParser):
    parser_name = "SpecificSiemensParser"
    parser_version = "1.0"
    supported_manufacturers = ["siemens"]
    supported_institutions = ["hospital_central"]
    supported_models = ["acuson"]
    supported_sop_class_uids = ["1.2.840.10008.5.1.4.1.1.88.33"]

    def parse(self, dataset):
        return []


def test_matching_selects_example_parser_for_exact_fingerprint():
    fingerprint = {
        "manufacturer": "siemens",
        "institution_name": "hospital_central",
        "manufacturer_model_name": "acuson",
        "sop_class_uid": "1.2.840.10008.5.1.4.1.1.88.33",
        "content_profile": "generic_sr",
    }
    parser = resolve_parser(fingerprint, [ExampleParser()])
    assert parser is not None
    assert parser.parser_name == "ExampleParser"


def test_matching_rejects_when_institution_does_not_match():
    fingerprint = {
        "manufacturer": "siemens",
        "institution_name": "otro_hospital",
        "manufacturer_model_name": "acuson",
        "sop_class_uid": "1.2.840.10008.5.1.4.1.1.88.33",
        "content_profile": "generic_sr",
    }
    parser = resolve_parser(fingerprint, [ExampleParser()])
    assert parser is None


def test_more_specific_parser_wins_over_generic_parser():
    fingerprint = {
        "manufacturer": "siemens",
        "institution_name": "hospital_central",
        "manufacturer_model_name": "acuson",
        "sop_class_uid": "1.2.840.10008.5.1.4.1.1.88.33",
        "content_profile": "generic_sr",
    }
    parser = resolve_parser(
        fingerprint,
        [GenericSiemensParser(), SpecificSiemensParser()],
    )
    assert parser is not None
    assert parser.parser_name == "SpecificSiemensParser"


def test_matching_selects_ge_logiqf_mycare_parser():
    fingerprint = {
        "manufacturer": "ge_healthcare",
        "institution_name": "mycare_medical",
        "manufacturer_model_name": "logiqf",
        "sop_class_uid": "1.2.840.10008.5.1.4.1.1.88.33",
        "content_profile": "vascular_doppler_sr",
    }
    parser = resolve_parser(fingerprint, [GELogiqFMyCareSRParser()])
    assert parser is not None
    assert parser.parser_name == "GELogiqFMyCareSRParser"


def test_matching_selects_ge_private_params_parser_for_private_profile():
    fingerprint = {
        "manufacturer": "ge_healthcare",
        "institution_name": "mycare_medical",
        "manufacturer_model_name": "logiqf",
        "sop_class_uid": "1.2.840.10008.5.1.4.1.1.88.33",
        "content_profile": "ge_us_private_params",
    }
    parser = resolve_parser(
        fingerprint,
        [GELogiqFMyCareSRParser(), GELogiqFMyCarePrivateParamsSRParser()],
    )
    assert parser is not None
    assert parser.parser_name == "GELogiqFMyCarePrivateParamsSRParser"
