import { Routes } from '@angular/router';
import { authGuard, inicioGuard, permisoGuard } from './core/guards';
import { ShellComponent, SinAccesoComponent } from './layout/shell.component';
import { LoginComponent } from './pages/login.component';
import { PanelComponent } from './pages/panel.component';
import { PosComponent } from './pages/pos.component';
import { InventarioComponent } from './pages/inventario.component';
import { ComprasComponent } from './pages/compras.component';
import { ProductosComponent } from './pages/productos.component';
import { ImportadorComponent } from './pages/importador.component';
import { ProveedoresComponent } from './pages/proveedores.component';
import { SociosComponent } from './pages/socios.component';
import { ReportesComponent } from './pages/reportes.component';
import { PronosticosComponent } from './pages/pronosticos.component';
import { ComexComponent } from './pages/comex.component';
import { UsuariosComponent } from './pages/usuarios.component';
import { BitacoraComponent } from './pages/bitacora.component';

const p = (permiso: string) => ({ canActivate: [permisoGuard], data: { permiso } });

export const routes: Routes = [
  { path: 'login', component: LoginComponent },
  {
    path: '',
    component: ShellComponent,
    canActivate: [authGuard],
    children: [
      { path: '', pathMatch: 'full', canActivate: [inicioGuard], children: [] },
      { path: 'panel', component: PanelComponent, ...p('panel.ver') },
      { path: 'reportes', component: ReportesComponent, ...p('reportes.ver') },
      { path: 'pronosticos', component: PronosticosComponent, ...p('pronosticos.ver') },
      { path: 'comercio-exterior', component: ComexComponent, ...p('comex.ver') },
      { path: 'punto-de-venta', component: PosComponent, ...p('pos.vender') },
      { path: 'inventario', component: InventarioComponent, ...p('inventario.ver') },
      { path: 'compras', component: ComprasComponent, ...p('compras.ver') },
      { path: 'productos', component: ProductosComponent, ...p('productos.ver') },
      { path: 'importador', component: ImportadorComponent, ...p('importador.usar') },
      { path: 'proveedores', component: ProveedoresComponent, ...p('proveedores.ver') },
      { path: 'socios', component: SociosComponent, ...p('socios.editar') },
      { path: 'usuarios', component: UsuariosComponent, ...p('usuarios.admin') },
      { path: 'bitacora', component: BitacoraComponent, ...p('bitacora.ver') },
      { path: 'sin-acceso', component: SinAccesoComponent },
    ],
  },
  { path: '**', redirectTo: '' },
];
