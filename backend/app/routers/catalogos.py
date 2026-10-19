from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from .. import audit
from ..db import get_conn
from ..security import UsuarioActual, get_current_user, requiere

router = APIRouter(prefix="/api", tags=["Catálogos"])


class CategoriaIn(BaseModel):
    codigo: str = Field(min_length=2, max_length=6)
    nombre: str = Field(min_length=2, max_length=80)
    descripcion: str | None = None


@router.get("/sucursales")
def sucursales(conn=Depends(get_conn), _: UsuarioActual = Depends(get_current_user)):
    return conn.execute(
        "SELECT id_sucursal, codigo, nombre, ubicacion, estado FROM sucursales ORDER BY id_sucursal"
    ).fetchall()


@router.get("/categorias")
def categorias(conn=Depends(get_conn), _: UsuarioActual = Depends(get_current_user)):
    return conn.execute(
        """SELECT c.id_categoria, c.codigo, c.nombre, c.descripcion,
                  (SELECT count(*) FROM productos p WHERE p.id_categoria = c.id_categoria) AS productos
             FROM categorias c ORDER BY c.nombre"""
    ).fetchall()


@router.post("/categorias", status_code=201)
def crear_categoria(datos: CategoriaIn, conn=Depends(get_conn), usuario: UsuarioActual = Depends(requiere("productos.editar"))):
    codigo = datos.codigo.strip().upper()
    if conn.execute("SELECT 1 FROM categorias WHERE codigo = %s OR lower(nombre) = lower(%s)", (codigo, datos.nombre)).fetchone():
        raise HTTPException(409, "Ya existe una categoría con ese código o nombre.")
    id_cat = conn.execute(
        "INSERT INTO categorias (codigo, nombre, descripcion) VALUES (%s, %s, %s) RETURNING id_categoria",
        (codigo, datos.nombre.strip(), datos.descripcion),
    ).fetchone()["id_categoria"]
    audit.registrar(conn, usuario.id_usuario, "CREAR_CATEGORIA", "categorias", id_cat, despues={"codigo": codigo, "nombre": datos.nombre})
    conn.commit()
    return {"id_categoria": id_cat}


@router.get("/clientes")
def clientes(q: str = "", conn=Depends(get_conn), _: UsuarioActual = Depends(requiere("pos.vender", "reportes.ver"))):
    return conn.execute(
        "SELECT id_cliente, nombre, documento, contacto FROM clientes WHERE nombre ILIKE %s ORDER BY nombre LIMIT 20",
        (f"%{q}%",),
    ).fetchall()
