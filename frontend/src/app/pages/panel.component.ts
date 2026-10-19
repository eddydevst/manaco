import { Component, OnInit, inject } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { ApiService } from '../core/api.service';
import { AuthService } from '../core/auth.service';
import { ESTADO_INV, MESES } from '../core/nav';
import { BarrasComponent, GraficoLineasComponent, Serie } from '../shared/graficos';
import { PIPES } from '../shared/pipes';

@Component({
  selector: 'app-panel',
  standalone: true,
  imports: [FormsModule, RouterLink, GraficoLineasComponent, BarrasComponent, ...PIPES],
  template: `
    <header class="ph">
      <div><div class="ph-t"><h1>Panel gerencial</h1></div>
        <p>Indicadores comerciales, financieros y de inventario calculados con las ventas registradas.</p></div>
      <div class="ph-a">
        <label class="field" for="pf-per"><span>Período</span>
          <select id="pf-per" [(ngModel)]="periodo" (ngModelChange)="cargar()">
            <option value="mes">Mes actual</option><option value="30">Últimos 30 días</option><option value="90">Últimos 90 días</option>
            <option value="anio">Año a la fecha</option><option value="12m">Últimos 12 meses</option>
          </select></label>
        <label class="field" for="pf-suc"><span>Sucursal</span>
          <select id="pf-suc" [(ngModel)]="sucursal" (ngModelChange)="cargar()" [disabled]="!!auth.sucursalFija()">
            <option [ngValue]="null">Todas</option>
            @for (s of sucursales; track s.id_sucursal) { <option [ngValue]="s.id_sucursal">{{ s.nombre }}</option> }
          </select></label>
        <label class="field" for="pf-cat"><span>Categoría</span>
          <select id="pf-cat" [(ngModel)]="categoria" (ngModelChange)="cargar()">
            <option [ngValue]="null">Todas</option>
            @for (c of categorias; track c.id_categoria) { <option [ngValue]="c.id_categoria">{{ c.nombre }}</option> }
          </select></label>
      </div>
    </header>

    @if (!d) { <div class="cargando"><span class="spin"></span> Calculando indicadores…</div> }
    @if (d) {
      <section class="kpis" aria-label="Indicadores clave">
        <div class="kpi"><span class="l">Ingresos por ventas</span><span class="v">{{ k.ingresos | bsc }}</span><span class="d" [innerHTML]="delta(k.ingresos, k.ingresos_prev)"></span></div>
        <div class="kpi"><span class="l">Unidades vendidas</span><span class="v">{{ k.unidades | num }} pares</span><span class="d" [innerHTML]="delta(k.unidades, k.unidades_prev)"></span></div>
        <div class="kpi"><span class="l">Margen bruto</span><span class="v">{{ k.margen | pct }}</span>
          <span class="d">@if (k.margen !== null && k.margen_prev !== null) {<span [class]="k.margen >= k.margen_prev ? 'up' : 'dn'">{{ k.margen >= k.margen_prev ? '▲' : '▼' }} {{ puntos(k.margen - k.margen_prev) }} pts</span>}</span></div>
        <div class="kpi"><span class="l">Ticket promedio</span><span class="v">{{ k.ticket | bs }}</span><span class="d" [innerHTML]="delta(k.ticket, k.ticket_prev)"></span></div>
        <div class="kpi"><span class="l">Rotación de inventario</span><span class="v">{{ rot(k.rotacion) }}</span><span class="d">costo de ventas 12 meses ÷ inventario a costo</span></div>
        <div class="kpi" [class.bad]="k.quiebres > 0"><span class="l">Quiebres de stock</span><span class="v">{{ k.quiebres | num }} SKU</span><span class="d">{{ k.bajo_minimo | num }} más bajo el mínimo</span></div>
        <div class="kpi info"><span class="l">Inventario inmovilizado</span><span class="v">{{ k.inmovilizado | bsc }}</span><span class="d">{{ k.inmovilizado_skus | num }} SKU sin ventas en 120 días</span></div>
        <div class="kpi"><span class="l">Cumplimiento de proveedores</span><span class="v">{{ k.cumplimiento_a_tiempo | pct }}</span><span class="d">a tiempo · {{ k.cumplimiento_cantidad | pct }} de lo pedido</span></div>
      </section>

      <div class="row">
        <section class="card c2">
          <div class="card-h"><h2>Ventas mensuales (Bs)</h2>
            <div class="legend"><span class="lg"><i style="border-top-color:var(--accent)"></i>{{ d.mensual.anio }}</span>
              <span class="lg"><i style="border-top-color:var(--prev);border-top-style:dashed"></i>{{ d.mensual.anio - 1 }}</span>
              <span class="lg"><i style="border-top-color:var(--info);border-top-style:dashed"></i>Pronóstico</span></div></div>
          <app-grafico-lineas [etiquetas]="meses" [series]="series" descripcion="Ventas mensuales del año frente al anterior, con pronóstico"></app-grafico-lineas>
          <p class="sm muted">El mes en curso incluye solo los días transcurridos.
            @if (d.mensual.mape !== null) { Pronóstico con {{ d.mensual.modelo }}; error medio en los últimos 3 meses: {{ d.mensual.mape | pct }}. }</p>
        </section>
        <section class="card c1"><h2>Ventas por sucursal</h2><app-barras [items]="d.por_sucursal" formato="bsc"></app-barras></section>
      </div>

      <div class="row">
        <section class="card c2">
          <div class="card-h"><h2>Productos más y menos vendidos</h2>@if (auth.puede('reportes.ver')) {<a class="btn btn-sm" routerLink="/reportes">Ver reporte completo</a>}</div>
          <div class="tw"><table class="t">
            <thead><tr><th>Producto</th><th>Categoría</th><th class="num">Pares</th><th class="num">Ingresos</th><th class="num">Margen</th></tr></thead>
            <tbody>
              @for (p of d.top_productos; track $index) { <tr><td class="b">{{ p.modelo }}</td><td class="muted">{{ p.categoria }}</td><td class="num">{{ p.unidades | num }}</td><td class="num">{{ p.ingresos | bs }}</td><td class="num" [style.color]="p.margen < .3 ? 'var(--bad)' : 'var(--ok)'">{{ p.margen | pct }}</td></tr> }
              @if (d.menos_vendidos.length) { <tr><td colspan="5" class="sm muted" style="background:var(--surface2)">Menos vendidos</td></tr> }
              @for (p of d.menos_vendidos; track $index) { <tr><td class="b">{{ p.modelo }}</td><td class="muted">{{ p.categoria }}</td><td class="num">{{ p.unidades | num }}</td><td class="num">{{ p.ingresos | bs }}</td><td class="num" [style.color]="p.margen < .3 ? 'var(--bad)' : 'var(--ok)'">{{ p.margen | pct }}</td></tr> }
              @if (!d.top_productos.length) { <tr><td colspan="5"><div class="empty">Sin ventas en el período</div></td></tr> }
            </tbody></table></div>
        </section>
        <div class="c1" style="display:flex;flex-direction:column;gap:16px">
          <section class="card"><h2>Margen bruto por categoría</h2><app-barras [items]="d.margen_categoria" formato="pct"></app-barras></section>
          <section class="card">
            <div class="card-h"><h2>Alertas de inventario</h2>@if (auth.puede('inventario.ver')) {<a class="btn btn-sm" routerLink="/inventario">Ir a inventario</a>}</div>
            @for (a of d.alertas; track $index) {
              <div class="al"><span class="badge {{ est(a.estado)[1] }}">{{ est(a.estado)[0] }}</span><span>{{ a.modelo }} · {{ a.color }} · T{{ a.talla }} · {{ a.sucursal }} · <span class="mono">{{ a.stock_actual }}</span> pares</span></div>
            } @empty { <div class="empty">Sin alertas</div> }
          </section>
        </div>
      </div>

      <section class="card"><details class="formulas"><summary>Cómo se calcula cada indicador</summary><dl>
        <dt>Ingresos</dt><dd>Suma de subtotales de líneas vendidas (precio × cantidad − descuento), descontando devoluciones.</dd>
        <dt>Margen bruto</dt><dd>(Ingresos − costo de ventas) ÷ ingresos. El costo es el costo unitario histórico guardado en cada venta.</dd>
        <dt>Ticket promedio</dt><dd>Ingresos ÷ número de ventas.</dd>
        <dt>Rotación</dt><dd>Costo de ventas de los últimos 12 meses ÷ valor actual del inventario a costo de referencia.</dd>
        <dt>Quiebres de stock</dt><dd>Combinaciones SKU-sucursal con existencia 0.</dd>
        <dt>Inventario inmovilizado</dt><dd>Valor a costo de los SKU con stock y sin ventas en 120 días.</dd>
        <dt>Cumplimiento</dt><dd>Órdenes cuya última recepción llegó hasta la fecha de entrega ÷ órdenes recibidas.</dd>
        <dt>Comparación</dt><dd>Contra {{ d.comparacion }}.</dd>
      </dl></details></section>
    }`,
})
export class PanelComponent implements OnInit {
  private api = inject(ApiService);
  auth = inject(AuthService);
  sucursales: any[] = [];
  categorias: any[] = [];
  periodo = 'anio';
  sucursal: number | null = null;
  categoria: number | null = null;
  d: any = null;
  k: any = {};
  meses = MESES;
  series: Serie[] = [];

  async ngOnInit() {
    this.sucursal = this.auth.sucursalFija();
    [this.sucursales, this.categorias] = await Promise.all([this.api.get('/api/sucursales'), this.api.get('/api/categorias')]);
    this.cargar();
  }

  async cargar() {
    const d = await this.api.get('/api/kpis/panel', { periodo: this.periodo, id_sucursal: this.sucursal, id_categoria: this.categoria });
    d.por_sucursal = d.por_sucursal.map((x: any) => ({ etiqueta: x.etiqueta, valor: +x.valor }));
    d.margen_categoria = d.margen_categoria.map((x: any) => ({ etiqueta: x.etiqueta, valor: +x.valor }));
    this.series = [
      { valores: d.mensual.anterior, color: 'var(--prev)', discontinua: true, grosor: 2 },
      { valores: d.mensual.pronostico, color: 'var(--info)', discontinua: true },
      { valores: d.mensual.actual, color: 'var(--accent)', area: true, punto: true },
    ];
    this.k = d.kpis;
    this.d = d;
  }

  delta(a: number, b: number): string {
    if (!b) return '<span class="muted">sin datos para comparar</span>';
    const x = (a - b) / b;
    return `<span class="${x >= 0 ? 'up' : 'dn'}">${x >= 0 ? '▲' : '▼'} ${(Math.abs(x) * 100).toFixed(1).replace('.', ',')} %</span> vs. ${this.d?.comparacion ?? ''}`;
  }
  puntos(x: number) { return (Math.abs(x) * 100).toFixed(1).replace('.', ','); }
  rot(x: number | null) { return x === null || x === undefined ? '—' : x.toFixed(1).replace('.', ',') + '×'; }
  est(e: string) { return ESTADO_INV[e] || [e, 'b-mut']; }
}
