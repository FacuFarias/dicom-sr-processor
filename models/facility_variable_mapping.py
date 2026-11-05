from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass
class FacilityVariableMapping:
    id: int | None = None
    parser_family: str | None = None
    parser_key: str | None = None
    semantic_signature: str | None = None
    source_type: str | None = None
    concept_code_value: str | None = None
    concept_code_scheme: str | None = None
    concept_code_meaning: str | None = None
    canonical_name: str | None = None
    canonical_code: str | None = None
    unit: str | None = None
    facility_id: str | None = None
    facility_name: str | None = None
    facility_code: str | None = None
    base_variable_id: int | None = None
    use_for_runtime_mapping: bool = True
    active: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
