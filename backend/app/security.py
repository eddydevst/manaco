"""Autenticación (JWT), contraseñas cifradas y control de acceso por permisos (RBAC)."""
import base64
import hashlib
import hmac
import os
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel

from . import config
from .db import get_conn

PBKDF2_ITERACIONES = 390_000


# ---------------------------------------------------------------- contraseñas
def hash_password(password: str) -> str:
    """PBKDF2-SHA256 con sal aleatoria (biblioteca estándar de Python)."""
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, PBKDF2_ITERACIONES)
    return "pbkdf2_sha256${}${}${}".format(
        PBKDF2_ITERACIONES, base64.b64encode(salt).decode(), base64.b64encode(dk).decode()
    )


def verify_password(password: str, stored: str) -> bool:
    try:
        algoritmo, iteraciones, salt_b64, hash_b64 = stored.split("$")
        if algoritmo != "pbkdf2_sha256":
            return False
        dk = hashlib.pbkdf2_hmac("sha256", password.encode(), base64.b64decode(salt_b64), int(iteraciones))
        return hmac.compare_digest(dk, base64.b64decode(hash_b64))
    except (ValueError, TypeError):
        return False


# ---------------------------------------------------------------- tokens
def crear_token(id_usuario: int) -> str:
    ahora = datetime.now(timezone.utc)
    payload = {"sub": str(id_usuario), "iat": ahora, "exp": ahora + timedelta(minutes=config.JWT_EXPIRE_MINUTES)}
    return jwt.encode(payload, config.JWT_SECRET, algorithm=config.JWT_ALGORITHM)


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/token")


class UsuarioActual(BaseModel):
    id_usuario: int
    nombre: str
    correo: str
    id_sucursal: int | None
    sucursal: str | None
    roles: list[str]
    permisos: list[str]

    def puede(self, permiso: str) -> bool:
        return permiso in self.permisos


def cargar_usuario(conn, id_usuario: int) -> UsuarioActual | None:
    u = conn.execute(
        """SELECT u.id_usuario, u.nombre, u.correo, u.id_sucursal, u.estado, s.nombre AS sucursal
             FROM usuarios u LEFT JOIN sucursales s ON s.id_sucursal = u.id_sucursal
            WHERE u.id_usuario = %s""",
        (id_usuario,),
    ).fetchone()
    if not u or u["estado"] != "ACTIVO":
        return None
    roles = [r["nombre"] for r in conn.execute(
        "SELECT r.nombre FROM usuarios_roles ur JOIN roles r USING (id_rol) WHERE ur.id_usuario = %s ORDER BY r.nombre",
        (id_usuario,),
    )]
    permisos = [r["codigo"] for r in conn.execute(
        """SELECT DISTINCT p.codigo FROM usuarios_roles ur
             JOIN roles_permisos rp ON rp.id_rol = ur.id_rol
             JOIN permisos p ON p.id_permiso = rp.id_permiso
            WHERE ur.id_usuario = %s ORDER BY p.codigo""",
        (id_usuario,),
    )]
    return UsuarioActual(
        id_usuario=u["id_usuario"], nombre=u["nombre"], correo=u["correo"], id_sucursal=u["id_sucursal"],
        sucursal=u["sucursal"], roles=roles, permisos=permisos,
    )


def get_current_user(token: str = Depends(oauth2_scheme), conn=Depends(get_conn)) -> UsuarioActual:
    no_autorizado = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="La sesión expiró o no es válida. Vuelve a iniciar sesión.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, config.JWT_SECRET, algorithms=[config.JWT_ALGORITHM])
        id_usuario = int(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        raise no_autorizado
    usuario = cargar_usuario(conn, id_usuario)
    if usuario is None:
        raise no_autorizado
    return usuario


def requiere(*permisos: str):
    """Dependencia: el usuario debe tener al menos uno de los permisos indicados."""

    def dependencia(usuario: UsuarioActual = Depends(get_current_user)) -> UsuarioActual:
        if not any(p in usuario.permisos for p in permisos):
            raise HTTPException(status_code=403, detail="Tu rol no tiene permiso para esta acción.")
        return usuario

    return dependencia


def sucursal_efectiva(usuario: UsuarioActual, id_sucursal: int | None) -> int | None:
    """Aplica la restricción por sucursal: un usuario asignado a una sucursal solo opera en ella."""
    if usuario.id_sucursal is not None:
        if id_sucursal is not None and id_sucursal != usuario.id_sucursal:
            raise HTTPException(status_code=403, detail="Solo puedes operar en tu sucursal asignada.")
        return usuario.id_sucursal
    return id_sucursal
