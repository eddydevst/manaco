"""API del Sistema Integral de Gestión Comercial e Inteligencia de Negocios MANACO.

Ejecutar (desde la carpeta backend):
    uvicorn app.main:app --reload
Documentación interactiva: http://localhost:8000/docs
"""
import psycopg
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from . import config
from .db import connect
from .routers import analitica, auth, caja, catalogos, compras, externos, importador, inventario, productos, proveedores, usuarios, ventas

app = FastAPI(
    title="MANACO · Gestión Comercial e Inteligencia de Negocios",
    version="1.0.0",
    description="Productos, compras, inventario por sucursal, punto de venta, KPIs y pronósticos de demanda.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],
)

for r in (auth, usuarios, catalogos, productos, importador, proveedores, compras, inventario, caja, ventas, analitica, externos):
    app.include_router(r.router)


# ---------------------------------------------------------------- errores de base de datos legibles
@app.exception_handler(psycopg.errors.CheckViolation)
def check_violation(_: Request, exc: psycopg.errors.CheckViolation):
    if "stock_actual" in str(exc):
        return JSONResponse(status_code=409, content={"detail": "Stock insuficiente: la operación dejaría el inventario en negativo."})
    return JSONResponse(status_code=400, content={"detail": "Algún dato no cumple las reglas de validación."})


@app.exception_handler(psycopg.errors.UniqueViolation)
def unique_violation(_: Request, exc: psycopg.errors.UniqueViolation):
    return JSONResponse(status_code=409, content={"detail": "Ya existe un registro con esos datos."})


@app.exception_handler(psycopg.errors.ForeignKeyViolation)
def fk_violation(_: Request, exc: psycopg.errors.ForeignKeyViolation):
    return JSONResponse(status_code=400, content={"detail": "Se hace referencia a un registro que no existe o que está en uso."})


@app.exception_handler(psycopg.OperationalError)
def sin_conexion(_: Request, exc: psycopg.OperationalError):
    return JSONResponse(status_code=503, content={"detail": "No se pudo conectar con la base de datos. Revisa el archivo .env y que PostgreSQL esté en línea."})


@app.get("/api/salud", tags=["Sistema"])
def salud():
    with connect() as conn:
        n = conn.execute("SELECT count(*) AS n FROM information_schema.tables WHERE table_schema = %s", (config.SCHEMA,)).fetchone()["n"]
    return {"estado": "ok", "esquema": config.SCHEMA, "tablas": n}
