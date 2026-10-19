"""Registro de operaciones en la bitácora (se guarda en la misma transacción que la operación)."""
from typing import Any

from fastapi.encoders import jsonable_encoder
from psycopg.types.json import Jsonb


def registrar(conn, id_usuario: int | None, accion: str, entidad: str, id_entidad: Any = None,
              antes: Any = None, despues: Any = None, ip: str | None = None) -> None:
    conn.execute(
        """INSERT INTO bitacora (id_usuario, accion, entidad, id_entidad, datos_anteriores, datos_nuevos, ip)
           VALUES (%s, %s, %s, %s, %s, %s, %s)""",
        (
            id_usuario, accion, entidad,
            None if id_entidad is None else str(id_entidad),
            None if antes is None else Jsonb(jsonable_encoder(antes)),
            None if despues is None else Jsonb(jsonable_encoder(despues)),
            ip,
        ),
    )
