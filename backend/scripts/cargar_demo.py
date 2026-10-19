"""Carga datos de DEMOSTRACIÓN para probar el sistema y los indicadores.

Genera proveedores, 12 modelos de calzado (≈90 SKU), usuarios por rol, un
historial de ventas desde enero de 2025 con estacionalidad (campaña escolar,
temporadas), órdenes de compra y los movimientos de inventario que explican
cada existencia. Los datos son ficticios: reemplázalos por los reales de MANACO
(por ejemplo, con el importador de productos) antes de usar el sistema en serio.

Uso: python -m scripts.cargar_demo            (solo si la base no tiene ventas)
     python -m scripts.cargar_demo --forzar   (agrega igualmente)
"""
import argparse
import math
import random
from datetime import date, datetime, timedelta

from app.db import connect
from app.security import hash_password

ESTACIONALIDAD = {
    "esc": [2.6, 2.2, .9, .7, .6, .6, .7, .8, .8, .9, 1, 1.4],
    "ver": [1.4, 1.3, 1.1, .9, .7, .6, .6, .7, .9, 1.1, 1.3, 1.4],
    "inv": [.6, .6, .8, 1.1, 1.4, 1.6, 1.5, 1.2, .9, .7, .6, .6],
    "nav": [.9, .8, .8, .8, .9, .9, 1, 1, .9, 1, 1.3, 2],
    "pla": [1, .9, 1, 1, 1, 1, 1.1, 1, 1, 1, 1.1, 1.3],
}
COLORES = {"Negro": "NG", "Café": "CF", "Blanco": "BL", "Beige": "BE", "Azul": "AZ", "Gris": "GR", "Rosa": "RS"}
PROVEEDORES = [
    ("PRV01", "Curtiembre del Valle S.R.L.", "1023456021", "Raúl Terrazas", "+591 4 4251122", "Bolivia"),
    ("PRV02", "Suelas Andinas Ltda.", "2034567012", "Silvia Paz", "+591 2 2443300", "Bolivia"),
    ("PRV03", "Textiles Oriente S.A.", "3045678015", "Hugo Saavedra", "+591 3 3366780", "Bolivia"),
    ("PRV04", "Calzados Sport Import", None, "Fernanda Lima", "+55 11 4000 1234", "Brasil"),
    ("PRV05", "Seguridad Industrial Sur", None, "Patricio Rojas", "+56 2 2900 4455", "Chile"),
]
# categoría, modelo, colores, tallas, precio, costo, temporada, popularidad, índice proveedor
MODELOS = [
    ("ESC", "Escolar cuero cordones", ["Negro"], (34, 40), 230, 135, "esc", 1.0, 0),
    ("ESC", "Escolar velcro", ["Negro"], (28, 33), 195, 112, "esc", .6, 0),
    ("ESC", "Zapatilla escolar", ["Blanco"], (33, 39), 180, 104, "esc", .8, 2),
    ("VCA", "Mocasín clásico", ["Negro", "Café"], (39, 43), 320, 180, "pla", .9, 0),
    ("VCA", "Oxford ejecutivo", ["Negro"], (39, 43), 360, 205, "pla", .5, 0),
    ("VDA", "Ballerina confort", ["Negro", "Beige"], (35, 38), 240, 140, "pla", .7, 1),
    ("DEP", "Zapatilla urbana lona", ["Blanco", "Azul"], (37, 42), 190, 127, "ver", .9, 3),
    ("DEP", "Running ligero", ["Gris"], (38, 42), 280, 170, "pla", .5, 3),
    ("CAS", "Sandalia plataforma", ["Beige"], (35, 38), 190, 148, "ver", .12, 1),
    ("SEG", "Bota punta de acero", ["Negro"], (38, 43), 390, 250, "pla", .45, 4),
    ("INF", "Zapatilla luces niño", ["Azul", "Rosa"], (24, 30), 160, 96, "nav", .5, 2),
    ("CAS", "Botín gamuza", ["Café"], (36, 40), 300, 185, "inv", .35, 0),
]
PESO_SUCURSAL = {"SCZ01": 1.0, "LPZ01": .85, "CBB01": .7, "EAL01": .5, "SUC01": .4}
USUARIOS = [
    ("Carlos Mendoza", "gerencia@manaco.demo", "Gerente comercial", None),
    ("Jorge Quispe", "almacen@manaco.demo", "Encargado de almacén", None),
    ("Lucía Flores", "caja.scz@manaco.demo", "Cajero", "SCZ01"),
    ("María Vargas", "caja.lpz@manaco.demo", "Cajero", "LPZ01"),
    ("Diego Choque", "caja.cbb@manaco.demo", "Cajero", "CBB01"),
    ("Rosa Mamani", "caja.eal@manaco.demo", "Cajero", "EAL01"),
    ("Pedro Arce", "caja.suc@manaco.demo", "Cajero", "SUC01"),
]


def nextval(cur, tabla, col):
    return cur.execute(f"SELECT nextval(pg_get_serial_sequence('{tabla}', '{col}')) AS n").fetchone()["n"]


def poisson(r, lam):
    L, k, p = math.exp(-lam), 0, 1.0
    while True:
        k += 1
        p *= r.random()
        if p <= L:
            return k - 1


def cargar(forzar: bool = False) -> None:
    r = random.Random(20261019)
    with connect() as conn, conn.cursor() as cur:
        if not forzar and cur.execute("SELECT count(*) AS n FROM ventas").fetchone()["n"] > 0:
            print("  · La base ya tiene ventas: no se cargan datos de demostración (usa --forzar si lo deseas).")
            return
        print("  Cargando datos de demostración...")
        suc = {x["codigo"]: x["id_sucursal"] for x in cur.execute("SELECT codigo, id_sucursal FROM sucursales")}
        cat = {x["codigo"]: x["id_categoria"] for x in cur.execute("SELECT codigo, id_categoria FROM categorias")}
        roles = {x["nombre"]: x["id_rol"] for x in cur.execute("SELECT nombre, id_rol FROM roles")}
        admin = cur.execute(
            "SELECT u.id_usuario FROM usuarios u JOIN usuarios_roles ur USING (id_usuario) JOIN roles ro USING (id_rol) "
            "WHERE ro.nombre = 'Administrador' ORDER BY u.id_usuario LIMIT 1").fetchone()["id_usuario"]

        # Proveedores
        prov_ids = []
        for codigo, rs, nit, ct, tel, pais in PROVEEDORES:
            x = cur.execute(
                """INSERT INTO proveedores (codigo, razon_social, nit, contacto, telefono, correo, pais)
                   VALUES (%s, %s, %s, %s, %s, %s, %s)
                   ON CONFLICT (codigo) DO UPDATE SET razon_social = EXCLUDED.razon_social RETURNING id_proveedor""",
                (codigo, rs, nit, ct, tel, f"ventas@{codigo.lower()}.demo", pais)).fetchone()
            prov_ids.append(x["id_proveedor"])

        # Usuarios demo (contraseña demo12345)
        pwd = hash_password("demo12345")
        usuarios = {}
        for nombre, correo, rol, s in USUARIOS:
            x = cur.execute(
                """INSERT INTO usuarios (nombre, correo, password_hash, id_sucursal) VALUES (%s, %s, %s, %s)
                   ON CONFLICT (correo) DO UPDATE SET nombre = EXCLUDED.nombre RETURNING id_usuario""",
                (nombre, correo, pwd, suc[s] if s else None)).fetchone()
            cur.execute("INSERT INTO usuarios_roles VALUES (%s, %s) ON CONFLICT DO NOTHING", (x["id_usuario"], roles[rol]))
            usuarios[correo] = x["id_usuario"]
        cajero = {suc[s]: usuarios[c] for _, c, _, s in USUARIOS if s}
        u_gerente, u_almacen = usuarios["gerencia@manaco.demo"], usuarios["almacen@manaco.demo"]

        # Productos y variantes
        modelos = []
        for ccod, modelo, colores, (t0, t1), precio, costo, temp, pop, pidx in MODELOS:
            p = cur.execute(
                """INSERT INTO productos (id_categoria, marca, modelo, descripcion) VALUES (%s, 'Manaco', %s, %s)
                   ON CONFLICT (id_categoria, marca, modelo) DO UPDATE SET descripcion = EXCLUDED.descripcion RETURNING id_producto""",
                (cat[ccod], modelo, f"{modelo} · {', '.join(colores)}")).fetchone()["id_producto"]
            vs = []
            for color in colores:
                for t in range(t0, t1 + 1):
                    sku = f"MNC-{ccod}-{p:03d}-{COLORES[color]}-{t}"
                    v = cur.execute(
                        """INSERT INTO variantes_producto (id_producto, talla, color, sku, precio_venta, costo_referencia)
                           VALUES (%s, %s, %s, %s, %s, %s)
                           ON CONFLICT (sku) DO UPDATE SET precio_venta = EXCLUDED.precio_venta RETURNING id_variante""",
                        (p, str(t), color, sku, precio, costo)).fetchone()["id_variante"]
                    vs.append({"id": v, "precio": precio, "costo": costo})
            cur.execute(
                """INSERT INTO productos_proveedores (id_producto, id_proveedor, codigo_proveedor, costo_referencia)
                   VALUES (%s, %s, %s, %s) ON CONFLICT DO NOTHING""",
                (p, prov_ids[pidx], f"{PROVEEDORES[pidx][0]}-{p:03d}", costo))
            modelos.append({"id": p, "modelo": modelo, "vs": vs, "pop": pop, "temp": ESTACIONALIDAD[temp], "prov": pidx})

        clientes = []
        for n in ["Familia Gutiérrez", "Unidad Educativa San Andrés", "Roberto Céspedes", "Carla Antelo",
                  "Constructora Norte Ltda.", "Marcela Ribera"]:
            clientes.append(cur.execute("INSERT INTO clientes (nombre, fecha_registro) VALUES (%s, '2025-01-02') RETURNING id_cliente",
                                        (n,)).fetchone()["id_cliente"])

        # Historial de ventas
        hoy = date.today()
        fin = hoy - timedelta(days=1)
        d = date(2025, 1, 1)
        total_pop = sum(m["pop"] for m in modelos)
        ventas, detalles, pagos, eventos = [], [], [], []   # eventos: (fecha, suc, var, tipo, cantidad, ref, usuario)
        siguiente_id = nextval(cur, "ventas", "id_venta")
        while d <= fin:
            dow = [1.05, 1.0, 1.0, 1.05, 1.3, 1.45, .55][d.weekday()]
            pesos = [m["pop"] * m["temp"][d.month - 1] for m in modelos]
            spes = sum(pesos)
            for codigo, peso in PESO_SUCURSAL.items():
                s = suc[codigo]
                n = poisson(r, 2.1 * peso * dow * (spes / total_pop) * (1.07 if d.year >= 2026 else 1))
                for _ in range(n):
                    fecha = datetime(d.year, d.month, d.day, 9 + r.randrange(11), r.randrange(60))
                    id_v = siguiente_id
                    siguiente_id += 1
                    numero = f"V-{id_v:06d}"
                    lineas = []
                    for _l in range(2 if r.random() < .22 else 1):
                        x, mi = r.random() * spes, 0
                        while mi < len(pesos) - 1 and x > pesos[mi]:
                            x -= pesos[mi]
                            mi += 1
                        v = r.choice(modelos[mi]["vs"])
                        if any(l[0] == v["id"] for l in lineas):
                            continue
                        c = 2 if r.random() < .12 else 1
                        f = .95 if d.year == 2025 else 1
                        precio, costo = round(v["precio"] * f), round(v["costo"] * f, 2)
                        desc = round(precio * c * .1, 2) if r.random() < .12 else 0
                        lineas.append((v["id"], c, precio, costo, desc, round(precio * c - desc, 2)))
                    sub = sum(l[2] * l[1] for l in lineas)
                    desc_t = round(sum(l[4] for l in lineas), 2)
                    total = round(sub - desc_t, 2)
                    met = "EFECTIVO" if r.random() < .55 else ("TARJETA" if r.random() < .55 else "QR")
                    cli = r.choice(clientes) if r.random() < .15 else None
                    ventas.append((id_v, numero, s, cajero[s], cli, fecha, sub, desc_t, total))
                    pagos.append((id_v, met, total, fecha))
                    for l in lineas:
                        detalles.append((id_v,) + l)
                        eventos.append((fecha, s, l[0], "SALIDA_VENTA", -l[1], numero, cajero[s]))
            d += timedelta(days=1)

        # Órdenes de compra: históricas recibidas + una aprobada + una pendiente
        def orden(pidx, s, fecha, entrega, lineas, estado, obs, recibir=None, fecha_rec=None, aprobada=None):
            id_o = nextval(cur, "ordenes_compra", "id_orden")
            numero = f"OC-{id_o:05d}"
            total = round(sum(c * k for _, c, k in lineas), 2)
            cur.execute(
                """INSERT INTO ordenes_compra (id_orden, numero, id_proveedor, id_sucursal, id_usuario, fecha, fecha_entrega, estado, total, observacion)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                (id_o, numero, prov_ids[pidx], s, u_almacen, fecha, entrega, estado, total, obs))
            if aprobada:
                cur.execute("INSERT INTO aprobaciones_compra (id_orden, id_usuario, decision, fecha) VALUES (%s, %s, 'APROBADA', %s)",
                            (id_o, u_gerente, aprobada))
            rec_id = None
            if recibir:
                rec_id = cur.execute("INSERT INTO recepciones_compra (id_orden, id_usuario, fecha, estado) VALUES (%s, %s, %s, 'TOTAL') RETURNING id_recepcion",
                                     (id_o, u_almacen, fecha_rec)).fetchone()["id_recepcion"]
            for v, c, k in lineas:
                rc = recibir.get(v, 0) if recibir else 0
                det = cur.execute(
                    """INSERT INTO detalle_orden_compra (id_orden, id_variante, cantidad, costo_unitario, cantidad_recibida)
                       VALUES (%s, %s, %s, %s, %s) RETURNING id_detalle""", (id_o, v, c, k, rc)).fetchone()["id_detalle"]
                if rc:
                    cur.execute("INSERT INTO detalle_recepcion (id_recepcion, id_detalle_orden, id_variante, cantidad_recibida) VALUES (%s, %s, %s, %s)",
                                (rec_id, det, v, rc))
                    eventos.append((fecha_rec, s, v, "ENTRADA_COMPRA", rc, numero, u_almacen))

        meses_hist = []
        m = date(2026, 2, 1)
        while m < date(hoy.year, hoy.month, 1) and len(meses_hist) < 8:
            meses_hist.append(m)
            m = date(m.year + (m.month // 12), m.month % 12 + 1, 1)
        for i, mes in enumerate(meses_hist):
            pidx = (i + 1) % 5
            ms = [x for x in modelos if x["prov"] == pidx][:2]
            if not ms:
                continue
            s = suc[list(PESO_SUCURSAL)[i % 5]]
            lineas = [(v["id"], 10 + r.randrange(20), v["costo"]) for x in ms for v in x["vs"][:3]]
            rec = {v: (round(c * .9) if r.random() < .15 else c) for v, c, _ in lineas}
            dia_rec = 12 + r.randrange(8)
            orden(pidx, s, datetime(mes.year, mes.month, 5, 10), date(mes.year, mes.month, 15), lineas, "RECIBIDA",
                  "Reposición mensual", rec, datetime(mes.year, mes.month, dia_rec, 15, 30), datetime(mes.year, mes.month, 6, 9, 30))
        hace = lambda n: datetime.combine(hoy - timedelta(days=n), datetime.min.time()).replace(hour=11)
        m6 = modelos[6]
        orden(3, suc["LPZ01"], hace(5), hoy + timedelta(days=5),
              [(v["id"], 18, v["costo"]) for v in m6["vs"][2:5]], "APROBADA", "Temporada de verano", aprobada=hace(4))
        m2 = modelos[2]
        orden(2, suc["SCZ01"], hace(2), hoy + timedelta(days=9),
              [(v["id"], 20, v["costo"]) for v in m2["vs"][2:5]], "PENDIENTE_APROBACION", "Faltantes en tallas medias")

        # Stock objetivo final y saldo inicial que explica todas las salidas y entradas
        objetivo = {}
        for x in modelos:
            for v in x["vs"]:
                for codigo, peso in PESO_SUCURSAL.items():
                    if x["modelo"] == "Sandalia plataforma":
                        st = 30 + r.randrange(35)
                    else:
                        st = round(x["pop"] * peso * 3 * (.3 + r.random() * 1.3))
                        if r.random() < .06:
                            st = 0
                    objetivo[(suc[codigo], v["id"])] = (st, max(1, round(x["pop"] * peso * 2)))
        eventos.sort(key=lambda e: e[0])
        neto, minimo = {}, {}
        for e in eventos:
            k = (e[1], e[2])
            neto[k] = neto.get(k, 0) + e[4]
            minimo[k] = min(minimo.get(k, 0), neto[k])
        inicio = datetime(2025, 1, 1, 7, 0)
        saldos = []
        for k, (st, mn) in objetivo.items():
            saldo = max(st - neto.get(k, 0), -minimo.get(k, 0))
            cur.execute(
                """INSERT INTO inventario (id_sucursal, id_variante, stock_actual, stock_minimo) VALUES (%s, %s, 0, %s)
                   ON CONFLICT (id_sucursal, id_variante) DO UPDATE SET stock_minimo = EXCLUDED.stock_minimo""", (k[0], k[1], mn))
            if saldo > 0:
                saldos.append((inicio, k[0], k[1], "SALDO_INICIAL", saldo, "Carga inicial", admin))

        cur.execute("SELECT setval(pg_get_serial_sequence('ventas', 'id_venta'), %s)", (siguiente_id,))
        with cur.copy("COPY ventas (id_venta, numero, id_sucursal, id_usuario, id_cliente, fecha, subtotal, descuento, total) FROM STDIN") as cp:
            for row in ventas:
                cp.write_row(row)
        with cur.copy("COPY detalle_venta (id_venta, id_variante, cantidad, precio_unitario, costo_unitario, descuento, subtotal) FROM STDIN") as cp:
            for row in detalles:
                cp.write_row(row)
        with cur.copy("COPY pagos_venta (id_venta, metodo_pago, monto, fecha) FROM STDIN") as cp:
            for row in pagos:
                cp.write_row(row)
        with cur.copy("COPY movimientos_inventario (fecha, id_sucursal, id_variante, tipo, cantidad, referencia, id_usuario) FROM STDIN") as cp:
            for row in saldos + eventos:
                cp.write_row(row)

        for nombre, pais, tipo, desc in [
            ("Distribuidora Calzados Pando", "Bolivia", "Distribuidor", "Distribución en Cobija y Riberalta (ejemplo de demostración)."),
            ("Comercial Andina Perú S.A.C.", "Perú", "Cliente mayorista", "Compras mayoristas de calzado escolar (ejemplo de demostración)."),
        ]:
            cur.execute("INSERT INTO socios_comerciales (nombre, pais, tipo_relacion, descripcion) VALUES (%s, %s, %s, %s)", (nombre, pais, tipo, desc))
        cur.execute(
            """INSERT INTO bitacora (id_usuario, accion, entidad, datos_nuevos)
               VALUES (%s, 'CARGA_DEMO', 'sistema', %s::jsonb)""",
            (admin, f'{{"ventas": {len(ventas)}, "variantes": {sum(len(x["vs"]) for x in modelos)}, "movimientos": {len(saldos) + len(eventos)}}}'))
        conn.commit()
        print(f"  ✓ {len(modelos)} modelos, {sum(len(x['vs']) for x in modelos)} SKU, {len(ventas)} ventas, "
              f"{len(saldos) + len(eventos)} movimientos de inventario. Usuarios demo con contraseña: demo12345")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--forzar", action="store_true")
    cargar(ap.parse_args().forzar)
