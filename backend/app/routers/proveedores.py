from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from .. import audit
from ..db import get_conn
from ..security import UsuarioActual, requiere

router = APIRouter(prefix="/api", tags=["Proveedores y socios"])

CUMPLIMIENTO_SQL = """
SELECT o.id_proveedor,
       count(*) FILTER (WHERE o.estado = 'RECIBIDA') AS cerradas,
       count(*) FILTER (WHERE o.estado = 'RECIBIDA' AND ur.ultima::date <= o.fecha_entrega) AS a_tiempo,
       sum(d.pedido) FILTER (WHERE o.estado = 'RECIBIDA') AS pedido,
       sum(d.recibido) FILTER (WHERE o.estado = 'RECIBIDA') AS recibido
  FROM ordenes_compra o
  LEFT JOIN (SELECT id_orden, max(fecha) AS ultima FROM recepciones_compra GROUP BY id_orden) ur ON ur.id_orden = o.id_orden
  LEFT JOIN (SELECT id_orden, sum(cantidad) AS pedido, sum(cantidad_recibida) AS recibido FROM detalle_orden_compra GROUP BY id_orden) d
         ON d.id_orden = o.id_orden
 WHERE o.estado IN ('RECIBIDA','RECIBIDA_PARCIAL','APROBADA')
 GROUP BY o.id_proveedor
"""


class ProveedorIn(BaseModel):
    codigo: str = Field(min_length=2, max_length=10)
    razon_social: str = Field(min_length=2, max_length=160)
    nit: str | None = None
    contacto: str | None = None
    telefono: str | None = None
    correo: str | None = None
    pais: str | None = None
    estado: str = "ACTIVO"


class ProductoProveedorIn(BaseModel):
    id_producto: int
    codigo_proveedor: str | None = None
    costo_referencia: float | None = Field(default=None, ge=0)


class SocioIn(BaseModel):
    nombre: str = Field(min_length=2, max_length=160)
    pais: str = Field(min_length=2, max_length=60)
    tipo_relacion: str = Field(min_length=2, max_length=40)
    descripcion: str | None = None
    estado: str = "ACTIVO"


@router.get("/proveedores")
def listar(conn=Depends(get_conn), _: UsuarioActual = Depends(requiere("proveedores.ver", "compras.crear"))):
    return conn.execute(
        f"""SELECT p.*, COALESCE(o.ordenes, 0) AS ordenes, COALESCE(o.monto, 0) AS monto_comprado,
                   CASE WHEN c.cerradas > 0 THEN c.a_tiempo::numeric / c.cerradas END AS a_tiempo,
                   CASE WHEN c.pedido > 0 THEN c.recibido::numeric / c.pedido END AS cantidad_entregada,
                   (SELECT count(*) FROM productos_proveedores pp WHERE pp.id_proveedor = p.id_proveedor) AS productos
              FROM proveedores p
              LEFT JOIN (SELECT id_proveedor, count(*) AS ordenes, sum(total) AS monto FROM ordenes_compra
                          WHERE estado <> 'RECHAZADA' GROUP BY id_proveedor) o ON o.id_proveedor = p.id_proveedor
              LEFT JOIN ({CUMPLIMIENTO_SQL}) c ON c.id_proveedor = p.id_proveedor
             ORDER BY p.codigo"""
    ).fetchall()


@router.get("/proveedores/{id_proveedor}")
def detalle(id_proveedor: int, conn=Depends(get_conn), _: UsuarioActual = Depends(requiere("proveedores.ver"))):
    p = conn.execute("SELECT * FROM proveedores WHERE id_proveedor = %s", (id_proveedor,)).fetchone()
    if not p:
        raise HTTPException(404, "Proveedor no encontrado.")
    p["productos"] = conn.execute(
        """SELECT pp.id_producto, pr.modelo, pr.marca, pp.codigo_proveedor, pp.costo_referencia
             FROM productos_proveedores pp JOIN productos pr USING (id_producto) WHERE pp.id_proveedor = %s ORDER BY pr.modelo""",
        (id_proveedor,),
    ).fetchall()
    p["ordenes"] = conn.execute(
        "SELECT id_orden, numero, fecha, fecha_entrega, total, estado FROM ordenes_compra WHERE id_proveedor = %s ORDER BY fecha DESC",
        (id_proveedor,),
    ).fetchall()
    p["cumplimiento"] = conn.execute(f"SELECT * FROM ({CUMPLIMIENTO_SQL}) c WHERE c.id_proveedor = %s", (id_proveedor,)).fetchone()
    return p


@router.post("/proveedores", status_code=201)
def crear(datos: ProveedorIn, conn=Depends(get_conn), usuario: UsuarioActual = Depends(requiere("proveedores.editar"))):
    if conn.execute("SELECT 1 FROM proveedores WHERE upper(codigo) = upper(%s)", (datos.codigo,)).fetchone():
        raise HTTPException(409, "Ese código de proveedor ya existe.")
    d = datos.model_dump()
    d["codigo"] = d["codigo"].strip().upper()
    id_p = conn.execute(
        """INSERT INTO proveedores (codigo, razon_social, nit, contacto, telefono, correo, pais, estado)
           VALUES (%(codigo)s, %(razon_social)s, %(nit)s, %(contacto)s, %(telefono)s, %(correo)s, %(pais)s, %(estado)s)
           RETURNING id_proveedor""",
        d,
    ).fetchone()["id_proveedor"]
    audit.registrar(conn, usuario.id_usuario, "CREAR_PROVEEDOR", "proveedores", id_p, despues=d)
    conn.commit()
    return {"id_proveedor": id_p}


@router.put("/proveedores/{id_proveedor}")
def editar(id_proveedor: int, datos: ProveedorIn, conn=Depends(get_conn), usuario: UsuarioActual = Depends(requiere("proveedores.editar"))):
    antes = conn.execute("SELECT * FROM proveedores WHERE id_proveedor = %s FOR UPDATE", (id_proveedor,)).fetchone()
    if not antes:
        raise HTTPException(404, "Proveedor no encontrado.")
    if conn.execute("SELECT 1 FROM proveedores WHERE upper(codigo) = upper(%s) AND id_proveedor <> %s", (datos.codigo, id_proveedor)).fetchone():
        raise HTTPException(409, "Ese código de proveedor ya existe.")
    d = {**datos.model_dump(), "id": id_proveedor}
    d["codigo"] = d["codigo"].strip().upper()
    conn.execute(
        """UPDATE proveedores SET codigo = %(codigo)s, razon_social = %(razon_social)s, nit = %(nit)s, contacto = %(contacto)s,
                  telefono = %(telefono)s, correo = %(correo)s, pais = %(pais)s, estado = %(estado)s WHERE id_proveedor = %(id)s""",
        d,
    )
    audit.registrar(conn, usuario.id_usuario, "EDITAR_PROVEEDOR", "proveedores", id_proveedor, antes=antes, despues=d)
    conn.commit()
    return {"ok": True}


@router.post("/proveedores/{id_proveedor}/productos", status_code=201)
def asociar_producto(id_proveedor: int, datos: ProductoProveedorIn, conn=Depends(get_conn),
                     usuario: UsuarioActual = Depends(requiere("proveedores.editar"))):
    conn.execute(
        """INSERT INTO productos_proveedores (id_producto, id_proveedor, codigo_proveedor, costo_referencia)
           VALUES (%s, %s, %s, %s)
           ON CONFLICT (id_producto, id_proveedor) DO UPDATE
              SET codigo_proveedor = EXCLUDED.codigo_proveedor, costo_referencia = EXCLUDED.costo_referencia""",
        (datos.id_producto, id_proveedor, datos.codigo_proveedor, datos.costo_referencia),
    )
    audit.registrar(conn, usuario.id_usuario, "ASOCIAR_PRODUCTO_PROVEEDOR", "productos_proveedores", id_proveedor, despues=datos.model_dump())
    conn.commit()
    return {"ok": True}


# ------------------------------------------------------------------ socios comerciales
SOCIO = requiere("socios.editar")


@router.get("/socios")
def listar_socios(conn=Depends(get_conn), _: UsuarioActual = Depends(SOCIO)):
    return conn.execute("SELECT * FROM socios_comerciales ORDER BY nombre").fetchall()


@router.post("/socios", status_code=201)
def crear_socio(datos: SocioIn, conn=Depends(get_conn), usuario: UsuarioActual = Depends(SOCIO)):
    id_s = conn.execute(
        """INSERT INTO socios_comerciales (nombre, pais, tipo_relacion, descripcion, estado)
           VALUES (%(nombre)s, %(pais)s, %(tipo_relacion)s, %(descripcion)s, %(estado)s) RETURNING id_socio""",
        datos.model_dump(),
    ).fetchone()["id_socio"]
    audit.registrar(conn, usuario.id_usuario, "CREAR_SOCIO", "socios_comerciales", id_s, despues=datos.model_dump())
    conn.commit()
    return {"id_socio": id_s}


@router.put("/socios/{id_socio}")
def editar_socio(id_socio: int, datos: SocioIn, conn=Depends(get_conn), usuario: UsuarioActual = Depends(SOCIO)):
    antes = conn.execute("SELECT * FROM socios_comerciales WHERE id_socio = %s FOR UPDATE", (id_socio,)).fetchone()
    if not antes:
        raise HTTPException(404, "Socio no encontrado.")
    conn.execute(
        """UPDATE socios_comerciales SET nombre = %(nombre)s, pais = %(pais)s, tipo_relacion = %(tipo_relacion)s,
                  descripcion = %(descripcion)s, estado = %(estado)s WHERE id_socio = %(id)s""",
        {**datos.model_dump(), "id": id_socio},
    )
    audit.registrar(conn, usuario.id_usuario, "EDITAR_SOCIO", "socios_comerciales", id_socio, antes=antes, despues=datos.model_dump())
    conn.commit()
    return {"ok": True}
