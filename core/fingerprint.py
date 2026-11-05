from __future__ import annotations


def _normalize_value(value) -> str:
    if value is None:
        return "unknown"

    normalized = str(value).strip().lower().replace(" ", "_")
    return normalized or "unknown"


def build_fingerprint(metadata: dict) -> dict:
    fingerprint = {
        "manufacturer": _normalize_value(metadata.get("manufacturer")),
        "institution_name": _normalize_value(metadata.get("institution_name")),
        "manufacturer_model_name": _normalize_value(
            metadata.get("manufacturer_model_name")
        ),
        "sop_class_uid": _normalize_value(metadata.get("sop_class_uid")),
        "content_profile": _normalize_value(metadata.get("content_profile")),
    }

    fingerprint["parser_key"] = (
        f"{fingerprint['manufacturer']}|"
        f"{fingerprint['institution_name']}|"
        f"{fingerprint['manufacturer_model_name']}|"
        f"{fingerprint['sop_class_uid']}"
    )

    return fingerprint
