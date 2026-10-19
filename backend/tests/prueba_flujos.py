"""Prueba de humo de la API: recorre los flujos principales contra un servidor en ejecución.

Uso:  python -m tests.prueba_flujos http://localhost:8000 admin@manaco.bo "TuClave"
Requiere datos de demostración cargados (python -m scripts.init_db --demo).
OJO: registra ventas, compras y ajustes reales en la base indicada; úsalo en una base de pruebas.
"""
import io
import sys
import uuid

import requests

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"
CORREO = sys.argv[2] if len(sys.argv) > 2 else "admin@manaco.bo"
CLAVE = sys.argv[3] if len(sys.argv) > 3 else "Admin12345"
ok_count = 0


def check(cond, msg):
    global ok_count
    if not cond:
        raise SystemExit(f"✗ {msg}")
    ok_count += 1
    print(f"✓ {msg}")


def api(s, metodo, ruta, esperado=200, **kw):
    r = s.request(metodo, BASE + ruta, **kw)
    if r.status_code != esperado:
        raise SystemExit(f"✗ {metodo} {ruta} → {r.status_code} (esperado {esperado}): {r.text[:400]}")
    return r.json() if r.headers.get("content-type", "").startswith("application/json") else r


def sesion(correo, clave):
    s = requests.Session()
    tok = api(s, "POST", "/api/auth/login", json={"correo": correo, "password": clave})
    s.headers["Authorization"] = f"Bearer {tok['access_token']}"
    return s, tok["usuario"]


def main():
    s, yo = sesion(CORREO, CLAVE)
    check("usuarios.admin" in yo["permisos"], "login de administrador con todos los permisos")
    api(s, "GET", "/api/auth/me")
    suc = api(s, "GET", "/api/sucursales")
    check(len(suc) == 5, "5 sucursales")
    cats = api(s, "GET", "/api/categorias")

    # Panel y reportes
    p = api(s, "GET", "/api/kpis/panel", params={"periodo": "anio"})
    check(p["kpis"]["ingresos"] > 0 and p["kpis"]["margen"] is not None, f"panel: ingresos {p['kpis']['ingresos']:.0f}, margen {p['kpis']['margen']:.3f}")
    check(len(p["mensual"]["actual"]) == 12, f"serie mensual con pronóstico ({p['mensual']['modelo']})")
    for per in ("mes", "30", "90", "12m"):
        api(s, "GET", "/api/kpis/panel", params={"periodo": per, "id_sucursal": suc[0]["id_sucursal"], "id_categoria": cats[0]["id_categoria"]})
    for tipo in ("categorias", "sucursales", "productos", "proveedores", "compras", "variacion", "pagos"):
        r = api(s, "GET", f"/api/reportes/{tipo}", params={"desde": "2025-01-01"})
        check(len(r["filas"]) > 0, f"reporte {tipo}: {len(r['filas'])} filas")
    csv = api(s, "GET", "/api/reportes/categorias/csv")
    check("Categoría" in csv.text, "reporte CSV")

    # Pronósticos
    pr = api(s, "GET", "/api/pronosticos", params={"nivel": "PRODUCTO"})
    check(len(pr["entidades"]) >= 12 and pr["total"].get("pronostico"), f"pronóstico total con {pr['total'].get('modelo')} (MAPE {pr['total'].get('mape')})")
    api(s, "GET", "/api/pronosticos", params={"nivel": "CATEGORIA", "id_sucursal": suc[1]["id_sucursal"]})
    g = api(s, "POST", "/api/pronosticos/guardar", json={"nivel": "CATEGORIA"})
    check(g["registros"] > 0, "pronóstico guardado")

    # Inventario
    inv = api(s, "GET", "/api/inventario", params={"estado": "AGOTADO"})
    check(inv["resumen"]["pares"] > 0, f"inventario: {inv['resumen']['pares']} pares, {inv['resumen']['agotado']} agotados")
    inv_all = api(s, "GET", "/api/inventario", params={"id_sucursal": suc[0]["id_sucursal"], "q": "escolar"})
    fila = max(inv_all["items"], key=lambda x: x["stock_actual"])
    k = api(s, "GET", "/api/inventario/kardex", params={"id_sucursal": fila["id_sucursal"], "id_variante": fila["id_variante"]})
    check(k["movimientos"] and k["movimientos"][0]["saldo"] == k["stock_actual"], "kardex cuadra con el stock")
    api(s, "POST", "/api/inventario/ajustes", json={"id_sucursal": fila["id_sucursal"], "sku": fila["sku"], "tipo": "ENTRADA_AJUSTE", "cantidad": 3, "motivo": "Conteo de prueba"})
    api(s, "POST", "/api/inventario/transferencias", json={"id_origen": fila["id_sucursal"], "id_destino": suc[1]["id_sucursal"], "sku": fila["sku"], "cantidad": 2})
    api(s, "POST", "/api/inventario/ajustes", 409, json={"id_sucursal": fila["id_sucursal"], "sku": fila["sku"], "tipo": "SALIDA_AJUSTE", "cantidad": 99999, "motivo": "Debe fallar"})
    check(True, "ajuste, transferencia y bloqueo de stock negativo")
    api(s, "PUT", "/api/inventario/minimo", json={"id_sucursal": fila["id_sucursal"], "id_variante": fila["id_variante"], "stock_minimo": 4})
    api(s, "GET", "/api/inventario/movimientos")

    # Productos
    prods = api(s, "GET", "/api/productos")
    det = api(s, "GET", f"/api/productos/{prods[0]['id_producto']}")
    check(det["variantes"], f"detalle de producto con {len(det['variantes'])} variantes")
    nuevo = api(s, "POST", "/api/productos", 201, json={"id_categoria": cats[0]["id_categoria"], "marca": "Manaco", "modelo": f"Prueba {uuid.uuid4().hex[:5]}",
                                                         "colores": ["Negro", "Rojo"], "tallas": "38-40", "precio_venta": 200, "costo_referencia": 110,
                                                         "id_proveedor": 1, "stock_minimo": 3})
    check(len(nuevo["skus"]) == 6, "producto nuevo con 6 SKU")
    v0 = api(s, "GET", f"/api/productos/{nuevo['id_producto']}")["variantes"][0]
    api(s, "PUT", f"/api/variantes/{v0['id_variante']}", json={"precio_venta": 210, "costo_referencia": 115})
    api(s, "POST", f"/api/productos/{nuevo['id_producto']}/variantes", 201, json={"talla": "41", "color": "Negro", "precio_venta": 200, "costo_referencia": 110})
    api(s, "PUT", f"/api/productos/{nuevo['id_producto']}", json={"id_categoria": cats[0]["id_categoria"], "marca": "Manaco", "modelo": "Prueba editada " + uuid.uuid4().hex[:4], "estado": "ACTIVO"})
    api(s, "GET", "/api/variantes/buscar", params={"q": "MNC", "id_proveedor": 1})

    # Importador
    api(s, "GET", "/api/importador/plantilla")
    sufijo = uuid.uuid4().hex[:4].upper()
    contenido = ("SKU;Categoría;Marca;Modelo;Talla;Color;Descripción;Precio de venta;Costo;Proveedor;Sucursal;Stock inicial\n"
                 f"IMP-{sufijo}-39;Casual;Manaco;Náutico {sufijo};39;Negro;;260;150;PRV01;SCZ01;12\n"
                 f"IMP-{sufijo}-40;Casual;Manaco;Náutico {sufijo};40;Negro;;260;150;PRV01;SCZ01;10\n"
                 f"IMP-{sufijo}-40;Casual;Manaco;Náutico {sufijo};40;Negro;;260;150;PRV01;SCZ01;10\n"
                 f"{fila['sku']};Escolar;Manaco;x;36;Negro;;250;140;;;\n"
                 f"IMP-{sufijo}-41;Inexistente;Manaco;Náutico;41;Negro;;;150;PRV99;SCZ01;4\n").encode("utf-8")
    val = api(s, "POST", "/api/importador/validar", files={"archivo": ("prueba.csv", io.BytesIO(contenido), "text/csv")})
    check(val["resumen"] == {"filas": 5, "nuevos": 2, "actualizaciones": 1, "errores": 2}, f"validación del importador {val['resumen']}")
    res = api(s, "POST", "/api/importador/confirmar", files={"archivo": ("prueba.csv", io.BytesIO(contenido), "text/csv")})
    check(res["variantes"] == 2 and res["pares"] == 22, f"importación confirmada {res}")
    api(s, "GET", "/api/importador/historial")
    api(s, "GET", f"/api/importador/{res['id_importacion']}/errores")

    # Proveedores y socios
    provs = api(s, "GET", "/api/proveedores")
    api(s, "GET", f"/api/proveedores/{provs[0]['id_proveedor']}")
    cod = "P" + uuid.uuid4().hex[:5].upper()
    np_ = api(s, "POST", "/api/proveedores", 201, json={"codigo": cod, "razon_social": "Proveedor de prueba", "pais": "Bolivia"})
    api(s, "PUT", f"/api/proveedores/{np_['id_proveedor']}", json={"codigo": cod, "razon_social": "Proveedor de prueba editado", "pais": "Bolivia"})
    api(s, "POST", f"/api/proveedores/{np_['id_proveedor']}/productos", 201, json={"id_producto": prods[0]["id_producto"], "costo_referencia": 100})
    so = api(s, "POST", "/api/socios", 201, json={"nombre": "Socio prueba", "pais": "Chile", "tipo_relacion": "Distribuidor"})
    api(s, "PUT", f"/api/socios/{so['id_socio']}", json={"nombre": "Socio prueba 2", "pais": "Chile", "tipo_relacion": "Distribuidor"})
    api(s, "GET", "/api/socios")
    check(True, "proveedores y socios")

    # Compras: crear → aprobar → recibir parcial → recibir resto
    vp = api(s, "GET", "/api/variantes/buscar", params={"id_proveedor": provs[0]["id_proveedor"], "limite": 2})
    oc = api(s, "POST", "/api/compras", 201, json={"id_proveedor": provs[0]["id_proveedor"], "id_sucursal": suc[0]["id_sucursal"],
                                                   "fecha_entrega": "2099-01-01", "items": [{"sku": vp[0]["sku"], "cantidad": 10, "costo_unitario": 100},
                                                                                           {"id_variante": vp[1]["id_variante"], "cantidad": 5, "costo_unitario": 90}]})
    api(s, "POST", f"/api/compras/{oc['id_orden']}/recepciones", 409, json={"items": []})
    api(s, "POST", f"/api/compras/{oc['id_orden']}/decision", json={"decision": "APROBADA", "observacion": "ok"})
    d = api(s, "GET", f"/api/compras/{oc['id_orden']}")
    api(s, "POST", f"/api/compras/{oc['id_orden']}/recepciones", json={"items": [{"id_detalle": d["items"][0]["id_detalle"], "cantidad": 4}]})
    d = api(s, "GET", f"/api/compras/{oc['id_orden']}")
    check(d["estado"] == "RECIBIDA_PARCIAL", "recepción parcial")
    r = api(s, "POST", f"/api/compras/{oc['id_orden']}/recepciones", json={"items": [{"id_detalle": i["id_detalle"], "cantidad": i["cantidad"] - i["cantidad_recibida"]} for i in d["items"]]})
    check(r["estado"] == "RECIBIDA", f"orden {oc['numero']} recibida por completo")
    api(s, "GET", "/api/compras", params={"estado": "RECIBIDA"})
    api(s, "GET", "/api/compras/resumen")
    sug = api(s, "GET", "/api/pronosticos/sugerencia-oc", params={"id_producto": prods[0]["id_producto"], "cantidad": 30, "id_sucursal": suc[0]["id_sucursal"]})
    check(sug["items"], "orden sugerida por pronóstico")

    # Cajero: restricción por sucursal y punto de venta
    c, cu = sesion("caja.scz@manaco.demo", "demo12345")
    check(cu["id_sucursal"] == suc[0]["id_sucursal"] and "usuarios.admin" not in cu["permisos"], "cajero restringido a su sucursal")
    api(c, "GET", "/api/kpis/panel", 403)
    api(c, "GET", "/api/inventario", 403, params={"id_sucursal": suc[1]["id_sucursal"]})
    if api(c, "GET", "/api/caja/sesion"):
        ses = api(c, "GET", "/api/caja/sesion")
        api(c, "POST", "/api/caja/cerrar", json={"saldo_contado": ses["resumen"]["efectivo_esperado"]})
    api(c, "POST", "/api/pos/catalogo", 405)
    api(c, "GET", "/api/pos/catalogo", 409)
    api(c, "POST", "/api/caja/abrir", 201, json={"id_sucursal": suc[0]["id_sucursal"], "saldo_inicial": 500})
    cat_pos = api(c, "GET", "/api/pos/catalogo", params={"q": "escolar"})
    talla = next(t for g in cat_pos for t in g["tallas"] if t["stock"] >= 3)
    clave = uuid.uuid4().hex
    venta = {"items": [{"id_variante": talla["id_variante"], "cantidad": 2, "descuento_pct": 10}], "metodo_pago": "EFECTIVO",
             "monto_recibido": 1000, "cliente": "Cliente de prueba", "idempotency_key": clave}
    v = api(c, "POST", "/api/ventas", 201, json=venta)
    check(v["numero"].startswith("V-") and v["cambio"] > 0, f"venta {v['numero']} por Bs {v['total']}")
    v2 = api(c, "POST", "/api/ventas", 201, json=venta)
    check(v2.get("duplicada") and v2["id_venta"] == v["id_venta"], "reintento con la misma clave no duplica la venta")
    api(c, "POST", "/api/ventas", 409, json={**venta, "idempotency_key": uuid.uuid4().hex,
                                              "items": [{"id_variante": talla["id_variante"], "cantidad": 100}]})
    check(True, "venta rechazada por stock insuficiente")
    vn = api(c, "GET", f"/api/ventas/numero/{v['numero']}")
    api(c, "POST", f"/api/ventas/{v['id_venta']}/devoluciones", 201,
        json={"items": [{"id_detalle": vn["items"][0]["id_detalle"], "cantidad": 1}], "motivo": "Talla incorrecta"})
    check(api(c, "GET", f"/api/ventas/{v['id_venta']}")["estado"] == "DEVOLUCION_PARCIAL", "devolución parcial")
    api(c, "POST", "/api/caja/movimientos", 201, json={"tipo": "EGRESO", "monto": 20, "concepto": "Transporte"})
    api(c, "POST", "/api/caja/movimientos", 409, json={"tipo": "EGRESO", "monto": 999999, "concepto": "Debe fallar"})
    ses = api(c, "GET", "/api/caja/sesion")
    esperado = 500 + v["total"] - round(v["items"][0]["subtotal"] / 2, 2) - 20
    check(abs(ses["resumen"]["efectivo_esperado"] - esperado) < 0.01, f"caja esperada Bs {ses['resumen']['efectivo_esperado']}")
    cierre = api(c, "POST", "/api/caja/cerrar", json={"saldo_contado": ses["resumen"]["efectivo_esperado"]})
    check(cierre["diferencia"] == 0, "cierre de caja sin diferencia")
    api(c, "GET", "/api/ventas")

    # Usuarios, roles y bitácora
    roles = api(s, "GET", "/api/roles")
    api(s, "GET", "/api/permisos")
    api(s, "GET", "/api/usuarios")
    nu = api(s, "POST", "/api/usuarios", 201, json={"nombre": "Usuario prueba", "correo": f"prueba{uuid.uuid4().hex[:6]}@manaco.bo",
                                                     "id_rol": roles[2]["id_rol"], "password": "secreto1"})
    api(s, "PUT", f"/api/usuarios/{nu['id_usuario']}", json={"nombre": "Usuario prueba 2", "correo": f"prueba{uuid.uuid4().hex[:6]}@manaco.bo",
                                                              "id_rol": roles[2]["id_rol"], "estado": "INACTIVO"})
    nr = api(s, "POST", "/api/roles", 201, json={"nombre": "Rol " + uuid.uuid4().hex[:5]})
    api(s, "PUT", f"/api/roles/{nr['id_rol']}/permisos", json={"permisos": ["panel.ver", "reportes.ver"]})
    api(s, "PUT", f"/api/roles/{roles[0]['id_rol']}/permisos", 400, json={"permisos": []})
    b = api(s, "GET", "/api/bitacora", params={"q": "VENTA"})
    check(b["total"] > 0, f"bitácora con {b['total']} registros de ventas")
    api(s, "GET", "/api/bitacora/usuarios")

    # Comercio exterior
    cx = (b"anio;flujo;pais_reportante;pais_socio;categoria;valor_comercial;cantidad;unidad\n"
          b"2024;Importaci\xc3\xb3n;Bolivia;China;Deportivo;1000;100;pares\n2024;Exportaci\xc3\xb3n;Bolivia;Per\xc3\xba;Escolar;500;40;pares\n")
    api(s, "POST", "/api/comex/importar", files={"archivo": ("comex.csv", io.BytesIO(cx), "text/csv")})
    cxr = api(s, "GET", "/api/comex")
    check(cxr["resumen"]["registros"] >= 2 and cxr["resumen"]["valor_por_par"], "comercio exterior importado")
    api(s, "DELETE", "/api/comex")
    print(f"\nTodo correcto: {ok_count} verificaciones.")


if __name__ == "__main__":
    main()
