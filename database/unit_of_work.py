from __future__ import annotations

from database.connection import ensure_schema, get_connection


class UnitOfWork:
    def __init__(self):
        self.connection = None

    def __enter__(self):
        self.connection = get_connection()
        ensure_schema(self.connection)
        return self.connection

    def __exit__(self, exc_type, exc_value, traceback):
        if self.connection is None:
            return False

        if exc_type is None:
            self.connection.commit()
        else:
            self.connection.rollback()

        self.connection.close()
        return False
