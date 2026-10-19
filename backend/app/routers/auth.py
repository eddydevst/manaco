from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel

from .. import audit
from ..db import get_conn
from ..security import UsuarioActual, cargar_usuario, crear_token, get_current_user, verify_password

router = APIRouter(prefix="/api/auth", tags=["Autenticación"])


class LoginIn(BaseModel):
    correo: str
    password: str


def _login(conn, correo: str, password: str, ip: str | None):
    u = conn.execute(
        "SELECT id_usuario, password_hash, estado FROM usuarios WHERE lower(correo) = lower(%s)", (correo.strip(),)
    ).fetchone()
    if not u or not verify_password(password, u["password_hash"]):
        raise HTTPException(401, "Correo o contraseña incorrectos.")
    if u["estado"] != "ACTIVO":
        raise HTTPException(403, "Esta cuenta está inactiva.")
    usuario = cargar_usuario(conn, u["id_usuario"])
    audit.registrar(conn, usuario.id_usuario, "INICIO_SESION", "usuarios", usuario.id_usuario, despues={"correo": usuario.correo}, ip=ip)
    conn.commit()
    return {"access_token": crear_token(usuario.id_usuario), "token_type": "bearer", "usuario": usuario}


@router.post("/login")
def login(datos: LoginIn, request: Request, conn=Depends(get_conn)):
    return _login(conn, datos.correo, datos.password, request.client.host if request.client else None)


@router.post("/token", include_in_schema=True, summary="Login con formulario (para el botón Authorize de /docs)")
def token(form: OAuth2PasswordRequestForm = Depends(), conn=Depends(get_conn)):
    r = _login(conn, form.username, form.password, None)
    return {"access_token": r["access_token"], "token_type": "bearer"}


@router.get("/me", response_model=UsuarioActual)
def me(usuario: UsuarioActual = Depends(get_current_user)):
    return usuario
