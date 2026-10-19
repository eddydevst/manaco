/** Menú lateral: cada opción se muestra solo si el usuario tiene el permiso. */
export interface ItemMenu {
  ruta: string;
  etiqueta: string;
  permiso: string;
}

export const MENU: { grupo: string; items: ItemMenu[] }[] = [
  {
    grupo: 'Inteligencia',
    items: [
      { ruta: 'panel', etiqueta: 'Panel gerencial', permiso: 'panel.ver' },
      { ruta: 'reportes', etiqueta: 'Reportes', permiso: 'reportes.ver' },
      { ruta: 'pronosticos', etiqueta: 'Pronósticos de demanda', permiso: 'pronosticos.ver' },
      { ruta: 'comercio-exterior', etiqueta: 'Comercio exterior', permiso: 'comex.ver' },
    ],
  },
  {
    grupo: 'Operación',
    items: [
      { ruta: 'punto-de-venta', etiqueta: 'Punto de Venta', permiso: 'pos.vender' },
      { ruta: 'inventario', etiqueta: 'Inventario', permiso: 'inventario.ver' },
      { ruta: 'compras', etiqueta: 'Compras', permiso: 'compras.ver' },
      { ruta: 'productos', etiqueta: 'Productos', permiso: 'productos.ver' },
      { ruta: 'importador', etiqueta: 'Importador', permiso: 'importador.usar' },
    ],
  },
  {
    grupo: 'Relaciones',
    items: [
      { ruta: 'proveedores', etiqueta: 'Proveedores', permiso: 'proveedores.ver' },
      { ruta: 'socios', etiqueta: 'Socios comerciales', permiso: 'socios.editar' },
    ],
  },
  {
    grupo: 'Administración',
    items: [
      { ruta: 'usuarios', etiqueta: 'Usuarios y roles', permiso: 'usuarios.admin' },
      { ruta: 'bitacora', etiqueta: 'Bitácora', permiso: 'bitacora.ver' },
    ],
  },
];

export const ESTADO_INV: Record<string, [string, string]> = {
  AGOTADO: ['Agotado', 'b-bad'],
  BAJO_MINIMO: ['Bajo mínimo', 'b-warn'],
  BAJA_ROTACION: ['Baja rotación', 'b-info'],
  SOBRESTOCK: ['Sobrestock', 'b-pur'],
  NORMAL: ['Normal', 'b-ok'],
};

export const ESTADO_OC: Record<string, [string, string]> = {
  PENDIENTE_APROBACION: ['Por aprobar', 'b-warn'],
  APROBADA: ['Aprobada', 'b-info'],
  RECHAZADA: ['Rechazada', 'b-bad'],
  RECIBIDA_PARCIAL: ['Recepción parcial', 'b-pur'],
  RECIBIDA: ['Recibida', 'b-ok'],
};

export const ESTADO_VENTA: Record<string, [string, string]> = {
  COMPLETADA: ['Completada', 'b-ok'],
  DEVOLUCION_PARCIAL: ['Dev. parcial', 'b-warn'],
  DEVUELTA: ['Devuelta', 'b-bad'],
  ANULADA: ['Anulada', 'b-mut'],
};

export const TIPOS_MOV: Record<string, string> = {
  SALDO_INICIAL: 'Saldo inicial',
  SALIDA_VENTA: 'Venta',
  DEVOLUCION: 'Devolución',
  ENTRADA_COMPRA: 'Recepción de compra',
  ENTRADA_AJUSTE: 'Ajuste (entrada)',
  SALIDA_AJUSTE: 'Ajuste (salida)',
  TRANSF_SALIDA: 'Transferencia (salida)',
  TRANSF_ENTRADA: 'Transferencia (entrada)',
  ENTRADA_IMPORTACION: 'Stock inicial importado',
};

export const MESES = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic'];
