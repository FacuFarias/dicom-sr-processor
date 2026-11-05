from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    project_name: str = "dicom_sr_processor"
    base_dir: Path = Path(__file__).resolve().parents[1]
    db_host: str = os.getenv("DB_HOST", "localhost")
    db_port: int = int(os.getenv("DB_PORT", "5432"))
    db_name: str = os.getenv("DB_NAME", "pacsdb")
    db_user: str = os.getenv("DB_USER", "pacs")
    db_pass: str = os.getenv("DB_PASS", "pacs")
    db_schema: str = os.getenv("DICOM_SR_SCHEMA", "dicom_sr")
    default_facility_id: int = int(os.getenv("DICOM_SR_DEFAULT_FACILITY_ID", "1"))


settings = Settings()
