import { Component, OnInit, inject } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ApiService } from '../core/api.service';
import { AuthService } from '../core/auth.service';
import { ESTADO_VENTA } from '../core/nav';
import { ToastService } from '../core/toast.service';
import { ModalComponent } from '../shared/graficos';
import { PIPES } from '../shared/pipes';

interface LineaCarrito { id_variante: number; sku: string; modelo: string; color: string; talla: string; precio: number; stock: number; cantidad: number; descuento_pct: number; }

const nuevaClave = () => (crypto as any).randomUUID ? crypto.randomUUID().replace(/-/g, '') : Math.random().toString(36).slice(2) + Date.now().toString(36);

@Component({
  selector: 'app-pos',
  standalone: true,
  imports: [FormsModule, ModalComponent, ...PIPES],
  template: `
    @if (cargando) { <div class="cargando"><span class="spin"></span> Cargando…</div> }

    @if (!cargando && !sesion) {
      <header class="ph"><div><div class="ph-t"><h1>Punto de Venta</h1></div><p>Abre una caja para empezar a vender. El saldo inicial es el efectivo con el que empiezas el turno.</p></div></header>
      @if (!auth.puede('caja.operar')) { <div class="card"><div class="empty"><h2>Necesitas una caja abierta</h2><p>Tu rol no puede abrir caja.</p></div></div> }
      @else {
        <form class="card" style="max-width:520px" (ngSubmit)="abrir()">
          <h2>Apertura de caja</h2>
          <div class="form-grid">
            <label class="field" for="ac-s"><span>Sucursal</span>
              <select id="ac-s" name="suc" [(ngModel)]="apertura.id_sucursal" [disabled]="!!auth.sucursalFija()">
                @for (c of cajas; track c.id_caja) { <option [ngValue]="c.id_sucursal">{{ c.sucursal }}</option> }
              </select></label>
            <label class="field" for="ac-i"><span>Saldo inicial en efectivo (Bs)</span>
              <input id="ac-i" name="ini" type="number" min="0" step="0.01" [(ngModel)]="apertura.saldo_inicial"></label>
          </div>
          @for (c of cajas; track c.id_caja) { @if (c.estado === 'ABIERTA') { <p class="note">{{ c.sucursal }}: caja abierta por {{ c.abierta_por }} desde {{ c.apertura | fechaHora }}.</p> } }
          <div><button class="btn btn-p" type="submit" [disabled]="ocupado">Abrir caja</button></div>
        </form>
      }
    }

    @if (sesion) {
      <header class="ph">
        <div><div class="ph-t"><h1>Punto de Venta</h1></div><p>{{ sesion.sucursal }} · {{ sesion.caja }}</p></div>
        <div class="ph-a">
          <span class="status-open">Caja abierta desde {{ sesion.apertura | fechaHora }}</span>
          @if (auth.puede('pos.devolver')) { <button class="btn" type="button" (click)="abrirDevolucion()">Devolución</button> }
          <button class="btn" type="button" (click)="modal = 'movimiento'">Movimiento de caja</button>
          <button class="btn btn-bad" type="button" (click)="abrirCierre()">Cerrar caja</button>
        </div>
      </header>

      <div class="pos">
        <section class="c3" style="display:flex;flex-direction:column;gap:12px" aria-label="Catálogo">
          <label class="field" for="pos-q"><span>Buscar por modelo, color o SKU</span>
            <input id="pos-q" type="search" [(ngModel)]="q" (ngModelChange)="buscar()" placeholder="Ej.: escolar, MNC-ESC-001" style="min-height:46px;font-size:15px"></label>
          <div class="chips" role="group" aria-label="Categorías">
            <button class="chip" type="button" [attr.aria-pressed]="!categoria" (click)="categoria = null; cargarCatalogo()">Todas</button>
            @for (c of categorias; track c.id_categoria) {
              <button class="chip" type="button" [attr.aria-pressed]="categoria === c.id_categoria" (click)="categoria = c.id_categoria; cargarCatalogo()">{{ c.nombre }}</button>
            }
          </div>
          <div class="cat-grid">
            @for (g of catalogo; track $index) {
              <div class="pc">
                <div style="display:flex;justify-content:space-between;gap:8px"><span class="pc-n">{{ g.modelo }}</span><span class="mono b">{{ g.precio | bs }}</span></div>
                <span class="sm muted">{{ g.color }} · {{ g.categoria }}</span>
                <div class="sizes">
                  @for (t of g.tallas; track t.id_variante) {
                    <button class="sz" type="button" [disabled]="disponible(t) <= 0" (click)="agregar(g, t)"
                      [attr.aria-label]="'Talla ' + t.talla + ', ' + disponible(t) + ' disponibles'">{{ t.talla }}<small>{{ disponible(t) }}</small></button>
                  }
                </div>
              </div>
            } @empty { <div class="empty" style="grid-column:1/-1">Ningún producto coincide con la búsqueda.</div> }
          </div>
          <p class="sm muted">El número bajo cada talla es el stock de esta sucursal, descontando lo que ya está en el carrito.</p>
        </section>

        <aside class="card cart" aria-label="Venta actual">
          <div class="card-h"><h2>Venta actual</h2></div>
          <label class="field" for="pos-cli"><span>Cliente (opcional)</span>
            <input id="pos-cli" [(ngModel)]="cliente" placeholder="Nombre del cliente" list="dl-cli" (input)="buscarClientes()"></label>
          <datalist id="dl-cli">@for (c of clientes; track c.id_cliente) { <option [value]="c.nombre"></option> }</datalist>
          <div>
            @for (l of carrito; track l.id_variante; let i = $index) {
              <div class="cl">
                <div class="cl-n"><span class="b">{{ l.modelo }}</span><span class="sm mono muted">{{ l.sku }}</span>
                  <label class="sm muted">Descuento
                    <select [(ngModel)]="l.descuento_pct" style="min-height:28px;width:auto;padding:0 6px;font-size:12px">
                      @for (d of [0, 5, 10, 15, 20]; track d) { <option [ngValue]="d">{{ d }} %</option> }
                    </select></label></div>
                <div class="qty"><button class="qb" type="button" (click)="cambiar(i, -1)" aria-label="Quitar uno">−</button>
                  <span class="mono" style="width:22px;text-align:center">{{ l.cantidad }}</span>
                  <button class="qb" type="button" (click)="cambiar(i, 1)" aria-label="Agregar uno">+</button></div>
                <span class="num" style="width:86px">{{ subtotal(l) | bs }}</span>
              </div>
            } @empty { <div class="empty">Elige una talla en el catálogo para agregarla.</div> }
          </div>
          <div class="tot"><span class="muted">Subtotal</span><span class="num">{{ totales().sub | bs }}</span></div>
          <div class="tot"><span class="muted">Descuentos</span><span class="num" style="color:var(--ok)">− {{ totales().desc | bs }}</span></div>
          <div class="tot big"><span class="b">Total</span><span class="num">{{ totales().total | bs }}</span></div>
          <div style="display:flex;flex-direction:column;gap:6px"><span class="sm muted">Método de pago</span>
            <div class="pay">
              @for (m of metodos; track m[0]) { <button class="chip" type="button" [attr.aria-pressed]="metodo === m[0]" (click)="metodo = m[0]">{{ m[1] }}</button> }
            </div></div>
          @if (metodo === 'EFECTIVO') {
            <label class="field" for="pos-rec"><span>Monto recibido (opcional)</span>
              <input id="pos-rec" type="number" min="0" step="0.5" [(ngModel)]="recibido"></label>
            @if (recibido !== null && recibido !== undefined && recibido !== '') {
              <div class="tot"><span class="muted">Cambio</span>
                <span class="num" [style.color]="+recibido >= totales().total ? 'var(--ok)' : 'var(--bad)'">
                  {{ +recibido >= totales().total ? (+recibido - totales().total | bs) : 'Falta ' + (totales().total - +recibido | bs) }}</span></div>
            }
          }
          <button class="btn btn-p btn-lg" type="button" (click)="cobrar()" [disabled]="!carrito.length || ocupado">
            @if (ocupado) { <span class="spin"></span> } Cobrar {{ totales().total | bs }}</button>
          @if (carrito.length) { <button class="btn btn-sm" type="button" (click)="carrito = []">Vaciar carrito</button> }
          @if (sesion.ventas?.length) {
            <div style="display:flex;flex-direction:column;gap:6px;border-top:1px solid var(--line);padding-top:10px">
              <h3>Ventas de este turno</h3>
              @for (v of sesion.ventas; track v.id_venta) {
                <div class="tot sm"><span><span class="mono">{{ v.numero }}</span> · {{ v.metodo_pago }}
                  @if (v.estado !== 'COMPLETADA') { <span class="badge {{ ev(v.estado)[1] }}">{{ ev(v.estado)[0] }}</span> }</span>
                  <button class="btn btn-sm" type="button" (click)="verRecibo(v.id_venta)">{{ v.total | bs }}</button></div>
              }
            </div>
          }
        </aside>
      </div>
    }

    @if (modal === 'recibo' && recibo) {
      <app-modal titulo="Venta registrada" (cerrar)="modal = null">
        <div class="ticket">
          <div class="tr b"><span>MANACO · {{ recibo.sucursal }}</span><span>{{ recibo.numero }}</span></div>
          <div class="tr muted"><span>{{ recibo.fecha | fechaHora }}</span><span>{{ recibo.usuario }}</span></div>
          @if (recibo.cliente) { <div class="tr"><span>Cliente: {{ recibo.cliente }}</span></div> }
          <hr style="border:0;border-top:1px dashed var(--line2);width:100%">
          @for (i of recibo.items; track i.id_detalle) {
            <div class="tr"><span>{{ i.cantidad }} × {{ i.modelo }} {{ i.color }} T{{ i.talla }}</span><span>{{ i.subtotal | bs }}</span></div>
            @if (+i.descuento) { <div class="tr muted"><span>  descuento</span><span>−{{ i.descuento | bs }}</span></div> }
            @if (i.cantidad_devuelta) { <div class="tr" style="color:var(--bad)"><span>  devuelto: {{ i.cantidad_devuelta }}</span></div> }
          }
          <hr style="border:0;border-top:1px dashed var(--line2);width:100%">
          <div class="tr"><span>Subtotal</span><span>{{ recibo.subtotal | bs }}</span></div>
          <div class="tr"><span>Descuentos</span><span>−{{ recibo.descuento | bs }}</span></div>
          <div class="tr b" style="font-size:15px"><span>TOTAL</span><span>{{ recibo.total | bs }}</span></div>
          <div class="tr"><span>Pago</span><span>{{ recibo.pagos[0]?.metodo_pago }}</span></div>
          @if (recibo.cambio !== undefined) { <div class="tr"><span>Recibido</span><span>{{ recibo.monto_recibido | bs }}</span></div><div class="tr"><span>Cambio</span><span>{{ recibo.cambio | bs }}</span></div> }
        </div>
        <p class="sm muted">El inventario de la sucursal ya se descontó y la venta quedó registrada en la bitácora.</p>
        <div class="modal-f"><button class="btn btn-p" type="button" (click)="modal = null">Nueva venta</button></div>
      </app-modal>
    }

    @if (modal === 'devolucion') {
      <app-modal titulo="Devolución" [ancho]="true" (cerrar)="modal = null">
        <form class="filters" (ngSubmit)="buscarVenta()">
          <label class="field w2" for="dv-n"><span>Número de venta</span><input id="dv-n" name="nro" [(ngModel)]="dev.numero" placeholder="V-000123"></label>
          <button class="btn" type="submit">Buscar</button>
        </form>
        @if (dev.venta) {
          <p class="sm muted">{{ dev.venta.numero }} · {{ dev.venta.fecha | fechaHora }} · {{ dev.venta.sucursal }} · pagado con {{ dev.venta.pagos[0]?.metodo_pago }}</p>
          <div class="tw"><table class="t"><thead><tr><th>Producto</th><th class="num">Vendidos</th><th class="num">Ya devueltos</th><th class="num">A devolver</th></tr></thead>
            <tbody>@for (i of dev.venta.items; track i.id_detalle) {
              <tr><td>{{ i.modelo }} · {{ i.color }} · T{{ i.talla }}</td><td class="num">{{ i.cantidad }}</td><td class="num">{{ i.cantidad_devuelta }}</td>
                <td class="num"><input type="number" min="0" [max]="i.cantidad - i.cantidad_devuelta" [(ngModel)]="i.devolver" [disabled]="i.cantidad - i.cantidad_devuelta <= 0" style="width:80px" aria-label="Cantidad a devolver"></td></tr>
            }</tbody></table></div>
          <label class="field" for="dv-m"><span>Motivo</span><input id="dv-m" [(ngModel)]="dev.motivo" placeholder="Ej.: talla incorrecta"></label>
          <p class="note">El dinero se devuelve en efectivo desde tu caja y las unidades vuelven al stock de la sucursal.</p>
          <div class="modal-f"><button class="btn" type="button" (click)="modal = null">Cancelar</button>
            <button class="btn btn-p" type="button" (click)="confirmarDevolucion()" [disabled]="ocupado">Registrar devolución</button></div>
        }
      </app-modal>
    }

    @if (modal === 'movimiento') {
      <app-modal titulo="Movimiento de caja" (cerrar)="modal = null">
        <form class="form-grid" (ngSubmit)="registrarMovimiento()">
          <label class="field" for="mc-t"><span>Tipo</span><select id="mc-t" name="tipo" [(ngModel)]="mov.tipo">
            <option value="INGRESO">Ingreso de efectivo</option><option value="EGRESO">Egreso de efectivo</option></select></label>
          <label class="field" for="mc-m"><span>Monto (Bs)</span><input id="mc-m" name="monto" type="number" min="0.01" step="0.01" [(ngModel)]="mov.monto" required></label>
          <label class="field full" for="mc-c"><span>Concepto</span><input id="mc-c" name="concepto" [(ngModel)]="mov.concepto" required placeholder="Ej.: pago de transporte"></label>
          <div class="modal-f full"><button type="button" class="btn" (click)="modal = null">Cancelar</button><button class="btn btn-p" type="submit" [disabled]="ocupado">Registrar</button></div>
        </form>
      </app-modal>
    }

    @if (modal === 'cierre' && sesion) {
      <app-modal titulo="Cierre de caja" (cerrar)="modal = null">
        <div class="ticket">
          <div class="tr"><span>Saldo inicial</span><span>{{ r.saldo_inicial | bs }}</span></div>
          <div class="tr"><span>Ventas en efectivo</span><span>{{ r.ventas_efectivo | bs }}</span></div>
          <div class="tr"><span>Ventas con tarjeta</span><span>{{ r.ventas_tarjeta | bs }}</span></div>
          <div class="tr"><span>Ventas con QR</span><span>{{ r.ventas_qr | bs }}</span></div>
          <div class="tr"><span>Ingresos manuales</span><span>{{ r.ingresos | bs }}</span></div>
          <div class="tr"><span>Egresos manuales</span><span>{{ r.egresos | bs }}</span></div>
          <div class="tr"><span>Devoluciones</span><span>{{ r.devoluciones | bs }}</span></div>
          <hr style="border:0;border-top:1px dashed var(--line2);width:100%">
          <div class="tr b"><span>Efectivo esperado</span><span>{{ r.efectivo_esperado | bs }}</span></div>
          <div class="tr muted"><span>{{ r.ventas }} ventas en el turno</span></div>
        </div>
        <form class="form-grid" (ngSubmit)="cerrarCaja()">
          <label class="field" for="cc-c"><span>Efectivo contado (Bs)</span><input id="cc-c" name="contado" type="number" min="0" step="0.01" [(ngModel)]="contado" required></label>
          <div class="modal-f full"><button type="button" class="btn" (click)="modal = null">Cancelar</button><button class="btn btn-bad" type="submit" [disabled]="ocupado">Cerrar caja</button></div>
        </form>
      </app-modal>
    }`,
})
export class PosComponent implements OnInit {
  private api = inject(ApiService);
  private toast = inject(ToastService);
  auth = inject(AuthService);

  cargando = true;
  ocupado = false;
  sesion: any = null;
  cajas: any[] = [];
  categorias: any[] = [];
  catalogo: any[] = [];
  clientes: any[] = [];
  apertura = { id_sucursal: null as number | null, saldo_inicial: 500 };
  q = '';
  categoria: number | null = null;
  carrito: LineaCarrito[] = [];
  cliente = '';
  metodo = 'EFECTIVO';
  metodos = [['EFECTIVO', 'Efectivo'], ['TARJETA', 'Tarjeta'], ['QR', 'QR']];
  recibido: any = '';
  clave = nuevaClave();
  modal: string | null = null;
  recibo: any = null;
  dev: any = { numero: '', venta: null, motivo: '' };
  mov = { tipo: 'INGRESO', monto: null as number | null, concepto: '' };
  r: any = {};
  contado: number | null = null;
  private t: any;

  async ngOnInit() {
    this.categorias = await this.api.get('/api/categorias');
    await this.cargarSesion();
  }

  async cargarSesion() {
    this.cargando = true;
    try {
      this.sesion = await this.api.get('/api/caja/sesion');
      if (this.sesion) await this.cargarCatalogo();
      else if (this.auth.puede('caja.operar')) {
        this.cajas = await this.api.get('/api/caja/estado');
        this.apertura.id_sucursal = this.auth.sucursalFija() ?? this.cajas[0]?.id_sucursal ?? null;
      }
    } finally {
      this.cargando = false;
    }
  }

  async cargarCatalogo() {
    this.catalogo = await this.api.get('/api/pos/catalogo', { q: this.q, id_categoria: this.categoria });
  }

  buscar() {
    clearTimeout(this.t);
    this.t = setTimeout(() => this.cargarCatalogo(), 250);
  }

  async buscarClientes() {
    if (this.cliente.length >= 2) this.clientes = await this.api.get('/api/clientes', { q: this.cliente });
  }

  async abrir() {
    this.ocupado = true;
    try {
      await this.api.post('/api/caja/abrir', this.apertura);
      this.toast.ok('Caja abierta.');
      await this.cargarSesion();
    } catch {} finally { this.ocupado = false; }
  }

  enCarrito(id: number) { return this.carrito.find((l) => l.id_variante === id)?.cantidad || 0; }
  disponible(t: any) { return t.stock - this.enCarrito(t.id_variante); }

  agregar(g: any, t: any) {
    const l = this.carrito.find((x) => x.id_variante === t.id_variante);
    if (this.disponible(t) <= 0) { this.toast.aviso('No hay más stock de esta talla en la sucursal.'); return; }
    if (l) l.cantidad++;
    else this.carrito.push({ id_variante: t.id_variante, sku: t.sku, modelo: g.modelo, color: g.color, talla: t.talla, precio: +t.precio, stock: t.stock, cantidad: 1, descuento_pct: 0 });
  }

  cambiar(i: number, d: number) {
    const l = this.carrito[i];
    if (d > 0 && l.cantidad + 1 > l.stock) { this.toast.aviso('No hay más stock de esta talla.'); return; }
    l.cantidad += d;
    if (l.cantidad <= 0) this.carrito.splice(i, 1);
  }

  subtotal(l: LineaCarrito) { const b = l.precio * l.cantidad; return b - Math.round(b * l.descuento_pct) / 100; }

  totales() {
    let sub = 0, desc = 0;
    for (const l of this.carrito) { const b = l.precio * l.cantidad; sub += b; desc += Math.round(b * l.descuento_pct) / 100; }
    return { sub, desc, total: Math.round((sub - desc) * 100) / 100 };
  }

  async cobrar() {
    if (this.ocupado || !this.carrito.length) return;
    const tot = this.totales().total;
    if (this.metodo === 'EFECTIVO' && this.recibido !== '' && this.recibido !== null && +this.recibido < tot) {
      this.toast.error('El monto recibido es menor que el total.'); return;
    }
    this.ocupado = true;
    try {
      const v = await this.api.post('/api/ventas', {
        items: this.carrito.map((l) => ({ id_variante: l.id_variante, cantidad: l.cantidad, descuento_pct: l.descuento_pct })),
        metodo_pago: this.metodo,
        monto_recibido: this.metodo === 'EFECTIVO' && this.recibido !== '' && this.recibido !== null ? +this.recibido : null,
        cliente: this.cliente || null,
        idempotency_key: this.clave, // si la red falla y se reintenta, la venta no se duplica
      });
      this.recibo = v;
      this.modal = 'recibo';
      this.carrito = [];
      this.cliente = '';
      this.recibido = '';
      this.clave = nuevaClave();
      this.sesion = await this.api.get('/api/caja/sesion');
      await this.cargarCatalogo();
    } catch {} finally { this.ocupado = false; }
  }

  async verRecibo(id: number) { this.recibo = await this.api.get(`/api/ventas/${id}`); this.modal = 'recibo'; }

  abrirDevolucion() { this.dev = { numero: '', venta: null, motivo: '' }; this.modal = 'devolucion'; }

  async buscarVenta() {
    if (!this.dev.numero) return;
    const v = await this.api.get(`/api/ventas/numero/${encodeURIComponent(this.dev.numero)}`).catch(() => null);
    if (v) v.items.forEach((i: any) => (i.devolver = 0));
    this.dev.venta = v;
  }

  async confirmarDevolucion() {
    const items = this.dev.venta.items.filter((i: any) => +i.devolver > 0).map((i: any) => ({ id_detalle: i.id_detalle, cantidad: +i.devolver }));
    if (!items.length) { this.toast.aviso('Indica al menos una unidad a devolver.'); return; }
    if (!this.dev.motivo?.trim()) { this.toast.aviso('Escribe el motivo de la devolución.'); return; }
    this.ocupado = true;
    try {
      const r = await this.api.post(`/api/ventas/${this.dev.venta.id_venta}/devoluciones`, { items, motivo: this.dev.motivo });
      this.toast.ok(`Devolución registrada: Bs ${r.monto} devueltos y stock actualizado.`);
      this.modal = null;
      this.sesion = await this.api.get('/api/caja/sesion');
      await this.cargarCatalogo();
    } catch {} finally { this.ocupado = false; }
  }

  async registrarMovimiento() {
    this.ocupado = true;
    try {
      await this.api.post('/api/caja/movimientos', this.mov);
      this.toast.ok('Movimiento registrado.');
      this.modal = null;
      this.mov = { tipo: 'INGRESO', monto: null, concepto: '' };
      this.sesion = await this.api.get('/api/caja/sesion');
    } catch {} finally { this.ocupado = false; }
  }

  async abrirCierre() {
    this.sesion = await this.api.get('/api/caja/sesion');
    this.r = this.sesion.resumen;
    this.contado = +this.r.efectivo_esperado;
    this.modal = 'cierre';
  }

  async cerrarCaja() {
    this.ocupado = true;
    try {
      const r = await this.api.post('/api/caja/cerrar', { saldo_contado: this.contado });
      if (Math.abs(r.diferencia) < 0.01) this.toast.ok('Caja cerrada sin diferencias.');
      else this.toast.aviso(`Caja cerrada con diferencia de Bs ${r.diferencia}.`);
      this.modal = null;
      this.carrito = [];
      await this.cargarSesion();
    } catch {} finally { this.ocupado = false; }
  }

  ev(e: string) { return ESTADO_VENTA[e] || [e, 'b-mut']; }
}
