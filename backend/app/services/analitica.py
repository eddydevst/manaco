"""Cálculo de KPIs y reportes a partir de las ventas registradas.

Fórmulas (documentadas también en el panel):
- Ingresos: suma de subtotales de líneas (precio × cantidad − descuento), descontando devoluciones.
- Costo de ventas: costo unitario histórico guardado en cada línea × unidades netas.
- Margen bruto %: (ingresos − costo) ÷ ingresos.
- Ticket promedio: ingresos ÷ número de ventas.
- Rotación: costo de ventas de los últimos 12 meses ÷ valor actual del inventario a costo de referencia.
- Quiebres: combinaciones SKU-sucursal con stock 0.
- Inmovilizado: valor a costo de los SKU con stock y sin ventas en N días.
- Cumplimiento de proveedores: órdenes recibidas antes de la fecha de entrega ÷ órdenes recibidas.
"""
from datetime import date, datetime, timedelta

from .inventario import ESTADO_SQL, ULTIMA_VENTA_CTE

MESES = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]

LINEAS_CTE = """
lineas AS (
  SELECT v.id_venta, v.id_sucursal, v.fecha, p.id_producto, p.id_categoria, d.id_variante,
         (d.cantidad - d.cantidad_devuelta) AS uni,
         d.subtotal * (d.cantidad - d.cantidad_devuelta)::numeric / d.cantidad AS ing,
         d.costo_unitario * (d.cantidad - d.cantidad_devuelta) AS cos,
         (SELECT pv.metodo_pago FROM pagos_venta pv WHERE pv.id_venta = v.id_venta ORDER BY pv.id_pago LIMIT 1) AS metodo
    FROM ventas v
    JOIN detalle_venta d ON d.id_venta = v.id_venta
    JOIN variantes_producto var ON var.id_variante = d.id_variante
    JOIN productos p ON p.id_producto = var.id_producto
   WHERE v.estado <> 'ANULADA' AND d.cantidad > d.cantidad_devuelta
     AND v.fecha >= %(a)s AND v.fecha < %(b)s
     AND (%(suc)s::int IS NULL OR v.id_sucursal = %(suc)s)
     AND (%(cat)s::int IS NULL OR p.id_categoria = %(cat)s)
)
"""


def _f(x) -> float:
    return float(x or 0)


def totales(conn, a, b, suc, cat) -> dict:
    r = conn.execute(
        "WITH " + LINEAS_CTE + """
        SELECT COALESCE(sum(ing), 0) AS ingresos, COALESCE(sum(cos), 0) AS costo, COALESCE(sum(uni), 0) AS unidades,
               count(DISTINCT id_venta) AS ventas FROM lineas""",
        {"a": a, "b": b, "suc": suc, "cat": cat},
    ).fetchone()
    r = {k: _f(v) for k, v in r.items()}
    r["margen"] = (r["ingresos"] - r["costo"]) / r["ingresos"] if r["ingresos"] else None
    r["ticket"] = r["ingresos"] / r["ventas"] if r["ventas"] else 0
    return r


def rango_periodo(periodo: str):
    hoy = datetime.now()
    b = hoy + timedelta(minutes=1)
    if periodo == "mes":
        a = datetime(hoy.year, hoy.month, 1)
        return a, b, a.replace(year=a.year - 1), b.replace(year=b.year - 1), "mismo mes del año anterior"
    if periodo == "anio":
        a = datetime(hoy.year, 1, 1)
        return a, b, a.replace(year=a.year - 1), b.replace(year=b.year - 1), f"mismo período de {hoy.year - 1}"
    dias = {"30": 30, "90": 90}.get(periodo, 365)
    a = hoy - timedelta(days=dias)
    return a, b, a - timedelta(days=dias), a, ("los 12 meses previos" if dias == 365 else f"los {dias} días previos")


def resumen_inventario(conn, suc, cat, dias: int = 120) -> dict:
    return conn.execute(
        "WITH " + ULTIMA_VENTA_CTE + ", base AS (SELECT i.stock_actual, v.costo_referencia, " + ESTADO_SQL + """ AS estado
               FROM inventario i JOIN variantes_producto v USING (id_variante) JOIN productos p USING (id_producto)
               LEFT JOIN uv ON uv.id_sucursal = i.id_sucursal AND uv.id_variante = i.id_variante
              WHERE p.estado = 'ACTIVO' AND (%(suc)s::int IS NULL OR i.id_sucursal = %(suc)s)
                AND (%(cat)s::int IS NULL OR p.id_categoria = %(cat)s))
        SELECT COALESCE(sum(stock_actual * costo_referencia), 0) AS valor,
               COALESCE(sum(stock_actual), 0) AS pares,
               count(*) FILTER (WHERE estado = 'AGOTADO') AS agotados,
               count(*) FILTER (WHERE estado = 'BAJO_MINIMO') AS bajo_minimo,
               count(*) FILTER (WHERE estado = 'BAJA_ROTACION') AS baja_rotacion,
               COALESCE(sum(stock_actual * costo_referencia) FILTER (WHERE estado = 'BAJA_ROTACION'), 0) AS inmovilizado
          FROM base""",
        {"suc": suc, "cat": cat, "dias": dias},
    ).fetchone()


def cumplimiento(conn) -> dict:
    return conn.execute(
        """SELECT CASE WHEN count(*) > 0 THEN avg(CASE WHEN ur.ultima::date <= o.fecha_entrega THEN 1.0 ELSE 0 END) END AS a_tiempo,
                  CASE WHEN sum(d.pedido) > 0 THEN sum(d.recibido)::numeric / sum(d.pedido) END AS cantidad
             FROM ordenes_compra o
             JOIN (SELECT id_orden, max(fecha) AS ultima FROM recepciones_compra GROUP BY id_orden) ur USING (id_orden)
             JOIN (SELECT id_orden, sum(cantidad) AS pedido, sum(cantidad_recibida) AS recibido FROM detalle_orden_compra GROUP BY id_orden) d USING (id_orden)
            WHERE o.estado = 'RECIBIDA'"""
    ).fetchone()


def panel(conn, periodo: str, suc: int | None, cat: int | None) -> dict:
    from .pronostico import serie_mensual, pronosticar

    a, b, pa, pb, etiqueta = rango_periodo(periodo)
    act, ant = totales(conn, a, b, suc, cat), totales(conn, pa, pb, suc, cat)
    inv = resumen_inventario(conn, suc, cat)
    hoy = datetime.now()
    ult12 = totales(conn, hoy - timedelta(days=365), hoy + timedelta(minutes=1), suc, cat)
    params = {"a": a, "b": b, "suc": suc, "cat": cat}

    por_sucursal = conn.execute(
        "WITH " + LINEAS_CTE + """SELECT s.nombre AS etiqueta, sum(l.ing) AS valor FROM lineas l
            JOIN sucursales s ON s.id_sucursal = l.id_sucursal GROUP BY s.nombre ORDER BY valor DESC""", params).fetchall()
    margen_cat = conn.execute(
        "WITH " + LINEAS_CTE + """SELECT c.nombre AS etiqueta, sum(l.ing) AS ingresos,
              CASE WHEN sum(l.ing) > 0 THEN (sum(l.ing) - sum(l.cos)) / sum(l.ing) END AS valor
            FROM lineas l JOIN categorias c ON c.id_categoria = l.id_categoria GROUP BY c.nombre ORDER BY valor DESC""", params).fetchall()
    productos = conn.execute(
        "WITH " + LINEAS_CTE + """SELECT p.modelo, c.nombre AS categoria, sum(l.uni) AS unidades, sum(l.ing) AS ingresos,
              CASE WHEN sum(l.ing) > 0 THEN (sum(l.ing) - sum(l.cos)) / sum(l.ing) END AS margen
            FROM lineas l JOIN productos p ON p.id_producto = l.id_producto JOIN categorias c ON c.id_categoria = p.id_categoria
           GROUP BY p.modelo, c.nombre ORDER BY ingresos DESC""", params).fetchall()
    alertas = conn.execute(
        "WITH " + ULTIMA_VENTA_CTE + ", base AS (SELECT i.stock_actual, v.sku, p.modelo, v.color, v.talla, s.nombre AS sucursal, "
        + ESTADO_SQL + """ AS estado
               FROM inventario i JOIN variantes_producto v USING (id_variante) JOIN productos p USING (id_producto)
               JOIN sucursales s ON s.id_sucursal = i.id_sucursal
               LEFT JOIN uv ON uv.id_sucursal = i.id_sucursal AND uv.id_variante = i.id_variante
              WHERE p.estado = 'ACTIVO' AND (%(suc)s::int IS NULL OR i.id_sucursal = %(suc)s)
                AND (%(cat)s::int IS NULL OR p.id_categoria = %(cat)s))
        SELECT * FROM base WHERE estado <> 'NORMAL'
         ORDER BY CASE estado WHEN 'AGOTADO' THEN 0 WHEN 'BAJO_MINIMO' THEN 1 WHEN 'BAJA_ROTACION' THEN 2 ELSE 3 END, stock_actual
         LIMIT 6""",
        {"suc": suc, "cat": cat, "dias": 120},
    ).fetchall()

    # Serie mensual de ingresos: año actual, año anterior y pronóstico del resto del año
    meses, valores, actual_parcial = serie_mensual(conn, "TOTAL" if not cat else "CATEGORIA", suc, "ingresos")
    clave = "T" if not cat else cat
    hist = valores.get(clave, [0.0] * len(meses))
    fc = pronosticar(hist, meses, horizonte=12 - hoy.month + 1) if hist else None
    actual, anterior, pron = [None] * 12, [None] * 12, [None] * 12
    for i, m in enumerate(meses):
        if m.year == hoy.year:
            actual[m.month - 1] = round(hist[i], 2)
        elif m.year == hoy.year - 1:
            anterior[m.month - 1] = round(hist[i], 2)
    actual[hoy.month - 1] = round(actual_parcial.get(clave, 0.0), 2)
    if fc:
        for k, v in enumerate(fc["pronostico"]):
            mes = hoy.month - 1 + k
            if mes < 12:
                pron[mes] = round(v, 2)
        if hoy.month >= 2 and actual[hoy.month - 2] is not None:
            pron[hoy.month - 2] = actual[hoy.month - 2]

    c = cumplimiento(conn)
    return {
        "comparacion": etiqueta,
        "kpis": {
            "ingresos": act["ingresos"], "ingresos_prev": ant["ingresos"],
            "unidades": act["unidades"], "unidades_prev": ant["unidades"],
            "margen": act["margen"], "margen_prev": ant["margen"],
            "ticket": act["ticket"], "ticket_prev": ant["ticket"],
            "ventas": act["ventas"],
            "rotacion": ult12["costo"] / _f(inv["valor"]) if _f(inv["valor"]) else None,
            "quiebres": inv["agotados"], "bajo_minimo": inv["bajo_minimo"],
            "inmovilizado": _f(inv["inmovilizado"]), "inmovilizado_skus": inv["baja_rotacion"],
            "cumplimiento_a_tiempo": c["a_tiempo"], "cumplimiento_cantidad": c["cantidad"],
        },
        "mensual": {"meses": MESES, "anio": hoy.year, "actual": actual, "anterior": anterior, "pronostico": pron,
                    "mape": fc["mape"] if fc else None, "modelo": fc["modelo"] if fc else None},
        "por_sucursal": por_sucursal,
        "margen_categoria": margen_cat,
        "top_productos": productos[:5],
        "menos_vendidos": productos[-3:] if len(productos) > 8 else [],
        "alertas": alertas,
    }


# ------------------------------------------------------------------ reportes
def _rango(desde: date, hasta: date):
    return datetime(desde.year, desde.month, desde.day), datetime(hasta.year, hasta.month, hasta.day) + timedelta(days=1)


REPORTES = {
    "categorias": ("Ventas por categoría", [("categoria", "Categoría", "texto"), ("unidades", "Pares", "entero"), ("ingresos", "Ingresos", "bs"),
                                             ("costo", "Costo de ventas", "bs"), ("margen_bs", "Margen bruto", "bs"), ("margen", "Margen %", "pct"),
                                             ("participacion", "Participación", "pct")]),
    "sucursales": ("Ventas por sucursal", [("sucursal", "Sucursal", "texto"), ("ventas", "Ventas", "entero"), ("unidades", "Pares", "entero"),
                                           ("ingresos", "Ingresos", "bs"), ("margen", "Margen %", "pct"), ("ticket", "Ticket promedio", "bs"),
                                           ("stock", "Stock actual", "entero")]),
    "productos": ("Productos más y menos vendidos", [("modelo", "Producto", "texto"), ("categoria", "Categoría", "texto"), ("unidades", "Pares", "entero"),
                                                     ("ingresos", "Ingresos", "bs"), ("margen", "Margen %", "pct"), ("stock", "Stock", "entero"),
                                                     ("ultima_venta", "Última venta", "fecha")]),
    "proveedores": ("Cumplimiento de proveedores", [("proveedor", "Proveedor", "texto"), ("ordenes", "Órdenes", "entero"), ("monto", "Monto", "bs"),
                                                     ("pedido", "Pares pedidos", "entero"), ("recibido", "Pares recibidos", "entero"),
                                                     ("cantidad", "Cantidad entregada", "pct"), ("a_tiempo", "A tiempo", "pct")]),
    "compras": ("Evolución de compras y costos", [("mes", "Mes", "mes"), ("ordenes", "Órdenes", "entero"), ("monto", "Monto comprado", "bs"),
                                                  ("pares", "Pares", "entero"), ("costo_par", "Costo promedio por par", "bs")]),
    "variacion": ("Variación de ventas por período", [("mes", "Mes", "mes"), ("ingresos", "Ingresos", "bs"), ("unidades", "Pares", "entero"),
                                                       ("var_mes", "vs. mes anterior", "var"), ("var_anio", "vs. mismo mes año anterior", "var")]),
    "pagos": ("Ventas por método de pago", [("metodo", "Método", "texto"), ("ventas", "Ventas", "entero"), ("ingresos", "Ingresos", "bs"),
                                            ("participacion", "Participación", "pct")]),
}


def reporte(conn, tipo: str, desde: date, hasta: date, suc: int | None) -> dict:
    a, b = _rango(desde, hasta)
    p = {"a": a, "b": b, "suc": suc, "cat": None}
    titulo, cols = REPORTES[tipo]
    if tipo == "categorias":
        filas = conn.execute("WITH " + LINEAS_CTE + """
            SELECT c.nombre AS categoria, sum(uni) AS unidades, sum(ing) AS ingresos, sum(cos) AS costo, sum(ing) - sum(cos) AS margen_bs,
                   CASE WHEN sum(ing) > 0 THEN (sum(ing) - sum(cos)) / sum(ing) END AS margen,
                   sum(ing) / NULLIF(sum(sum(ing)) OVER (), 0) AS participacion
              FROM lineas l JOIN categorias c ON c.id_categoria = l.id_categoria GROUP BY c.nombre ORDER BY ingresos DESC""", p).fetchall()
    elif tipo == "sucursales":
        filas = conn.execute("WITH " + LINEAS_CTE + """
            SELECT s.nombre AS sucursal, count(DISTINCT l.id_venta) AS ventas, COALESCE(sum(uni), 0) AS unidades, COALESCE(sum(ing), 0) AS ingresos,
                   CASE WHEN sum(ing) > 0 THEN (sum(ing) - sum(cos)) / sum(ing) END AS margen,
                   CASE WHEN count(DISTINCT l.id_venta) > 0 THEN sum(ing) / count(DISTINCT l.id_venta) END AS ticket,
                   (SELECT COALESCE(sum(stock_actual), 0) FROM inventario i WHERE i.id_sucursal = s.id_sucursal) AS stock
              FROM sucursales s LEFT JOIN lineas l ON l.id_sucursal = s.id_sucursal
             WHERE (%(suc)s::int IS NULL OR s.id_sucursal = %(suc)s)
             GROUP BY s.id_sucursal ORDER BY ingresos DESC""", p).fetchall()
    elif tipo == "productos":
        filas = conn.execute("WITH " + LINEAS_CTE + """, agg AS (SELECT id_producto, sum(uni) AS unidades, sum(ing) AS ingresos, sum(cos) AS costo
                                                         FROM lineas GROUP BY id_producto)
            SELECT p.modelo, c.nombre AS categoria, COALESCE(agg.unidades, 0) AS unidades, COALESCE(agg.ingresos, 0) AS ingresos,
                   CASE WHEN agg.ingresos > 0 THEN (agg.ingresos - agg.costo) / agg.ingresos END AS margen,
                   (SELECT COALESCE(sum(i.stock_actual), 0) FROM inventario i JOIN variantes_producto v USING (id_variante)
                     WHERE v.id_producto = p.id_producto AND (%(suc)s::int IS NULL OR i.id_sucursal = %(suc)s)) AS stock,
                   (SELECT max(v2.fecha) FROM ventas v2 JOIN detalle_venta d2 USING (id_venta) JOIN variantes_producto x USING (id_variante)
                     WHERE x.id_producto = p.id_producto AND (%(suc)s::int IS NULL OR v2.id_sucursal = %(suc)s)) AS ultima_venta
              FROM productos p JOIN categorias c USING (id_categoria) LEFT JOIN agg USING (id_producto)
             ORDER BY ingresos DESC""", p).fetchall()
    elif tipo == "proveedores":
        filas = conn.execute("""
            SELECT pr.razon_social AS proveedor, count(o.id_orden) AS ordenes, COALESCE(sum(o.total), 0) AS monto,
                   COALESCE(sum(d.pedido), 0) AS pedido, COALESCE(sum(d.recibido), 0) AS recibido,
                   CASE WHEN sum(d.pedido) > 0 THEN sum(d.recibido)::numeric / sum(d.pedido) END AS cantidad,
                   avg(CASE WHEN o.estado = 'RECIBIDA' THEN CASE WHEN ur.ultima::date <= o.fecha_entrega THEN 1.0 ELSE 0 END END) AS a_tiempo
              FROM proveedores pr
              LEFT JOIN ordenes_compra o ON o.id_proveedor = pr.id_proveedor AND o.estado <> 'RECHAZADA'
                    AND o.fecha >= %(a)s AND o.fecha < %(b)s AND (%(suc)s::int IS NULL OR o.id_sucursal = %(suc)s)
              LEFT JOIN (SELECT id_orden, sum(cantidad) AS pedido, sum(cantidad_recibida) AS recibido FROM detalle_orden_compra GROUP BY id_orden) d
                     ON d.id_orden = o.id_orden
              LEFT JOIN (SELECT id_orden, max(fecha) AS ultima FROM recepciones_compra GROUP BY id_orden) ur ON ur.id_orden = o.id_orden
             GROUP BY pr.id_proveedor ORDER BY monto DESC""", p).fetchall()
    elif tipo == "compras":
        filas = conn.execute("""
            SELECT date_trunc('month', o.fecha)::date AS mes, count(*) AS ordenes, sum(o.total) AS monto, sum(d.pares) AS pares,
                   sum(o.total) / NULLIF(sum(d.pares), 0) AS costo_par
              FROM ordenes_compra o JOIN (SELECT id_orden, sum(cantidad) AS pares FROM detalle_orden_compra GROUP BY id_orden) d USING (id_orden)
             WHERE o.estado <> 'RECHAZADA' AND o.fecha >= %(a)s AND o.fecha < %(b)s AND (%(suc)s::int IS NULL OR o.id_sucursal = %(suc)s)
             GROUP BY 1 ORDER BY 1""", p).fetchall()
    elif tipo == "variacion":
        p2 = {**p, "a": a.replace(year=a.year - 1)}
        filas = conn.execute("WITH " + LINEAS_CTE + """, m AS (
                SELECT date_trunc('month', fecha)::date AS mes, sum(ing) AS ingresos, sum(uni) AS unidades FROM lineas GROUP BY 1)
            SELECT m.mes, m.ingresos, m.unidades,
                   (m.ingresos - p.ingresos) / NULLIF(p.ingresos, 0) AS var_mes,
                   (m.ingresos - y.ingresos) / NULLIF(y.ingresos, 0) AS var_anio
              FROM m LEFT JOIN m p ON p.mes = (m.mes - interval '1 month')::date
                     LEFT JOIN m y ON y.mes = (m.mes - interval '1 year')::date
             WHERE m.mes >= date_trunc('month', %(desde)s::date) ORDER BY m.mes""", {**p2, "desde": desde}).fetchall()
    elif tipo == "pagos":
        filas = conn.execute("WITH " + LINEAS_CTE + """
            SELECT metodo, count(DISTINCT id_venta) AS ventas, sum(ing) AS ingresos, sum(ing) / NULLIF(sum(sum(ing)) OVER (), 0) AS participacion
              FROM lineas GROUP BY metodo ORDER BY ingresos DESC""", p).fetchall()
    else:
        raise KeyError(tipo)
    return {"titulo": titulo, "columnas": [{"clave": c, "etiqueta": e, "tipo": t} for c, e, t in cols], "filas": filas}
