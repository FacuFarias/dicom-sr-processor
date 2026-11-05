from __future__ import annotations

import importlib.util
import inspect
from pathlib import Path
from typing import List

from models.parser_manifest import ParserManifest
from parsers.base_parser import BaseSRParser


def _load_module_from_file(module_name: str, file_path: Path):
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    if spec is None or spec.loader is None:
        return None

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_parsers(parsers_dir: Path | None = None) -> List[BaseSRParser]:
    if parsers_dir is None:
        parsers_dir = Path(__file__).resolve().parents[1] / "parsers"

    parser_instances: List[BaseSRParser] = []

    for parser_file in sorted(parsers_dir.glob("*.py")):
        if parser_file.name in {"__init__.py", "base_parser.py"}:
            continue

        module_name = f"dynamic_parsers.{parser_file.stem}"
        module = _load_module_from_file(module_name, parser_file)
        if module is None:
            continue

        for _, obj in inspect.getmembers(module, inspect.isclass):
            if obj is BaseSRParser:
                continue
            if issubclass(obj, BaseSRParser):
                parser_instances.append(obj())

    parser_instances.sort(key=lambda parser: parser.__class__.__name__)
    return parser_instances


def get_parser_manifests(parsers: list[BaseSRParser]) -> list[ParserManifest]:
    manifests: list[ParserManifest] = []

    for parser in parsers:
        manifest_payload = parser.get_manifest()
        manifests.append(ParserManifest(**manifest_payload))

    manifests.sort(key=lambda item: (item.parser_family, item.parser_name, item.parser_version))
    return manifests


def _normalize(value) -> str:
    if value is None:
        return "unknown"
    normalized = str(value).strip().lower().replace(" ", "_")
    return normalized or "unknown"


def _field_score(supported_values: list, fingerprint_value: str, points: int):
    normalized_supported = [_normalize(item) for item in (supported_values or ["*"])]
    if "*" in normalized_supported:
        return True, 0
    if fingerprint_value in normalized_supported:
        return True, points
    return False, 0


def _score_parser(parser: BaseSRParser, fingerprint: dict) -> int:
    manufacturer = _normalize(fingerprint.get("manufacturer"))
    institution_name = _normalize(fingerprint.get("institution_name"))
    manufacturer_model_name = _normalize(fingerprint.get("manufacturer_model_name"))
    sop_class_uid = _normalize(fingerprint.get("sop_class_uid"))
    content_profile = _normalize(fingerprint.get("content_profile"))

    matched, manufacturer_score = _field_score(
        getattr(parser, "supported_manufacturers", ["*"]), manufacturer, 4
    )
    if not matched:
        return -1

    matched, institution_score = _field_score(
        getattr(parser, "supported_institutions", ["*"]), institution_name, 3
    )
    if not matched:
        return -1

    matched, model_score = _field_score(
        getattr(parser, "supported_models", ["*"]), manufacturer_model_name, 2
    )
    if not matched:
        return -1

    matched, sop_score = _field_score(
        getattr(parser, "supported_sop_class_uids", ["*"]), sop_class_uid, 5
    )
    if not matched:
        return -1

    matched, content_profile_score = _field_score(
        getattr(parser, "supported_content_profiles", ["*"]), content_profile, 1
    )
    if not matched:
        return -1

    return (
        manufacturer_score
        + institution_score
        + model_score
        + sop_score
        + content_profile_score
    )


def resolve_parser(fingerprint: dict, parsers: list):
    best_parser = None
    best_score = -1

    for parser in parsers:
        if not parser.can_parse(fingerprint):
            continue

        current_score = _score_parser(parser, fingerprint)
        if current_score > best_score:
            best_score = current_score
            best_parser = parser

    if best_score < 0:
        return None

    return best_parser
