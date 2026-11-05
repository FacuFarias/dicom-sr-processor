from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class ParserManifest:
    parser_name: str
    parser_version: str
    parser_family: str
    supported_manufacturers: list[str] = field(default_factory=list)
    supported_institutions: list[str] = field(default_factory=list)
    supported_models: list[str] = field(default_factory=list)
    supported_sop_class_uids: list[str] = field(default_factory=list)
    compatibility_level: str = "strict"
    is_active: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def __str__(self) -> str:
        return (
            f"ParserManifest(name={self.parser_name}, version={self.parser_version}, "
            f"family={self.parser_family}, level={self.compatibility_level}, active={self.is_active})"
        )

    def equals(self, other: "ParserManifest") -> bool:
        return self.to_dict() == other.to_dict()
