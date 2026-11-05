from __future__ import annotations

import re


def _normalize_key(value: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9]+", "_", value.strip().lower())
    return normalized.strip("_")


def build_report_context(metadata: dict, variables: list) -> dict:
    context: dict[str, object] = {
        "patient_name": metadata.get("patient_name") or "",
        "patient_id": metadata.get("patient_id") or "",
        "manufacturer": metadata.get("manufacturer") or "",
        "institution_name": metadata.get("institution_name") or "",
        "study_instance_uid": metadata.get("study_instance_uid") or "",
        "series_instance_uid": metadata.get("series_instance_uid") or "",
        "sop_instance_uid": metadata.get("sop_instance_uid") or "",
    }

    for variable in variables:
        if variable.value_numeric is not None:
            value = variable.value_numeric
            if variable.value_unit:
                value = f"{value} {variable.value_unit}"
        elif variable.value_text is not None:
            value = variable.value_text
        else:
            value = ""

        key_candidates = []

        if variable.canonical_code:
            key_candidates.append(variable.canonical_code)

        if variable.concept_code_scheme and variable.concept_code_value:
            key_candidates.append(
                f"concept_{variable.concept_code_scheme}_{variable.concept_code_value}"
            )

        if variable.concept_code_meaning:
            key_candidates.append(variable.concept_code_meaning)

        for key in key_candidates:
            normalized_key = _normalize_key(str(key))
            if normalized_key and normalized_key not in context:
                context[normalized_key] = value

    return context


def render_template(template_body: str, context: dict) -> str:
    pattern = re.compile(r"\{\{\s*([a-zA-Z0-9_\-\.]+)\s*\}\}")

    def replace(match):
        key = _normalize_key(match.group(1))
        value = context.get(key)
        if value is None:
            return ""
        return str(value)

    return pattern.sub(replace, template_body)
