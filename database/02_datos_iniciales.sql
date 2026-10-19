-- =====================================================================
-- Datos iniciales: permisos, roles, sucursales, categorías y cajas.
-- El usuario administrador se crea con:  python -m scripts.init_db
-- (así la contraseña se guarda cifrada con bcrypt).
-- =====================================================================
SET search_path TO manaco;

INSERT INTO permisos (codigo, recurso, accion, descripcion) VALUES
 ('panel.ver',          'Panel gerencial',   'ver',       'Ver indicadores'),
 ('reportes.ver',       'Reportes',          'ver',       'Ver y exportar reportes'),
 ('pronosticos.ver',    'Pronósticos',       'ver',       'Ver y guardar pronósticos'),
 ('comex.ver',          'Comercio exterior', 'ver',       'Ver e importar datos externos'),
 ('pos.vender',         'Punto de Venta',    'vender',    'Registrar ventas'),
 ('pos.devolver',       'Punto de Venta',    'devolver',  'Registrar devoluciones'),
 ('caja.operar',        'Caja',              'operar',    'Abrir, mover y cerrar caja'),
 ('inventario.ver',     'Inventario',        'ver',       'Ver existencias y kardex'),
 ('inventario.ajustar', 'Inventario',        'ajustar',   'Ajustes, transferencias y mínimos'),
 ('compras.ver',        'Compras',           'ver',       'Ver órdenes de compra'),
 ('compras.crear',      'Compras',           'crear',     'Crear órdenes de compra'),
 ('compras.aprobar',    'Compras',           'aprobar',   'Aprobar o rechazar órdenes'),
 ('compras.recibir',    'Compras',           'recibir',   'Registrar recepciones'),
 ('productos.ver',      'Productos',         'ver',       'Ver catálogo'),
 ('productos.editar',   'Productos',         'editar',    'Crear y editar productos'),
 ('importador.usar',    'Importador',        'usar',      'Importar planillas de productos'),
 ('proveedores.ver',    'Proveedores',       'ver',       'Ver proveedores'),
 ('proveedores.editar', 'Proveedores',       'editar',    'Crear y editar proveedores'),
 ('socios.editar',      'Socios comerciales','editar',    'Ver y editar socios'),
 ('usuarios.admin',     'Usuarios y roles',  'administrar','Administrar usuarios, roles y permisos'),
 ('bitacora.ver',       'Bitácora',          'ver',       'Consultar la bitácora')
ON CONFLICT (codigo) DO NOTHING;

INSERT INTO roles (nombre, descripcion, es_sistema) VALUES
 ('Administrador',        'Acceso total al sistema', TRUE),
 ('Gerente comercial',    'Indicadores, reportes, pronósticos y aprobación de compras', FALSE),
 ('Cajero',               'Ventas, devoluciones y caja de su sucursal', FALSE),
 ('Encargado de almacén', 'Inventario, compras, catálogo e importación', FALSE)
ON CONFLICT (nombre) DO NOTHING;

-- Administrador: todos los permisos
INSERT INTO roles_permisos (id_rol, id_permiso)
SELECT r.id_rol, p.id_permiso FROM roles r CROSS JOIN permisos p WHERE r.nombre = 'Administrador'
ON CONFLICT DO NOTHING;

INSERT INTO roles_permisos (id_rol, id_permiso)
SELECT r.id_rol, p.id_permiso FROM roles r JOIN permisos p ON p.codigo IN
 ('panel.ver','reportes.ver','pronosticos.ver','comex.ver','inventario.ver','compras.ver','compras.aprobar',
  'productos.ver','proveedores.ver','socios.editar','bitacora.ver')
WHERE r.nombre = 'Gerente comercial'
ON CONFLICT DO NOTHING;

INSERT INTO roles_permisos (id_rol, id_permiso)
SELECT r.id_rol, p.id_permiso FROM roles r JOIN permisos p ON p.codigo IN
 ('pos.vender','pos.devolver','caja.operar','inventario.ver','productos.ver')
WHERE r.nombre = 'Cajero'
ON CONFLICT DO NOTHING;

INSERT INTO roles_permisos (id_rol, id_permiso)
SELECT r.id_rol, p.id_permiso FROM roles r JOIN permisos p ON p.codigo IN
 ('inventario.ver','inventario.ajustar','compras.ver','compras.crear','compras.recibir','productos.ver',
  'productos.editar','importador.usar','proveedores.ver','proveedores.editar')
WHERE r.nombre = 'Encargado de almacén'
ON CONFLICT DO NOTHING;

INSERT INTO sucursales (codigo, nombre, ubicacion) VALUES
 ('SCZ01', 'Santa Cruz – Centro',     'Santa Cruz'),
 ('LPZ01', 'La Paz – Prado',          'La Paz'),
 ('CBB01', 'Cochabamba – Planta',     'Cochabamba'),
 ('EAL01', 'El Alto – 16 de Julio',   'El Alto'),
 ('SUC01', 'Sucre – Centro',          'Sucre')
ON CONFLICT (codigo) DO NOTHING;

INSERT INTO cajas (id_sucursal, nombre)
SELECT id_sucursal, 'Caja 01' FROM sucursales
ON CONFLICT DO NOTHING;

INSERT INTO categorias (codigo, nombre) VALUES
 ('ESC', 'Escolar'),
 ('VCA', 'Vestir caballero'),
 ('VDA', 'Vestir dama'),
 ('DEP', 'Deportivo'),
 ('CAS', 'Casual'),
 ('SEG', 'Seguridad industrial'),
 ('INF', 'Infantil')
ON CONFLICT (codigo) DO NOTHING;
