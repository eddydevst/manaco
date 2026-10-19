from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from .. import audit
from ..db import get_conn
from ..security import UsuarioActual, requiere, sucursal_efectiva
from ..services.inventario import bloquear_stock, registrar_movimiento
from .caja import resumen_sesion, sesion_abierta

router = APIRouter(prefix="/api", tags=["Punto de Venta"])

METODOS = ("EFECTIVO", "TARJETA", "QR")


class LineaVenta(BaseModel):
    id_variante: int
    cantidad: int = Field(gt=0, le=100)
    descuento_pct: float = Field(default=0, ge=0, le=50)


class VentaIn(BaseModel):
    items: list[LineaVenta] = Field(min_length=1)
    metodo_pago: str = Field(pattern="^(EFECTIVO|TARJETA|QR)$")
    monto_recibido: float | None = Field(default=None, ge=0)
    cliente: str | None = None
    idempotency_key: str = Field(min_length=8, max_length=64)


class LineaDevolucion(BaseModel):
    id_detalle: int
    cantidad: int = Field(ge=0)


class DevolucionIn(BaseModel):
    items: list[LineaDevolucion]
    motivo: str = Field(min_length=3, max_length=250)


@router.get("/pos/catalogo")
def catalogo(q: str = "", id_categoria: int | None = None, conn=Depends(get_conn), usuario: UsuarioActual = Depends(requiere("pos.vender"))):
    s = sesion_abierta(conn, usuario.id_usuario)
    if not s:
        raise HTTPException(409, "Abre una caja para ver el catálogo de la sucursal.")
    return conn.execute(
        """SELECT p.id_producto, p.modelo, p.marca, c.nombre AS categoria, v.color,
                  json_agg(json_build_object('id_variante', v.id_variante, 'talla', v.talla, 'sku', v.sku,
                           'precio', v.precio_venta, 'stock', COALESCE(i.stock_actual, 0))
                           ORDER BY CASE WHEN v.talla ~ '^[0-9]+$' THEN v.talla::int END, v.talla) AS tallas,
                  min(v.precio_venta) AS precio
             FROM productos p JOIN categorias c USING (id_categoria)
             JOIN variantes_producto v ON v.id_producto = p.id_producto AND v.estado = 'ACTIVO'
             LEFT JOIN inventario i ON i.id_variante = v.id_variante AND i.id_sucursal = %(suc)s
            WHERE p.estado = 'ACTIVO' AND (%(cat)s::int IS NULL OR p.id_categoria = %(cat)s)
              AND (%(q)s = '' OR p.modelo ILIKE %(ql)s OR v.color ILIKE %(ql)s OR v.sku ILIKE %(ql)s OR p.marca ILIKE %(ql)s)
            GROUP BY p.id_producto, c.nombre, v.color
            ORDER BY c.nombre, p.modelo, v.color""",
        {"suc": s["id_sucursal"], "cat": id_categoria, "q": q.strip(), "ql": f"%{q.strip()}%"},
    ).fetchall()


def cargar_venta(conn, where: str, valor):
    v = conn.execute(
        f"""SELECT v.*, s.nombre AS sucursal, u.nombre AS usuario, c.nombre AS cliente
              FROM ventas v JOIN sucursales s USING (id_sucursal) JOIN usuarios u ON u.id_usuario = v.id_usuario
              LEFT JOIN clientes c ON c.id_cliente = v.id_cliente WHERE {where} = %s""",
        (valor,),
    ).fetchone()
    if not v:
        raise HTTPException(404, "No existe una venta con ese número.")
    v["items"] = conn.execute(
        """SELECT d.id_detalle, d.id_variante, var.sku, p.modelo, var.color, var.talla, d.cantidad, d.precio_unitario,
                  d.descuento, d.subtotal, d.cantidad_devuelta
             FROM detalle_venta d JOIN variantes_producto var USING (id_variante) JOIN productos p USING (id_producto)
            WHERE d.id_venta = %s ORDER BY d.id_detalle""",
        (v["id_venta"],),
    ).fetchall()
    v["pagos"] = conn.execute("SELECT metodo_pago, monto, fecha FROM pagos_venta WHERE id_venta = %s", (v["id_venta"],)).fetchall()
    return v


@router.post("/ventas", status_code=201)
def registrar_venta(datos: VentaIn, conn=Depends(get_conn), usuario: UsuarioActual = Depends(requiere("pos.vender"))):
    # Reintento de la misma operación: se devuelve la venta ya registrada, no se duplica.
    previa = conn.execute("SELECT id_venta FROM ventas WHERE idempotency_key = %s", (datos.idempotency_key,)).fetchone()
    if previa:
        return {**cargar_venta(conn, "v.id_venta", previa["id_venta"]), "duplicada": True}
    s = sesion_abierta(conn, usuario.id_usuario, bloquear=True)
    if not s:
        raise HTTPException(409, "Abre una caja antes de vender.")
    suc = s["id_sucursal"]
    # Agrupar líneas repetidas y bloquear stock en orden fijo (evita interbloqueos)
    lineas: dict[int, LineaVenta] = {}
    for l in datos.items:
        if l.id_variante in lineas:
            lineas[l.id_variante].cantidad += l.cantidad
        else:
            lineas[l.id_variante] = l.model_copy()
    detalle = []
    for id_var in sorted(lineas):
        l = lineas[id_var]
        v = conn.execute(
            """SELECT v.sku, v.precio_venta, v.costo_referencia, v.estado, p.estado AS estado_producto, p.modelo
                 FROM variantes_producto v JOIN productos p USING (id_producto) WHERE v.id_variante = %s""",
            (id_var,),
        ).fetchone()
        if not v or v["estado"] != "ACTIVO" or v["estado_producto"] != "ACTIVO":
            raise HTTPException(400, f"La variante {id_var} no está disponible para la venta.")
        stock = bloquear_stock(conn, suc, id_var)
        if stock < l.cantidad:
            raise HTTPException(409, f"Stock insuficiente de {v['sku']} ({v['modelo']}): hay {stock}, se piden {l.cantidad}.")
        bruto = float(v["precio_venta"]) * l.cantidad
        desc = round(bruto * l.descuento_pct / 100, 2)
        detalle.append({"id_variante": id_var, "cantidad": l.cantidad, "precio": float(v["precio_venta"]),
                        "costo": float(v["costo_referencia"]), "descuento": desc, "subtotal": round(bruto - desc, 2)})
    subtotal = round(sum(d["precio"] * d["cantidad"] for d in detalle), 2)
    descuento = round(sum(d["descuento"] for d in detalle), 2)
    total = round(subtotal - descuento, 2)
    if datos.metodo_pago == "EFECTIVO" and datos.monto_recibido is not None and datos.monto_recibido < total:
        raise HTTPException(400, f"El monto recibido es menor que el total (Bs {total:.2f}).")
    id_cliente = None
    if datos.cliente and datos.cliente.strip():
        c = conn.execute("SELECT id_cliente FROM clientes WHERE lower(nombre) = lower(%s)", (datos.cliente.strip(),)).fetchone()
        id_cliente = c["id_cliente"] if c else conn.execute(
            "INSERT INTO clientes (nombre) VALUES (%s) RETURNING id_cliente", (datos.cliente.strip(),)).fetchone()["id_cliente"]
    id_v = conn.execute("SELECT nextval(pg_get_serial_sequence('ventas', 'id_venta')) AS id").fetchone()["id"]
    numero = f"V-{id_v:06d}"
    venta = conn.execute(
        """INSERT INTO ventas (id_venta, numero, id_sucursal, id_usuario, id_cliente, id_sesion, subtotal, descuento, total, idempotency_key)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id_venta""",
        (id_v, numero, suc, usuario.id_usuario, id_cliente, s["id_sesion"], subtotal, descuento, total, datos.idempotency_key),
    ).fetchone()
    for d in detalle:
        conn.execute(
            """INSERT INTO detalle_venta (id_venta, id_variante, cantidad, precio_unitario, costo_unitario, descuento, subtotal)
               VALUES (%s, %s, %s, %s, %s, %s, %s)""",
            (venta["id_venta"], d["id_variante"], d["cantidad"], d["precio"], d["costo"], d["descuento"], d["subtotal"]),
        )
        registrar_movimiento(conn, suc, d["id_variante"], "SALIDA_VENTA", d["cantidad"], numero, usuario.id_usuario)
    conn.execute("INSERT INTO pagos_venta (id_venta, metodo_pago, monto) VALUES (%s, %s, %s)", (venta["id_venta"], datos.metodo_pago, total))
    conn.execute(
        "INSERT INTO movimientos_caja (id_sesion, tipo, metodo_pago, monto, concepto, id_usuario) VALUES (%s, 'VENTA', %s, %s, %s, %s)",
        (s["id_sesion"], datos.metodo_pago, total, numero, usuario.id_usuario),
    )
    audit.registrar(conn, usuario.id_usuario, "REGISTRAR_VENTA", "ventas", venta["id_venta"],
                    despues={"numero": numero, "sucursal": s["sucursal"], "total": total, "lineas": len(detalle), "metodo_pago": datos.metodo_pago})
    conn.commit()
    resultado = cargar_venta(conn, "v.id_venta", venta["id_venta"])
    if datos.metodo_pago == "EFECTIVO" and datos.monto_recibido is not None:
        resultado["monto_recibido"] = datos.monto_recibido
        resultado["cambio"] = round(datos.monto_recibido - total, 2)
    return resultado


@router.get("/ventas")
def listar(id_sucursal: int | None = None, desde: date | None = None, hasta: date | None = None, pagina: int = 1,
           conn=Depends(get_conn), usuario: UsuarioActual = Depends(requiere("reportes.ver", "pos.vender"))):
    desde = desde or date.today() - timedelta(days=30)
    hasta = hasta or date.today()
    return conn.execute(
        """SELECT v.id_venta, v.numero, v.fecha, v.total, v.estado, s.nombre AS sucursal, u.nombre AS usuario
             FROM ventas v JOIN sucursales s USING (id_sucursal) JOIN usuarios u ON u.id_usuario = v.id_usuario
            WHERE v.fecha >= %(d)s AND v.fecha < %(h)s::date + 1 AND (%(s)s::int IS NULL OR v.id_sucursal = %(s)s)
            ORDER BY v.fecha DESC LIMIT 100 OFFSET %(o)s""",
        {"d": desde, "h": hasta, "s": sucursal_efectiva(usuario, id_sucursal), "o": (max(pagina, 1) - 1) * 100},
    ).fetchall()


@router.get("/ventas/numero/{numero}")
def por_numero(numero: str, conn=Depends(get_conn), usuario: UsuarioActual = Depends(requiere("pos.vender", "pos.devolver", "reportes.ver"))):
    n = numero.strip().upper()
    if n.isdigit():
        n = f"V-{int(n):06d}"
    v = cargar_venta(conn, "v.numero", n)
    sucursal_efectiva(usuario, v["id_sucursal"])
    return v


@router.get("/ventas/{id_venta}")
def detalle(id_venta: int, conn=Depends(get_conn), usuario: UsuarioActual = Depends(requiere("pos.vender", "reportes.ver"))):
    v = cargar_venta(conn, "v.id_venta", id_venta)
    sucursal_efectiva(usuario, v["id_sucursal"])
    return v


@router.post("/ventas/{id_venta}/devoluciones", status_code=201)
def devolver(id_venta: int, datos: DevolucionIn, conn=Depends(get_conn), usuario: UsuarioActual = Depends(requiere("pos.devolver"))):
    s = sesion_abierta(conn, usuario.id_usuario, bloquear=True)
    if not s:
        raise HTTPException(409, "Necesitas una caja abierta para devolver dinero.")
    v = conn.execute("SELECT numero, id_sucursal, estado FROM ventas WHERE id_venta = %s FOR UPDATE", (id_venta,)).fetchone()
    if not v:
        raise HTTPException(404, "Venta no encontrada.")
    if v["id_sucursal"] != s["id_sucursal"]:
        raise HTTPException(409, "La venta es de otra sucursal; la devolución debe hacerse allí.")
    lineas = [l for l in datos.items if l.cantidad > 0]
    if not lineas:
        raise HTTPException(400, "Indica al menos una unidad a devolver.")
    dev = conn.execute(
        "INSERT INTO devoluciones (id_venta, id_usuario, id_sesion, motivo, monto) VALUES (%s, %s, %s, %s, 0) RETURNING id_devolucion",
        (id_venta, usuario.id_usuario, s["id_sesion"], datos.motivo),
    ).fetchone()["id_devolucion"]
    monto_total = 0.0
    for l in lineas:
        d = conn.execute(
            "SELECT id_variante, cantidad, cantidad_devuelta, subtotal FROM detalle_venta WHERE id_detalle = %s AND id_venta = %s FOR UPDATE",
            (l.id_detalle, id_venta),
        ).fetchone()
        if not d:
            raise HTTPException(400, "Una línea no pertenece a la venta.")
        if l.cantidad > d["cantidad"] - d["cantidad_devuelta"]:
            raise HTTPException(400, "La cantidad a devolver supera lo vendido.")
        monto = round(float(d["subtotal"]) / d["cantidad"] * l.cantidad, 2)
        monto_total += monto
        conn.execute("UPDATE detalle_venta SET cantidad_devuelta = cantidad_devuelta + %s WHERE id_detalle = %s", (l.cantidad, l.id_detalle))
        conn.execute("INSERT INTO detalle_devolucion (id_devolucion, id_detalle_venta, cantidad, monto) VALUES (%s, %s, %s, %s)",
                     (dev, l.id_detalle, l.cantidad, monto))
        registrar_movimiento(conn, v["id_sucursal"], d["id_variante"], "DEVOLUCION", l.cantidad, v["numero"], usuario.id_usuario)
    monto_total = round(monto_total, 2)
    disponible = resumen_sesion(conn, s["id_sesion"], s["saldo_inicial"])["efectivo_esperado"]
    if monto_total > disponible:
        raise HTTPException(409, f"No hay suficiente efectivo en caja para devolver Bs {monto_total:.2f} (hay Bs {disponible:.2f}).")
    conn.execute("UPDATE devoluciones SET monto = %s WHERE id_devolucion = %s", (monto_total, dev))
    conn.execute(
        """INSERT INTO movimientos_caja (id_sesion, tipo, metodo_pago, monto, concepto, id_usuario)
           VALUES (%s, 'DEVOLUCION', 'EFECTIVO', %s, %s, %s)""",
        (s["id_sesion"], -monto_total, f"Devolución {v['numero']}", usuario.id_usuario),
    )
    pend = conn.execute("SELECT bool_and(cantidad_devuelta = cantidad) AS todo FROM detalle_venta WHERE id_venta = %s", (id_venta,)).fetchone()
    nuevo = "DEVUELTA" if pend["todo"] else "DEVOLUCION_PARCIAL"
    conn.execute("UPDATE ventas SET estado = %s WHERE id_venta = %s", (nuevo, id_venta))
    audit.registrar(conn, usuario.id_usuario, "REGISTRAR_DEVOLUCION", "ventas", id_venta, antes={"estado": v["estado"]},
                    despues={"numero": v["numero"], "estado": nuevo, "monto": monto_total, "motivo": datos.motivo})
    conn.commit()
    return {"ok": True, "monto": monto_total, "estado": nuevo}
