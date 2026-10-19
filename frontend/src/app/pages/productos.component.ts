import { Component, OnInit, inject } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ApiService } from '../core/api.service';
import { AuthService } from '../core/auth.service';
import { ToastService } from '../core/toast.service';
import { ModalComponent } from '../shared/graficos';
import { PIPES } from '../shared/pipes';

@Component({
  selector: 'app-productos',
  standalone: true,
  imports: [FormsModule, ModalComponent, ...PIPES],
  template: `
    <header class="ph">
      <div><div class="ph-t"><h1>Productos</h1></div><p>Catálogo por modelo con variantes de talla y color. Cada variante tiene SKU, precio y costo de referencia.</p></div>
      @if (puedeEditar) { <div class="ph-a"><button class="btn" type="button" (click)="modal = 'categorias'">Categorías</button>
        <button class="btn btn-p" type="button" (click)="abrirNuevo()">Nuevo producto</button></div> }
    </header>
    <section class="card">
      <div class="filters">
        <label class="field w2" for="pr-q"><span>Buscar</span><input id="pr-q" type="search" [(ngModel)]="q" (ngModelChange)="buscar()" placeholder="Modelo, marca o SKU"></label>
        <label class="field" for="pr-c"><span>Categoría</span><select id="pr-c" [(ngModel)]="categoria" (ngModelChange)="cargar()">
          <option [ngValue]="null">Todas</option>@for (c of categorias; track c.id_categoria) { <option [ngValue]="c.id_categoria">{{ c.nombre }}</option> }</select></label>
      </div>
      <div class="tw"><table class="t">
        <thead><tr><th>Modelo</th><th>Categoría</th><th>Marca</th><th>Proveedor</th><th class="num">Variantes</th><th class="num">Precio</th><th class="num">Margen ref.</th><th class="num">Stock total</th><th>Estado</th><th></th></tr></thead>
        <tbody>@for (p of productos; track p.id_producto) {
          <tr><td class="b">{{ p.modelo }}</td><td class="muted">{{ p.categoria }}</td><td>{{ p.marca }}</td><td class="sm">{{ p.proveedores || '—' }}</td><td class="num">{{ p.variantes }}</td>
            <td class="num">@if (p.precio_min === p.precio_max) { {{ p.precio_min | bs }} } @else { {{ p.precio_min | bs }} – {{ p.precio_max | bs }} }</td>
            <td class="num">{{ p.margen_ref | pct }}</td><td class="num">{{ p.stock_total | num }}</td>
            <td><span class="badge {{ p.estado === 'ACTIVO' ? 'b-ok' : 'b-mut' }}">{{ p.estado === 'ACTIVO' ? 'Activo' : 'Inactivo' }}</span></td>
            <td><button class="btn btn-sm" type="button" (click)="ver(p.id_producto)">Ver</button></td></tr>
        } @empty { <tr><td colspan="10"><div class="empty">Sin productos</div></td></tr> }</tbody></table></div>
    </section>

    @if (modal === 'ver' && p) {
      <app-modal [titulo]="p.modelo" [ancho]="true" (cerrar)="modal = null">
        <div class="form-grid">
          <label class="field" for="pv-m"><span>Modelo</span><input id="pv-m" [(ngModel)]="p.modelo" [disabled]="!puedeEditar"></label>
          <label class="field" for="pv-b"><span>Marca</span><input id="pv-b" [(ngModel)]="p.marca" [disabled]="!puedeEditar"></label>
          <label class="field" for="pv-c"><span>Categoría</span><select id="pv-c" [(ngModel)]="p.id_categoria" [disabled]="!puedeEditar">
            @for (c of categorias; track c.id_categoria) { <option [ngValue]="c.id_categoria">{{ c.nombre }}</option> }</select></label>
          <label class="field" for="pv-e"><span>Estado</span><select id="pv-e" [(ngModel)]="p.estado" [disabled]="!puedeEditar">
            <option value="ACTIVO">Activo</option><option value="INACTIVO">Inactivo</option></select></label>
          <label class="field full" for="pv-d"><span>Descripción</span><textarea id="pv-d" [(ngModel)]="p.descripcion" [disabled]="!puedeEditar"></textarea></label>
        </div>
        <p class="sm muted">Proveedores: @for (x of p.proveedores; track x.id_proveedor) { {{ x.razon_social }} ({{ x.codigo_proveedor }}) } @empty { sin proveedor asociado }</p>
        <div class="tw" style="max-height:340px;overflow:auto"><table class="t">
          <thead><tr><th>SKU</th><th>Color</th><th>Talla</th><th class="num">Precio venta</th><th class="num">Costo ref.</th><th class="num">Stock</th></tr></thead>
          <tbody>@for (v of p.variantes; track v.id_variante) {
            <tr><td class="mono sm">{{ v.sku }}</td><td>{{ v.color }}</td><td>{{ v.talla }}</td>
              <td class="num">@if (puedeEditar) { <input type="number" min="0" step="0.5" [(ngModel)]="v.precio_venta" style="width:100px" [attr.aria-label]="'Precio ' + v.sku"> } @else { {{ v.precio_venta | bs }} }</td>
              <td class="num">@if (puedeEditar) { <input type="number" min="0" step="0.01" [(ngModel)]="v.costo_referencia" style="width:100px" [attr.aria-label]="'Costo ' + v.sku"> } @else { {{ v.costo_referencia | bs }} }</td>
              <td class="num">{{ v.stock_total | num }}</td></tr>
          }</tbody></table></div>
        @if (puedeEditar) {
          <form class="filters" (ngSubmit)="agregarVariante()">
            <label class="field" for="av-t"><span>Nueva talla</span><input id="av-t" name="talla" [(ngModel)]="nv.talla" required></label>
            <label class="field" for="av-c"><span>Color</span><input id="av-c" name="color" [(ngModel)]="nv.color" required></label>
            <label class="field" for="av-p"><span>Precio</span><input id="av-p" name="precio" type="number" min="0" step="0.5" [(ngModel)]="nv.precio_venta" required></label>
            <label class="field" for="av-k"><span>Costo</span><input id="av-k" name="costo" type="number" min="0" step="0.01" [(ngModel)]="nv.costo_referencia" required></label>
            <button class="btn" type="submit">Agregar variante</button>
          </form>
          <p class="sm muted">Los cambios de precio y costo quedan en la bitácora con el valor anterior. Las ventas ya registradas conservan su costo histórico.</p>
          <div class="modal-f"><button class="btn" type="button" (click)="modal = null">Cerrar</button><button class="btn btn-p" type="button" (click)="guardar()" [disabled]="ocupado">Guardar cambios</button></div>
        }
      </app-modal>
    }

    @if (modal === 'nuevo') {
      <app-modal titulo="Nuevo producto" [ancho]="true" (cerrar)="modal = null">
        <form class="form-grid" (ngSubmit)="crear()">
          <label class="field" for="np-c"><span>Categoría</span><select id="np-c" name="cat" [(ngModel)]="np.id_categoria">
            @for (c of categorias; track c.id_categoria) { <option [ngValue]="c.id_categoria">{{ c.nombre }}</option> }</select></label>
          <label class="field" for="np-b"><span>Marca</span><input id="np-b" name="marca" [(ngModel)]="np.marca" required></label>
          <label class="field" for="np-m"><span>Modelo</span><input id="np-m" name="modelo" [(ngModel)]="np.modelo" required></label>
          <label class="field" for="np-p"><span>Proveedor</span><select id="np-p" name="prov" [(ngModel)]="np.id_proveedor">
            <option [ngValue]="null">Sin proveedor</option>@for (x of proveedores; track x.id_proveedor) { <option [ngValue]="x.id_proveedor">{{ x.razon_social }}</option> }</select></label>
          <label class="field" for="np-co"><span>Colores (separados por coma)</span><input id="np-co" name="colores" [(ngModel)]="np.colores" required placeholder="Negro, Café"></label>
          <label class="field" for="np-t"><span>Tallas (rango o lista)</span><input id="np-t" name="tallas" [(ngModel)]="np.tallas" required placeholder="38-43 o 38,39,40"></label>
          <label class="field" for="np-pv"><span>Precio de venta (Bs)</span><input id="np-pv" name="precio" type="number" min="0.5" step="0.5" [(ngModel)]="np.precio_venta" required></label>
          <label class="field" for="np-k"><span>Costo de referencia (Bs)</span><input id="np-k" name="costo" type="number" min="0" step="0.01" [(ngModel)]="np.costo_referencia" required></label>
          <label class="field" for="np-mi"><span>Stock mínimo por sucursal</span><input id="np-mi" name="min" type="number" min="0" [(ngModel)]="np.stock_minimo"></label>
          <label class="field full" for="np-d"><span>Descripción</span><textarea id="np-d" name="desc" [(ngModel)]="np.descripcion"></textarea></label>
          <p class="note full">Se crea un SKU por cada combinación de color y talla, con stock 0 en todas las sucursales. Las existencias entran después por compra, ajuste o importación.</p>
          <div class="modal-f full"><button type="button" class="btn" (click)="modal = null">Cancelar</button><button class="btn btn-p" type="submit" [disabled]="ocupado">Crear producto</button></div>
        </form>
      </app-modal>
    }

    @if (modal === 'categorias') {
      <app-modal titulo="Categorías" (cerrar)="modal = null">
        <div class="tw"><table class="t"><thead><tr><th>Código</th><th>Nombre</th><th class="num">Productos</th></tr></thead>
          <tbody>@for (c of categorias; track c.id_categoria) { <tr><td class="mono">{{ c.codigo }}</td><td>{{ c.nombre }}</td><td class="num">{{ c.productos }}</td></tr> }</tbody></table></div>
        <form class="filters" (ngSubmit)="crearCategoria()">
          <label class="field" for="nc-c"><span>Código (3 letras)</span><input id="nc-c" name="codigo" maxlength="6" [(ngModel)]="nc.codigo" required></label>
          <label class="field w2" for="nc-n"><span>Nombre</span><input id="nc-n" name="nombre" [(ngModel)]="nc.nombre" required></label>
          <button class="btn btn-p" type="submit">Agregar</button>
        </form>
      </app-modal>
    }`,
})
export class ProductosComponent implements OnInit {
  private api = inject(ApiService);
  private toast = inject(ToastService);
  auth = inject(AuthService);
  puedeEditar = false;
  productos: any[] = [];
  categorias: any[] = [];
  proveedores: any[] = [];
  q = '';
  categoria: number | null = null;
  modal: string | null = null;
  p: any = null;
  original: any = null;
  nv: any = {};
  np: any = {};
  nc: any = { codigo: '', nombre: '' };
  ocupado = false;
  private t: any;

  async ngOnInit() {
    this.puedeEditar = this.auth.puede('productos.editar');
    this.categorias = await this.api.get('/api/categorias');
    if (this.puedeEditar) this.proveedores = await this.api.get('/api/proveedores').catch(() => []);
    this.cargar();
  }

  buscar() { clearTimeout(this.t); this.t = setTimeout(() => this.cargar(), 250); }
  async cargar() { this.productos = await this.api.get('/api/productos', { q: this.q, id_categoria: this.categoria }); }

  async ver(id: number) {
    this.p = await this.api.get(`/api/productos/${id}`);
    this.p.variantes.forEach((v: any) => { v.precio_venta = +v.precio_venta; v.costo_referencia = +v.costo_referencia; });
    this.original = JSON.parse(JSON.stringify(this.p));
    const v0 = this.p.variantes[0];
    this.nv = { talla: '', color: v0?.color || '', precio_venta: v0?.precio_venta || null, costo_referencia: v0?.costo_referencia || null };
    this.modal = 'ver';
  }

  async guardar() {
    this.ocupado = true;
    try {
      await this.api.put(`/api/productos/${this.p.id_producto}`, {
        id_categoria: this.p.id_categoria, marca: this.p.marca, modelo: this.p.modelo, descripcion: this.p.descripcion, estado: this.p.estado,
      });
      for (const v of this.p.variantes) {
        const o = this.original.variantes.find((x: any) => x.id_variante === v.id_variante);
        if (o && (+o.precio_venta !== +v.precio_venta || +o.costo_referencia !== +v.costo_referencia)) {
          await this.api.put(`/api/variantes/${v.id_variante}`, { precio_venta: +v.precio_venta, costo_referencia: +v.costo_referencia });
        }
      }
      this.toast.ok('Producto actualizado.');
      await this.ver(this.p.id_producto);
      this.cargar();
    } catch {} finally { this.ocupado = false; }
  }

  async agregarVariante() {
    try {
      const r = await this.api.post(`/api/productos/${this.p.id_producto}/variantes`, { ...this.nv, precio_venta: +this.nv.precio_venta, costo_referencia: +this.nv.costo_referencia });
      this.toast.ok(`Variante ${r.sku} creada.`);
      await this.ver(this.p.id_producto);
      this.cargar();
    } catch {}
  }

  abrirNuevo() {
    this.np = { id_categoria: this.categorias[0]?.id_categoria, marca: 'Manaco', modelo: '', id_proveedor: null, colores: '', tallas: '',
                precio_venta: null, costo_referencia: null, stock_minimo: 4, descripcion: '' };
    this.modal = 'nuevo';
  }

  async crear() {
    this.ocupado = true;
    try {
      const r = await this.api.post('/api/productos', {
        ...this.np, colores: String(this.np.colores).split(',').map((s: string) => s.trim()).filter(Boolean),
        precio_venta: +this.np.precio_venta, costo_referencia: +this.np.costo_referencia, stock_minimo: +this.np.stock_minimo || 0,
      });
      this.toast.ok(`Producto creado con ${r.skus.length} SKU.`);
      this.modal = null;
      this.cargar();
    } catch {} finally { this.ocupado = false; }
  }

  async crearCategoria() {
    try {
      await this.api.post('/api/categorias', this.nc);
      this.toast.ok('Categoría creada.');
      this.nc = { codigo: '', nombre: '' };
      this.categorias = await this.api.get('/api/categorias');
    } catch {}
  }
}
