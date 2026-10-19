-- =====================================================================
-- MANACO · Sistema Integral de Gestión Comercial e Inteligencia de Negocios
-- Esquema físico PostgreSQL. Todas las tablas viven en el esquema "manaco".
-- Ejecutar con un usuario con permiso para crear esquemas:
--     psql -h HOST -U USUARIO -d BASE -f 01_schema.sql
-- =====================================================================

CREATE SCHEMA IF NOT EXISTS manaco;
SET search_path TO manaco;

-- ---------------------------------------------------------------------
-- Organización y seguridad
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS sucursales (
    id_sucursal   SERIAL PRIMARY KEY,
    codigo        VARCHAR(10)  NOT NULL UNIQUE,
    nombre        VARCHAR(120) NOT NULL,
    ubicacion     VARCHAR(200),
    estado        VARCHAR(10)  NOT NULL DEFAULT 'ACTIVA' CHECK (estado IN ('ACTIVA','INACTIVA'))
);

CREATE TABLE IF NOT EXISTS roles (
    id_rol        SERIAL PRIMARY KEY,
    nombre        VARCHAR(60)  NOT NULL UNIQUE,
    descripcion   VARCHAR(250),
    es_sistema    BOOLEAN      NOT NULL DEFAULT FALSE   -- el rol Administrador no se puede editar
);

CREATE TABLE IF NOT EXISTS permisos (
    id_permiso    SERIAL PRIMARY KEY,
    codigo        VARCHAR(60)  NOT NULL UNIQUE,         -- ej.: ventas.registrar
    recurso       VARCHAR(60)  NOT NULL,
    accion        VARCHAR(60)  NOT NULL,
    descripcion   VARCHAR(200)
);

CREATE TABLE IF NOT EXISTS usuarios (
    id_usuario    SERIAL PRIMARY KEY,
    nombre        VARCHAR(120) NOT NULL,
    correo        VARCHAR(160) NOT NULL UNIQUE,
    password_hash VARCHAR(200) NOT NULL,
    estado        VARCHAR(10)  NOT NULL DEFAULT 'ACTIVO' CHECK (estado IN ('ACTIVO','INACTIVO')),
    id_sucursal   INTEGER REFERENCES sucursales(id_sucursal),   -- NULL = acceso a todas
    creado_en     TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS usuarios_roles (
    id_usuario    INTEGER NOT NULL REFERENCES usuarios(id_usuario) ON DELETE CASCADE,
    id_rol        INTEGER NOT NULL REFERENCES roles(id_rol) ON DELETE RESTRICT,
    PRIMARY KEY (id_usuario, id_rol)
);

CREATE TABLE IF NOT EXISTS roles_permisos (
    id_rol        INTEGER NOT NULL REFERENCES roles(id_rol) ON DELETE CASCADE,
    id_permiso    INTEGER NOT NULL REFERENCES permisos(id_permiso) ON DELETE CASCADE,
    PRIMARY KEY (id_rol, id_permiso)
);

CREATE TABLE IF NOT EXISTS bitacora (
    id_bitacora       BIGSERIAL PRIMARY KEY,
    id_usuario        INTEGER REFERENCES usuarios(id_usuario),
    accion            VARCHAR(60)  NOT NULL,
    entidad           VARCHAR(60)  NOT NULL,
    id_entidad        VARCHAR(60),
    fecha             TIMESTAMPTZ  NOT NULL DEFAULT now(),
    datos_anteriores  JSONB,
    datos_nuevos      JSONB,
    ip                VARCHAR(60)
);
CREATE INDEX IF NOT EXISTS ix_bitacora_fecha   ON bitacora (fecha DESC);
CREATE INDEX IF NOT EXISTS ix_bitacora_entidad ON bitacora (entidad, fecha DESC);
CREATE INDEX IF NOT EXISTS ix_bitacora_usuario ON bitacora (id_usuario, fecha DESC);

-- ---------------------------------------------------------------------
-- Catálogo de productos
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS categorias (
    id_categoria  SERIAL PRIMARY KEY,
    codigo        VARCHAR(6)   NOT NULL UNIQUE,
    nombre        VARCHAR(80)  NOT NULL UNIQUE,
    descripcion   VARCHAR(250)
);

CREATE TABLE IF NOT EXISTS productos (
    id_producto   SERIAL PRIMARY KEY,
    id_categoria  INTEGER NOT NULL REFERENCES categorias(id_categoria),
    marca         VARCHAR(80)  NOT NULL,
    modelo        VARCHAR(120) NOT NULL,
    descripcion   TEXT,
    estado        VARCHAR(10)  NOT NULL DEFAULT 'ACTIVO' CHECK (estado IN ('ACTIVO','INACTIVO')),
    UNIQUE (id_categoria, marca, modelo)
);

CREATE TABLE IF NOT EXISTS variantes_producto (
    id_variante       SERIAL PRIMARY KEY,
    id_producto       INTEGER NOT NULL REFERENCES productos(id_producto) ON DELETE CASCADE,
    talla             VARCHAR(10)  NOT NULL,
    color             VARCHAR(40)  NOT NULL,
    sku               VARCHAR(40)  NOT NULL UNIQUE,
    precio_venta      NUMERIC(12,2) NOT NULL CHECK (precio_venta > 0),
    costo_referencia  NUMERIC(12,2) NOT NULL CHECK (costo_referencia >= 0),
    estado            VARCHAR(10)  NOT NULL DEFAULT 'ACTIVO' CHECK (estado IN ('ACTIVO','INACTIVO')),
    UNIQUE (id_producto, talla, color)
);
CREATE INDEX IF NOT EXISTS ix_variantes_producto ON variantes_producto (id_producto);

-- ---------------------------------------------------------------------
-- Proveedores y socios
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS proveedores (
    id_proveedor  SERIAL PRIMARY KEY,
    codigo        VARCHAR(10)  NOT NULL UNIQUE,
    razon_social  VARCHAR(160) NOT NULL,
    nit           VARCHAR(30),
    contacto      VARCHAR(120),
    telefono      VARCHAR(40),
    correo        VARCHAR(160),
    pais          VARCHAR(60),
    estado        VARCHAR(10)  NOT NULL DEFAULT 'ACTIVO' CHECK (estado IN ('ACTIVO','INACTIVO'))
);

CREATE TABLE IF NOT EXISTS productos_proveedores (
    id_producto       INTEGER NOT NULL REFERENCES productos(id_producto) ON DELETE CASCADE,
    id_proveedor      INTEGER NOT NULL REFERENCES proveedores(id_proveedor),
    codigo_proveedor  VARCHAR(40),
    costo_referencia  NUMERIC(12,2) CHECK (costo_referencia >= 0),
    PRIMARY KEY (id_producto, id_proveedor)
);

CREATE TABLE IF NOT EXISTS socios_comerciales (
    id_socio       SERIAL PRIMARY KEY,
    nombre         VARCHAR(160) NOT NULL,
    pais           VARCHAR(60)  NOT NULL,
    tipo_relacion  VARCHAR(40)  NOT NULL,
    descripcion    TEXT,
    estado         VARCHAR(10)  NOT NULL DEFAULT 'ACTIVO' CHECK (estado IN ('ACTIVO','INACTIVO'))
);

-- ---------------------------------------------------------------------
-- Compras
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ordenes_compra (
    id_orden       SERIAL PRIMARY KEY,
    numero         VARCHAR(20)  NOT NULL UNIQUE,
    id_proveedor   INTEGER NOT NULL REFERENCES proveedores(id_proveedor),
    id_sucursal    INTEGER NOT NULL REFERENCES sucursales(id_sucursal),   -- sucursal de destino
    id_usuario     INTEGER NOT NULL REFERENCES usuarios(id_usuario),
    fecha          TIMESTAMPTZ  NOT NULL DEFAULT now(),
    fecha_entrega  DATE         NOT NULL,
    estado         VARCHAR(25)  NOT NULL DEFAULT 'PENDIENTE_APROBACION'
                   CHECK (estado IN ('PENDIENTE_APROBACION','APROBADA','RECHAZADA','RECIBIDA_PARCIAL','RECIBIDA')),
    total          NUMERIC(14,2) NOT NULL DEFAULT 0,
    observacion    TEXT
);
CREATE INDEX IF NOT EXISTS ix_ordenes_estado    ON ordenes_compra (estado);
CREATE INDEX IF NOT EXISTS ix_ordenes_proveedor ON ordenes_compra (id_proveedor, fecha);

CREATE TABLE IF NOT EXISTS detalle_orden_compra (
    id_detalle         SERIAL PRIMARY KEY,
    id_orden           INTEGER NOT NULL REFERENCES ordenes_compra(id_orden) ON DELETE CASCADE,
    id_variante        INTEGER NOT NULL REFERENCES variantes_producto(id_variante),
    cantidad           INTEGER NOT NULL CHECK (cantidad > 0),
    costo_unitario     NUMERIC(12,2) NOT NULL CHECK (costo_unitario >= 0),
    cantidad_recibida  INTEGER NOT NULL DEFAULT 0,
    CHECK (cantidad_recibida BETWEEN 0 AND cantidad),
    UNIQUE (id_orden, id_variante)
);

CREATE TABLE IF NOT EXISTS aprobaciones_compra (
    id_aprobacion  SERIAL PRIMARY KEY,
    id_orden       INTEGER NOT NULL REFERENCES ordenes_compra(id_orden) ON DELETE CASCADE,
    id_usuario     INTEGER NOT NULL REFERENCES usuarios(id_usuario),
    decision       VARCHAR(10) NOT NULL CHECK (decision IN ('APROBADA','RECHAZADA')),
    fecha          TIMESTAMPTZ NOT NULL DEFAULT now(),
    observacion    TEXT
);

CREATE TABLE IF NOT EXISTS recepciones_compra (
    id_recepcion   SERIAL PRIMARY KEY,
    id_orden       INTEGER NOT NULL REFERENCES ordenes_compra(id_orden) ON DELETE CASCADE,
    id_usuario     INTEGER NOT NULL REFERENCES usuarios(id_usuario),
    fecha          TIMESTAMPTZ NOT NULL DEFAULT now(),
    estado         VARCHAR(10) NOT NULL DEFAULT 'PARCIAL' CHECK (estado IN ('PARCIAL','TOTAL'))
);

CREATE TABLE IF NOT EXISTS detalle_recepcion (
    id_detalle         SERIAL PRIMARY KEY,
    id_recepcion       INTEGER NOT NULL REFERENCES recepciones_compra(id_recepcion) ON DELETE CASCADE,
    id_detalle_orden   INTEGER NOT NULL REFERENCES detalle_orden_compra(id_detalle),
    id_variante        INTEGER NOT NULL REFERENCES variantes_producto(id_variante),
    cantidad_recibida  INTEGER NOT NULL CHECK (cantidad_recibida > 0)
);

-- ---------------------------------------------------------------------
-- Inventario
-- El stock SOLO cambia insertando en movimientos_inventario:
-- el trigger fn_aplicar_movimiento actualiza inventario.stock_actual.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS inventario (
    id_inventario  SERIAL PRIMARY KEY,
    id_sucursal    INTEGER NOT NULL REFERENCES sucursales(id_sucursal),
    id_variante    INTEGER NOT NULL REFERENCES variantes_producto(id_variante) ON DELETE CASCADE,
    stock_actual   INTEGER NOT NULL DEFAULT 0 CHECK (stock_actual >= 0),
    stock_minimo   INTEGER NOT NULL DEFAULT 0 CHECK (stock_minimo >= 0),
    UNIQUE (id_sucursal, id_variante)
);
CREATE INDEX IF NOT EXISTS ix_inventario_variante ON inventario (id_variante);

CREATE TABLE IF NOT EXISTS movimientos_inventario (
    id_movimiento  BIGSERIAL PRIMARY KEY,
    id_sucursal    INTEGER NOT NULL REFERENCES sucursales(id_sucursal),
    id_variante    INTEGER NOT NULL REFERENCES variantes_producto(id_variante),
    tipo           VARCHAR(25) NOT NULL CHECK (tipo IN (
                     'SALDO_INICIAL','ENTRADA_COMPRA','SALIDA_VENTA','DEVOLUCION',
                     'ENTRADA_AJUSTE','SALIDA_AJUSTE','TRANSF_SALIDA','TRANSF_ENTRADA','ENTRADA_IMPORTACION')),
    cantidad       INTEGER NOT NULL CHECK (cantidad <> 0),   -- positivo = entrada, negativo = salida
    fecha          TIMESTAMPTZ NOT NULL DEFAULT now(),
    referencia     VARCHAR(120),
    id_usuario     INTEGER REFERENCES usuarios(id_usuario)
);
CREATE INDEX IF NOT EXISTS ix_mov_suc_var_fecha ON movimientos_inventario (id_sucursal, id_variante, fecha);
CREATE INDEX IF NOT EXISTS ix_mov_fecha         ON movimientos_inventario (fecha DESC);

CREATE OR REPLACE FUNCTION fn_aplicar_movimiento() RETURNS trigger AS $$
BEGIN
    INSERT INTO manaco.inventario (id_sucursal, id_variante, stock_actual)
    VALUES (NEW.id_sucursal, NEW.id_variante, 0)
    ON CONFLICT (id_sucursal, id_variante) DO NOTHING;

    UPDATE manaco.inventario
       SET stock_actual = stock_actual + NEW.cantidad
     WHERE id_sucursal = NEW.id_sucursal AND id_variante = NEW.id_variante;
    -- Si el stock queda negativo, el CHECK de inventario aborta la transacción.
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS tg_aplicar_movimiento ON movimientos_inventario;
CREATE TRIGGER tg_aplicar_movimiento
AFTER INSERT ON movimientos_inventario
FOR EACH ROW EXECUTE FUNCTION fn_aplicar_movimiento();

-- Los movimientos son un registro histórico: no se editan ni se borran.
CREATE OR REPLACE FUNCTION fn_movimiento_inmutable() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'Los movimientos de inventario no se pueden modificar ni eliminar; registre un ajuste.';
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS tg_movimiento_inmutable ON movimientos_inventario;
CREATE TRIGGER tg_movimiento_inmutable
BEFORE UPDATE OR DELETE ON movimientos_inventario
FOR EACH ROW EXECUTE FUNCTION fn_movimiento_inmutable();

-- ---------------------------------------------------------------------
-- Punto de venta y caja
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS clientes (
    id_cliente      SERIAL PRIMARY KEY,
    nombre          VARCHAR(160) NOT NULL,
    documento       VARCHAR(30),
    contacto        VARCHAR(160),
    fecha_registro  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS cajas (
    id_caja      SERIAL PRIMARY KEY,
    id_sucursal  INTEGER NOT NULL REFERENCES sucursales(id_sucursal),
    nombre       VARCHAR(40) NOT NULL,
    estado       VARCHAR(10) NOT NULL DEFAULT 'CERRADA' CHECK (estado IN ('ABIERTA','CERRADA')),
    UNIQUE (id_sucursal, nombre)
);

CREATE TABLE IF NOT EXISTS sesiones_caja (
    id_sesion       SERIAL PRIMARY KEY,
    id_caja         INTEGER NOT NULL REFERENCES cajas(id_caja),
    id_usuario      INTEGER NOT NULL REFERENCES usuarios(id_usuario),
    apertura        TIMESTAMPTZ NOT NULL DEFAULT now(),
    cierre          TIMESTAMPTZ,
    saldo_inicial   NUMERIC(12,2) NOT NULL CHECK (saldo_inicial >= 0),
    saldo_esperado  NUMERIC(12,2),
    saldo_final     NUMERIC(12,2),
    estado          VARCHAR(10) NOT NULL DEFAULT 'ABIERTA' CHECK (estado IN ('ABIERTA','CERRADA'))
);
-- Una sola sesión abierta por caja
CREATE UNIQUE INDEX IF NOT EXISTS ux_sesion_abierta ON sesiones_caja (id_caja) WHERE estado = 'ABIERTA';

CREATE TABLE IF NOT EXISTS movimientos_caja (
    id_movimiento  SERIAL PRIMARY KEY,
    id_sesion      INTEGER NOT NULL REFERENCES sesiones_caja(id_sesion),
    tipo           VARCHAR(12) NOT NULL CHECK (tipo IN ('VENTA','DEVOLUCION','INGRESO','EGRESO')),
    metodo_pago    VARCHAR(12) NOT NULL DEFAULT 'EFECTIVO' CHECK (metodo_pago IN ('EFECTIVO','TARJETA','QR')),
    monto          NUMERIC(12,2) NOT NULL,          -- negativo para egresos y devoluciones
    concepto       VARCHAR(200),
    fecha          TIMESTAMPTZ NOT NULL DEFAULT now(),
    id_usuario     INTEGER REFERENCES usuarios(id_usuario)
);
CREATE INDEX IF NOT EXISTS ix_movcaja_sesion ON movimientos_caja (id_sesion);

CREATE TABLE IF NOT EXISTS ventas (
    id_venta         SERIAL PRIMARY KEY,
    numero           VARCHAR(20) NOT NULL UNIQUE,
    id_sucursal      INTEGER NOT NULL REFERENCES sucursales(id_sucursal),
    id_usuario       INTEGER NOT NULL REFERENCES usuarios(id_usuario),
    id_cliente       INTEGER REFERENCES clientes(id_cliente),
    id_sesion        INTEGER REFERENCES sesiones_caja(id_sesion),
    fecha            TIMESTAMPTZ NOT NULL DEFAULT now(),
    subtotal         NUMERIC(14,2) NOT NULL,
    descuento        NUMERIC(14,2) NOT NULL DEFAULT 0,
    total            NUMERIC(14,2) NOT NULL,
    estado           VARCHAR(20) NOT NULL DEFAULT 'COMPLETADA'
                     CHECK (estado IN ('COMPLETADA','DEVOLUCION_PARCIAL','DEVUELTA','ANULADA')),
    idempotency_key  VARCHAR(64) UNIQUE      -- evita ventas duplicadas por reintentos
);
CREATE INDEX IF NOT EXISTS ix_ventas_fecha     ON ventas (fecha);
CREATE INDEX IF NOT EXISTS ix_ventas_suc_fecha ON ventas (id_sucursal, fecha);

CREATE TABLE IF NOT EXISTS detalle_venta (
    id_detalle         SERIAL PRIMARY KEY,
    id_venta           INTEGER NOT NULL REFERENCES ventas(id_venta) ON DELETE CASCADE,
    id_variante        INTEGER NOT NULL REFERENCES variantes_producto(id_variante),
    cantidad           INTEGER NOT NULL CHECK (cantidad > 0),
    precio_unitario    NUMERIC(12,2) NOT NULL,
    costo_unitario     NUMERIC(12,2) NOT NULL,     -- costo histórico al momento de vender
    descuento          NUMERIC(12,2) NOT NULL DEFAULT 0,
    subtotal           NUMERIC(14,2) NOT NULL,
    cantidad_devuelta  INTEGER NOT NULL DEFAULT 0,
    CHECK (cantidad_devuelta BETWEEN 0 AND cantidad)
);
CREATE INDEX IF NOT EXISTS ix_detventa_venta    ON detalle_venta (id_venta);
CREATE INDEX IF NOT EXISTS ix_detventa_variante ON detalle_venta (id_variante);

CREATE TABLE IF NOT EXISTS pagos_venta (
    id_pago      SERIAL PRIMARY KEY,
    id_venta     INTEGER NOT NULL REFERENCES ventas(id_venta) ON DELETE CASCADE,
    metodo_pago  VARCHAR(12) NOT NULL CHECK (metodo_pago IN ('EFECTIVO','TARJETA','QR')),
    monto        NUMERIC(14,2) NOT NULL CHECK (monto > 0),
    fecha        TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_pagos_venta ON pagos_venta (id_venta);

CREATE TABLE IF NOT EXISTS devoluciones (
    id_devolucion  SERIAL PRIMARY KEY,
    id_venta       INTEGER NOT NULL REFERENCES ventas(id_venta),
    id_usuario     INTEGER NOT NULL REFERENCES usuarios(id_usuario),
    id_sesion      INTEGER REFERENCES sesiones_caja(id_sesion),
    fecha          TIMESTAMPTZ NOT NULL DEFAULT now(),
    motivo         VARCHAR(250) NOT NULL,
    monto          NUMERIC(14,2) NOT NULL
);

CREATE TABLE IF NOT EXISTS detalle_devolucion (
    id_detalle         SERIAL PRIMARY KEY,
    id_devolucion      INTEGER NOT NULL REFERENCES devoluciones(id_devolucion) ON DELETE CASCADE,
    id_detalle_venta   INTEGER NOT NULL REFERENCES detalle_venta(id_detalle),
    cantidad           INTEGER NOT NULL CHECK (cantidad > 0),
    monto              NUMERIC(14,2) NOT NULL
);

-- ---------------------------------------------------------------------
-- Importación masiva
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS importaciones_productos (
    id_importacion       SERIAL PRIMARY KEY,
    id_usuario           INTEGER NOT NULL REFERENCES usuarios(id_usuario),
    archivo              VARCHAR(200) NOT NULL,
    fecha                TIMESTAMPTZ NOT NULL DEFAULT now(),
    estado               VARCHAR(20) NOT NULL CHECK (estado IN ('COMPLETA','CON_OBSERVACIONES','FALLIDA')),
    registros_correctos  INTEGER NOT NULL DEFAULT 0,
    registros_error      INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS detalle_importacion (
    id_detalle      SERIAL PRIMARY KEY,
    id_importacion  INTEGER NOT NULL REFERENCES importaciones_productos(id_importacion) ON DELETE CASCADE,
    numero_fila     INTEGER NOT NULL,
    sku             VARCHAR(40),
    estado          VARCHAR(12) NOT NULL CHECK (estado IN ('NUEVO','ACTUALIZA','ERROR')),
    mensaje_error   TEXT
);

-- ---------------------------------------------------------------------
-- Información externa y analítica
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS datos_comercio_exterior (
    id_registro      SERIAL PRIMARY KEY,
    anio             INTEGER NOT NULL,
    flujo            VARCHAR(20) NOT NULL,          -- Importación / Exportación
    pais_reportante  VARCHAR(80),
    pais_socio       VARCHAR(80),
    categoria        VARCHAR(120),
    valor_comercial  NUMERIC(18,2),
    cantidad         NUMERIC(18,2),
    unidad           VARCHAR(30)
);
CREATE INDEX IF NOT EXISTS ix_comex_anio ON datos_comercio_exterior (anio, flujo);

CREATE TABLE IF NOT EXISTS pronosticos_demanda (
    id_pronostico      SERIAL PRIMARY KEY,
    nivel              VARCHAR(12) NOT NULL CHECK (nivel IN ('PRODUCTO','CATEGORIA','VARIANTE')),
    id_variante        INTEGER REFERENCES variantes_producto(id_variante),
    id_producto        INTEGER REFERENCES productos(id_producto),
    id_categoria       INTEGER REFERENCES categorias(id_categoria),
    id_sucursal        INTEGER REFERENCES sucursales(id_sucursal),   -- NULL = todas
    periodo            DATE NOT NULL,                                -- primer día del mes proyectado
    cantidad_estimada  NUMERIC(12,2) NOT NULL,
    modelo             VARCHAR(80) NOT NULL,
    mape               NUMERIC(8,4),
    fecha_generacion   TIMESTAMPTZ NOT NULL DEFAULT now(),
    id_usuario         INTEGER REFERENCES usuarios(id_usuario)
);
CREATE INDEX IF NOT EXISTS ix_pron_periodo ON pronosticos_demanda (periodo, nivel);
