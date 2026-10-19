"""Crea el esquema 'manaco', carga los datos iniciales y el usuario administrador.

Uso (desde la carpeta backend, con el entorno virtual activado):
    python -m scripts.init_db
    python -m scripts.init_db --admin-correo admin@manaco.bo --admin-password "MiClave123"
    python -m scripts.init_db --demo        # además carga datos de demostración

Se puede ejecutar más de una vez: las tablas y los datos iniciales no se duplican.
"""
import argparse
import getpass
from pathlib import Path

from app import config
from app.db import connect
from app.security import hash_password

DB_DIR = Path(__file__).resolve().parents[2] / "database"


def ejecutar_sql(conn, archivo: Path) -> None:
    sql = archivo.read_text(encoding="utf-8")
    sql = sql.replace("SET search_path TO manaco;", f"SET search_path TO {config.SCHEMA};")
    sql = sql.replace("CREATE SCHEMA IF NOT EXISTS manaco;", f"CREATE SCHEMA IF NOT EXISTS {config.SCHEMA};")
    sql = sql.replace("manaco.inventario", f"{config.SCHEMA}.inventario")
    conn.execute(sql)
    print(f"  ✓ {archivo.name}")


def crear_admin(conn, correo: str, password: str, nombre: str) -> None:
    existe = conn.execute("SELECT id_usuario FROM usuarios WHERE lower(correo) = lower(%s)", (correo,)).fetchone()
    if existe:
        print(f"  · El usuario {correo} ya existe; no se modifica.")
        return
    u = conn.execute(
        "INSERT INTO usuarios (nombre, correo, password_hash) VALUES (%s, lower(%s), %s) RETURNING id_usuario",
        (nombre, correo, hash_password(password)),
    ).fetchone()
    conn.execute(
        "INSERT INTO usuarios_roles (id_usuario, id_rol) SELECT %s, id_rol FROM roles WHERE nombre = 'Administrador'",
        (u["id_usuario"],),
    )
    conn.execute(
        "INSERT INTO bitacora (id_usuario, accion, entidad, id_entidad, datos_nuevos) VALUES (%s, 'CREAR_USUARIO', 'usuarios', %s, %s::jsonb)",
        (u["id_usuario"], str(u["id_usuario"]), f'{{"correo": "{correo}", "rol": "Administrador", "origen": "init_db"}}'),
    )
    print(f"  ✓ Administrador creado: {correo}")


def main() -> None:
    ap = argparse.ArgumentParser(description="Inicializa la base de datos de MANACO")
    ap.add_argument("--admin-correo", default="admin@manaco.bo")
    ap.add_argument("--admin-nombre", default="Administrador del sistema")
    ap.add_argument("--admin-password")
    ap.add_argument("--demo", action="store_true", help="Cargar datos de demostración (productos, ventas desde 2025, etc.)")
    args = ap.parse_args()

    password = args.admin_password or getpass.getpass(f"Contraseña para {args.admin_correo} (mínimo 8 caracteres): ")
    if len(password) < 8:
        raise SystemExit("La contraseña debe tener al menos 8 caracteres.")

    print(f"Conectando a {config.DB_HOST}:{config.DB_PORT}/{config.DB_NAME} (esquema {config.SCHEMA})...")
    with connect() as conn:
        ejecutar_sql(conn, DB_DIR / "01_schema.sql")
        ejecutar_sql(conn, DB_DIR / "02_datos_iniciales.sql")
        crear_admin(conn, args.admin_correo, password, args.admin_nombre)
        conn.commit()
    if args.demo:
        from scripts.cargar_demo import cargar

        cargar()
    print("Listo.")


if __name__ == "__main__":
    main()
