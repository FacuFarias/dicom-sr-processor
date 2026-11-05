from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass
class ReportTemplate:
    id: int | None = None
    name: str | None = None
    facility_id: int | None = None
    parser_family: str | None = None
    template_body: str | None = None
    is_active: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
