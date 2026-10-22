"""Comercio exterior (información externa) y bitácora."""
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse

from .. import audit
from ..db import get_conn
from ..security import UsuarioActual, requiere
from ..services.importador import leer_matriz, norm

router = APIRouter(prefix="/api", tags=["Comercio exterior y bitácora"])
COLS = ["anio", "flujo", "pais_reportante", "pais_socio", "categoria", "valor_comercial", "cantidad", "unidad"]
COMEX = requiere("comex.ver")


@router.get("/comex")
def comex(conn=Depends(get_conn), _: UsuarioActual = Depends(COMEX)):
    total = conn.execute(
        """SELECT count(*) AS registros,
                  COALESCE(sum(valor_comercial) FILTER (WHERE flujo ILIKE 'imp%%'), 0) AS importaciones,
                  COALESCE(sum(valor_comercial) FILTER (WHERE flujo ILIKE 'exp%%'), 0) AS exportaciones,
                  sum(valor_comercial) FILTER (WHERE flujo ILIKE 'imp%%' AND unidad ILIKE '%%par%%')
                    / NULLIF(sum(cantidad) FILTER (WHERE flujo ILIKE 'imp%%' AND unidad ILIKE '%%par%%'), 0) AS valor_por_par
             FROM datos_comercio_exterior"""
    ).fetchone()
    return {
        "resumen": total,
        "por_pais": conn.execute(
            """SELECT pais_socio AS etiqueta, sum(valor_comercial) AS valor FROM datos_comercio_exterior
                WHERE flujo ILIKE 'imp%%' GROUP BY 1 ORDER BY 2 DESC NULLS LAST LIMIT 10""").fetchall(),
        "por_anio": conn.execute(
            """SELECT anio, COALESCE(sum(valor_comercial) FILTER (WHERE flujo ILIKE 'imp%%'), 0) AS importaciones,
                      COALESCE(sum(valor_comercial) FILTER (WHERE flujo ILIKE 'exp%%'), 0) AS exportaciones
                 FROM datos_comercio_exterior GROUP BY anio ORDER BY anio""").fetchall(),
        "por_categoria": conn.execute(
            """SELECT categoria AS etiqueta, sum(valor_comercial) AS valor FROM datos_comercio_exterior
                GROUP BY 1 ORDER BY 2 DESC NULLS LAST LIMIT 10""").fetchall(),
        "registros": conn.execute(f"SELECT {', '.join(COLS)} FROM datos_comercio_exterior ORDER BY anio, flujo LIMIT 300").fetchall(),
    }


@router.get("/comex/plantilla")
def plantilla(_: UsuarioActual = Depends(COMEX)):
    contenido = ";".join(COLS) + "\n2024;Importación;Bolivia;China;Calzado deportivo;1250000;98000;pares\n"
    return StreamingResponse(iter(["﻿" + contenido]), media_type="text/csv",
                             headers={"Content-Disposition": 'attachment; filename="plantilla_comercio_exterior.csv"'})


@router.post("/comex/importar")
async def importar(archivo: UploadFile = File(...), conn=Depends(get_conn), usuario: UsuarioActual = Depends(COMEX)):
    m = leer_matriz(await archivo.read(), archivo.filename)
    if len(m) < 2:
        raise HTTPException(400, "El archivo no tiene filas de datos.")
    cab = [norm(h).replace(" ", "_") for h in m[0]]
    faltan = [c for c in COLS if c not in cab]
    if faltan:
        raise HTTPException(400, "Faltan columnas: " + ", ".join(faltan))
    filas, rechazadas = [], 0
    for f in m[1:]:
        r = {c: (f[cab.index(c)] if cab.index(c) < len(f) else "") for c in COLS}
        try:
            r["anio"] = int(float(str(r["anio"]).strip()))
            for c in ("valor_comercial", "cantidad"):
                r[c] = float(str(r[c]).replace(",", ".")) if str(r[c]).strip() else None
        except ValueError:
            rechazadas += 1
            continue
        if not str(r["flujo"]).strip():
            rechazadas += 1
            continue
        filas.append(r)
    with conn.cursor() as cur:
        cur.executemany(
            f"INSERT INTO datos_comercio_exterior ({', '.join(COLS)}) VALUES ({', '.join('%(' + c + ')s' for c in COLS)})", filas)
    audit.registrar(conn, usuario.id_usuario, "IMPORTAR_COMEX", "datos_comercio_exterior", None,
                    despues={"archivo": archivo.filename, "registros": len(filas), "rechazadas": rechazadas})
    conn.commit()
    return {"registros": len(filas), "rechazadas": rechazadas}


@router.delete("/comex")
def borrar(conn=Depends(get_conn), usuario: UsuarioActual = Depends(COMEX)):
    n = conn.execute("SELECT count(*) AS n FROM datos_comercio_exterior").fetchone()["n"]
    conn.execute("DELETE FROM datos_comercio_exterior")
    audit.registrar(conn, usuario.id_usuario, "BORRAR_COMEX", "datos_comercio_exterior", None, antes={"registros": n})
    conn.commit()
    return {"ok": True}


@router.get("/bitacora")
def bitacora(id_usuario: int | None = None, entidad: str | None = None, q: str = "", pagina: int = 1, tamano: int = 50,
             conn=Depends(get_conn), _: UsuarioActual = Depends(requiere("bitacora.ver"))):
    p = {"u": id_usuario, "e": entidad or None, "q": q.strip(), "ql": f"%{q.strip()}%",
         "lim": min(tamano, 200), "off": (max(pagina, 1) - 1) * min(tamano, 200)}
    where = """WHERE (%(u)s::int IS NULL OR b.id_usuario = %(u)s) AND (%(e)s::text IS NULL OR b.entidad = %(e)s)
                 AND (%(q)s = '' OR b.accion ILIKE %(ql)s OR b.datos_nuevos::text ILIKE %(ql)s OR b.datos_anteriores::text ILIKE %(ql)s)"""
    total = conn.execute("SELECT count(*) AS n FROM bitacora b " + where, p).fetchone()["n"]
    items = conn.execute(
        """SELECT b.id_bitacora, b.fecha, b.accion, b.entidad, b.id_entidad, b.datos_anteriores, b.datos_nuevos, b.ip, u.nombre AS usuario
             FROM bitacora b LEFT JOIN usuarios u USING (id_usuario) """ + where + " ORDER BY b.fecha DESC, b.id_bitacora DESC LIMIT %(lim)s OFFSET %(off)s",
        p,
    ).fetchall()
    entidades = [r["entidad"] for r in conn.execute("SELECT DISTINCT entidad FROM bitacora ORDER BY 1")]
    return {"total": total, "items": items, "entidades": entidades}


@router.get("/bitacora/usuarios")
def usuarios_bitacora(conn=Depends(get_conn), _: UsuarioActual = Depends(requiere("bitacora.ver"))):
    return conn.execute("SELECT id_usuario, nombre FROM usuarios ORDER BY nombre").fetchall()


@router.get("/comex/mercado")
def mercado(anio: int | None = None, pais: str | None = None, categoria: str | None = None,
            flujo: str | None = None, _: UsuarioActual = Depends(COMEX)):
    from ..config import COMEX_ARCHIVO
    from ..services.comercio_exterior import dashboard
    try:
        return dashboard(COMEX_ARCHIVO, anio, pais, categoria, flujo)
    except FileNotFoundError:
        raise HTTPException(404, "No se encontró el Excel de comercio exterior configurado.")
    except ValueError as exc:
        raise HTTPException(422, str(exc))
