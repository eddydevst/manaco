from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from .. import audit
from ..db import get_conn
from ..security import UsuarioActual, hash_password, requiere

router = APIRouter(prefix="/api", tags=["Usuarios y roles"])
ADMIN = requiere("usuarios.admin")


class UsuarioIn(BaseModel):
    nombre: str = Field(min_length=2, max_length=120)
    correo: str = Field(min_length=5, max_length=160)
    id_rol: int
    id_sucursal: int | None = None
    estado: str = "ACTIVO"
    password: str | None = Field(default=None, min_length=6)


class RolIn(BaseModel):
    nombre: str = Field(min_length=2, max_length=60)
    descripcion: str | None = None


class PermisosIn(BaseModel):
    permisos: list[str]


def _resumen_usuario(conn, id_usuario):
    return conn.execute(
        """SELECT u.nombre, u.correo, u.estado, s.nombre AS sucursal,
                  (SELECT string_agg(r.nombre, ', ') FROM usuarios_roles ur JOIN roles r USING (id_rol) WHERE ur.id_usuario = u.id_usuario) AS rol
             FROM usuarios u LEFT JOIN sucursales s ON s.id_sucursal = u.id_sucursal WHERE u.id_usuario = %s""",
        (id_usuario,),
    ).fetchone()


@router.get("/usuarios")
def listar_usuarios(conn=Depends(get_conn), _: UsuarioActual = Depends(ADMIN)):
    return conn.execute(
        """SELECT u.id_usuario, u.nombre, u.correo, u.estado, u.id_sucursal, s.nombre AS sucursal,
                  r.id_rol, r.nombre AS rol
             FROM usuarios u
             LEFT JOIN sucursales s ON s.id_sucursal = u.id_sucursal
             LEFT JOIN LATERAL (SELECT ur.id_rol FROM usuarios_roles ur WHERE ur.id_usuario = u.id_usuario ORDER BY ur.id_rol LIMIT 1) x ON TRUE
             LEFT JOIN roles r ON r.id_rol = x.id_rol
            ORDER BY u.nombre"""
    ).fetchall()


@router.post("/usuarios", status_code=201)
def crear_usuario(datos: UsuarioIn, conn=Depends(get_conn), usuario: UsuarioActual = Depends(ADMIN)):
    if not datos.password:
        raise HTTPException(400, "La contraseña es obligatoria (mínimo 6 caracteres).")
    if conn.execute("SELECT 1 FROM usuarios WHERE lower(correo) = lower(%s)", (datos.correo,)).fetchone():
        raise HTTPException(409, "Ya existe un usuario con ese correo.")
    nuevo = conn.execute(
        """INSERT INTO usuarios (nombre, correo, password_hash, estado, id_sucursal)
           VALUES (%s, lower(%s), %s, %s, %s) RETURNING id_usuario""",
        (datos.nombre.strip(), datos.correo.strip(), hash_password(datos.password), datos.estado, datos.id_sucursal),
    ).fetchone()["id_usuario"]
    conn.execute("INSERT INTO usuarios_roles (id_usuario, id_rol) VALUES (%s, %s)", (nuevo, datos.id_rol))
    audit.registrar(conn, usuario.id_usuario, "CREAR_USUARIO", "usuarios", nuevo, despues=_resumen_usuario(conn, nuevo))
    conn.commit()
    return {"id_usuario": nuevo}


@router.put("/usuarios/{id_usuario}")
def editar_usuario(id_usuario: int, datos: UsuarioIn, conn=Depends(get_conn), usuario: UsuarioActual = Depends(ADMIN)):
    antes = _resumen_usuario(conn, id_usuario)
    if not antes:
        raise HTTPException(404, "Usuario no encontrado.")
    if conn.execute("SELECT 1 FROM usuarios WHERE lower(correo) = lower(%s) AND id_usuario <> %s", (datos.correo, id_usuario)).fetchone():
        raise HTTPException(409, "Ya existe otro usuario con ese correo.")
    if id_usuario == usuario.id_usuario:
        tiene_admin = conn.execute(
            "SELECT 1 FROM roles_permisos rp JOIN permisos p USING (id_permiso) WHERE rp.id_rol = %s AND p.codigo = 'usuarios.admin'",
            (datos.id_rol,),
        ).fetchone()
        if not tiene_admin or datos.estado != "ACTIVO":
            raise HTTPException(400, "No puedes quitarte a ti mismo el acceso de administración.")
    conn.execute(
        "UPDATE usuarios SET nombre = %s, correo = lower(%s), estado = %s, id_sucursal = %s WHERE id_usuario = %s",
        (datos.nombre.strip(), datos.correo.strip(), datos.estado, datos.id_sucursal, id_usuario),
    )
    if datos.password:
        conn.execute("UPDATE usuarios SET password_hash = %s WHERE id_usuario = %s", (hash_password(datos.password), id_usuario))
    conn.execute("DELETE FROM usuarios_roles WHERE id_usuario = %s", (id_usuario,))
    conn.execute("INSERT INTO usuarios_roles (id_usuario, id_rol) VALUES (%s, %s)", (id_usuario, datos.id_rol))
    despues = dict(_resumen_usuario(conn, id_usuario), cambio_contrasena=bool(datos.password))
    audit.registrar(conn, usuario.id_usuario, "EDITAR_USUARIO", "usuarios", id_usuario, antes=antes, despues=despues)
    conn.commit()
    return {"ok": True}


@router.get("/permisos")
def listar_permisos(conn=Depends(get_conn), _: UsuarioActual = Depends(ADMIN)):
    return conn.execute("SELECT id_permiso, codigo, recurso, accion, descripcion FROM permisos ORDER BY id_permiso").fetchall()


@router.get("/roles")
def listar_roles(conn=Depends(get_conn), _: UsuarioActual = Depends(ADMIN)):
    return conn.execute(
        """SELECT r.id_rol, r.nombre, r.descripcion, r.es_sistema,
                  COALESCE((SELECT array_agg(p.codigo ORDER BY p.codigo) FROM roles_permisos rp JOIN permisos p USING (id_permiso)
                             WHERE rp.id_rol = r.id_rol), '{}') AS permisos,
                  (SELECT count(*) FROM usuarios_roles ur WHERE ur.id_rol = r.id_rol) AS usuarios
             FROM roles r ORDER BY r.id_rol"""
    ).fetchall()


@router.post("/roles", status_code=201)
def crear_rol(datos: RolIn, conn=Depends(get_conn), usuario: UsuarioActual = Depends(ADMIN)):
    if conn.execute("SELECT 1 FROM roles WHERE lower(nombre) = lower(%s)", (datos.nombre,)).fetchone():
        raise HTTPException(409, "Ya existe un rol con ese nombre.")
    id_rol = conn.execute(
        "INSERT INTO roles (nombre, descripcion) VALUES (%s, %s) RETURNING id_rol", (datos.nombre.strip(), datos.descripcion)
    ).fetchone()["id_rol"]
    audit.registrar(conn, usuario.id_usuario, "CREAR_ROL", "roles", id_rol, despues=datos.model_dump())
    conn.commit()
    return {"id_rol": id_rol}


@router.put("/roles/{id_rol}/permisos")
def asignar_permisos(id_rol: int, datos: PermisosIn, conn=Depends(get_conn), usuario: UsuarioActual = Depends(ADMIN)):
    rol = conn.execute("SELECT nombre, es_sistema FROM roles WHERE id_rol = %s", (id_rol,)).fetchone()
    if not rol:
        raise HTTPException(404, "Rol no encontrado.")
    if rol["es_sistema"]:
        raise HTTPException(400, "El rol Administrador siempre conserva todos los permisos.")
    mis_roles = [r["id_rol"] for r in conn.execute("SELECT id_rol FROM usuarios_roles WHERE id_usuario = %s", (usuario.id_usuario,))]
    if id_rol in mis_roles and "usuarios.admin" not in datos.permisos:
        raise HTTPException(400, "No puedes quitar a tu propio rol el permiso de administrar usuarios.")
    antes = [r["codigo"] for r in conn.execute(
        "SELECT p.codigo FROM roles_permisos rp JOIN permisos p USING (id_permiso) WHERE rp.id_rol = %s ORDER BY 1", (id_rol,))]
    validos = {r["codigo"]: r["id_permiso"] for r in conn.execute("SELECT codigo, id_permiso FROM permisos")}
    desconocidos = [p for p in datos.permisos if p not in validos]
    if desconocidos:
        raise HTTPException(400, f"Permisos desconocidos: {', '.join(desconocidos)}")
    conn.execute("DELETE FROM roles_permisos WHERE id_rol = %s", (id_rol,))
    for p in sorted(set(datos.permisos)):
        conn.execute("INSERT INTO roles_permisos (id_rol, id_permiso) VALUES (%s, %s)", (id_rol, validos[p]))
    audit.registrar(conn, usuario.id_usuario, "CAMBIAR_PERMISOS", "roles_permisos", id_rol,
                    antes={"rol": rol["nombre"], "permisos": antes}, despues={"rol": rol["nombre"], "permisos": sorted(set(datos.permisos))})
    conn.commit()
    return {"ok": True}
