from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from .. import audit
from ..db import get_conn
from ..security import UsuarioActual, requiere, sucursal_efectiva
from ..services.inventario import registrar_movimiento

router = APIRouter(prefix="/api/compras", tags=["Compras"])


class LineaOC(BaseModel):
    id_variante: int | None = None
    sku: str | None = None
    cantidad: int = Field(gt=0)
    costo_unitario: float = Field(ge=0)


class OrdenIn(BaseModel):
    id_proveedor: int
    id_sucursal: int
    fecha_entrega: date
    observacion: str | None = None
    items: list[LineaOC] = Field(min_length=1)


class DecisionIn(BaseModel):
    decision: str = Field(pattern="^(APROBADA|RECHAZADA)$")
    observacion: str | None = None


class LineaRecepcion(BaseModel):
    id_detalle: int
    cantidad: int = Field(ge=0)


class RecepcionIn(BaseModel):
    items: list[LineaRecepcion]


@router.get("/resumen")
def resumen(conn=Depends(get_conn), usuario: UsuarioActual = Depends(requiere("compras.ver"))):
    suc = usuario.id_sucursal
    return conn.execute(
        """SELECT count(*) FILTER (WHERE estado = 'PENDIENTE_APROBACION') AS por_aprobar,
                  count(*) FILTER (WHERE estado IN ('APROBADA','RECIBIDA_PARCIAL')) AS por_recibir,
                  COALESCE(sum(total) FILTER (WHERE estado <> 'RECHAZADA' AND date_trunc('month', fecha) = date_trunc('month', now())), 0) AS monto_mes
             FROM ordenes_compra WHERE (%(s)s::int IS NULL OR id_sucursal = %(s)s)""",
        {"s": suc},
    ).fetchone()


@router.get("")
def listar(estado: str | None = None, conn=Depends(get_conn), usuario: UsuarioActual = Depends(requiere("compras.ver"))):
    return conn.execute(
        """SELECT o.id_orden, o.numero, o.fecha, o.fecha_entrega, o.estado, o.total, o.observacion,
                  p.razon_social AS proveedor, s.nombre AS sucursal,
                  d.pedido, d.recibido
             FROM ordenes_compra o
             JOIN proveedores p USING (id_proveedor)
             JOIN sucursales s USING (id_sucursal)
             JOIN (SELECT id_orden, sum(cantidad) AS pedido, sum(cantidad_recibida) AS recibido
                     FROM detalle_orden_compra GROUP BY id_orden) d USING (id_orden)
            WHERE (%(e)s::text IS NULL OR o.estado = %(e)s)
              AND (%(s)s::int IS NULL OR o.id_sucursal = %(s)s)
            ORDER BY o.fecha DESC""",
        {"e": estado or None, "s": usuario.id_sucursal},
    ).fetchall()


def _cargar(conn, id_orden: int):
    o = conn.execute(
        """SELECT o.*, p.razon_social AS proveedor, s.nombre AS sucursal, u.nombre AS usuario
             FROM ordenes_compra o JOIN proveedores p USING (id_proveedor) JOIN sucursales s USING (id_sucursal)
             JOIN usuarios u ON u.id_usuario = o.id_usuario WHERE o.id_orden = %s""",
        (id_orden,),
    ).fetchone()
    if not o:
        raise HTTPException(404, "Orden no encontrada.")
    o["items"] = conn.execute(
        """SELECT d.id_detalle, d.id_variante, v.sku, p.modelo, v.color, v.talla, d.cantidad, d.cantidad_recibida, d.costo_unitario,
                  d.cantidad * d.costo_unitario AS subtotal
             FROM detalle_orden_compra d JOIN variantes_producto v USING (id_variante) JOIN productos p USING (id_producto)
            WHERE d.id_orden = %s ORDER BY v.sku""",
        (id_orden,),
    ).fetchall()
    o["aprobaciones"] = conn.execute(
        """SELECT a.decision, a.fecha, a.observacion, u.nombre AS usuario
             FROM aprobaciones_compra a JOIN usuarios u USING (id_usuario) WHERE a.id_orden = %s ORDER BY a.fecha""",
        (id_orden,),
    ).fetchall()
    o["recepciones"] = conn.execute(
        """SELECT r.id_recepcion, r.fecha, r.estado, u.nombre AS usuario,
                  (SELECT sum(cantidad_recibida) FROM detalle_recepcion dr WHERE dr.id_recepcion = r.id_recepcion) AS pares
             FROM recepciones_compra r JOIN usuarios u USING (id_usuario) WHERE r.id_orden = %s ORDER BY r.fecha""",
        (id_orden,),
    ).fetchall()
    return o


@router.get("/{id_orden}")
def detalle(id_orden: int, conn=Depends(get_conn), usuario: UsuarioActual = Depends(requiere("compras.ver"))):
    o = _cargar(conn, id_orden)
    sucursal_efectiva(usuario, o["id_sucursal"])
    return o


@router.post("", status_code=201)
def crear(datos: OrdenIn, conn=Depends(get_conn), usuario: UsuarioActual = Depends(requiere("compras.crear"))):
    suc = sucursal_efectiva(usuario, datos.id_sucursal)
    prov = conn.execute("SELECT id_proveedor, razon_social, estado FROM proveedores WHERE id_proveedor = %s", (datos.id_proveedor,)).fetchone()
    if not prov or prov["estado"] != "ACTIVO":
        raise HTTPException(400, "El proveedor no existe o está inactivo.")
    if datos.fecha_entrega < date.today():
        raise HTTPException(400, "La fecha de entrega no puede ser anterior a hoy.")
    lineas, vistos = [], set()
    for l in datos.items:
        v = conn.execute(
            """SELECT v.id_variante, v.sku FROM variantes_producto v
                JOIN productos_proveedores pp ON pp.id_producto = v.id_producto AND pp.id_proveedor = %s
               WHERE v.id_variante = %s OR upper(v.sku) = upper(%s)""",
            (datos.id_proveedor, l.id_variante or 0, (l.sku or "").strip()),
        ).fetchone()
        if not v:
            raise HTTPException(400, f"El SKU {l.sku or l.id_variante} no existe o no está asociado a {prov['razon_social']}.")
        if v["id_variante"] in vistos:
            raise HTTPException(400, f"El SKU {v['sku']} está repetido en la orden.")
        vistos.add(v["id_variante"])
        lineas.append((v["id_variante"], l.cantidad, l.costo_unitario))
    total = round(sum(c * k for _, c, k in lineas), 2)
    id_o = conn.execute("SELECT nextval(pg_get_serial_sequence('ordenes_compra', 'id_orden')) AS id").fetchone()["id"]
    numero = f"OC-{id_o:05d}"
    o = conn.execute(
        """INSERT INTO ordenes_compra (id_orden, numero, id_proveedor, id_sucursal, id_usuario, fecha_entrega, total, observacion)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING id_orden""",
        (id_o, numero, datos.id_proveedor, suc, usuario.id_usuario, datos.fecha_entrega, total, datos.observacion),
    ).fetchone()
    for id_var, cant, costo in lineas:
        conn.execute(
            "INSERT INTO detalle_orden_compra (id_orden, id_variante, cantidad, costo_unitario) VALUES (%s, %s, %s, %s)",
            (o["id_orden"], id_var, cant, costo),
        )
    audit.registrar(conn, usuario.id_usuario, "CREAR_ORDEN_COMPRA", "ordenes_compra", o["id_orden"],
                    despues={"numero": numero, "proveedor": prov["razon_social"], "total": total, "lineas": len(lineas)})
    conn.commit()
    return {"id_orden": o["id_orden"], "numero": numero}


@router.post("/{id_orden}/decision")
def decidir(id_orden: int, datos: DecisionIn, conn=Depends(get_conn), usuario: UsuarioActual = Depends(requiere("compras.aprobar"))):
    o = conn.execute("SELECT numero, estado FROM ordenes_compra WHERE id_orden = %s FOR UPDATE", (id_orden,)).fetchone()
    if not o:
        raise HTTPException(404, "Orden no encontrada.")
    if o["estado"] != "PENDIENTE_APROBACION":
        raise HTTPException(409, "La orden ya no está pendiente de aprobación.")
    if datos.decision == "RECHAZADA" and not (datos.observacion or "").strip():
        raise HTTPException(400, "Indica el motivo del rechazo.")
    conn.execute(
        "INSERT INTO aprobaciones_compra (id_orden, id_usuario, decision, observacion) VALUES (%s, %s, %s, %s)",
        (id_orden, usuario.id_usuario, datos.decision, datos.observacion),
    )
    conn.execute("UPDATE ordenes_compra SET estado = %s WHERE id_orden = %s", (datos.decision, id_orden))
    audit.registrar(conn, usuario.id_usuario, "APROBAR_ORDEN" if datos.decision == "APROBADA" else "RECHAZAR_ORDEN",
                    "ordenes_compra", id_orden, antes={"numero": o["numero"], "estado": o["estado"]},
                    despues={"numero": o["numero"], "estado": datos.decision, "observacion": datos.observacion})
    conn.commit()
    return {"ok": True}


@router.post("/{id_orden}/recepciones")
def recibir(id_orden: int, datos: RecepcionIn, conn=Depends(get_conn), usuario: UsuarioActual = Depends(requiere("compras.recibir"))):
    o = conn.execute("SELECT numero, estado, id_sucursal FROM ordenes_compra WHERE id_orden = %s FOR UPDATE", (id_orden,)).fetchone()
    if not o:
        raise HTTPException(404, "Orden no encontrada.")
    sucursal_efectiva(usuario, o["id_sucursal"])
    if o["estado"] not in ("APROBADA", "RECIBIDA_PARCIAL"):
        raise HTTPException(409, "Solo se reciben órdenes aprobadas o con recepción parcial.")
    lineas = [l for l in datos.items if l.cantidad > 0]
    if not lineas:
        raise HTTPException(400, "Indica al menos una cantidad a recibir.")
    rec = conn.execute(
        "INSERT INTO recepciones_compra (id_orden, id_usuario) VALUES (%s, %s) RETURNING id_recepcion", (id_orden, usuario.id_usuario)
    ).fetchone()["id_recepcion"]
    total = 0
    for l in lineas:
        d = conn.execute(
            "SELECT id_variante, cantidad, cantidad_recibida FROM detalle_orden_compra WHERE id_detalle = %s AND id_orden = %s FOR UPDATE",
            (l.id_detalle, id_orden),
        ).fetchone()
        if not d:
            raise HTTPException(400, f"La línea {l.id_detalle} no pertenece a la orden.")
        if l.cantidad > d["cantidad"] - d["cantidad_recibida"]:
            raise HTTPException(400, "No se puede recibir más de lo pendiente en una línea.")
        conn.execute("UPDATE detalle_orden_compra SET cantidad_recibida = cantidad_recibida + %s WHERE id_detalle = %s",
                     (l.cantidad, l.id_detalle))
        conn.execute(
            "INSERT INTO detalle_recepcion (id_recepcion, id_detalle_orden, id_variante, cantidad_recibida) VALUES (%s, %s, %s, %s)",
            (rec, l.id_detalle, d["id_variante"], l.cantidad),
        )
        registrar_movimiento(conn, o["id_sucursal"], d["id_variante"], "ENTRADA_COMPRA", l.cantidad, o["numero"], usuario.id_usuario)
        total += l.cantidad
    pendiente = conn.execute(
        "SELECT COALESCE(sum(cantidad - cantidad_recibida), 0) AS p FROM detalle_orden_compra WHERE id_orden = %s", (id_orden,)
    ).fetchone()["p"]
    nuevo = "RECIBIDA" if pendiente == 0 else "RECIBIDA_PARCIAL"
    conn.execute("UPDATE ordenes_compra SET estado = %s WHERE id_orden = %s", (nuevo, id_orden))
    conn.execute("UPDATE recepciones_compra SET estado = %s WHERE id_recepcion = %s", ("TOTAL" if pendiente == 0 else "PARCIAL", rec))
    audit.registrar(conn, usuario.id_usuario, "REGISTRAR_RECEPCION", "recepciones_compra", rec,
                    antes={"numero": o["numero"], "estado": o["estado"]},
                    despues={"numero": o["numero"], "estado": nuevo, "pares": total})
    conn.commit()
    return {"ok": True, "estado": nuevo, "pares": total}
