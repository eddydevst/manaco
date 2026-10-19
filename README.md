# MANACO · Sistema Integral de Gestión Comercial e Inteligencia de Negocios

Sistema web para gestionar productos, compras, proveedores, socios comerciales, inventario por sucursal y punto de venta. Incluye KPIs gerenciales, reportes y pronósticos de demanda.

| Parte | Tecnología | Carpeta |
|---|---|---|
| Base de datos | PostgreSQL (esquema `manaco`) | `database/` |
| Backend (API REST) | Python 3.11+ · FastAPI · psycopg 3 · pandas · scikit-learn | `backend/` |
| Frontend | Angular 18 (componentes standalone) | `frontend/` |

---

## 1. Requisitos

- **Python 3.11 o superior**: https://www.python.org/downloads/ (en Windows marca “Add Python to PATH”).
- **Node.js 20 LTS**: https://nodejs.org (trae `npm`).
- **Acceso a PostgreSQL 14 o superior.** El archivo `backend/.env` ya trae los datos del servidor `dev_db`.
- Recomendado: **Visual Studio Code**.

## 2. Backend (API)

Abre una terminal en la carpeta `backend`:

```bash
# 1) Crear y activar el entorno virtual
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS / Linux:
source .venv/bin/activate

# 2) Instalar dependencias
pip install -r requirements.txt

# 3) Crear el esquema "manaco", los datos iniciales y el usuario administrador
python -m scripts.init_db --admin-correo admin@manaco.bo --admin-password "TuClaveSegura"

#    (opcional) agregar datos de DEMOSTRACIÓN para ver los KPIs y pronósticos con historial:
python -m scripts.init_db --admin-password "TuClaveSegura" --demo

# 4) Iniciar la API
uvicorn app.main:app --reload
```

- API: http://localhost:8000
- Documentación interactiva (Swagger): http://localhost:8000/docs. Usa el botón **Authorize** con tu correo y contraseña.
- Prueba de conexión: http://localhost:8000/api/salud

> `init_db` se puede ejecutar varias veces: no duplica tablas ni datos. Todas las tablas se crean en el esquema `manaco`; nada queda en `public`.

### Configuración (`backend/.env`)

| Variable | Uso |
|---|---|
| `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD` | Conexión a PostgreSQL |
| `DB_SCHEMA` | Esquema (por defecto `manaco`) |
| `TIMEZONE` | Zona horaria de las fechas (por defecto `America/La_Paz`) |
| `JWT_SECRET` | Clave para firmar las sesiones. Cámbiala por una larga y aleatoria. |
| `JWT_EXPIRE_MINUTES` | Duración de la sesión (480 = 8 horas) |
| `CORS_ORIGINS` | Dirección del frontend (por defecto `http://localhost:4200`) |

`.env.example` es la plantilla para otros entornos. **No subas `.env` a GitHub**: contiene la contraseña de la base de datos. El `.gitignore` ya lo excluye.

## 3. Frontend (Angular)

En otra terminal, dentro de `frontend`:

```bash
npm install
npm start
```

Abre http://localhost:4200 e ingresa con el administrador que creaste.

Si la API está en otra dirección, cámbiala en `src/environments/environment.ts` (`apiUrl`). Para generar la versión de producción usa `npm run build`; el resultado queda en `dist/manaco/browser`.

## 4. Usuarios de demostración (solo con `--demo`)

Todas estas cuentas usan la contraseña **`demo12345`**.

| Correo | Rol | Sucursal |
|---|---|---|
| gerencia@manaco.demo | Gerente comercial | Todas |
| almacen@manaco.demo | Encargado de almacén | Todas |
| caja.scz@manaco.demo | Cajero | Santa Cruz – Centro |
| caja.lpz@manaco.demo | Cajero | La Paz – Prado |
| caja.cbb@manaco.demo, caja.eal@manaco.demo, caja.suc@manaco.demo | Cajero | Cochabamba, El Alto, Sucre |

Los datos de demostración son ficticios: 12 modelos, unos 90 SKU, ventas desde enero de 2025 y órdenes de compra. Sirven para probar el sistema. Reemplázalos por los datos reales de MANACO (por ejemplo, con el importador de productos) antes de usarlo en serio. En producción, desactiva o borra estas cuentas.

## 5. Módulos

| Módulo | Qué hace |
|---|---|
| **Usuarios y roles** | Login con JWT. Roles con permisos editables (RBAC) que el backend valida en cada endpoint. Restricción por sucursal. |
| **Bitácora** | Registra cada operación con usuario, fecha, acción, entidad y los datos antes y después del cambio. |
| **Productos** | Categorías, marcas, modelos y variantes (talla × color) con SKU automático, precio y costo de referencia. |
| **Importador** | Plantilla Excel descargable. Valida cada fila (obligatorios, SKU duplicado, categoría, proveedor y sucursal) y muestra una previsualización antes de confirmar. Crea productos nuevos y actualiza los existentes por SKU. El stock inicial entra como movimiento. Genera reporte de errores. |
| **Proveedores** | Datos comerciales, productos suministrados, historial de compras y cumplimiento (entregas a tiempo y cantidad entregada). |
| **Socios comerciales** | Relaciones empresariales. Se mantienen separadas de los países de comercio exterior. |
| **Compras** | Orden → aprobación (solo con permiso) → recepción parcial o total → movimiento de inventario. |
| **Inventario** | Stock por SKU y sucursal, kardex, ajustes, transferencias y stock mínimo. Alertas: agotado, bajo mínimo, baja rotación (días configurables) y sobrestock. |
| **Punto de Venta** | Apertura de caja, catálogo con stock por talla, descuentos, efectivo/tarjeta/QR, cambio, devoluciones, ingresos y egresos, y cierre con arqueo. Una venta reintentada no se duplica (clave de idempotencia). |
| **Panel (KPIs)** | Ingresos, unidades, margen bruto con costo histórico, ticket promedio, rotación, quiebres, inventario inmovilizado y cumplimiento de proveedores. Gráfico mensual con pronóstico. Filtros por período, sucursal y categoría. |
| **Reportes** | Por categoría, sucursal, producto, proveedores, compras y costos, variación mensual y métodos de pago. Exportables a CSV. |
| **Pronósticos** | Compara tres modelos por serie y elige el de menor error (MAPE) en los últimos 3 meses: promedio móvil, promedio móvil estacional y regresión lineal con scikit-learn. Sugiere reposición y puede crear la orden de compra. |
| **Comercio exterior** | Importa el Excel o CSV del caso académico (información externa, no ventas de MANACO). Muestra análisis por país, año, categoría y valor aproximado por par. |

## 6. Reglas de negocio garantizadas

- **El stock solo cambia con movimientos.** Un trigger de PostgreSQL (`fn_aplicar_movimiento`) actualiza `inventario.stock_actual` al registrar cada movimiento. Otro trigger impide editar o borrar movimientos.
- **El inventario nunca queda negativo.** Hay un `CHECK (stock_actual >= 0)` y la fila se bloquea con `SELECT … FOR UPDATE`, así dos ventas simultáneas no pueden vender la misma unidad.
- **Las operaciones críticas son transacciones completas.** Ventas, devoluciones, compras, recepciones e importaciones se confirman enteras o no se aplican.
- **Los márgenes usan el costo histórico.** Cada línea de venta guarda el costo del momento en que se vendió.
- **Una sola caja abierta por sucursal** (índice único parcial).
- **Las credenciales se leen de variables de entorno**, y las contraseñas se guardan cifradas con PBKDF2-SHA256.

## 7. Prueba automática

Con la API en ejecución y los datos de demostración cargados:

```bash
cd backend
python -m tests.prueba_flujos http://localhost:8000 admin@manaco.bo "TuClaveSegura"
```

Hace 34 verificaciones: login, KPIs, reportes, pronósticos, inventario, importador, compras completas, venta, reintento sin duplicar, devolución, caja, permisos y bitácora. **Ojo:** registra operaciones reales, así que úsala en una base de pruebas.

## 8. Estructura

```
manaco/
├── database/
│   ├── 01_schema.sql            tablas, claves, índices y triggers del esquema manaco
│   └── 02_datos_iniciales.sql   permisos, roles, sucursales, categorías y cajas
├── backend/
│   ├── app/
│   │   ├── main.py              aplicación FastAPI y manejo de errores
│   │   ├── config.py, db.py     variables de entorno y conexión
│   │   ├── security.py          JWT, contraseñas, permisos y sucursal
│   │   ├── audit.py             bitácora
│   │   ├── routers/             endpoints por módulo
│   │   └── services/            inventario, KPIs/reportes, pronósticos, importador
│   ├── scripts/init_db.py       crea el esquema y el administrador
│   ├── scripts/cargar_demo.py   datos de demostración
│   └── tests/prueba_flujos.py   prueba de humo de la API
└── frontend/
    └── src/app/
        ├── core/                API, sesión, interceptor, guards, menú
        ├── shared/              gráficos SVG, modal y formatos (Bs, %, fechas)
        ├── layout/              barra lateral según permisos
        └── pages/               una pantalla por módulo
```

## 9. Problemas frecuentes

| Problema | Solución |
|---|---|
| `No se pudo conectar con la base de datos` | Revisa `backend/.env` y que el servidor PostgreSQL acepte conexiones desde tu red (puerto 5432). |
| `permission denied for database` al ejecutar `init_db` | El usuario de la base necesita permiso para crear esquemas: `GRANT CREATE ON DATABASE dev_db TO dev;` |
| El frontend dice “No se pudo conectar con la API” | Inicia el backend (`uvicorn app.main:app --reload`) y revisa `apiUrl` en `environment.ts`. |
| Error de CORS en el navegador | Agrega la dirección del frontend en `CORS_ORIGINS` del `.env` y reinicia la API. |
| `npm install` falla | Usa Node 20 LTS (`node -v`). |
