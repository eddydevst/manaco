import csv
import io
import math
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from .. import audit
from ..db import get_conn
from ..security import UsuarioActual, requiere, sucursal_efectiva
from ..services import analitica
from ..services.pronostico import pronosticar, serie_mensual

router = APIRouter(prefix="/api", tags=["Inteligencia de negocios"])


@router.get("/kpis/panel")
def panel(periodo: str = "anio", id_sucursal: int | None = None, id_categoria: int | None = None,
          conn=Depends(get_conn), usuario: UsuarioActual = Depends(requiere("panel.ver"))):
    if periodo not in ("mes", "30", "90", "anio", "12m"):
        raise HTTPException(400, "Período no válido.")
    return analitica.panel(conn, periodo, sucursal_efectiva(usuario, id_sucursal), id_categoria)


@router.get("/reportes/{tipo}")
def reporte(tipo: str, desde: date | None = None, hasta: date | None = None, id_sucursal: int | None = None,
            conn=Depends(get_conn), usuario: UsuarioActual = Depends(requiere("reportes.ver"))):
    if tipo not in analitica.REPORTES:
        raise HTTPException(404, "Reporte no encontrado.")
    hasta = hasta or date.today()
    desde = desde or date(hasta.year, 1, 1)
    return analitica.reporte(conn, tipo, desde, hasta, sucursal_efectiva(usuario, id_sucursal))


@router.get("/reportes/{tipo}/csv")
def reporte_csv(tipo: str, desde: date | None = None, hasta: date | None = None, id_sucursal: int | None = None,
                conn=Depends(get_conn), usuario: UsuarioActual = Depends(requiere("reportes.ver"))):
    r = reporte(tipo, desde, hasta, id_sucursal, conn, usuario)
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";")
    w.writerow([c["etiqueta"] for c in r["columnas"]])
    for f in r["filas"]:
        w.writerow([("" if f[c["clave"]] is None else f[c["clave"]]) for c in r["columnas"]])
    buf.seek(0)
    return StreamingResponse(iter(["﻿" + buf.getvalue()]), media_type="text/csv",
                             headers={"Content-Disposition": f'attachment; filename="reporte_{tipo}.csv"'})


# ------------------------------------------------------------------ pronósticos
def _nombres(conn, nivel):
    if nivel == "CATEGORIA":
        return {r["id"]: r for r in conn.execute("SELECT id_categoria AS id, nombre FROM categorias")}
    return {r["id"]: r for r in conn.execute("SELECT id_producto AS id, modelo AS nombre FROM productos WHERE estado = 'ACTIVO'")}


def calcular_pronosticos(conn, nivel: str, suc: int | None) -> dict:
    meses, series, parcial = serie_mensual(conn, nivel, suc, "unidades")
    nombres = _nombres(conn, nivel)
    col = "p.id_categoria" if nivel == "CATEGORIA" else "p.id_producto"
    stocks = {r["id"]: float(r["stock"]) for r in conn.execute(
        f"""SELECT {col} AS id, COALESCE(sum(i.stock_actual), 0) AS stock
              FROM inventario i JOIN variantes_producto v USING (id_variante) JOIN productos p USING (id_producto)
             WHERE p.estado = 'ACTIVO' AND (%(s)s::int IS NULL OR i.id_sucursal = %(s)s) GROUP BY 1""", {"s": suc})}
    entidades = []
    for clave, info in nombres.items():
        hist = series.get(clave, [0.0] * len(meses))
        fc = pronosticar(hist, meses, 3)
        siguiente = fc["pronostico"][1] if fc else 0.0
        stock = stocks.get(clave, 0.0)
        diaria = siguiente / 30
        cobertura = stock / diaria if diaria > 0 else None
        sugerido = max(0, math.ceil(siguiente * 1.2 - stock)) if fc else 0
        entidades.append({
            "clave": clave, "nombre": info["nombre"], "historial": hist, "parcial": parcial.get(clave, 0.0),
            "ultimos_3": sum(hist[-3:]), "pronostico": fc["pronostico"] if fc else None, "modelo": fc["modelo"] if fc else None,
            "mape": fc["mape"] if fc else None, "stock": stock, "cobertura_dias": cobertura, "sugerido": sugerido,
            "senal": "REPONER" if sugerido > 0 else ("SOBRESTOCK" if cobertura and cobertura > 120 and stock > 0 else "CUBIERTO"),
        })
    entidades.sort(key=lambda e: -(e["pronostico"][1] if e["pronostico"] else 0))
    total = series.get("T", [])
    fct = pronosticar(total, meses, 3) if total else None
    hoy = date.today()
    return {
        "nivel": nivel, "meses": [m.isoformat() for m in meses],
        "meses_pronostico": fct["meses"] if fct else [],
        "mes_actual": date(hoy.year, hoy.month, 1).isoformat(),
        "total": {"historial": total, "parcial": parcial.get("T", 0.0), **(fct or {})},
        "entidades": entidades,
    }


@router.get("/pronosticos")
def pronosticos(nivel: str = "PRODUCTO", id_sucursal: int | None = None, conn=Depends(get_conn),
                usuario: UsuarioActual = Depends(requiere("pronosticos.ver"))):
    if nivel not in ("PRODUCTO", "CATEGORIA"):
        raise HTTPException(400, "Nivel no válido.")
    data = calcular_pronosticos(conn, nivel, sucursal_efectiva(usuario, id_sucursal))
    ultimo = conn.execute(
        """SELECT p.fecha_generacion, u.nombre AS usuario FROM pronosticos_demanda p LEFT JOIN usuarios u USING (id_usuario)
            ORDER BY p.fecha_generacion DESC LIMIT 1""").fetchone()
    data["ultimo_guardado"] = ultimo
    return data


class GuardarIn(BaseModel):
    nivel: str = "PRODUCTO"
    id_sucursal: int | None = None


@router.post("/pronosticos/guardar")
def guardar(datos: GuardarIn, conn=Depends(get_conn), usuario: UsuarioActual = Depends(requiere("pronosticos.ver"))):
    suc = sucursal_efectiva(usuario, datos.id_sucursal)
    data = calcular_pronosticos(conn, datos.nivel, suc)
    n = 0
    for e in data["entidades"]:
        if not e["pronostico"]:
            continue
        for periodo, cant in zip(data["meses_pronostico"], e["pronostico"]):
            conn.execute(
                """INSERT INTO pronosticos_demanda (nivel, id_producto, id_categoria, id_sucursal, periodo, cantidad_estimada, modelo, mape, id_usuario)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                (datos.nivel, e["clave"] if datos.nivel == "PRODUCTO" else None, e["clave"] if datos.nivel == "CATEGORIA" else None,
                 suc, periodo, cant, e["modelo"], e["mape"], usuario.id_usuario),
            )
            n += 1
    audit.registrar(conn, usuario.id_usuario, "GUARDAR_PRONOSTICO", "pronosticos_demanda", None,
                    despues={"nivel": datos.nivel, "id_sucursal": suc, "registros": n, "periodos": data["meses_pronostico"]})
    conn.commit()
    return {"ok": True, "registros": n}


@router.get("/pronosticos/sugerencia-oc")
def sugerencia_oc(id_producto: int, cantidad: int, id_sucursal: int | None = None, conn=Depends(get_conn),
                  usuario: UsuarioActual = Depends(requiere("compras.crear"))):
    suc = sucursal_efectiva(usuario, id_sucursal)
    prov = conn.execute(
        """SELECT pp.id_proveedor, pp.costo_referencia FROM productos_proveedores pp JOIN proveedores p USING (id_proveedor)
            WHERE pp.id_producto = %s AND p.estado = 'ACTIVO' ORDER BY pp.costo_referencia NULLS LAST LIMIT 1""", (id_producto,)).fetchone()
    if not prov:
        raise HTTPException(409, "El producto no tiene proveedor asociado.")
    pesos = conn.execute(
        """SELECT v.id_variante, v.sku, v.costo_referencia,
                  1 + COALESCE((SELECT sum(d.cantidad) FROM detalle_venta d JOIN ventas ve USING (id_venta)
                                 WHERE d.id_variante = v.id_variante AND ve.fecha > now() - interval '180 days'
                                   AND (%(s)s::int IS NULL OR ve.id_sucursal = %(s)s)), 0) AS peso
             FROM variantes_producto v WHERE v.id_producto = %(p)s AND v.estado = 'ACTIVO' ORDER BY v.sku""",
        {"p": id_producto, "s": suc}).fetchall()
    total = sum(float(p["peso"]) for p in pesos) or 1
    lineas = [{"sku": p["sku"], "cantidad": round(cantidad * float(p["peso"]) / total),
               "costo_unitario": float(prov["costo_referencia"] or p["costo_referencia"])} for p in pesos]
    entrega = date.today() + timedelta(days=10)
    return {"id_proveedor": prov["id_proveedor"], "id_sucursal": suc, "fecha_entrega": entrega.isoformat(),
            "observacion": "Sugerida por pronóstico de demanda", "items": [l for l in lineas if l["cantidad"] > 0]}
