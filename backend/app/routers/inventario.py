from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from .. import audit, config
from ..db import get_conn
from ..security import UsuarioActual, requiere, sucursal_efectiva
from ..services.inventario import ESTADO_SQL, ULTIMA_VENTA_CTE, registrar_movimiento

router = APIRouter(prefix="/api/inventario", tags=["Inventario"])
VER = requiere("inventario.ver")
AJUSTAR = requiere("inventario.ajustar")


class AjusteIn(BaseModel):
    id_sucursal: int
    sku: str
    tipo: str = Field(pattern="^(ENTRADA_AJUSTE|SALIDA_AJUSTE)$")
    cantidad: int = Field(gt=0)
    motivo: str = Field(min_length=3, max_length=100)


class TransferenciaIn(BaseModel):
    id_origen: int
    id_destino: int
    sku: str
    cantidad: int = Field(gt=0)


class MinimoIn(BaseModel):
    id_sucursal: int
    id_variante: int
    stock_minimo: int = Field(ge=0)


def _variante_por_sku(conn, sku: str):
    v = conn.execute("SELECT id_variante, sku FROM variantes_producto WHERE upper(sku) = upper(%s)", (sku.strip(),)).fetchone()
    if not v:
        raise HTTPException(404, f"El SKU {sku} no existe.")
    return v


BASE_SQL = f"""
WITH {ULTIMA_VENTA_CTE},
base AS (
  SELECT i.id_sucursal, i.id_variante, i.stock_actual, i.stock_minimo, v.sku, v.talla, v.color, v.costo_referencia,
         p.modelo, p.id_categoria, c.nombre AS categoria, s.nombre AS sucursal, uv.ultima_venta,
         {ESTADO_SQL} AS estado
    FROM inventario i
    JOIN variantes_producto v ON v.id_variante = i.id_variante
    JOIN productos p ON p.id_producto = v.id_producto AND p.estado = 'ACTIVO'
    JOIN categorias c ON c.id_categoria = p.id_categoria
    JOIN sucursales s ON s.id_sucursal = i.id_sucursal
    LEFT JOIN uv ON uv.id_sucursal = i.id_sucursal AND uv.id_variante = i.id_variante
   WHERE (%(suc)s::int IS NULL OR i.id_sucursal = %(suc)s)
     AND (%(cat)s::int IS NULL OR p.id_categoria = %(cat)s)
)
"""


@router.get("")
def listar(id_sucursal: int | None = None, id_categoria: int | None = None, estado: str | None = None, q: str = "",
           dias: int = config.DIAS_BAJA_ROTACION, pagina: int = 1, tamano: int = 40,
           conn=Depends(get_conn), usuario: UsuarioActual = Depends(VER)):
    params = {"suc": sucursal_efectiva(usuario, id_sucursal), "cat": id_categoria, "dias": dias,
              "estado": estado or None, "q": q.strip(), "ql": f"%{q.strip()}%",
              "lim": min(max(tamano, 1), 200), "off": (max(pagina, 1) - 1) * min(max(tamano, 1), 200)}
    resumen = conn.execute(
        BASE_SQL + """
        SELECT COALESCE(sum(stock_actual), 0) AS pares,
               COALESCE(sum(stock_actual * costo_referencia), 0) AS valor,
               count(*) FILTER (WHERE estado = 'AGOTADO') AS agotado,
               count(*) FILTER (WHERE estado = 'BAJO_MINIMO') AS bajo_minimo,
               count(*) FILTER (WHERE estado = 'BAJA_ROTACION') AS baja_rotacion,
               count(*) FILTER (WHERE estado = 'SOBRESTOCK') AS sobrestock
          FROM base""",
        params,
    ).fetchone()
    filtro = """ FROM base WHERE (%(estado)s::text IS NULL OR estado = %(estado)s)
                  AND (%(q)s = '' OR sku ILIKE %(ql)s OR modelo ILIKE %(ql)s OR color ILIKE %(ql)s)"""
    total = conn.execute(BASE_SQL + "SELECT count(*) AS n" + filtro, params).fetchone()["n"]
    items = conn.execute(
        BASE_SQL + "SELECT *" + filtro + """
          ORDER BY CASE estado WHEN 'AGOTADO' THEN 0 WHEN 'BAJO_MINIMO' THEN 1 WHEN 'BAJA_ROTACION' THEN 2
                               WHEN 'SOBRESTOCK' THEN 3 ELSE 4 END, sku, id_sucursal
          LIMIT %(lim)s OFFSET %(off)s""",
        params,
    ).fetchall()
    return {"resumen": resumen, "total": total, "items": items}


@router.get("/kardex")
def kardex(id_sucursal: int, id_variante: int, conn=Depends(get_conn), usuario: UsuarioActual = Depends(VER)):
    suc = sucursal_efectiva(usuario, id_sucursal)
    fila = conn.execute(
        """SELECT i.stock_actual, i.stock_minimo, v.sku, v.talla, v.color, v.precio_venta, v.costo_referencia, p.modelo, s.nombre AS sucursal
             FROM inventario i JOIN variantes_producto v USING (id_variante) JOIN productos p USING (id_producto)
             JOIN sucursales s ON s.id_sucursal = i.id_sucursal
            WHERE i.id_sucursal = %s AND i.id_variante = %s""",
        (suc, id_variante),
    ).fetchone()
    if not fila:
        raise HTTPException(404, "No hay registro de inventario para ese SKU en la sucursal.")
    fila["movimientos"] = conn.execute(
        """SELECT m.id_movimiento, m.fecha, m.tipo, m.cantidad, m.referencia, u.nombre AS usuario,
                  sum(m.cantidad) OVER (ORDER BY m.fecha, m.id_movimiento) AS saldo
             FROM movimientos_inventario m LEFT JOIN usuarios u ON u.id_usuario = m.id_usuario
            WHERE m.id_sucursal = %s AND m.id_variante = %s
            ORDER BY m.fecha DESC, m.id_movimiento DESC""",
        (suc, id_variante),
    ).fetchall()
    return fila


@router.get("/movimientos")
def movimientos(id_sucursal: int | None = None, limite: int = 10, conn=Depends(get_conn), usuario: UsuarioActual = Depends(VER)):
    return conn.execute(
        """SELECT m.fecha, m.tipo, m.cantidad, m.referencia, v.sku, s.nombre AS sucursal
             FROM movimientos_inventario m JOIN variantes_producto v USING (id_variante) JOIN sucursales s ON s.id_sucursal = m.id_sucursal
            WHERE (%(s)s::int IS NULL OR m.id_sucursal = %(s)s)
            ORDER BY m.id_movimiento DESC LIMIT %(l)s""",
        {"s": sucursal_efectiva(usuario, id_sucursal), "l": min(limite, 100)},
    ).fetchall()


@router.post("/ajustes")
def ajuste(datos: AjusteIn, conn=Depends(get_conn), usuario: UsuarioActual = Depends(AJUSTAR)):
    suc = sucursal_efectiva(usuario, datos.id_sucursal)
    v = _variante_por_sku(conn, datos.sku)
    n = conn.execute("SELECT count(*) + 1 AS n FROM movimientos_inventario WHERE tipo IN ('ENTRADA_AJUSTE','SALIDA_AJUSTE')").fetchone()["n"]
    ref = f"AJ-{n:05d} {datos.motivo}"
    antes = conn.execute("SELECT stock_actual FROM inventario WHERE id_sucursal = %s AND id_variante = %s", (suc, v["id_variante"])).fetchone()
    stock = registrar_movimiento(conn, suc, v["id_variante"], datos.tipo, datos.cantidad, ref, usuario.id_usuario)
    audit.registrar(conn, usuario.id_usuario, "AJUSTE_INVENTARIO", "movimientos_inventario", ref,
                    antes={"sku": v["sku"], "stock": antes["stock_actual"] if antes else 0},
                    despues={"sku": v["sku"], "stock": stock, "tipo": datos.tipo, "motivo": datos.motivo})
    conn.commit()
    return {"ok": True, "stock": stock, "referencia": ref}


@router.post("/transferencias")
def transferencia(datos: TransferenciaIn, conn=Depends(get_conn), usuario: UsuarioActual = Depends(AJUSTAR)):
    origen = sucursal_efectiva(usuario, datos.id_origen)
    if origen == datos.id_destino:
        raise HTTPException(400, "El origen y el destino deben ser distintos.")
    v = _variante_por_sku(conn, datos.sku)
    n = conn.execute("SELECT count(*) + 1 AS n FROM movimientos_inventario WHERE tipo = 'TRANSF_SALIDA'").fetchone()["n"]
    ref = f"TR-{n:05d}"
    registrar_movimiento(conn, origen, v["id_variante"], "TRANSF_SALIDA", datos.cantidad, ref, usuario.id_usuario)
    registrar_movimiento(conn, datos.id_destino, v["id_variante"], "TRANSF_ENTRADA", datos.cantidad, ref, usuario.id_usuario)
    audit.registrar(conn, usuario.id_usuario, "TRANSFERENCIA", "movimientos_inventario", ref,
                    despues={"sku": v["sku"], "origen": origen, "destino": datos.id_destino, "cantidad": datos.cantidad})
    conn.commit()
    return {"ok": True, "referencia": ref}


@router.put("/minimo")
def minimo(datos: MinimoIn, conn=Depends(get_conn), usuario: UsuarioActual = Depends(AJUSTAR)):
    suc = sucursal_efectiva(usuario, datos.id_sucursal)
    antes = conn.execute("SELECT stock_minimo FROM inventario WHERE id_sucursal = %s AND id_variante = %s FOR UPDATE",
                         (suc, datos.id_variante)).fetchone()
    if not antes:
        raise HTTPException(404, "No hay registro de inventario para ese SKU en la sucursal.")
    conn.execute("UPDATE inventario SET stock_minimo = %s WHERE id_sucursal = %s AND id_variante = %s",
                 (datos.stock_minimo, suc, datos.id_variante))
    audit.registrar(conn, usuario.id_usuario, "CAMBIAR_MINIMO", "inventario", f"{suc}-{datos.id_variante}",
                    antes=antes, despues={"stock_minimo": datos.stock_minimo})
    conn.commit()
    return {"ok": True}
