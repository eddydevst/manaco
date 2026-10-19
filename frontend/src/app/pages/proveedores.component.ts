import { Component, OnInit, inject } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ApiService } from '../core/api.service';
import { AuthService } from '../core/auth.service';
import { ESTADO_OC } from '../core/nav';
import { ToastService } from '../core/toast.service';
import { ModalComponent } from '../shared/graficos';
import { PIPES } from '../shared/pipes';

@Component({
  selector: 'app-proveedores',
  standalone: true,
  imports: [FormsModule, ModalComponent, ...PIPES],
  template: `
    <header class="ph">
      <div><div class="ph-t"><h1>Proveedores</h1></div><p>Datos comerciales, productos suministrados e historial de compras de cada proveedor.</p></div>
      @if (puedeEditar) { <div class="ph-a"><button class="btn btn-p" type="button" (click)="editar(null)">Nuevo proveedor</button></div> }
    </header>
    <section class="card"><div class="tw"><table class="t">
      <thead><tr><th>Código</th><th>Razón social</th><th>NIT</th><th>Contacto</th><th>País</th><th class="num">Órdenes</th><th class="num">Comprado</th><th class="num">A tiempo</th><th>Estado</th><th></th></tr></thead>
      <tbody>@for (p of lista; track p.id_proveedor) {
        <tr><td class="mono">{{ p.codigo }}</td><td class="b">{{ p.razon_social }}</td><td class="mono sm">{{ p.nit || '—' }}</td>
          <td class="sm">{{ p.contacto }}<br><span class="muted">{{ p.telefono }}</span></td><td>{{ p.pais }}</td><td class="num">{{ p.ordenes }}</td>
          <td class="num">{{ p.monto_comprado | bsc }}</td><td class="num">{{ p.a_tiempo | pct }}</td>
          <td><span class="badge {{ p.estado === 'ACTIVO' ? 'b-ok' : 'b-mut' }}">{{ p.estado === 'ACTIVO' ? 'Activo' : 'Inactivo' }}</span></td>
          <td style="white-space:nowrap"><button class="btn btn-sm" type="button" (click)="ver(p.id_proveedor)">Ver</button>
            @if (puedeEditar) { <button class="btn btn-sm" type="button" (click)="editar(p)">Editar</button> }</td></tr>
      }</tbody></table></div></section>

    @if (modal === 'form') {
      <app-modal [titulo]="form.id_proveedor ? 'Editar proveedor' : 'Nuevo proveedor'" (cerrar)="modal = null">
        <form class="form-grid" (ngSubmit)="guardar()">
          @for (c of campos; track c[0]) {
            <label class="field" [for]="'pf-' + c[0]"><span>{{ c[1] }}</span><input [id]="'pf-' + c[0]" [name]="c[0]" [(ngModel)]="form[c[0]]" [required]="c[0] === 'codigo' || c[0] === 'razon_social'"></label>
          }
          <label class="field" for="pf-e"><span>Estado</span><select id="pf-e" name="estado" [(ngModel)]="form.estado"><option value="ACTIVO">Activo</option><option value="INACTIVO">Inactivo</option></select></label>
          <div class="modal-f full"><button type="button" class="btn" (click)="modal = null">Cancelar</button><button class="btn btn-p" type="submit">Guardar</button></div>
        </form>
      </app-modal>
    }

    @if (modal === 'ver' && d) {
      <app-modal [titulo]="d.razon_social" [ancho]="true" (cerrar)="modal = null">
        <p class="muted">{{ d.codigo }} · NIT {{ d.nit || '—' }} · {{ d.pais }} · {{ d.contacto }} · {{ d.telefono }} · {{ d.correo }}</p>
        <div class="kpis">
          <div class="kpi"><span class="l">Órdenes</span><span class="v">{{ d.ordenes.length }}</span></div>
          <div class="kpi"><span class="l">Recibidas a tiempo</span><span class="v">{{ (d.cumplimiento?.cerradas ? d.cumplimiento.a_tiempo / d.cumplimiento.cerradas : null) | pct }}</span></div>
          <div class="kpi"><span class="l">Cantidad entregada</span><span class="v">{{ (d.cumplimiento?.pedido ? d.cumplimiento.recibido / d.cumplimiento.pedido : null) | pct }}</span><span class="d">recibido ÷ pedido</span></div>
        </div>
        <h3>Productos suministrados</h3>
        <div class="tw"><table class="t"><thead><tr><th>Código proveedor</th><th>Producto</th><th class="num">Costo ref.</th></tr></thead>
          <tbody>@for (x of d.productos; track x.id_producto) { <tr><td class="mono">{{ x.codigo_proveedor }}</td><td>{{ x.modelo }}</td><td class="num">{{ x.costo_referencia | bs }}</td></tr> }
          @empty { <tr><td colspan="3" class="muted">Sin productos asociados</td></tr> }</tbody></table></div>
        @if (puedeEditar) {
          <form class="filters" (ngSubmit)="asociar()">
            <label class="field w2" for="ap-p"><span>Asociar producto</span><select id="ap-p" name="prod" [(ngModel)]="asoc.id_producto">
              @for (p of productos; track p.id_producto) { <option [ngValue]="p.id_producto">{{ p.modelo }} ({{ p.categoria }})</option> }</select></label>
            <label class="field" for="ap-c"><span>Costo (Bs)</span><input id="ap-c" name="costo" type="number" min="0" step="0.01" [(ngModel)]="asoc.costo_referencia"></label>
            <button class="btn" type="submit">Asociar</button></form>
        }
        <h3>Historial de compras</h3>
        <div class="tw"><table class="t"><thead><tr><th>Orden</th><th>Fecha</th><th>Entrega</th><th class="num">Total</th><th>Estado</th></tr></thead>
          <tbody>@for (o of d.ordenes; track o.id_orden) {
            <tr><td class="mono">{{ o.numero }}</td><td>{{ o.fecha | fecha }}</td><td>{{ o.fecha_entrega | fecha }}</td><td class="num">{{ o.total | bs }}</td>
              <td><span class="badge {{ eo(o.estado)[1] }}">{{ eo(o.estado)[0] }}</span></td></tr>
          } @empty { <tr><td colspan="5" class="muted">Sin órdenes</td></tr> }</tbody></table></div>
      </app-modal>
    }`,
})
export class ProveedoresComponent implements OnInit {
  private api = inject(ApiService);
  private toast = inject(ToastService);
  auth = inject(AuthService);
  puedeEditar = false;
  lista: any[] = [];
  productos: any[] = [];
  modal: string | null = null;
  form: any = {};
  d: any = null;
  asoc: any = {};
  campos = [['codigo', 'Código'], ['razon_social', 'Razón social'], ['nit', 'NIT'], ['contacto', 'Contacto'], ['telefono', 'Teléfono'], ['correo', 'Correo'], ['pais', 'País']];

  async ngOnInit() {
    this.puedeEditar = this.auth.puede('proveedores.editar');
    this.cargar();
    if (this.puedeEditar && this.auth.puede('productos.ver')) this.productos = await this.api.get('/api/productos');
  }
  async cargar() { this.lista = await this.api.get('/api/proveedores'); }
  eo(e: string) { return ESTADO_OC[e] || [e, 'b-mut']; }

  editar(p: any) {
    this.form = p ? { ...p } : { codigo: 'PRV' + String(this.lista.length + 1).padStart(2, '0'), razon_social: '', nit: '', contacto: '', telefono: '', correo: '', pais: 'Bolivia', estado: 'ACTIVO' };
    this.modal = 'form';
  }

  async guardar() {
    const datos = { codigo: this.form.codigo, razon_social: this.form.razon_social, nit: this.form.nit, contacto: this.form.contacto,
                    telefono: this.form.telefono, correo: this.form.correo, pais: this.form.pais, estado: this.form.estado };
    try {
      if (this.form.id_proveedor) await this.api.put(`/api/proveedores/${this.form.id_proveedor}`, datos);
      else await this.api.post('/api/proveedores', datos);
      this.toast.ok('Proveedor guardado.');
      this.modal = null;
      this.cargar();
    } catch {}
  }

  async ver(id: number) {
    this.d = await this.api.get(`/api/proveedores/${id}`);
    this.asoc = { id_producto: this.productos[0]?.id_producto, costo_referencia: null };
    this.modal = 'ver';
  }

  async asociar() {
    try {
      await this.api.post(`/api/proveedores/${this.d.id_proveedor}/productos`, { id_producto: this.asoc.id_producto, costo_referencia: this.asoc.costo_referencia ? +this.asoc.costo_referencia : null });
      this.toast.ok('Producto asociado al proveedor.');
      this.ver(this.d.id_proveedor);
      this.cargar();
    } catch {}
  }
}
