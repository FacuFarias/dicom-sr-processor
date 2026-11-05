from __future__ import annotations

import json

from config.settings import settings
from models.parser_manifest import ParserManifest
from services.parser_versioning_service import compare_versions


def _row_to_manifest(row) -> ParserManifest:
    return ParserManifest(
        parser_name=row[0],
        parser_version=row[1],
        parser_family=row[2],
        compatibility_level=row[3],
        is_active=row[4],
        supported_manufacturers=row[5] or [],
        supported_institutions=row[6] or [],
        supported_models=row[7] or [],
        supported_sop_class_uids=row[8] or [],
    )


def upsert_parser_manifest(connection, manifest) -> int:
    if isinstance(manifest, dict):
        manifest = ParserManifest(**manifest)

    query = f"""
        INSERT INTO {settings.db_schema}.parser_manifest (
            parser_name,
            parser_version,
            parser_family,
            compatibility_level,
            is_active,
            supported_manufacturers,
            supported_institutions,
            supported_models,
            supported_sop_class_uids,
            created_at,
            updated_at
        ) VALUES (
            %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, %s::jsonb, %s::jsonb, NOW(), NOW()
        )
        ON CONFLICT (parser_name, parser_version)
        DO UPDATE SET
            parser_family = EXCLUDED.parser_family,
            compatibility_level = EXCLUDED.compatibility_level,
            is_active = EXCLUDED.is_active,
            supported_manufacturers = EXCLUDED.supported_manufacturers,
            supported_institutions = EXCLUDED.supported_institutions,
            supported_models = EXCLUDED.supported_models,
            supported_sop_class_uids = EXCLUDED.supported_sop_class_uids,
            updated_at = NOW()
        RETURNING id;
    """

    with connection.cursor() as cursor:
        cursor.execute(
            query,
            (
                manifest.parser_name,
                manifest.parser_version,
                manifest.parser_family,
                manifest.compatibility_level,
                manifest.is_active,
                json.dumps(manifest.supported_manufacturers),
                json.dumps(manifest.supported_institutions),
                json.dumps(manifest.supported_models),
                json.dumps(manifest.supported_sop_class_uids),
            ),
        )
        return int(cursor.fetchone()[0])


def get_parser_manifest(connection, parser_name, parser_version):
    query = f"""
        SELECT parser_name, parser_version, parser_family, compatibility_level, is_active,
               supported_manufacturers, supported_institutions, supported_models,
               supported_sop_class_uids
          FROM {settings.db_schema}.parser_manifest
         WHERE parser_name = %s
           AND parser_version = %s;
    """
    with connection.cursor() as cursor:
        cursor.execute(query, (parser_name, parser_version))
        row = cursor.fetchone()
    return _row_to_manifest(row) if row else None


def list_active_parsers(connection) -> list[ParserManifest]:
    query = f"""
        SELECT parser_name, parser_version, parser_family, compatibility_level, is_active,
               supported_manufacturers, supported_institutions, supported_models,
               supported_sop_class_uids
          FROM {settings.db_schema}.parser_manifest
         WHERE is_active = true
      ORDER BY parser_family, parser_name, parser_version;
    """
    with connection.cursor() as cursor:
        cursor.execute(query)
        rows = cursor.fetchall()

    return [_row_to_manifest(row) for row in rows]


def get_latest_parser_version(connection, parser_family):
    query = f"""
        SELECT parser_name, parser_version, parser_family, compatibility_level, is_active,
               supported_manufacturers, supported_institutions, supported_models,
               supported_sop_class_uids
          FROM {settings.db_schema}.parser_manifest
         WHERE parser_family = %s
      ORDER BY parser_name, parser_version;
    """
    with connection.cursor() as cursor:
        cursor.execute(query, (parser_family,))
        rows = cursor.fetchall()

    manifests = [_row_to_manifest(row) for row in rows]
    if not manifests:
        return None

    latest = manifests[0]
    for manifest in manifests[1:]:
        if compare_versions(latest.parser_version, manifest.parser_version) == -1:
            latest = manifest

    return latest
