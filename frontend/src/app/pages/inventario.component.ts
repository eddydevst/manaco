import { Component, OnInit, inject } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ApiService } from '../core/api.service';
import { AuthService } from '../core/auth.service';
import { ESTADO_INV, TIPOS_MOV } from '../core/nav';
import { ToastService } from '../core/toast.service';
import { ModalComponent } from '../shared/graficos';
import { PIPES } from '../shared/pipes';

@Component({
  selector: 'app-inventario',
  standalone: true,
  imports: [FormsModule, ModalComponent, ...PIPES],
  template: `
    <header class="ph">
      <div><div class="ph-t"><h1>Inventario</h1></div><p>Existencias por variante (SKU) y sucursal. Todo cambio de stock queda registrado como movimiento.</p></div>
      @if (auth.puede('inventario.ajustar')) {
        <div class="ph-a"><button class="btn" type="button" (click)="abrirAjuste()">Ajuste de inventario</button>
          <button class="btn btn-p" type="button" (click)="abrirTransferencia()">Nueva transferencia</button></div>
      }
    </header>

    @if (res) {
      <section class="kpis">
        <div class="kpi"><span class="l">Pares en stock</span><span class="v">{{ res.pares | num }}</span></div>
        <div class="kpi"><span class="l">Valor a costo</span><span class="v">{{ res.valor | bsc }}</span></div>
        <div class="kpi" [class.bad]="res.agotado > 0"><span class="l">Agotados</span><span class="v">{{ res.agotado | num }}</span></div>
        <div class="kpi warn"><span class="l">Bajo mínimo</span><span class="v">{{ res.bajo_minimo | num }}</span></div>
        <div class="kpi info"><span class="l">Baja rotación</span><span class="v">{{ res.baja_rotacion | num }}</span><span class="d">sin ventas en {{ f.dias }} días</span></div>
        <div class="kpi pur"><span class="l">Sobrestock</span><span class="v">{{ res.sobrestock | num }}</span><span class="d">más de 4× el mínimo</span></div>
      </section>
    }

    <div class="row">
      <section class="card c3">
        <div class="filters">
          <label class="field w2" for="in-q"><span>Buscar</span><input id="in-q" type="search" [(ngModel)]="f.q" (ngModelChange)="buscar()" placeholder="SKU, modelo, color"></label>
          <label class="field" for="in-s"><span>Sucursal</span>
            <select id="in-s" [(ngModel)]="f.id_sucursal" (ngModelChange)="ir(1)" [disabled]="!!auth.sucursalFija()">
              <option [ngValue]="null">Todas</option>
              @for (s of sucursales; track s.id_sucursal) { <option [ngValue]="s.id_sucursal">{{ s.nombre }}</option> }
            </select></label>
          <label class="field" for="in-c"><span>Categoría</span>
            <select id="in-c" [(ngModel)]="f.id_categoria" (ngModelChange)="ir(1)">
              <option [ngValue]="null">Todas</option>
              @for (c of categorias; track c.id_categoria) { <option [ngValue]="c.id_categoria">{{ c.nombre }}</option> }
            </select></label>
          <label class="field" for="in-e"><span>Estado</span>
            <select id="in-e" [(ngModel)]="f.estado" (ngModelChange)="ir(1)">
              <option [ngValue]="null">Todos</option>
              @for (e of estados; track e[0]) { <option [ngValue]="e[0]">{{ e[1][0] }}</option> }
            </select></label>
          <label class="field" for="in-d"><span>Baja rotación desde</span>
            <select id="in-d" [(ngModel)]="f.dias" (ngModelChange)="ir(1)">
              @for (d of [30, 60, 90, 120, 180]; track d) { <option [ngValue]="d">{{ d }} días</option> }
            </select></label>
        </div>
        <div class="tw"><table class="t">
          <thead><tr><th>SKU</th><th>Producto</th><th>Sucursal</th><th class="num">Stock</th><th class="num">Mínimo</th><th>Estado</th><th>Última venta</th><th></th></tr></thead>
          <tbody>
            @for (x of items; track x.sku + x.id_sucursal) {
              <tr><td class="mono">{{ x.sku }}</td><td>{{ x.modelo }} · {{ x.color }} · T{{ x.talla }}</td><td class="muted">{{ x.sucursal }}</td>
                <td class="num b" [style.color]="x.estado === 'AGOTADO' ? 'var(--bad)' : x.estado === 'BAJO_MINIMO' ? 'var(--warn)' : null">{{ x.stock_actual }}</td>
                <td class="num">{{ x.stock_minimo }}</td>
                <td><span class="badge {{ est(x.estado)[1] }}">{{ est(x.estado)[0] }}</span></td>
                <td class="sm muted">{{ x.ultima_venta | fecha }}</td>
                <td><button class="btn btn-sm" type="button" (click)="verKardex(x)">Kardex</button></td></tr>
            } @empty { <tr><td colspan="8"><div class="empty">Ninguna existencia coincide con los filtros.</div></td></tr> }
          </tbody></table></div>
        <div class="pager"><span>{{ total | num }} registros · página {{ pagina }} de {{ paginas() }}</span>
          <span style="display:flex;gap:6px"><button class="btn btn-sm" type="button" (click)="ir(pagina - 1)" [disabled]="pagina <= 1">Anterior</button>
            <button class="btn btn-sm" type="button" (click)="ir(pagina + 1)" [disabled]="pagina >= paginas()">Siguiente</button></span></div>
      </section>
      <aside class="card c1"><h2>Últimos movimientos</h2>
        @for (m of movimientos; track $index) {
          <div style="display:flex;flex-direction:column;gap:2px;padding-bottom:8px;border-bottom:1px solid var(--line)">
            <div class="tot"><span class="b sm">{{ tipo(m.tipo) }}</span><span class="num sm" [style.color]="m.cantidad > 0 ? 'var(--ok)' : 'var(--bad)'">{{ m.cantidad > 0 ? '+' : '' }}{{ m.cantidad }}</span></div>
            <span class="sm muted">{{ m.sku }} · {{ m.sucursal }}</span><span class="sm muted">{{ m.referencia }} · {{ m.fecha | fechaHora }}</span>
          </div>
        } @empty { <div class="empty">Sin movimientos</div> }
      </aside>
    </div>

    @if (modal === 'kardex' && kardex) {
      <app-modal [titulo]="'Kardex · ' + kardex.sku" [ancho]="true" (cerrar)="modal = null">
        <p class="muted">{{ kardex.modelo }} · {{ kardex.color }} · T{{ kardex.talla }} · {{ kardex.sucursal }}</p>
        <div class="kpis">
          <div class="kpi"><span class="l">Stock actual</span><span class="v">{{ kardex.stock_actual | num }}</span></div>
          <div class="kpi"><span class="l">Saldo según movimientos</span><span class="v">{{ (kardex.movimientos[0]?.saldo ?? 0) | num }}</span>
            <span class="d">@if ((kardex.movimientos[0]?.saldo ?? 0) == kardex.stock_actual) {<span class="up">cuadra con el stock</span>} @else {<span class="dn">no cuadra</span>}</span></div>
          <div class="kpi"><span class="l">Precio / costo</span><span class="v">{{ kardex.precio_venta | bs }}</span><span class="d">costo {{ kardex.costo_referencia | bs }}</span></div>
        </div>
        @if (auth.puede('inventario.ajustar')) {
          <form class="filters" (ngSubmit)="guardarMinimo()">
            <label class="field" for="km-m"><span>Stock mínimo</span><input id="km-m" name="min" type="number" min="0" [(ngModel)]="kardex.stock_minimo"></label>
            <button class="btn" type="submit">Guardar mínimo</button></form>
        }
        <div class="tw" style="max-height:360px;overflow:auto"><table class="t">
          <thead><tr><th>Fecha</th><th>Tipo</th><th>Referencia</th><th>Usuario</th><th class="num">Cantidad</th><th class="num">Saldo</th></tr></thead>
          <tbody>@for (m of kardex.movimientos; track m.id_movimiento) {
            <tr><td class="sm">{{ m.fecha | fechaHora }}</td><td>{{ tipo(m.tipo) }}</td><td class="mono sm">{{ m.referencia }}</td><td class="sm muted">{{ m.usuario }}</td>
              <td class="num" [style.color]="m.cantidad > 0 ? 'var(--ok)' : 'var(--bad)'">{{ m.cantidad > 0 ? '+' : '' }}{{ m.cantidad }}</td><td class="num b">{{ m.saldo }}</td></tr>
          } @empty { <tr><td colspan="6"><div class="empty">Sin movimientos registrados</div></td></tr> }</tbody></table></div>
      </app-modal>
    }

    @if (modal === 'ajuste') {
      <app-modal titulo="Ajuste de inventario" (cerrar)="modal = null">
        <form class="form-grid" (ngSubmit)="guardarAjuste()">
          <label class="field" for="aj-s"><span>Sucursal</span><select id="aj-s" name="suc" [(ngModel)]="aj.id_sucursal">
            @for (s of sucursalesPermitidas(); track s.id_sucursal) { <option [ngValue]="s.id_sucursal">{{ s.nombre }}</option> }</select></label>
          <label class="field" for="aj-k"><span>SKU</span><input id="aj-k" name="sku" [(ngModel)]="aj.sku" list="dl-sku" (input)="sugerirSku(aj.sku)" required autocomplete="off"></label>
          <label class="field" for="aj-t"><span>Tipo</span><select id="aj-t" name="tipo" [(ngModel)]="aj.tipo">
            <option value="ENTRADA_AJUSTE">Entrada (sobrante, hallazgo)</option><option value="SALIDA_AJUSTE">Salida (merma, daño, faltante)</option></select></label>
          <label class="field" for="aj-c"><span>Cantidad (pares)</span><input id="aj-c" name="cant" type="number" min="1" step="1" [(ngModel)]="aj.cantidad" required></label>
          <label class="field full" for="aj-m"><span>Motivo</span><input id="aj-m" name="motivo" [(ngModel)]="aj.motivo" required placeholder="Ej.: conteo físico del 18/10"></label>
          <div class="modal-f full"><button type="button" class="btn" (click)="modal = null">Cancelar</button><button class="btn btn-p" type="submit">Registrar ajuste</button></div>
        </form>
      </app-modal>
    }

    @if (modal === 'transferencia') {
      <app-modal titulo="Transferencia entre sucursales" (cerrar)="modal = null">
        <form class="form-grid" (ngSubmit)="guardarTransferencia()">
          <label class="field" for="tr-o"><span>Sucursal de origen</span><select id="tr-o" name="orig" [(ngModel)]="tr.id_origen">
            @for (s of sucursalesPermitidas(); track s.id_sucursal) { <option [ngValue]="s.id_sucursal">{{ s.nombre }}</option> }</select></label>
          <label class="field" for="tr-d"><span>Sucursal de destino</span><select id="tr-d" name="dest" [(ngModel)]="tr.id_destino">
            @for (s of sucursales; track s.id_sucursal) { <option [ngValue]="s.id_sucursal">{{ s.nombre }}</option> }</select></label>
          <label class="field" for="tr-k"><span>SKU</span><input id="tr-k" name="sku" [(ngModel)]="tr.sku" list="dl-sku" (input)="sugerirSku(tr.sku)" required autocomplete="off"></label>
          <label class="field" for="tr-c"><span>Cantidad (pares)</span><input id="tr-c" name="cant" type="number" min="1" step="1" [(ngModel)]="tr.cantidad" required></label>
          <div class="modal-f full"><button type="button" class="btn" (click)="modal = null">Cancelar</button><button class="btn btn-p" type="submit">Transferir</button></div>
        </form>
      </app-modal>
    }
    <datalist id="dl-sku">@for (v of skus; track v.id_variante) { <option [value]="v.sku">{{ v.modelo }} · {{ v.color }} · T{{ v.talla }}</option> }</datalist>`,
})
export class InventarioComponent implements OnInit {
  private api = inject(ApiService);
  private toast = inject(ToastService);
  auth = inject(AuthService);
  sucursales: any[] = [];
  categorias: any[] = [];
  estados = Object.entries(ESTADO_INV);
  f: any = { q: '', id_sucursal: null, id_categoria: null, estado: null, dias: 120 };
  pagina = 1;
  tamano = 40;
  total = 0;
  items: any[] = [];
  res: any = null;
  movimientos: any[] = [];
  modal: string | null = null;
  kardex: any = null;
  aj: any = {};
  tr: any = {};
  skus: any[] = [];
  private t: any;
  private ts: any;

  async ngOnInit() {
    this.f.id_sucursal = this.auth.sucursalFija();
    [this.sucursales, this.categorias] = await Promise.all([this.api.get('/api/sucursales'), this.api.get('/api/categorias')]);
    this.ir(1);
  }

  sucursalesPermitidas() { const s = this.auth.sucursalFija(); return s ? this.sucursales.filter((x) => x.id_sucursal === s) : this.sucursales; }
  paginas() { return Math.max(1, Math.ceil(this.total / this.tamano)); }
  est(e: string) { return ESTADO_INV[e] || [e, 'b-mut']; }
  tipo(t: string) { return TIPOS_MOV[t] || t; }

  buscar() { clearTimeout(this.t); this.t = setTimeout(() => this.ir(1), 250); }

  async ir(p: number) {
    this.pagina = Math.max(1, p);
    const r = await this.api.get('/api/inventario', { ...this.f, pagina: this.pagina, tamano: this.tamano });
    this.res = r.resumen;
    this.total = r.total;
    this.items = r.items;
    this.movimientos = await this.api.get('/api/inventario/movimientos', { id_sucursal: this.f.id_sucursal, limite: 8 });
  }

  async verKardex(x: any) {
    this.kardex = await this.api.get('/api/inventario/kardex', { id_sucursal: x.id_sucursal, id_variante: x.id_variante });
    this.kardex.id_sucursal = x.id_sucursal;
    this.kardex.id_variante = x.id_variante;
    this.modal = 'kardex';
  }

  async guardarMinimo() {
    await this.api.put('/api/inventario/minimo', { id_sucursal: this.kardex.id_sucursal, id_variante: this.kardex.id_variante, stock_minimo: +this.kardex.stock_minimo });
    this.toast.ok('Stock mínimo actualizado.');
    this.ir(this.pagina);
  }

  sugerirSku(q: string) {
    clearTimeout(this.ts);
    this.ts = setTimeout(async () => { if ((q || '').length >= 2) this.skus = await this.api.get('/api/variantes/buscar', { q, limite: 20 }); }, 250);
  }

  abrirAjuste() { this.aj = { id_sucursal: this.sucursalesPermitidas()[0]?.id_sucursal, sku: '', tipo: 'ENTRADA_AJUSTE', cantidad: null, motivo: '' }; this.modal = 'ajuste'; }
  abrirTransferencia() {
    const o = this.sucursalesPermitidas()[0]?.id_sucursal;
    this.tr = { id_origen: o, id_destino: this.sucursales.find((s) => s.id_sucursal !== o)?.id_sucursal, sku: '', cantidad: null };
    this.modal = 'transferencia';
  }

  async guardarAjuste() {
    try {
      const r = await this.api.post('/api/inventario/ajustes', { ...this.aj, cantidad: +this.aj.cantidad });
      this.toast.ok(`Ajuste registrado (${r.referencia}). Stock actual: ${r.stock}.`);
      this.modal = null;
      this.ir(this.pagina);
    } catch {}
  }

  async guardarTransferencia() {
    try {
      const r = await this.api.post('/api/inventario/transferencias', { ...this.tr, cantidad: +this.tr.cantidad });
      this.toast.ok(`Transferencia ${r.referencia} registrada.`);
      this.modal = null;
      this.ir(this.pagina);
    } catch {}
  }
}
