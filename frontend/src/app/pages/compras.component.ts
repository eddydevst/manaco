import { Component, OnInit, inject } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute } from '@angular/router';
import { ApiService } from '../core/api.service';
import { AuthService } from '../core/auth.service';
import { ESTADO_OC } from '../core/nav';
import { ToastService } from '../core/toast.service';
import { ModalComponent } from '../shared/graficos';
import { PIPES } from '../shared/pipes';

/** Orden sugerida desde Pronósticos (se pasa entre pantallas). */
export const ordenSugerida: { datos: any } = { datos: null };

@Component({
  selector: 'app-compras',
  standalone: true,
  imports: [FormsModule, ModalComponent, ...PIPES],
  template: `
    <header class="ph">
      <div><div class="ph-t"><h1>Compras</h1></div><p>Orden de compra → aprobación → recepción (total o parcial) → ingreso al inventario.</p></div>
      @if (auth.puede('compras.crear')) { <div class="ph-a"><button class="btn btn-p" type="button" (click)="nueva()">Nueva orden de compra</button></div> }
    </header>

    @if (resumen) {
      <section class="kpis">
        <div class="kpi" [class.warn]="resumen.por_aprobar > 0"><span class="l">Por aprobar</span><span class="v">{{ resumen.por_aprobar | num }}</span></div>
        <div class="kpi info"><span class="l">Por recibir</span><span class="v">{{ resumen.por_recibir | num }}</span></div>
        <div class="kpi"><span class="l">Comprado este mes</span><span class="v">{{ resumen.monto_mes | bsc }}</span></div>
      </section>
    }

    <section class="card">
      <div class="chips" role="group" aria-label="Filtrar por estado">
        <button class="chip" type="button" [attr.aria-pressed]="!estado" (click)="estado = null; cargar()">Todas</button>
        @for (e of estados; track e[0]) { <button class="chip" type="button" [attr.aria-pressed]="estado === e[0]" (click)="estado = e[0]; cargar()">{{ e[1][0] }}</button> }
      </div>
      <div class="tw"><table class="t">
        <thead><tr><th>Orden</th><th>Fecha</th><th>Proveedor</th><th>Destino</th><th>Entrega</th><th class="num">Total</th><th class="num">Recibido</th><th>Estado</th><th></th></tr></thead>
        <tbody>
          @for (o of ordenes; track o.id_orden) {
            <tr><td class="mono b">{{ o.numero }}</td><td class="sm">{{ o.fecha | fecha }}</td><td>{{ o.proveedor }}</td><td class="muted">{{ o.sucursal }}</td>
              <td class="sm">{{ o.fecha_entrega | fecha }}</td><td class="num">{{ o.total | bs }}</td><td class="num">{{ o.pedido ? (o.recibido / o.pedido | pct) : '—' }}</td>
              <td><span class="badge {{ eo(o.estado)[1] }}">{{ eo(o.estado)[0] }}</span></td>
              <td><button class="btn btn-sm" type="button" (click)="ver(o.id_orden)">Ver</button></td></tr>
          } @empty { <tr><td colspan="9"><div class="empty">No hay órdenes con este estado.</div></td></tr> }
        </tbody></table></div>
    </section>

    @if (modal === 'nueva') {
      <app-modal titulo="Nueva orden de compra" [ancho]="true" (cerrar)="modal = null">
        <div class="form-grid">
          <label class="field" for="oc-p"><span>Proveedor</span>
            <select id="oc-p" [(ngModel)]="b.id_proveedor" (ngModelChange)="cambiarProveedor()">
              @for (p of proveedores; track p.id_proveedor) { @if (p.estado === 'ACTIVO') { <option [ngValue]="p.id_proveedor">{{ p.razon_social }}</option> } }
            </select></label>
          <label class="field" for="oc-s"><span>Sucursal de destino</span>
            <select id="oc-s" [(ngModel)]="b.id_sucursal" [disabled]="!!auth.sucursalFija()">
              @for (s of sucursales; track s.id_sucursal) { <option [ngValue]="s.id_sucursal">{{ s.nombre }}</option> }
            </select></label>
          <label class="field" for="oc-e"><span>Entrega comprometida</span><input id="oc-e" type="date" [(ngModel)]="b.fecha_entrega"></label>
          <label class="field" for="oc-o"><span>Observación</span><input id="oc-o" [(ngModel)]="b.observacion"></label>
        </div>
        <datalist id="dl-oc">@for (v of skusProv; track v.id_variante) { <option [value]="v.sku">{{ v.modelo }} · {{ v.color }} · T{{ v.talla }}</option> }</datalist>
        <div class="tw"><table class="t">
          <thead><tr><th>SKU ({{ skusProv.length }} de este proveedor)</th><th>Producto</th><th class="num">Cantidad</th><th class="num">Costo unit. (Bs)</th><th class="num">Subtotal</th><th></th></tr></thead>
          <tbody>@for (l of b.items; track $index; let i = $index) {
            <tr><td><input [(ngModel)]="l.sku" (ngModelChange)="elegirSku(l)" list="dl-oc" autocomplete="off" aria-label="SKU" style="min-width:190px"></td>
              <td class="sm">{{ nombreSku(l.sku) }}</td>
              <td><input type="number" min="1" step="1" [(ngModel)]="l.cantidad" aria-label="Cantidad" style="width:90px"></td>
              <td><input type="number" min="0" step="0.01" [(ngModel)]="l.costo_unitario" aria-label="Costo unitario" style="width:110px"></td>
              <td class="num">{{ (+l.cantidad || 0) * (+l.costo_unitario || 0) | bs }}</td>
              <td><button class="btn btn-sm" type="button" (click)="quitar(i)">Quitar</button></td></tr>
          }</tbody></table></div>
        <div style="display:flex;justify-content:space-between;align-items:center;gap:8px;flex-wrap:wrap">
          <button class="btn btn-sm" type="button" (click)="b.items.push({ sku: '', cantidad: null, costo_unitario: null })">Agregar línea</button>
          <span class="b">Total {{ totalBorrador() | bs }}</span></div>
        <div class="modal-f"><button class="btn" type="button" (click)="modal = null">Cancelar</button>
          <button class="btn btn-p" type="button" (click)="guardar()" [disabled]="ocupado">Enviar a aprobación</button></div>
      </app-modal>
    }

    @if (modal === 'ver' && o) {
      <app-modal [titulo]="o.numero + ' · ' + o.proveedor" [ancho]="true" (cerrar)="modal = null">
        <div style="display:flex;gap:10px;flex-wrap:wrap;align-items:center"><span class="badge {{ eo(o.estado)[1] }}">{{ eo(o.estado)[0] }}</span>
          <span class="sm muted">Emitida {{ o.fecha | fechaHora }} por {{ o.usuario }} · destino {{ o.sucursal }} · entrega {{ o.fecha_entrega | fecha }}</span></div>
        @if (o.observacion) { <p class="note">{{ o.observacion }}</p> }
        <div class="tw"><table class="t">
          <thead><tr><th>SKU</th><th>Producto</th><th class="num">Pedido</th><th class="num">Recibido</th><th class="num">Pendiente</th><th class="num">Costo</th>@if (puedeRecibir()) {<th class="num">Recibir ahora</th>}</tr></thead>
          <tbody>@for (i of o.items; track i.id_detalle) {
            <tr><td class="mono sm">{{ i.sku }}</td><td class="sm">{{ i.modelo }} · {{ i.color }} · T{{ i.talla }}</td><td class="num">{{ i.cantidad }}</td><td class="num">{{ i.cantidad_recibida }}</td>
              <td class="num b">{{ i.cantidad - i.cantidad_recibida }}</td><td class="num">{{ i.costo_unitario | bs }}</td>
              @if (puedeRecibir()) { <td class="num"><input type="number" min="0" [max]="i.cantidad - i.cantidad_recibida" [(ngModel)]="i.recibir" [disabled]="i.cantidad - i.cantidad_recibida <= 0" style="width:80px" aria-label="Cantidad a recibir"></td> }</tr>
          }
          <tr><td colspan="5" class="b">Total</td><td class="num b">{{ o.total | bs }}</td>@if (puedeRecibir()) {<td></td>}</tr></tbody></table></div>
        @if (o.estado === 'PENDIENTE_APROBACION' && auth.puede('compras.aprobar')) {
          <label class="field" for="oc-ob"><span>Observación de la aprobación</span><input id="oc-ob" [(ngModel)]="obs"></label>
          <div class="modal-f"><button class="btn btn-bad" type="button" (click)="decidir('RECHAZADA')" [disabled]="ocupado">Rechazar</button>
            <button class="btn btn-ok" type="button" (click)="decidir('APROBADA')" [disabled]="ocupado">Aprobar orden</button></div>
        }
        @if (o.estado === 'PENDIENTE_APROBACION' && !auth.puede('compras.aprobar')) {
          <p class="note">Esta orden espera la aprobación de un usuario con permiso para aprobar compras (por ejemplo, Gerente comercial).</p>
        }
        @if (puedeRecibir()) {
          <p class="note">Puedes registrar una recepción parcial; lo pendiente se recibe después. Cada unidad recibida entra al inventario de {{ o.sucursal }}.</p>
          <div class="modal-f"><button class="btn btn-p" type="button" (click)="recibir()" [disabled]="ocupado">Registrar recepción</button></div>
        }
        <div class="row">
          <div class="c1"><h3>Aprobaciones</h3>
            @for (a of o.aprobaciones; track $index) { <p class="sm"><span class="badge {{ a.decision === 'APROBADA' ? 'b-ok' : 'b-bad' }}">{{ a.decision === 'APROBADA' ? 'Aprobada' : 'Rechazada' }}</span> {{ a.usuario }} · {{ a.fecha | fechaHora }}@if (a.observacion) { · {{ a.observacion }} }</p> }
            @empty { <p class="sm muted">Sin decisiones aún.</p> }</div>
          <div class="c1"><h3>Recepciones</h3>
            @for (r of o.recepciones; track r.id_recepcion) { <p class="sm">{{ r.fecha | fechaHora }} · {{ r.usuario }} · {{ r.pares }} pares</p> }
            @empty { <p class="sm muted">Sin recepciones.</p> }</div>
        </div>
      </app-modal>
    }`,
})
export class ComprasComponent implements OnInit {
  private api = inject(ApiService);
  private toast = inject(ToastService);
  private route = inject(ActivatedRoute);
  auth = inject(AuthService);
  estados = Object.entries(ESTADO_OC);
  estado: string | null = null;
  ordenes: any[] = [];
  resumen: any = null;
  proveedores: any[] = [];
  sucursales: any[] = [];
  skusProv: any[] = [];
  modal: string | null = null;
  b: any = null;
  o: any = null;
  obs = '';
  ocupado = false;

  async ngOnInit() {
    this.sucursales = await this.api.get('/api/sucursales');
    if (this.auth.puede('compras.crear')) this.proveedores = await this.api.get('/api/proveedores');
    await this.cargar();
    if (ordenSugerida.datos) {
      const d = ordenSugerida.datos;
      ordenSugerida.datos = null;
      this.nueva(d);
    }
  }

  eo(e: string) { return ESTADO_OC[e] || [e, 'b-mut']; }

  async cargar() {
    [this.ordenes, this.resumen] = await Promise.all([this.api.get('/api/compras', { estado: this.estado }), this.api.get('/api/compras/resumen')]);
  }

  async nueva(base?: any) {
    const entrega = new Date(Date.now() + 10 * 864e5).toISOString().slice(0, 10);
    this.b = base
      ? { ...base, id_sucursal: base.id_sucursal ?? this.auth.sucursalFija() ?? this.sucursales[0]?.id_sucursal }
      : { id_proveedor: this.proveedores.find((p) => p.estado === 'ACTIVO')?.id_proveedor, id_sucursal: this.auth.sucursalFija() ?? this.sucursales[0]?.id_sucursal,
          fecha_entrega: entrega, observacion: '', items: [{ sku: '', cantidad: null, costo_unitario: null }] };
    await this.cargarSkus();
    this.modal = 'nueva';
  }

  async cargarSkus() { this.skusProv = this.b?.id_proveedor ? await this.api.get('/api/variantes/buscar', { id_proveedor: this.b.id_proveedor, limite: 200 }) : []; }
  async cambiarProveedor() { this.b.items = [{ sku: '', cantidad: null, costo_unitario: null }]; await this.cargarSkus(); }
  nombreSku(sku: string) { const v = this.skusProv.find((x) => x.sku.toUpperCase() === (sku || '').trim().toUpperCase()); return v ? `${v.modelo} · ${v.color} · T${v.talla}` : '—'; }
  elegirSku(l: any) {
    const v = this.skusProv.find((x) => x.sku.toUpperCase() === (l.sku || '').trim().toUpperCase());
    if (v) { if (!l.costo_unitario) l.costo_unitario = +v.costo_proveedor; if (!l.cantidad) l.cantidad = 10; }
  }
  quitar(i: number) { this.b.items.splice(i, 1); if (!this.b.items.length) this.b.items.push({ sku: '', cantidad: null, costo_unitario: null }); }
  totalBorrador() { return (this.b?.items || []).reduce((a: number, l: any) => a + (+l.cantidad || 0) * (+l.costo_unitario || 0), 0); }

  async guardar() {
    const items = this.b.items.filter((l: any) => (l.sku || '').trim()).map((l: any) => ({ sku: l.sku.trim(), cantidad: +l.cantidad, costo_unitario: +l.costo_unitario }));
    if (!items.length) { this.toast.aviso('Agrega al menos una línea.'); return; }
    this.ocupado = true;
    try {
      const r = await this.api.post('/api/compras', { ...this.b, items });
      this.toast.ok(`Orden ${r.numero} enviada a aprobación.`);
      this.modal = null;
      await this.cargar();
    } catch {} finally { this.ocupado = false; }
  }

  async ver(id: number) {
    this.o = await this.api.get(`/api/compras/${id}`);
    this.o.items.forEach((i: any) => (i.recibir = i.cantidad - i.cantidad_recibida));
    this.obs = '';
    this.modal = 'ver';
  }

  puedeRecibir() { return this.o && (this.o.estado === 'APROBADA' || this.o.estado === 'RECIBIDA_PARCIAL') && this.auth.puede('compras.recibir'); }

  async decidir(decision: string) {
    if (decision === 'RECHAZADA' && !this.obs.trim()) { this.toast.aviso('Escribe el motivo del rechazo.'); return; }
    this.ocupado = true;
    try {
      await this.api.post(`/api/compras/${this.o.id_orden}/decision`, { decision, observacion: this.obs });
      this.toast.ok(decision === 'APROBADA' ? 'Orden aprobada.' : 'Orden rechazada.');
      await this.ver(this.o.id_orden);
      await this.cargar();
    } catch {} finally { this.ocupado = false; }
  }

  async recibir() {
    const items = this.o.items.filter((i: any) => +i.recibir > 0).map((i: any) => ({ id_detalle: i.id_detalle, cantidad: +i.recibir }));
    if (!items.length) { this.toast.aviso('Indica cantidades a recibir.'); return; }
    this.ocupado = true;
    try {
      const r = await this.api.post(`/api/compras/${this.o.id_orden}/recepciones`, { items });
      this.toast.ok(`Recepción registrada: ${r.pares} pares ingresaron al inventario.`);
      await this.ver(this.o.id_orden);
      await this.cargar();
    } catch {} finally { this.ocupado = false; }
  }
}
