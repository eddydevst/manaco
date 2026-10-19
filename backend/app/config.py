"""Configuración leída de variables de entorno (archivo .env en la carpeta backend)."""
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "dev_db")
DB_USER = os.getenv("DB_USER", "dev")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")

SCHEMA = os.getenv("DB_SCHEMA", "manaco")
TIMEZONE = os.getenv("TIMEZONE", "America/La_Paz")

JWT_SECRET = os.getenv("JWT_SECRET", "cambia-esta-clave-en-produccion")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "480"))

CORS_ORIGINS = [o.strip() for o in os.getenv("CORS_ORIGINS", "https://manaco-zt5s.onrender.com/").split(",") if o.strip()]

# Días sin ventas para considerar un SKU de baja rotación (configurable por consulta)
DIAS_BAJA_ROTACION = int(os.getenv("DIAS_BAJA_ROTACION", "120"))
