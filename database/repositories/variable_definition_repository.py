from __future__ import annotations

from config.settings import settings
from models.variable_definition import VariableDefinition


def _row_to_definition(row) -> VariableDefinition | None:
    if row is None:
        return None
    return VariableDefinition(
        id=row[0],
        canonical_code=row[1],
        canonical_name=row[2],
        unit=row[3],
        value_type=row[4],
        description=row[5],
        active=row[6],
    )


def get_variable_definition_by_id(connection, definition_id):
    query = f"""
        SELECT id, canonical_code, canonical_name, unit, value_type, description, active
        FROM {settings.db_schema}.variable_definition
        WHERE id = %s;
    """
    with connection.cursor() as cursor:
        cursor.execute(query, (definition_id,))
        return _row_to_definition(cursor.fetchone())


def get_variable_definition_by_code(connection, canonical_code):
    query = f"""
        SELECT id, canonical_code, canonical_name, unit, value_type, description, active
        FROM {settings.db_schema}.variable_definition
        WHERE canonical_code = %s;
    """
    with connection.cursor() as cursor:
        cursor.execute(query, (canonical_code,))
        return _row_to_definition(cursor.fetchone())


def insert_variable_definition(connection, variable_definition: VariableDefinition) -> int:
    query = f"""
        INSERT INTO {settings.db_schema}.variable_definition (
            canonical_code,
            canonical_name,
            unit,
            value_type,
            description,
            active
        ) VALUES (%s, %s, %s, %s, %s, %s)
        RETURNING id;
    """
    with connection.cursor() as cursor:
        cursor.execute(
            query,
            (
                variable_definition.canonical_code,
                variable_definition.canonical_name,
                variable_definition.unit,
                variable_definition.value_type,
                variable_definition.description,
                variable_definition.active,
            ),
        )
        return int(cursor.fetchone()[0])


def list_active_variable_definitions(connection) -> list[VariableDefinition]:
    query = f"""
        SELECT id, canonical_code, canonical_name, unit, value_type, description, active
        FROM {settings.db_schema}.variable_definition
        WHERE active = true
        ORDER BY canonical_code;
    """
    with connection.cursor() as cursor:
        cursor.execute(query)
        rows = cursor.fetchall()
    return [_row_to_definition(row) for row in rows]
