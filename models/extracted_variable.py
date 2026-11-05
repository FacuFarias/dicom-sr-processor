from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any


@dataclass
class ExtractedVariable:
    dicom_tag: str | None = None
    dicom_description: str | None = None
    dicom_path: str | None = None
    concept_code_value: str | None = None
    concept_code_scheme: str | None = None
    concept_code_meaning: str | None = None
    canonical_variable_definition_id: int | None = None
    canonical_code: str | None = None
    canonical_name: str | None = None
    facility_description: str | None = None
    mapping_status: str | None = None
    value_type: str | None = None
    value_text: str | None = None
    value_numeric: float | str | None = None
    value_unit: str | None = None
    value_datetime: datetime | str | None = None
    sequence_index: int | None = None
    raw_value: Any = None
    raw_item_json: dict[str, Any] | list[Any] | str | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        if isinstance(self.value_datetime, datetime):
            payload["value_datetime"] = self.value_datetime.isoformat()
        return payload

    def __str__(self) -> str:
        path = self.dicom_path or "<sin_path>"
        concept = self.concept_code_meaning or self.concept_code_value or "<sin_concepto>"
        value = self.value_numeric if self.value_numeric is not None else self.value_text
        return f"ExtractedVariable(path={path}, concept={concept}, value={value})"
