import re
import unicodedata

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from .. import audit
from ..db import get_conn
from ..security import UsuarioActual, requiere, sucursal_efectiva
from ..services.inventario import asegurar_fila

router = APIRouter(prefix="/api", tags=["Productos"])
VER = requiere("productos.ver")
EDITAR = requiere("productos.editar")

COLORES = {"negro": "NG", "cafe": "CF", "blanco": "BL", "beige": "BE", "azul": "AZ", "gris": "GR",
           "rosa": "RS", "rojo": "RJ", "verde": "VD", "marron": "MR"}


def normalizar(texto: str) -> str:
    return unicodedata.normalize("NFD", str(texto or "")).encode("ascii", "ignore").decode().lower().strip()


def codigo_color(color: str) -> str:
    n = normalizar(color)
    return COLORES.get(n) or (re.sub(r"[^a-z]", "", n)[:2].upper() or "XX")


def generar_sku(cat_codigo: str, id_producto: int, color: str, talla: str) -> str:
    return f"MNC-{cat_codigo}-{id_producto:03d}-{codigo_color(color)}-{talla}".upper()


def parse_tallas(texto: str) -> list[str]:
    texto = texto.strip()
    m = re.fullmatch(r"(\d+)\s*-\s*(\d+)", texto)
    if m:
        a, b = int(m.group(1)), int(m.group(2))
        if a > b or b - a > 30:
            return []
        return [str(t) for t in range(a, b + 1)]
    return [t for t in re.split(r"[,;\s]+", texto) if t]


class ProductoIn(BaseModel):
    id_categoria: int
    marca: str = Field(min_length=1, max_length=80)
    modelo: str = Field(min_length=1, max_length=120)
    descripcion: str | None = None
    id_proveedor: int | None = None
    colores: list[str]
    tallas: str
    precio_venta: float = Field(gt=0)
    costo_referencia: float = Field(ge=0)
    stock_minimo: int = Field(default=0, ge=0)


class ProductoUpd(BaseModel):
    id_categoria: int
    marca: str = Field(min_length=1, max_length=80)
    modelo: str = Field(min_length=1, max_length=120)
    descripcion: str | None = None
    estado: str = "ACTIVO"


class VarianteIn(BaseModel):
    talla: str = Field(min_length=1, max_length=10)
    color: str = Field(min_length=1, max_length=40)
    precio_venta: float = Field(gt=0)
    costo_referencia: float = Field(ge=0)


class PrecioIn(BaseModel):
    precio_venta: float = Field(gt=0)
    costo_referencia: float = Field(ge=0)


@router.get("/productos")
def listar(q: str = "", id_categoria: int | None = None, conn=Depends(get_conn), _: UsuarioActual = Depends(VER)):
    return conn.execute(
        """SELECT p.id_producto, p.marca, p.modelo, p.descripcion, p.estado, p.id_categoria, c.nombre AS categoria,
                  count(v.id_variante) AS variantes,
                  min(v.precio_venta) AS precio_min, max(v.precio_venta) AS precio_max,
                  avg((v.precio_venta - v.costo_referencia) / v.precio_venta) AS margen_ref,
                  COALESCE((SELECT sum(i.stock_actual) FROM inventario i JOIN variantes_producto v2 USING (id_variante)
                             WHERE v2.id_producto = p.id_producto), 0) AS stock_total,
                  (SELECT string_agg(pr.razon_social, ', ') FROM productos_proveedores pp JOIN proveedores pr USING (id_proveedor)
                    WHERE pp.id_producto = p.id_producto) AS proveedores
             FROM productos p
             JOIN categorias c ON c.id_categoria = p.id_categoria
             LEFT JOIN variantes_producto v ON v.id_producto = p.id_producto
            WHERE (%(cat)s::int IS NULL OR p.id_categoria = %(cat)s)
              AND (%(q)s = '' OR p.modelo ILIKE %(ql)s OR p.marca ILIKE %(ql)s
                   OR EXISTS (SELECT 1 FROM variantes_producto vx WHERE vx.id_producto = p.id_producto AND vx.sku ILIKE %(ql)s))
            GROUP BY p.id_producto, c.nombre
            ORDER BY c.nombre, p.modelo""",
        {"cat": id_categoria, "q": q.strip(), "ql": f"%{q.strip()}%"},
    ).fetchall()


@router.get("/productos/{id_producto}")
def detalle(id_producto: int, conn=Depends(get_conn), _: UsuarioActual = Depends(VER)):
    p = conn.execute(
        """SELECT p.*, c.nombre AS categoria, c.codigo AS categoria_codigo
             FROM productos p JOIN categorias c USING (id_categoria) WHERE p.id_producto = %s""",
        (id_producto,),
    ).fetchone()
    if not p:
        raise HTTPException(404, "Producto no encontrado.")
    p["variantes"] = conn.execute(
        """SELECT v.id_variante, v.sku, v.talla, v.color, v.precio_venta, v.costo_referencia, v.estado,
                  COALESCE(sum(i.stock_actual), 0) AS stock_total,
                  COALESCE(json_agg(json_build_object('id_sucursal', i.id_sucursal, 'stock', i.stock_actual)
                           ORDER BY i.id_sucursal) FILTER (WHERE i.id_inventario IS NOT NULL), '[]') AS stock_sucursales
             FROM variantes_producto v LEFT JOIN inventario i ON i.id_variante = v.id_variante
            WHERE v.id_producto = %s
            GROUP BY v.id_variante
            ORDER BY v.color, CASE WHEN v.talla ~ '^[0-9]+(\\.[0-9]+)?$' THEN v.talla::numeric END, v.talla""",
        (id_producto,),
    ).fetchall()
    p["proveedores"] = conn.execute(
        """SELECT pp.id_proveedor, pr.codigo, pr.razon_social, pp.codigo_proveedor, pp.costo_referencia
             FROM productos_proveedores pp JOIN proveedores pr USING (id_proveedor) WHERE pp.id_producto = %s""",
        (id_producto,),
    ).fetchall()
    return p


@router.post("/productos", status_code=201)
def crear(datos: ProductoIn, conn=Depends(get_conn), usuario: UsuarioActual = Depends(EDITAR)):
    cat = conn.execute("SELECT id_categoria, codigo, nombre FROM categorias WHERE id_categoria = %s", (datos.id_categoria,)).fetchone()
    if not cat:
        raise HTTPException(400, "La categoría no existe.")
    colores = [c.strip() for c in datos.colores if c.strip()]
    tallas = parse_tallas(datos.tallas)
    if not colores or not tallas:
        raise HTTPException(400, "Indica al menos un color y una talla válida (ej.: 38-43 o 38,39,40).")
    if conn.execute("SELECT 1 FROM productos WHERE id_categoria = %s AND lower(marca) = lower(%s) AND lower(modelo) = lower(%s)",
                    (cat["id_categoria"], datos.marca.strip(), datos.modelo.strip())).fetchone():
        raise HTTPException(409, "Ya existe ese modelo en la categoría.")
    id_prod = conn.execute(
        "INSERT INTO productos (id_categoria, marca, modelo, descripcion) VALUES (%s, %s, %s, %s) RETURNING id_producto",
        (cat["id_categoria"], datos.marca.strip(), datos.modelo.strip(), datos.descripcion),
    ).fetchone()["id_producto"]
    sucursales = [r["id_sucursal"] for r in conn.execute("SELECT id_sucursal FROM sucursales")]
    skus = []
    for color in colores:
        for talla in tallas:
            sku = generar_sku(cat["codigo"], id_prod, color, talla)
            if sku in skus or conn.execute("SELECT 1 FROM variantes_producto WHERE sku = %s", (sku,)).fetchone():
                raise HTTPException(409, f"El SKU {sku} ya existe.")
            skus.append(sku)
            id_var = conn.execute(
                """INSERT INTO variantes_producto (id_producto, talla, color, sku, precio_venta, costo_referencia)
                   VALUES (%s, %s, %s, %s, %s, %s) RETURNING id_variante""",
                (id_prod, talla, color, sku, datos.precio_venta, datos.costo_referencia),
            ).fetchone()["id_variante"]
            for s in sucursales:
                asegurar_fila(conn, s, id_var, datos.stock_minimo)
    if datos.id_proveedor:
        cod = conn.execute("SELECT codigo FROM proveedores WHERE id_proveedor = %s", (datos.id_proveedor,)).fetchone()
        if not cod:
            raise HTTPException(400, "El proveedor no existe.")
        conn.execute(
            "INSERT INTO productos_proveedores (id_producto, id_proveedor, codigo_proveedor, costo_referencia) VALUES (%s, %s, %s, %s)",
            (id_prod, datos.id_proveedor, f"{cod['codigo']}-{id_prod:03d}", datos.costo_referencia),
        )
    audit.registrar(conn, usuario.id_usuario, "CREAR_PRODUCTO", "productos", id_prod,
                    despues={"modelo": datos.modelo, "marca": datos.marca, "categoria": cat["nombre"], "variantes": len(skus)})
    conn.commit()
    return {"id_producto": id_prod, "skus": skus}


@router.put("/productos/{id_producto}")
def editar(id_producto: int, datos: ProductoUpd, conn=Depends(get_conn), usuario: UsuarioActual = Depends(EDITAR)):
    antes = conn.execute("SELECT id_categoria, marca, modelo, descripcion, estado FROM productos WHERE id_producto = %s FOR UPDATE",
                         (id_producto,)).fetchone()
    if not antes:
        raise HTTPException(404, "Producto no encontrado.")
    conn.execute(
        "UPDATE productos SET id_categoria = %s, marca = %s, modelo = %s, descripcion = %s, estado = %s WHERE id_producto = %s",
        (datos.id_categoria, datos.marca.strip(), datos.modelo.strip(), datos.descripcion, datos.estado, id_producto),
    )
    audit.registrar(conn, usuario.id_usuario, "EDITAR_PRODUCTO", "productos", id_producto, antes=antes, despues=datos.model_dump())
    conn.commit()
    return {"ok": True}


@router.post("/productos/{id_producto}/variantes", status_code=201)
def crear_variante(id_producto: int, datos: VarianteIn, conn=Depends(get_conn), usuario: UsuarioActual = Depends(EDITAR)):
    p = conn.execute(
        "SELECT p.id_producto, c.codigo FROM productos p JOIN categorias c USING (id_categoria) WHERE p.id_producto = %s", (id_producto,)
    ).fetchone()
    if not p:
        raise HTTPException(404, "Producto no encontrado.")
    sku = generar_sku(p["codigo"], id_producto, datos.color.strip(), datos.talla.strip())
    if conn.execute("SELECT 1 FROM variantes_producto WHERE sku = %s", (sku,)).fetchone():
        raise HTTPException(409, f"Ya existe la variante {sku}.")
    id_var = conn.execute(
        """INSERT INTO variantes_producto (id_producto, talla, color, sku, precio_venta, costo_referencia)
           VALUES (%s, %s, %s, %s, %s, %s) RETURNING id_variante""",
        (id_producto, datos.talla.strip(), datos.color.strip(), sku, datos.precio_venta, datos.costo_referencia),
    ).fetchone()["id_variante"]
    for r in conn.execute("SELECT id_sucursal FROM sucursales").fetchall():
        asegurar_fila(conn, r["id_sucursal"], id_var)
    audit.registrar(conn, usuario.id_usuario, "CREAR_VARIANTE", "variantes_producto", id_var, despues={"sku": sku, **datos.model_dump()})
    conn.commit()
    return {"id_variante": id_var, "sku": sku}


@router.put("/variantes/{id_variante}")
def cambiar_precio(id_variante: int, datos: PrecioIn, conn=Depends(get_conn), usuario: UsuarioActual = Depends(EDITAR)):
    antes = conn.execute("SELECT sku, precio_venta, costo_referencia FROM variantes_producto WHERE id_variante = %s FOR UPDATE",
                         (id_variante,)).fetchone()
    if not antes:
        raise HTTPException(404, "Variante no encontrada.")
    if float(antes["precio_venta"]) == datos.precio_venta and float(antes["costo_referencia"]) == datos.costo_referencia:
        return {"ok": True, "sin_cambios": True}
    conn.execute("UPDATE variantes_producto SET precio_venta = %s, costo_referencia = %s WHERE id_variante = %s",
                 (datos.precio_venta, datos.costo_referencia, id_variante))
    audit.registrar(conn, usuario.id_usuario, "CAMBIAR_PRECIO", "variantes_producto", id_variante,
                    antes=antes, despues={"sku": antes["sku"], **datos.model_dump()})
    conn.commit()
    return {"ok": True}


@router.get("/variantes/buscar")
def buscar_variantes(q: str = "", id_sucursal: int | None = None, id_proveedor: int | None = None, limite: int = 30,
                     conn=Depends(get_conn),
                     usuario: UsuarioActual = Depends(requiere("productos.ver", "pos.vender", "compras.crear", "inventario.ver"))):
    suc = sucursal_efectiva(usuario, id_sucursal)
    return conn.execute(
        """SELECT v.id_variante, v.sku, v.talla, v.color, v.precio_venta, v.costo_referencia, p.modelo, p.marca,
                  COALESCE(pp.costo_referencia, v.costo_referencia) AS costo_proveedor,
                  (SELECT i.stock_actual FROM inventario i WHERE i.id_variante = v.id_variante AND i.id_sucursal = %(suc)s) AS stock
             FROM variantes_producto v JOIN productos p USING (id_producto)
             LEFT JOIN productos_proveedores pp ON pp.id_producto = p.id_producto AND pp.id_proveedor = %(prov)s
            WHERE (%(q)s = '' OR v.sku ILIKE %(ql)s OR p.modelo ILIKE %(ql)s OR v.color ILIKE %(ql)s)
              AND (%(prov)s::int IS NULL OR pp.id_proveedor IS NOT NULL)
            ORDER BY v.sku LIMIT %(lim)s""",
        {"suc": suc, "prov": id_proveedor, "q": q.strip(), "ql": f"%{q.strip()}%", "lim": min(limite, 200)},
    ).fetchall()
