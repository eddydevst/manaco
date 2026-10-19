from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from .. import audit
from ..db import get_conn
from ..security import UsuarioActual, get_current_user, requiere, sucursal_efectiva

router = APIRouter(prefix="/api/caja", tags=["Caja"])
OPERAR = requiere("caja.operar")


class AbrirIn(BaseModel):
    id_sucursal: int
    saldo_inicial: float = Field(ge=0)


class MovCajaIn(BaseModel):
    tipo: str = Field(pattern="^(INGRESO|EGRESO)$")
    monto: float = Field(gt=0)
    concepto: str = Field(min_length=3, max_length=200)


class CerrarIn(BaseModel):
    saldo_contado: float = Field(ge=0)


def sesion_abierta(conn, id_usuario: int, bloquear: bool = False):
    return conn.execute(
        """SELECT se.*, c.id_sucursal, c.nombre AS caja, s.nombre AS sucursal
             FROM sesiones_caja se JOIN cajas c USING (id_caja) JOIN sucursales s ON s.id_sucursal = c.id_sucursal
            WHERE se.id_usuario = %s AND se.estado = 'ABIERTA'""" + (" FOR UPDATE OF se" if bloquear else ""),
        (id_usuario,),
    ).fetchone()


def resumen_sesion(conn, id_sesion: int, saldo_inicial) -> dict:
    r = conn.execute(
        """SELECT COALESCE(sum(monto) FILTER (WHERE metodo_pago = 'EFECTIVO'), 0) AS efectivo_neto,
                  COALESCE(sum(monto) FILTER (WHERE tipo = 'VENTA' AND metodo_pago = 'EFECTIVO'), 0) AS ventas_efectivo,
                  COALESCE(sum(monto) FILTER (WHERE tipo = 'VENTA' AND metodo_pago = 'TARJETA'), 0) AS ventas_tarjeta,
                  COALESCE(sum(monto) FILTER (WHERE tipo = 'VENTA' AND metodo_pago = 'QR'), 0) AS ventas_qr,
                  COALESCE(sum(monto) FILTER (WHERE tipo = 'DEVOLUCION'), 0) AS devoluciones,
                  COALESCE(sum(monto) FILTER (WHERE tipo = 'INGRESO'), 0) AS ingresos,
                  COALESCE(sum(monto) FILTER (WHERE tipo = 'EGRESO'), 0) AS egresos,
                  count(*) FILTER (WHERE tipo = 'VENTA') AS ventas
             FROM movimientos_caja WHERE id_sesion = %s""",
        (id_sesion,),
    ).fetchone()
    r["saldo_inicial"] = saldo_inicial
    r["efectivo_esperado"] = float(saldo_inicial) + float(r["efectivo_neto"])
    return r


@router.get("/sesion")
def mi_sesion(conn=Depends(get_conn), usuario: UsuarioActual = Depends(get_current_user)):
    s = sesion_abierta(conn, usuario.id_usuario)
    if not s:
        return None
    s["resumen"] = resumen_sesion(conn, s["id_sesion"], s["saldo_inicial"])
    s["ventas"] = conn.execute(
        """SELECT v.id_venta, v.numero, v.fecha, v.total, v.estado, (SELECT metodo_pago FROM pagos_venta p WHERE p.id_venta = v.id_venta LIMIT 1) AS metodo_pago
             FROM ventas v WHERE v.id_sesion = %s ORDER BY v.fecha DESC LIMIT 10""",
        (s["id_sesion"],),
    ).fetchall()
    return s


@router.get("/estado")
def estado_cajas(conn=Depends(get_conn), usuario: UsuarioActual = Depends(OPERAR)):
    return conn.execute(
        """SELECT c.id_caja, c.nombre, c.estado, s.id_sucursal, s.nombre AS sucursal, u.nombre AS abierta_por, se.apertura
             FROM cajas c JOIN sucursales s USING (id_sucursal)
             LEFT JOIN sesiones_caja se ON se.id_caja = c.id_caja AND se.estado = 'ABIERTA'
             LEFT JOIN usuarios u ON u.id_usuario = se.id_usuario
            WHERE (%(s)s::int IS NULL OR c.id_sucursal = %(s)s) ORDER BY s.id_sucursal""",
        {"s": usuario.id_sucursal},
    ).fetchall()


@router.post("/abrir", status_code=201)
def abrir(datos: AbrirIn, conn=Depends(get_conn), usuario: UsuarioActual = Depends(OPERAR)):
    suc = sucursal_efectiva(usuario, datos.id_sucursal)
    if sesion_abierta(conn, usuario.id_usuario):
        raise HTTPException(409, "Ya tienes una caja abierta.")
    caja = conn.execute("SELECT id_caja, estado FROM cajas WHERE id_sucursal = %s ORDER BY id_caja LIMIT 1 FOR UPDATE", (suc,)).fetchone()
    if not caja:
        raise HTTPException(404, "La sucursal no tiene caja registrada.")
    if caja["estado"] == "ABIERTA":
        quien = conn.execute(
            "SELECT u.nombre FROM sesiones_caja se JOIN usuarios u USING (id_usuario) WHERE se.id_caja = %s AND se.estado = 'ABIERTA'",
            (caja["id_caja"],),
        ).fetchone()
        raise HTTPException(409, f"La caja ya está abierta por {quien['nombre'] if quien else 'otro usuario'}.")
    s = conn.execute(
        "INSERT INTO sesiones_caja (id_caja, id_usuario, saldo_inicial) VALUES (%s, %s, %s) RETURNING id_sesion",
        (caja["id_caja"], usuario.id_usuario, datos.saldo_inicial),
    ).fetchone()
    conn.execute("UPDATE cajas SET estado = 'ABIERTA' WHERE id_caja = %s", (caja["id_caja"],))
    audit.registrar(conn, usuario.id_usuario, "ABRIR_CAJA", "sesiones_caja", s["id_sesion"],
                    despues={"id_sucursal": suc, "saldo_inicial": datos.saldo_inicial})
    conn.commit()
    return {"id_sesion": s["id_sesion"]}


@router.post("/movimientos", status_code=201)
def movimiento(datos: MovCajaIn, conn=Depends(get_conn), usuario: UsuarioActual = Depends(OPERAR)):
    s = sesion_abierta(conn, usuario.id_usuario, bloquear=True)
    if not s:
        raise HTTPException(409, "No tienes una caja abierta.")
    if datos.tipo == "EGRESO":
        disp = resumen_sesion(conn, s["id_sesion"], s["saldo_inicial"])["efectivo_esperado"]
        if datos.monto > disp:
            raise HTTPException(409, f"No hay suficiente efectivo en caja (disponible Bs {disp:.2f}).")
    monto = -datos.monto if datos.tipo == "EGRESO" else datos.monto
    conn.execute(
        "INSERT INTO movimientos_caja (id_sesion, tipo, metodo_pago, monto, concepto, id_usuario) VALUES (%s, %s, 'EFECTIVO', %s, %s, %s)",
        (s["id_sesion"], datos.tipo, monto, datos.concepto, usuario.id_usuario),
    )
    audit.registrar(conn, usuario.id_usuario, f"{datos.tipo}_CAJA", "movimientos_caja", s["id_sesion"], despues=datos.model_dump())
    conn.commit()
    return {"ok": True}


@router.post("/cerrar")
def cerrar(datos: CerrarIn, conn=Depends(get_conn), usuario: UsuarioActual = Depends(OPERAR)):
    s = sesion_abierta(conn, usuario.id_usuario, bloquear=True)
    if not s:
        raise HTTPException(409, "No tienes una caja abierta.")
    r = resumen_sesion(conn, s["id_sesion"], s["saldo_inicial"])
    conn.execute(
        """UPDATE sesiones_caja SET estado = 'CERRADA', cierre = now(), saldo_esperado = %s, saldo_final = %s WHERE id_sesion = %s""",
        (r["efectivo_esperado"], datos.saldo_contado, s["id_sesion"]),
    )
    conn.execute("UPDATE cajas SET estado = 'CERRADA' WHERE id_caja = %s", (s["id_caja"],))
    diferencia = round(datos.saldo_contado - r["efectivo_esperado"], 2)
    audit.registrar(conn, usuario.id_usuario, "CERRAR_CAJA", "sesiones_caja", s["id_sesion"], antes={"estado": "ABIERTA"},
                    despues={"esperado": r["efectivo_esperado"], "contado": datos.saldo_contado, "diferencia": diferencia, "ventas": r["ventas"]})
    conn.commit()
    return {"ok": True, "esperado": r["efectivo_esperado"], "diferencia": diferencia}
