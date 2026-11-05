from __future__ import annotations


def _parse_semver(version: str) -> tuple[int, int, int]:
    parts = (version or "0.0.0").split(".")
    numbers = []
    for index in range(3):
        if index < len(parts):
            chunk = "".join(ch for ch in parts[index] if ch.isdigit())
            numbers.append(int(chunk) if chunk else 0)
        else:
            numbers.append(0)
    return tuple(numbers)


def compare_versions(current_version: str, new_version: str) -> int:
    current = _parse_semver(current_version)
    new = _parse_semver(new_version)

    if new > current:
        return -1
    if new == current:
        return 0
    return 1


def should_mark_for_reprocessing(document, latest_manifest) -> bool:
    if latest_manifest is None:
        return False
    if not getattr(latest_manifest, "is_active", False):
        return False
    if getattr(latest_manifest, "compatibility_level", "strict") == "legacy":
        return False

    document_family = getattr(document, "parser_family", None)
    if not document_family or document_family != latest_manifest.parser_family:
        return False

    current_version = getattr(document, "parser_version", None)
    if not current_version:
        return False

    return compare_versions(current_version, latest_manifest.parser_version) == -1
