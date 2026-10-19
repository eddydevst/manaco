"""Reglas de inventario.

El stock nunca se modifica directamente: se inserta un movimiento y el trigger
fn_aplicar_movimiento actualiza inventario.stock_actual. Antes de una salida se
bloquea la fila de inventario (SELECT ... FOR UPDATE) para que dos ventas
simultáneas no vendan la misma unidad.
"""
from fastapi import HTTPException

TIPOS_ENTRADA = {"SALDO_INICIAL", "ENTRADA_COMPRA", "DEVOLUCION", "ENTRADA_AJUSTE", "TRANSF_ENTRADA", "ENTRADA_IMPORTACION"}
TIPOS_SALIDA = {"SALIDA_VENTA", "SALIDA_AJUSTE", "TRANSF_SALIDA"}


def asegurar_fila(conn, id_sucursal: int, id_variante: int, stock_minimo: int | None = None) -> None:
    conn.execute(
        """INSERT INTO inventario (id_sucursal, id_variante, stock_actual, stock_minimo)
           VALUES (%s, %s, 0, COALESCE(%s, 0))
           ON CONFLICT (id_sucursal, id_variante) DO NOTHING""",
        (id_sucursal, id_variante, stock_minimo),
    )


def bloquear_stock(conn, id_sucursal: int, id_variante: int) -> int:
    asegurar_fila(conn, id_sucursal, id_variante)
    fila = conn.execute(
        "SELECT stock_actual FROM inventario WHERE id_sucursal = %s AND id_variante = %s FOR UPDATE",
        (id_sucursal, id_variante),
    ).fetchone()
    return fila["stock_actual"]


def registrar_movimiento(conn, id_sucursal: int, id_variante: int, tipo: str, cantidad: int,
                         referencia: str, id_usuario: int | None) -> int:
    """Registra un movimiento. cantidad siempre positiva; el signo lo define el tipo.
    Devuelve el stock resultante."""
    if cantidad <= 0:
        raise HTTPException(400, "La cantidad debe ser mayor a cero.")
    if tipo not in TIPOS_ENTRADA | TIPOS_SALIDA:
        raise HTTPException(400, f"Tipo de movimiento no válido: {tipo}")
    stock = bloquear_stock(conn, id_sucursal, id_variante)
    signo = -1 if tipo in TIPOS_SALIDA else 1
    if signo < 0 and stock < cantidad:
        sku = conn.execute("SELECT sku FROM variantes_producto WHERE id_variante = %s", (id_variante,)).fetchone()
        suc = conn.execute("SELECT nombre FROM sucursales WHERE id_sucursal = %s", (id_sucursal,)).fetchone()
        raise HTTPException(
            409,
            f"Stock insuficiente de {sku['sku'] if sku else id_variante} en {suc['nombre'] if suc else id_sucursal}: "
            f"hay {stock} y se necesitan {cantidad}.",
        )
    conn.execute(
        """INSERT INTO movimientos_inventario (id_sucursal, id_variante, tipo, cantidad, referencia, id_usuario)
           VALUES (%s, %s, %s, %s, %s, %s)""",
        (id_sucursal, id_variante, tipo, signo * cantidad, referencia[:120], id_usuario),
    )
    return stock + signo * cantidad


ESTADO_SQL = """
CASE
  WHEN i.stock_actual <= 0 THEN 'AGOTADO'
  WHEN i.stock_actual < i.stock_minimo THEN 'BAJO_MINIMO'
  WHEN uv.ultima_venta IS NULL OR uv.ultima_venta < now() - make_interval(days => %(dias)s) THEN 'BAJA_ROTACION'
  WHEN i.stock_actual > GREATEST(i.stock_minimo * 4, 30) THEN 'SOBRESTOCK'
  ELSE 'NORMAL'
END
"""

ULTIMA_VENTA_CTE = """
uv AS (
  SELECT v.id_sucursal, dv.id_variante, max(v.fecha) AS ultima_venta
    FROM ventas v JOIN detalle_venta dv ON dv.id_venta = v.id_venta
   WHERE v.estado <> 'ANULADA'
   GROUP BY v.id_sucursal, dv.id_variante
)
"""
