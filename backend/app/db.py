"""Conexión a PostgreSQL con psycopg 3.

Cada petición HTTP recibe su propia conexión (transacción). Los endpoints que
escriben llaman a conn.commit() al final; si ocurre un error, la conexión se
cierra sin confirmar y PostgreSQL deshace todo (integridad transaccional).
"""
from collections.abc import Iterator

import psycopg
from psycopg.rows import dict_row

from . import config


def conninfo() -> str:
    return psycopg.conninfo.make_conninfo(
        host=config.DB_HOST,
        port=config.DB_PORT,
        dbname=config.DB_NAME,
        user=config.DB_USER,
        password=config.DB_PASSWORD,
        options=f"-c search_path={config.SCHEMA},public -c timezone={config.TIMEZONE}",
        application_name="manaco-api",
    )


def connect() -> psycopg.Connection:
    return psycopg.connect(conninfo(), row_factory=dict_row)


def get_conn() -> Iterator[psycopg.Connection]:
    conn = connect()
    try:
        yield conn
    finally:
        if not conn.closed:
            conn.rollback()  # no hace nada si el endpoint ya confirmó
            conn.close()
