from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class SRDocument:
    id: int | None = None
    sop_instance_uid: str | None = None
    study_instance_uid: str | None = None
    series_instance_uid: str | None = None
    sop_class_uid: str | None = None
    manufacturer: str | None = None
    manufacturer_model_name: str | None = None
    institution_name: str | None = None
    station_name: str | None = None
    software_versions: str | None = None
    parser_key: str | None = None
    parser_name: str | None = None
    parser_family: str | None = None
    parser_version: str | None = None
    raw_metadata_json: dict[str, Any] = field(default_factory=dict)
    status: str = "received"
    received_at: datetime | None = None
    processing_started_at: datetime | None = None
    processing_finished_at: datetime | None = None
    needs_reprocessing: bool = False
    processing_error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        if self.received_at is not None:
            data["received_at"] = self.received_at.isoformat()
        if self.processing_started_at is not None:
            data["processing_started_at"] = self.processing_started_at.isoformat()
        if self.processing_finished_at is not None:
            data["processing_finished_at"] = self.processing_finished_at.isoformat()
        return data
