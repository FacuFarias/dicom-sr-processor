from __future__ import annotations

from pathlib import Path

from core.fingerprint import build_fingerprint
from core.parser_loader import load_parsers, resolve_parser
from dicom.dicom_reader import read_dicom_metadata


def test_all_sr_examples_have_a_parser():
    examples_dir = Path(__file__).resolve().parents[1] / "sr_examples"
    parsers = load_parsers()

    for dcm_file in sorted(examples_dir.glob("*.dcm")):
        metadata = read_dicom_metadata(str(dcm_file))
        fingerprint = build_fingerprint(metadata)
        parser = resolve_parser(fingerprint, parsers)

        assert parser is not None, f"Sin parser para {dcm_file.name}"


def test_private_profile_sr_selects_private_parser():
    examples_dir = Path(__file__).resolve().parents[1] / "sr_examples"
    dcm_file = examples_dir / "1.2.840.113619.2.423.963336823046.1772652344.1390.dcm"

    metadata = read_dicom_metadata(str(dcm_file))
    fingerprint = build_fingerprint(metadata)
    parser = resolve_parser(fingerprint, load_parsers())

    assert metadata["content_profile"] == "ge_us_private_params"
    assert parser is not None
    assert parser.parser_name == "GELogiqFMyCarePrivateParamsSRParser"


def test_vascular_profile_srs_select_vascular_parser():
    examples_dir = Path(__file__).resolve().parents[1] / "sr_examples"
    filenames = [
        "1.2.840.113619.2.423.963336823046.1772718953.332.dcm",
        "1.2.840.113619.2.423.963336823046.1772805879.160.dcm",
    ]

    parsers = load_parsers()

    for name in filenames:
        dcm_file = examples_dir / name
        metadata = read_dicom_metadata(str(dcm_file))
        fingerprint = build_fingerprint(metadata)
        parser = resolve_parser(fingerprint, parsers)

        assert metadata["content_profile"] == "vascular_doppler_sr"
        assert parser is not None
        assert parser.parser_name == "GELogiqFMyCareSRParser"


def test_carotid_sr_selects_carotid_parser():
    examples_dir = Path(__file__).resolve().parents[1] / "sr_examples"
    dcm_file = examples_dir / "carotid.dcm"

    metadata = read_dicom_metadata(str(dcm_file))
    fingerprint = build_fingerprint(metadata)
    parser = resolve_parser(fingerprint, load_parsers())

    assert metadata["content_profile"] == "vascular_doppler_sr"
    assert parser is not None
    assert parser.parser_name == "GEVividS70CarotidSRParser"
