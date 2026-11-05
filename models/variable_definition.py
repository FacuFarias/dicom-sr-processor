from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass
class VariableDefinition:
    id: int | None = None
    canonical_code: str | None = None
    canonical_name: str | None = None
    unit: str | None = None
    value_type: str | None = None
    description: str | None = None
    active: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def __str__(self) -> str:
        return (
            f"VariableDefinition(id={self.id}, code={self.canonical_code}, "
            f"name={self.canonical_name}, unit={self.unit}, type={self.value_type}, "
            f"active={self.active})"
        )
